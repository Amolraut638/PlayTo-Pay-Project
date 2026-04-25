import random
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Payout


@shared_task
def process_due_payouts():
    now = timezone.now()    
    retry_stuck_processing(now)
    payout_ids = list(
        Payout.objects.filter(status=Payout.Status.PENDING, next_attempt_at__lte=now)
        .order_by("created_at")
        .values_list("id", flat=True)[:25]
    )
    for payout_id in payout_ids:
        process_payout.delay(str(payout_id))


def retry_stuck_processing(now):
    cutoff = now - timedelta(seconds=settings.PAYOUT_PROCESSING_STUCK_SECONDS)
    stuck_ids = list(
        Payout.objects.filter(
            status=Payout.Status.PROCESSING,
            processing_started_at__lt=cutoff,
            next_attempt_at__lte=now,
        ).values_list("id", flat=True)[:25]
    )
    for payout_id in stuck_ids:
        process_payout.delay(str(payout_id))


@shared_task(bind=True, max_retries=3)
def process_payout(self, payout_id):
    with transaction.atomic():
        payout = Payout.objects.select_for_update(skip_locked=True).filter(pk=payout_id).first()
        if payout is None or payout.status in Payout.TERMINAL_STATUSES:
            return

        if payout.attempts >= 3:
            payout.transition_to(Payout.Status.FAILED, failure_reason="Max retry attempts exceeded")
            return

        if payout.status == Payout.Status.PENDING:
            payout.transition_to(Payout.Status.PROCESSING)
            transaction.on_commit(lambda: settle_payout.delay(str(payout.id)))
            return

        if payout.status == Payout.Status.PROCESSING:
            # Do NOT increment attempts here — transition_to(PROCESSING) already
            # handles that inside the state machine. Just reschedule and re-settle.
            payout.processing_started_at = timezone.now()
            payout.next_attempt_at = timezone.now() + timedelta(seconds=2**payout.attempts)
            payout.save(
                update_fields=[
                    "processing_started_at",
                    "next_attempt_at",
                    "updated_at",
                ]
            )
            transaction.on_commit(lambda: settle_payout.delay(str(payout.id)))


@shared_task
def settle_payout(payout_id):
    outcome = random.random()
    try:
        payout = Payout.objects.get(pk=payout_id)
        if outcome < 0.70:
            payout.transition_to(Payout.Status.COMPLETED)
        elif outcome < 0.90:
            payout.transition_to(Payout.Status.FAILED, failure_reason="Bank rejected payout")
        else:
            return
    except (Payout.DoesNotExist, ValidationError):
        return


@shared_task
def expire_idempotency_keys():
    from .models import IdempotencyKey

    IdempotencyKey.objects.filter(expires_at__lt=timezone.now()).delete()
