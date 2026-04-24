import uuid
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import BigIntegerField, Case, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone


class Merchant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class BankAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, related_name="bank_accounts", on_delete=models.CASCADE)
    label = models.CharField(max_length=80)
    account_last4 = models.CharField(max_length=4)
    ifsc = models.CharField(max_length=11)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["merchant", "is_active"], name="bank_merchant_active_idx")]

    def __str__(self):
        return f"{self.label} ****{self.account_last4}"


class LedgerEntry(models.Model):
    class Direction(models.TextChoices):
        CREDIT = "credit", "Credit"
        DEBIT = "debit", "Debit"

    class Reason(models.TextChoices):
        CUSTOMER_PAYMENT = "customer_payment", "Customer payment"
        PAYOUT_HOLD = "payout_hold", "Payout hold"
        PAYOUT_RELEASE = "payout_release", "Payout release"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, related_name="ledger_entries", on_delete=models.CASCADE)
    direction = models.CharField(max_length=8, choices=Direction.choices)
    reason = models.CharField(max_length=32, choices=Reason.choices)
    amount_paise = models.BigIntegerField()
    payout = models.ForeignKey(
        "Payout", related_name="ledger_entries", null=True, blank=True, on_delete=models.PROTECT
    )
    reference = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["merchant", "-created_at"], name="ledger_merchant_created_idx"),
            models.Index(fields=["payout", "reason"], name="ledger_payout_reason_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(amount_paise__gt=0), name="ledger_amount_positive")
        ]

    @classmethod
    def balance_expression(cls):
        return Coalesce(
            Sum(
                Case(
                    When(direction=cls.Direction.CREDIT, then=F("amount_paise")),
                    When(direction=cls.Direction.DEBIT, then=-F("amount_paise")),
                    default=Value(0),
                    output_field=BigIntegerField(),
                )
            ),
            Value(0),
            output_field=BigIntegerField(),
        )

    @classmethod
    def available_balance_for_merchant(cls, merchant_id):
        return cls.objects.filter(merchant_id=merchant_id).aggregate(
            balance_paise=cls.balance_expression()
        )["balance_paise"]


class Payout(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    TERMINAL_STATUSES = {Status.COMPLETED, Status.FAILED}
    LEGAL_TRANSITIONS = {
        Status.PENDING: {Status.PROCESSING},
        Status.PROCESSING: {Status.COMPLETED, Status.FAILED},
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, related_name="payouts", on_delete=models.PROTECT)
    bank_account = models.ForeignKey(BankAccount, related_name="payouts", on_delete=models.PROTECT)
    amount_paise = models.BigIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "next_attempt_at"], name="payout_status_due_idx"),
            models.Index(fields=["merchant", "-created_at"], name="payout_merchant_created_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(amount_paise__gt=0), name="payout_amount_positive")
        ]

    def transition_to(self, new_status, *, failure_reason=""):
        if new_status not in self.LEGAL_TRANSITIONS.get(self.status, set()):
            raise ValidationError(f"Illegal payout transition {self.status} -> {new_status}")

        with transaction.atomic():
            locked = Payout.objects.select_for_update().get(pk=self.pk)
            if new_status not in self.LEGAL_TRANSITIONS.get(locked.status, set()):
                raise ValidationError(f"Illegal payout transition {locked.status} -> {new_status}")

            old_status = locked.status
            locked.status = new_status
            if new_status == self.Status.PROCESSING:
                locked.attempts += 1
                locked.processing_started_at = timezone.now()
                locked.next_attempt_at = timezone.now() + timedelta(seconds=2**locked.attempts)
            if new_status == self.Status.FAILED:
                locked.failure_reason = failure_reason or "Bank settlement failed"
                LedgerEntry.objects.create(
                    merchant=locked.merchant,
                    payout=locked,
                    direction=LedgerEntry.Direction.CREDIT,
                    reason=LedgerEntry.Reason.PAYOUT_RELEASE,
                    amount_paise=locked.amount_paise,
                    reference=f"release:{locked.id}",
                )

            locked.save()
            locked.refresh_from_db()
            self.__dict__.update(locked.__dict__)
            return old_status, locked.status


class IdempotencyKey(models.Model):
    key = models.UUIDField()
    merchant = models.ForeignKey(Merchant, related_name="idempotency_keys", on_delete=models.CASCADE)
    request_hash = models.CharField(max_length=64)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    payout = models.ForeignKey(Payout, null=True, blank=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["merchant", "key"], name="unique_idempotency_key_per_merchant")
        ]
        indexes = [
            models.Index(fields=["merchant", "key"], name="idem_merchant_key_idx"),
            models.Index(fields=["expires_at"], name="idem_expires_idx"),
        ]

    def is_expired(self):
        return timezone.now() >= self.expires_at
