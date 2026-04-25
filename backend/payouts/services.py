import hashlib
import json
import uuid
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework import status

from .models import BankAccount, IdempotencyKey, LedgerEntry, Merchant, Payout
from .serializers import PayoutSerializer


class InsufficientFunds(ValidationError):
    pass


def canonical_request_hash(payload):
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def create_payout(*, merchant_id, idempotency_key, amount_paise, bank_account_id):
    request_payload = {
        "amount_paise": int(amount_paise),
        "bank_account_id": str(bank_account_id),
    }
    request_hash = canonical_request_hash(request_payload)

    try:
        uuid.UUID(str(idempotency_key))
    except ValueError as exc:
        raise ValidationError("Idempotency-Key must be a UUID") from exc

    try:
        with transaction.atomic():
            now = timezone.now()
            idem = IdempotencyKey.objects.create(
                key=idempotency_key,
                merchant_id=merchant_id,
                request_hash=request_hash,
                expires_at=now + timedelta(hours=24),
            )

            merchant = Merchant.objects.select_for_update().get(pk=merchant_id)
            try:
                bank_account = BankAccount.objects.get(
                    pk=bank_account_id, merchant=merchant, is_active=True
                )
            except BankAccount.DoesNotExist:
                response = {"detail": "Bank account does not belong to this merchant"}
                idem.response_status = status.HTTP_400_BAD_REQUEST
                idem.response_body = response
                idem.save(update_fields=["response_status", "response_body"])
                return response, status.HTTP_400_BAD_REQUEST
            available = LedgerEntry.available_balance_for_merchant(merchant.id)
            if available < amount_paise:
                response = {"detail": "Insufficient available balance"}
                idem.response_status = status.HTTP_409_CONFLICT
                idem.response_body = response
                idem.save(update_fields=["response_status", "response_body"])
                return response, status.HTTP_409_CONFLICT

            payout = Payout.objects.create(
                merchant=merchant,
                bank_account=bank_account,
                amount_paise=amount_paise,
                status=Payout.Status.PENDING,
            )
            LedgerEntry.objects.create(
                merchant=merchant,
                payout=payout,
                direction=LedgerEntry.Direction.DEBIT,
                reason=LedgerEntry.Reason.PAYOUT_HOLD,
                amount_paise=amount_paise,
                reference=f"hold:{payout.id}",
            )

            response = json.loads(json.dumps(PayoutSerializer(payout).data, default=str))
            idem.payout = payout
            idem.response_status = status.HTTP_201_CREATED
            idem.response_body = response
            idem.save(update_fields=["payout", "response_status", "response_body"])
            return response, status.HTTP_201_CREATED
    except IntegrityError:
        existing = IdempotencyKey.objects.get(merchant_id=merchant_id, key=idempotency_key)
        if existing.is_expired():
            return {"detail": "Idempotency key expired; use a new key"}, status.HTTP_409_CONFLICT
        if existing.request_hash != request_hash:
            return {
                "detail": "Idempotency-Key was already used with a different request body"
            }, status.HTTP_409_CONFLICT
        if existing.response_body is None:
            return {"detail": "Identical request is still being processed"}, status.HTTP_409_CONFLICT
        return existing.response_body, existing.response_status
