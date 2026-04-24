from django.db.models import BigIntegerField, Case, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import BankAccount, LedgerEntry, Merchant, Payout
from .serializers import (
    BankAccountSerializer,
    LedgerEntrySerializer,
    MerchantSerializer,
    PayoutCreateSerializer,
    PayoutSerializer,
)
from .services import create_payout


def get_merchant_from_header(request):
    merchant_id = request.headers.get("X-Merchant-Id")
    if not merchant_id:
        return None, Response({"detail": "X-Merchant-Id header is required"}, status=400)
    return get_object_or_404(Merchant, pk=merchant_id), None


def held_balance_expression():
    return Coalesce(
        Sum(
            Case(
                When(status__in=[Payout.Status.PENDING, Payout.Status.PROCESSING], then=F("amount_paise")),
                default=Value(0),
                output_field=BigIntegerField(),
            )
        ),
        Value(0),
        output_field=BigIntegerField(),
    )


@api_view(["GET"])
def merchants(request):
    data = MerchantSerializer(Merchant.objects.order_by("name"), many=True).data
    return Response(data)


@api_view(["GET"])
def dashboard(request):
    merchant, error = get_merchant_from_header(request)
    if error:
        return error

    available = LedgerEntry.available_balance_for_merchant(merchant.id)
    held = Payout.objects.filter(merchant=merchant).aggregate(
        held_paise=held_balance_expression()
    )["held_paise"]
    payload = {
        "merchant": MerchantSerializer(merchant).data,
        "available_balance_paise": available,
        "held_balance_paise": held,
        "bank_accounts": BankAccountSerializer(
            BankAccount.objects.filter(merchant=merchant, is_active=True), many=True
        ).data,
        "recent_ledger_entries": LedgerEntrySerializer(
            LedgerEntry.objects.filter(merchant=merchant).order_by("-created_at")[:20],
            many=True,
        ).data,
        "payouts": PayoutSerializer(
            Payout.objects.filter(merchant=merchant)
            .select_related("bank_account")
            .order_by("-created_at")[:50],
            many=True,
        ).data,
    }
    return Response(payload)


@api_view(["GET", "POST"])
def payouts(request):
    merchant, error = get_merchant_from_header(request)
    if error:
        return error

    if request.method == "GET":
        queryset = (
            Payout.objects.filter(merchant=merchant).select_related("bank_account").order_by("-created_at")
        )
        return Response(PayoutSerializer(queryset, many=True).data)

    idem_key = request.headers.get("Idempotency-Key")
    if not idem_key:
        return Response({"detail": "Idempotency-Key header is required"}, status=400)

    serializer = PayoutCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    body, response_status = create_payout(
        merchant_id=merchant.id,
        idempotency_key=idem_key,
        amount_paise=serializer.validated_data["amount_paise"],
        bank_account_id=serializer.validated_data["bank_account_id"],
    )
    return Response(body, status=response_status)
