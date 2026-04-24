import uuid

from django.test import TestCase
from rest_framework.test import APIClient

from payouts.models import BankAccount, LedgerEntry, Merchant, Payout


class PayoutIdempotencyTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.merchant = Merchant.objects.create(name="Idem Studio", email="idem@example.com")
        self.bank = BankAccount.objects.create(
            merchant=self.merchant,
            label="HDFC",
            account_last4="1111",
            ifsc="HDFC0001111",
        )
        LedgerEntry.objects.create(
            merchant=self.merchant,
            direction=LedgerEntry.Direction.CREDIT,
            reason=LedgerEntry.Reason.CUSTOMER_PAYMENT,
            amount_paise=10000,
            reference="test-credit",
        )

    def test_same_key_returns_same_response_without_duplicate_payout(self):
        key = str(uuid.uuid4())
        payload = {"amount_paise": 6000, "bank_account_id": str(self.bank.id)}
        headers = {"HTTP_X_MERCHANT_ID": str(self.merchant.id), "HTTP_IDEMPOTENCY_KEY": key}

        first = self.client.post("/api/v1/payouts", payload, format="json", **headers)
        second = self.client.post("/api/v1/payouts", payload, format="json", **headers)

        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json() == second.json()
        assert Payout.objects.count() == 1
        assert LedgerEntry.available_balance_for_merchant(self.merchant.id) == 4000

    def test_same_key_with_different_body_is_rejected(self):
        key = str(uuid.uuid4())
        headers = {"HTTP_X_MERCHANT_ID": str(self.merchant.id), "HTTP_IDEMPOTENCY_KEY": key}

        first = self.client.post(
            "/api/v1/payouts",
            {"amount_paise": 3000, "bank_account_id": str(self.bank.id)},
            format="json",
            **headers,
        )
        second = self.client.post(
            "/api/v1/payouts",
            {"amount_paise": 4000, "bank_account_id": str(self.bank.id)},
            format="json",
            **headers,
        )

        assert first.status_code == 201
        assert second.status_code == 409
        assert Payout.objects.count() == 1
