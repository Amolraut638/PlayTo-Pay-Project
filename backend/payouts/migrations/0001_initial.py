import uuid
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Merchant",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=120)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="BankAccount",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("label", models.CharField(max_length=80)),
                ("account_last4", models.CharField(max_length=4)),
                ("ifsc", models.CharField(max_length=11)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("merchant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="bank_accounts", to="payouts.merchant")),
            ],
        ),
        migrations.CreateModel(
            name="Payout",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("amount_paise", models.BigIntegerField()),
                ("status", models.CharField(choices=[("pending", "Pending"), ("processing", "Processing"), ("completed", "Completed"), ("failed", "Failed")], default="pending", max_length=16)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("next_attempt_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("processing_started_at", models.DateTimeField(blank=True, null=True)),
                ("failure_reason", models.CharField(blank=True, max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("bank_account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payouts", to="payouts.bankaccount")),
                ("merchant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payouts", to="payouts.merchant")),
            ],
        ),
        migrations.CreateModel(
            name="IdempotencyKey",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.UUIDField()),
                ("request_hash", models.CharField(max_length=64)),
                ("response_status", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("response_body", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("merchant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="idempotency_keys", to="payouts.merchant")),
                ("payout", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="payouts.payout")),
            ],
        ),
        migrations.CreateModel(
            name="LedgerEntry",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("direction", models.CharField(choices=[("credit", "Credit"), ("debit", "Debit")], max_length=8)),
                ("reason", models.CharField(choices=[("customer_payment", "Customer payment"), ("payout_hold", "Payout hold"), ("payout_release", "Payout release")], max_length=32)),
                ("amount_paise", models.BigIntegerField()),
                ("reference", models.CharField(blank=True, max_length=120)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("merchant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ledger_entries", to="payouts.merchant")),
                ("payout", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="ledger_entries", to="payouts.payout")),
            ],
        ),
        migrations.AddIndex(model_name="bankaccount", index=models.Index(fields=["merchant", "is_active"], name="bank_merchant_active_idx")),
        migrations.AddIndex(model_name="payout", index=models.Index(fields=["status", "next_attempt_at"], name="payout_status_due_idx")),
        migrations.AddIndex(model_name="payout", index=models.Index(fields=["merchant", "-created_at"], name="payout_merchant_created_idx")),
        migrations.AddIndex(model_name="idempotencykey", index=models.Index(fields=["merchant", "key"], name="idem_merchant_key_idx")),
        migrations.AddIndex(model_name="idempotencykey", index=models.Index(fields=["expires_at"], name="idem_expires_idx")),
        migrations.AddIndex(model_name="ledgerentry", index=models.Index(fields=["merchant", "-created_at"], name="ledger_merchant_created_idx")),
        migrations.AddIndex(model_name="ledgerentry", index=models.Index(fields=["payout", "reason"], name="ledger_payout_reason_idx")),
        migrations.AddConstraint(model_name="payout", constraint=models.CheckConstraint(condition=models.Q(("amount_paise__gt", 0)), name="payout_amount_positive")),
        migrations.AddConstraint(model_name="idempotencykey", constraint=models.UniqueConstraint(fields=("merchant", "key"), name="unique_idempotency_key_per_merchant")),
        migrations.AddConstraint(model_name="ledgerentry", constraint=models.CheckConstraint(condition=models.Q(("amount_paise__gt", 0)), name="ledger_amount_positive")),
    ]
