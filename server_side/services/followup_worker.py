"""Background worker for executing due follow-up tasks."""

import json
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import or_

from server_side.core.config import settings
from server_side.core.logger import logger
from server_side.database.connection import SessionLocal
from server_side.database.models import (
    Email,
    EmailStatusEnum,
    FollowUp,
    FollowUpTypeEnum,
    HumanReview,
    ReviewReasonEnum,
    ReviewStatusEnum,
)
from server_side.services.followup_monitor import record_worker_heartbeat
from server_side.services.email import EmailService


WORKER_INSTANCE_ID = f"followup-worker-{uuid4()}"
WORKER_METRICS = {
    "followups_executed_total": 0,
    "followups_failed_total": 0,
    "followups_retried_total": 0,
}


class NonRetryableFollowUpError(Exception):
    """Raised when retrying a follow-up would never succeed."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _log_event(level: str, event: str, **fields) -> None:
    payload = {
        "event": event,
        "worker_instance": WORKER_INSTANCE_ID,
        "timestamp": _utc_now().isoformat(),
        **fields,
    }
    message = json.dumps(payload, default=str)
    log_fn = getattr(logger, level, logger.info)
    log_fn(message)


def _backoff_seconds(retry_count: int) -> int:
    return settings.FOLLOWUP_RETRY_BASE_SECONDS * (2 ** max(0, retry_count - 1))


def _build_execution_key(email_id: int, followup_type, scheduled_for: datetime) -> str:
    followup_type_value = _enum_value(followup_type)
    scheduled = scheduled_for.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    return f"{email_id}:{followup_type_value}:{scheduled}"


async def _execute_reminder(email: Email) -> str:
    """Send reminder follow-up email to the customer."""
    email_service = EmailService()
    subject = str(email.subject or "").strip()
    if subject.lower().startswith("re:"):
        reminder_subject = f"Follow-up: {subject}"
    elif subject:
        reminder_subject = f"Follow-up: Re: {subject}"
    else:
        reminder_subject = "Follow-up from Customer Support"

    reminder_body = (
        "Hello,\n\n"
        "This is a follow-up from our support team regarding your earlier request. "
        "If your issue is still unresolved, please reply to this email and we will continue assisting you.\n\n"
        "Best regards,\n"
        "Customer Support"
    )

    sent = await email_service.send_email(
        to_address=email.sender,
        subject=reminder_subject,
        body=reminder_body,
    )
    if not sent:
        raise RuntimeError("Failed to send reminder email")

    return "Reminder notification sent"


def _ensure_review_queue_entry(
    session,
    email_id: int,
    reason: ReviewReasonEnum,
    notes: str,
) -> None:
    """Ensure a pending review record exists for support queue handling."""
    review = session.query(HumanReview).filter(HumanReview.email_id == email_id).first()

    if review is None:
        review = HumanReview(
            email_id=email_id,
            reason=reason,
            status=ReviewStatusEnum.PENDING,
            notes=notes,
        )
        session.add(review)
    else:
        review.status = ReviewStatusEnum.PENDING
        review.notes = notes


async def _recover_stale_processing_tasks() -> int:
    """Recover follow-up tasks stuck in processing beyond timeout."""
    session = SessionLocal()
    now = _utc_now()
    cutoff = now - timedelta(seconds=settings.FOLLOWUP_STALE_TIMEOUT_SECONDS)

    try:
        stale_rows = (
            session.query(FollowUp)
            .filter(
                FollowUp.status == "processing",
                FollowUp.processing_since.isnot(None),
                FollowUp.processing_since <= cutoff,
            )
            .all()
        )

        recovered = 0
        for row in stale_rows:
            previous_processing_since = row.processing_since.isoformat() if row.processing_since else None
            row.status = "pending"
            row.processing_since = None
            row.next_retry_at = now
            row.updated_at = now
            row.result = "recovered_stale_task"
            recovered += 1

            _log_event(
                "warning",
                "recovered_stale_task",
                followup_id=row.id,
                email_id=row.email_id,
                followup_type=_enum_value(row.followup_type),
                previous_processing_since=previous_processing_since,
            )

        if recovered:
            session.commit()
        return recovered

    except Exception as e:
        session.rollback()
        _log_event("error", "stale_recovery_failed", error=str(e))
        return 0

    finally:
        session.close()


async def _query_due_followup_rows(batch_size: int) -> list[FollowUp]:
    now = _utc_now()
    session = SessionLocal()
    try:
        return (
            session.query(FollowUp)
            .filter(
                FollowUp.status == "pending",
                FollowUp.scheduled_for <= now,
                or_(FollowUp.next_retry_at.is_(None), FollowUp.next_retry_at <= now),
            )
            .order_by(FollowUp.scheduled_for.asc())
            .limit(batch_size)
            .all()
        )
    except Exception as e:
        _log_event("error", "due_followups_query_failed", error=str(e))
        return []
    finally:
        session.close()


async def _process_single_followup(followup_id: int) -> None:
    """Process one follow-up task with idempotent claim and execution."""
    session = SessionLocal()
    started_at = _utc_now()
    started_perf = time.perf_counter()

    try:
        # Atomic claim: only one worker can transition pending -> processing.
        updated = (
            session.query(FollowUp)
            .filter(
                FollowUp.id == followup_id,
                FollowUp.status == "pending",
            )
            .update(
                {
                    FollowUp.status: "processing",
                    FollowUp.processing_since: started_at,
                    FollowUp.updated_at: started_at,
                },
                synchronize_session=False,
            )
        )
        session.commit()

        if updated == 0:
            _log_event("info", "followup_claim_skipped", followup_id=followup_id)
            return

        followup = session.query(FollowUp).filter(FollowUp.id == followup_id).first()
        if followup is None:
            _log_event("warning", "followup_missing_after_claim", followup_id=followup_id)
            return

        followup_type = _enum_value(followup.followup_type)
        email_id = followup.email_id
        execution_key = followup.execution_key or _build_execution_key(email_id, followup.followup_type, followup.scheduled_for)
        followup.execution_key = execution_key
        session.commit()

        if bool(getattr(followup, "simulate_failure", False)) or followup.result == "simulate_failure":
            _log_event(
                "warning",
                "followup_simulated_failure",
                followup_id=followup.id,
                email_id=email_id,
                followup_type=followup_type,
                retry_count=int(followup.retry_count or 0),
                next_retry_at=followup.next_retry_at.isoformat() if followup.next_retry_at else None,
            )
            raise RuntimeError("Simulated failure for testing")

        duplicate_executed = (
            session.query(FollowUp.id)
            .filter(
                FollowUp.execution_key == execution_key,
                FollowUp.status == "executed",
                FollowUp.id != followup.id,
            )
            .first()
        )
        if duplicate_executed is not None:
            followup.status = "executed"
            followup.executed_at = _utc_now()
            followup.processing_since = None
            followup.result = "Skipped duplicate execution due to existing executed follow-up"
            followup.updated_at = _utc_now()
            session.commit()
            _log_event(
                "warning",
                "followup_duplicate_skipped",
                followup_id=followup.id,
                email_id=email_id,
                followup_type=followup_type,
                execution_key=execution_key,
            )
            return

        _log_event(
            "info",
            "followup_execution_start",
            followup_id=followup.id,
            email_id=email_id,
            followup_type=followup_type,
            execution_key=execution_key,
            processing_since=started_at.isoformat(),
        )

        email = session.query(Email).filter(Email.id == email_id).first()
        if email is None:
            raise NonRetryableFollowUpError(f"Email {email_id} not found")

        result_message: Optional[str] = None

        if followup_type == FollowUpTypeEnum.REMINDER.value:
            result_message = await _execute_reminder(email)

        elif followup_type == FollowUpTypeEnum.VERIFICATION.value:
            _ensure_review_queue_entry(
                session,
                email_id=email_id,
                reason=ReviewReasonEnum.CUSTOM,
                notes="Billing verification follow-up triggered automatically.",
            )
            email.status = EmailStatusEnum.AWAITING_REVIEW
            result_message = "Billing verification workflow queued to support review"

        elif followup_type == FollowUpTypeEnum.ESCALATION.value:
            _ensure_review_queue_entry(
                session,
                email_id=email_id,
                reason=ReviewReasonEnum.ESCALATED_COMPLAINT,
                notes="Escalation follow-up triggered automatically.",
            )
            email.status = EmailStatusEnum.AWAITING_REVIEW
            result_message = "Escalated to support queue"

        else:
            raise NonRetryableFollowUpError(f"Unsupported followup_type: {followup_type}")

        followup.status = "executed"
        followup.executed_at = _utc_now()
        followup.processing_since = None
        followup.result = result_message
        followup.last_error = None
        followup.updated_at = _utc_now()
        session.commit()
        WORKER_METRICS["followups_executed_total"] += 1

        execution_time_ms = int((time.perf_counter() - started_perf) * 1000)

        _log_event(
            "info",
            "followup_execution_success",
            followup_id=followup.id,
            email_id=email_id,
            followup_type=followup_type,
            status_from="processing",
            status_to="executed",
            execution_time_ms=execution_time_ms,
        )

    except Exception as e:
        session.rollback()

        try:
            row = session.query(FollowUp).filter(FollowUp.id == followup_id).first()
            if row is not None:
                retryable = not isinstance(e, NonRetryableFollowUpError)
                row.retry_count = int(row.retry_count or 0) + 1
                max_retries = int(row.max_retries or settings.FOLLOWUP_MAX_RETRIES)
                now = _utc_now()

                if retryable and row.retry_count < max_retries:
                    backoff_seconds = _backoff_seconds(row.retry_count)
                    row.status = "pending"
                    row.next_retry_at = now + timedelta(seconds=backoff_seconds)
                    row.processing_since = None
                    row.last_error = str(e)
                    row.result = f"Retry scheduled after error: {str(e)}"
                    row.updated_at = now
                    WORKER_METRICS["followups_retried_total"] += 1

                    _log_event(
                        "warning",
                        "followup_retry_scheduled",
                        followup_id=row.id,
                        email_id=row.email_id,
                        followup_type=_enum_value(row.followup_type),
                        retry_count=row.retry_count,
                        max_retries=max_retries,
                        next_retry_at=row.next_retry_at.isoformat() if row.next_retry_at else None,
                        error=str(e),
                    )
                else:
                    row.status = "failed"
                    row.processing_since = None
                    row.last_error = str(e)
                    row.result = f"Execution failed: {str(e)}"
                    row.updated_at = now
                    WORKER_METRICS["followups_failed_total"] += 1

                    _log_event(
                        "error",
                        "followup_execution_failed",
                        followup_id=row.id,
                        email_id=row.email_id,
                        followup_type=_enum_value(row.followup_type),
                        retry_count=row.retry_count,
                        max_retries=max_retries,
                        error=str(e),
                        execution_time_ms=int((time.perf_counter() - started_perf) * 1000),
                    )

                session.commit()
        except Exception as mark_error:
            session.rollback()
            _log_event(
                "error",
                "followup_failure_marking_failed",
                followup_id=followup_id,
                error=str(mark_error),
            )

    finally:
        session.close()


async def process_due_followups(app=None, batch_size: int = 50) -> None:
    """Process due follow-ups using DB polling (source of truth)."""
    record_worker_heartbeat(started=True)
    recovered_count = await _recover_stale_processing_tasks()
    if recovered_count:
        _log_event("warning", "stale_recovery_completed", recovered_count=recovered_count)

    due_rows = await _query_due_followup_rows(batch_size=batch_size)
    if not due_rows:
        _log_event("debug", "no_due_followups")
        record_worker_heartbeat(started=False)
        return

    _log_event("info", "due_followups_found", due_count=len(due_rows))

    for row in due_rows:
        await _process_single_followup(row.id)

    _log_event("info", "followup_worker_metrics", **WORKER_METRICS)
    record_worker_heartbeat(started=False)
