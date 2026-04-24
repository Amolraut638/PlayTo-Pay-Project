import threading
import uuid

from django.db import close_old_connections
from django.test import TransactionTestCase

from payouts.models import BankAccount, LedgerEntry, Merchant, Payout
from payouts.services import create_payout


class PayoutConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.merchant = Merchant.objects.create(name="Race Studio", email="race@example.com")
        self.bank = BankAccount.objects.create(
            merchant=self.merchant,
            label="ICICI",
            account_last4="2222",
            ifsc="ICIC0002222",
        )
        LedgerEntry.objects.create(
            merchant=self.merchant,
            direction=LedgerEntry.Direction.CREDIT,
            reason=LedgerEntry.Reason.CUSTOMER_PAYMENT,
            amount_paise=10000,
            reference="opening-balance",
        )

    def test_parallel_payouts_do_not_overdraw_available_balance(self):
        barrier = threading.Barrier(2)
        results = []
        errors = []

        def submit():
            close_old_connections()
            barrier.wait(timeout=5)
            try:
                body, status_code = create_payout(
                    merchant_id=self.merchant.id,
                    idempotency_key=uuid.uuid4(),
                    amount_paise=6000,
                    bank_account_id=self.bank.id,
                )
                results.append((status_code, body))
            except Exception as exc:
                errors.append(exc)
            finally:
                close_old_connections()

        threads = [threading.Thread(target=submit), threading.Thread(target=submit)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        assert not errors
        assert sorted(status for status, _ in results) == [201, 409]
        assert Payout.objects.count() == 1
        assert LedgerEntry.available_balance_for_merchant(self.merchant.id) == 4000
