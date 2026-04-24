from rest_framework import serializers

from .models import BankAccount, LedgerEntry, Merchant, Payout


class MerchantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Merchant
        fields = ["id", "name", "email"]


class BankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = ["id", "label", "account_last4", "ifsc", "is_active"]


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = ["id", "direction", "reason", "amount_paise", "reference", "created_at", "payout_id"]


class PayoutSerializer(serializers.ModelSerializer):
    bank_account_label = serializers.CharField(source="bank_account.label", read_only=True)

    class Meta:
        model = Payout
        fields = [
            "id",
            "amount_paise",
            "status",
            "attempts",
            "bank_account",
            "bank_account_label",
            "failure_reason",
            "created_at",
            "updated_at",
        ]


class PayoutCreateSerializer(serializers.Serializer):
    amount_paise = serializers.IntegerField(min_value=1)
    bank_account_id = serializers.UUIDField()
