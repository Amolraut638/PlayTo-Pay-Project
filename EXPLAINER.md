# EXPLAINER

## 1. The Ledger

Balance calculation query:

```python
LedgerEntry.objects.filter(merchant_id=merchant_id).aggregate(
    balance_paise=Coalesce(
        Sum(
            Case(
                When(direction=LedgerEntry.Direction.CREDIT, then=F("amount_paise")),
                When(direction=LedgerEntry.Direction.DEBIT, then=-F("amount_paise")),
                default=Value(0),
                output_field=BigIntegerField(),
            )
        ),
        Value(0),
        output_field=BigIntegerField(),
    )
)["balance_paise"]
```

I modelled the ledger as append-only credit/debit rows because the account balance should be derived, not mutated as a cached number. Customer payments are credits. A payout request creates a debit with reason `payout_hold`, so available balance drops immediately while the payout is pending or processing. If the bank fails the payout, the system writes a compensating credit with reason `payout_release`. Completion writes no new ledger row because the hold is already the money leaving the merchant balance.

## 2. The Lock

The overdraft prevention is in `payouts/services.py`:

```python
with transaction.atomic():
    idem = IdempotencyKey.objects.create(...)

    merchant = Merchant.objects.select_for_update().get(pk=merchant_id)
    bank_account = BankAccount.objects.get(pk=bank_account_id, merchant=merchant, is_active=True)
    available = LedgerEntry.available_balance_for_merchant(merchant.id)
    if available < amount_paise:
        ...

    payout = Payout.objects.create(...)
    LedgerEntry.objects.create(... reason=LedgerEntry.Reason.PAYOUT_HOLD ...)
```

The primitive is PostgreSQL row-level locking through `SELECT ... FOR UPDATE`. Every payout creation for the same merchant must acquire the same merchant row lock before calculating available balance and inserting the hold debit. That serializes competing requests for one merchant while still allowing different merchants to create payouts in parallel.

## 3. The Idempotency

The table `IdempotencyKey` has a unique constraint on `(merchant, key)`. The row stores `request_hash`, `response_status`, `response_body`, `payout`, `created_at`, and `expires_at`.

On the first request, the service inserts the idempotency row inside the same transaction that creates the payout and ledger hold. It stores the final response before commit. A duplicate request tries to insert the same `(merchant, key)`, hits the unique constraint, then reads the saved response and returns it exactly. If the first request is still in flight, PostgreSQL makes the second insert wait on the unique index conflict until the first transaction commits or rolls back. Keys are scoped per merchant and a Celery task deletes expired keys after 24 hours.

## 4. The State Machine

The legal transitions are defined on `Payout`:

```python
LEGAL_TRANSITIONS = {
    Status.PENDING: {Status.PROCESSING},
    Status.PROCESSING: {Status.COMPLETED, Status.FAILED},
}
```

The guard is in `transition_to`:

```python
if new_status not in self.LEGAL_TRANSITIONS.get(locked.status, set()):
    raise ValidationError(f"Illegal payout transition {locked.status} -> {new_status}")
```

So `failed -> completed` is blocked because `FAILED` is not a key in `LEGAL_TRANSITIONS`; the allowed next-state set is empty. The same method writes the payout release credit atomically when the transition is `processing -> failed`.

## 5. The AI Audit

One subtly wrong version AI suggested was this check-then-create payout flow:

```python
available = LedgerEntry.available_balance_for_merchant(merchant_id)
if available < amount_paise:
    raise InsufficientFunds()
payout = Payout.objects.create(...)
LedgerEntry.objects.create(direction="debit", amount_paise=amount_paise, payout=payout)
```

That looks reasonable, but it is race-prone. Two concurrent requests can both read the same 100 rupee balance and both insert 60 rupee debits, overdrawing the merchant.

I replaced it with the `transaction.atomic()` plus `Merchant.objects.select_for_update()` version shown above. The important change is that the balance read and hold debit happen while holding a PostgreSQL row lock for that merchant.
