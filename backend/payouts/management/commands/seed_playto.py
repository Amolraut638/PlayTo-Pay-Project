from django.core.management.base import BaseCommand
from django.db import transaction

from payouts.models import BankAccount, LedgerEntry, Merchant


MERCHANTS = [
    ("Aarav Design Studio", "aarav@example.com", "Primary HDFC", "1024", "HDFC0001234", [2500000, 475000, 125000]),
    ("Nisha Growth Labs", "nisha@example.com", "ICICI Current", "7788", "ICIC0009876", [980000, 620000, 300000]),
    ("Studio Kaveri", "kaveri@example.com", "Axis Business", "4309", "UTIB0002468", [1500000, 225000]),
]


class Command(BaseCommand):
    help = "Seed merchants, bank accounts, and customer payment credits."

    @transaction.atomic
    def handle(self, *args, **options):
        for name, email, bank_label, last4, ifsc, credits in MERCHANTS:
            merchant, _ = Merchant.objects.update_or_create(
                email=email,
                defaults={"name": name},
            )
            BankAccount.objects.update_or_create(
                merchant=merchant,
                account_last4=last4,
                defaults={"label": bank_label, "ifsc": ifsc, "is_active": True},
            )
            LedgerEntry.objects.filter(
                merchant=merchant, reason=LedgerEntry.Reason.CUSTOMER_PAYMENT
            ).delete()
            for index, amount in enumerate(credits, start=1):
                LedgerEntry.objects.create(
                    merchant=merchant,
                    direction=LedgerEntry.Direction.CREDIT,
                    reason=LedgerEntry.Reason.CUSTOMER_PAYMENT,
                    amount_paise=amount,
                    reference=f"seed-payment-{index}",
                )
            self.stdout.write(self.style.SUCCESS(f"Seeded {merchant.name} ({merchant.id})"))