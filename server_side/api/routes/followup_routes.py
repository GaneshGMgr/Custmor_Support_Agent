"""FollowUp monitoring and visibility APIs."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from server_side.core.config import settings
from server_side.core.logger import logger
from server_side.database.connection import SessionLocal
from server_side.database.models import Email, FollowUp, FollowUpTypeEnum
from server_side.services.followup_monitor import evaluate_followup_alerts, get_worker_health
from server_side.services.followup_monitor import record_worker_heartbeat
from server_side.services.database import DatabaseService

try:
    from server_side.services import followup_worker as followup_worker_module
except Exception:  # pragma: no cover - optional diagnostic context
    worker_instance_id = None
    process_due_followups = None
else:
    worker_instance_id = getattr(followup_worker_module, "WORKER_INSTANCE_ID", None)
    process_due_followups = getattr(followup_worker_module, "process_due_followups", None)

router = APIRouter(prefix="/api/followups", tags=["FollowUps"])
dev_router = APIRouter(prefix="/api/dev/followup", tags=["FollowUp Dev"])


def _to_iso(dt: Any) -> Optional[str]:
    if dt is None:
        return None
    normalized = _to_utc_datetime(dt)
    if normalized is None:
        return None
    return normalized.isoformat()


def _to_utc_datetime(dt: Any) -> Optional[datetime]:
    if not isinstance(dt, datetime):
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _enum_or_str(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _followup_to_list_item(f: Any) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    scheduled_for = _to_utc_datetime(getattr(f, "scheduled_for", None))
    executed_at = _to_utc_datetime(getattr(f, "executed_at", None))
    next_retry_at = _to_utc_datetime(getattr(f, "next_retry_at", None))
    status = getattr(f, "status", None)
    due_at = next_retry_at or scheduled_for
    overdue = (due_at is not None and due_at < now and status in {"pending", "processing"})

    delay_ms = None
    if executed_at is not None and scheduled_for is not None:
        delay_ms = int((executed_at - scheduled_for).total_seconds() * 1000)

    return {
        "id": getattr(f, "id", None),
        "email_id": getattr(f, "email_id", None),
        "type": _enum_or_str(getattr(f, "followup_type", None)),
        "status": getattr(f, "status", None),
        "scheduled_for": _to_iso(scheduled_for),
        "executed_at": _to_iso(executed_at),
        "retry_count": int(getattr(f, "retry_count", 0) or 0),
        "next_retry_at": _to_iso(next_retry_at),
        "created_at": _to_iso(getattr(f, "created_at", None)),
        "last_error": getattr(f, "last_error", None),
        "simulate_failure": bool(getattr(f, "simulate_failure", False)),
        "delay_ms": delay_ms,
        "overdue": overdue,
    }


def _compute_stats(session: Any) -> dict[str, Any]:
    now = datetime.now(timezone.utc)

    rows: list[Any] = session.query(FollowUp).all()
    total = len(rows)

    pending = sum(1 for r in rows if getattr(r, "status", None) == "pending")
    processing = sum(1 for r in rows if getattr(r, "status", None) == "processing")
    executed = sum(1 for r in rows if getattr(r, "status", None) == "executed")
    failed = sum(1 for r in rows if getattr(r, "status", None) == "failed")
    retrying = sum(1 for r in rows if getattr(r, "status", None) == "pending" and int(getattr(r, "retry_count", 0) or 0) > 0)
    overdue = 0
    delays: list[int] = []
    for r in rows:
        scheduled_for = _to_utc_datetime(getattr(r, "scheduled_for", None))
        executed_at = _to_utc_datetime(getattr(r, "executed_at", None))
        next_retry_at = _to_utc_datetime(getattr(r, "next_retry_at", None))
        due_at = next_retry_at or scheduled_for

        if due_at is not None and due_at < now and getattr(r, "status", None) in {"pending", "processing"}:
            overdue += 1

        if executed_at is not None and scheduled_for is not None:
            delays.append(int((executed_at - scheduled_for).total_seconds() * 1000))
    average_delay_ms = int(sum(delays) / len(delays)) if delays else 0
    max_delay_ms = max(delays) if delays else 0
    late_executions = sum(1 for d in delays if d > 0)

    return {
        "total_followups": total,
        "pending": pending,
        "processing": processing,
        "executed": executed,
        "failed": failed,
        "retrying": retrying,
        "overdue": overdue,
        "average_delay_ms": average_delay_ms,
        "max_delay_ms": max_delay_ms,
        "late_executions": late_executions,
        "generated_at": now.isoformat(),
    }


def _log_structured_event(event: str, **fields: Any) -> None:
    payload: dict[str, Any] = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "worker_instance_id": worker_instance_id,
        **fields,
    }
    logger.info("{}", json.dumps(payload, default=str))


@router.get("")
async def list_followups(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=200),
    status: Optional[str] = Query(default=None),
    type: Optional[str] = Query(default=None),
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
) -> dict[str, Any]:
    """Paginated follow-up list for dashboard monitoring."""
    session = SessionLocal()
    try:
        query = session.query(FollowUp)

        if status:
            query = query.filter(FollowUp.status == status)

        if type:
            query = query.filter(FollowUp.followup_type == type)

        if start_date:
            query = query.filter(FollowUp.scheduled_for >= start_date)

        if end_date:
            query = query.filter(FollowUp.scheduled_for <= end_date)

        total = query.count()

        rows: list[Any] = (
            query.order_by(FollowUp.scheduled_for.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        items = [_followup_to_list_item(row) for row in rows]
        pages = (total + per_page - 1) // per_page

        return {
            "items": items,
            "total": total,
            "page": page,
            "pages": pages,
            "per_page": per_page,
        }
    except Exception as e:
        logger.error("Failed to list follow-ups: {}", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/stats")
async def followup_stats():
    """Aggregated metrics and SLA stats for follow-ups."""
    session = SessionLocal()
    try:
        stats = _compute_stats(session)
        health = get_worker_health(settings.FOLLOWUP_WORKER_INTERVAL_SECONDS)
        await evaluate_followup_alerts(stats, health)
        return stats
    except Exception as e:
        logger.error("Failed to compute follow-up stats: {}", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/health")
async def followup_worker_health() -> dict[str, Any]:
    """Follow-up worker heartbeat health."""
    try:
        session = SessionLocal()
        try:
            stats = _compute_stats(session)
        finally:
            session.close()

        health = get_worker_health(settings.FOLLOWUP_WORKER_INTERVAL_SECONDS)
        await evaluate_followup_alerts(stats, health)
        return health
    except Exception as e:
        logger.error("Failed to fetch follow-up worker health: {}", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{followup_id}")
async def followup_detail(followup_id: int) -> dict[str, Any]:
    """Full follow-up record for inspection."""
    session = SessionLocal()
    try:
        row: Any = session.query(FollowUp).filter(FollowUp.id == followup_id).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Follow-up not found")

        now = datetime.now(timezone.utc)
        scheduled_for = _to_utc_datetime(getattr(row, "scheduled_for", None))
        next_retry_at = _to_utc_datetime(getattr(row, "next_retry_at", None))
        status = getattr(row, "status", None)
        due_at = next_retry_at or scheduled_for
        overdue = (due_at is not None and due_at < now and status in {"pending", "processing"})

        delay_ms = None
        executed_at = _to_utc_datetime(getattr(row, "executed_at", None))
        if executed_at is not None and scheduled_for is not None:
            delay_ms = int((executed_at - scheduled_for).total_seconds() * 1000)

        return {
            "id": getattr(row, "id", None),
            "email_id": getattr(row, "email_id", None),
            "followup_type": _enum_or_str(getattr(row, "followup_type", None)),
            "status": getattr(row, "status", None),
            "scheduled_for": _to_iso(scheduled_for),
            "executed_at": _to_iso(executed_at),
            "processing_since": _to_iso(getattr(row, "processing_since", None)),
            "retry_count": int(getattr(row, "retry_count", 0) or 0),
            "max_retries": int(getattr(row, "max_retries", None) or settings.FOLLOWUP_MAX_RETRIES),
            "next_retry_at": _to_iso(getattr(row, "next_retry_at", None)),
            "execution_key": getattr(row, "execution_key", None),
            "simulate_failure": bool(getattr(row, "simulate_failure", False)),
            "result": getattr(row, "result", None),
            "last_error": getattr(row, "last_error", None),
            "created_at": _to_iso(getattr(row, "created_at", None)),
            "updated_at": _to_iso(getattr(row, "updated_at", None)),
            "delay_ms": delay_ms,
            "overdue": overdue,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch follow-up detail {}: {}", followup_id, str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@dev_router.post("/heartbeat/ping")
async def manual_followup_heartbeat_ping():
    """DEV ONLY: manually refresh the worker heartbeat for dashboard testing."""
    if not settings.DEBUG:
        raise HTTPException(status_code=403, detail="Forbidden")

    record_worker_heartbeat(started=True)
    record_worker_heartbeat(started=False)

    timestamp = datetime.now(timezone.utc).isoformat()
    _log_structured_event("manual_heartbeat_triggered", timestamp=timestamp)

    return {
        "status": "ok",
        "message": "Heartbeat updated",
        "timestamp": timestamp,
    }


@dev_router.post("/run")
async def manual_followup_worker_run() -> dict[str, Any]:
    """DEV ONLY: manually execute due follow-ups through the standard worker flow."""
    if not settings.DEBUG:
        raise HTTPException(status_code=403, detail="Forbidden")

    if process_due_followups is None:
        raise HTTPException(status_code=500, detail="Follow-up worker is unavailable")

    started = time.perf_counter()
    await process_due_followups()
    execution_ms = int((time.perf_counter() - started) * 1000)

    timestamp = datetime.now(timezone.utc).isoformat()
    _log_structured_event(
        "manual_worker_triggered",
        timestamp=timestamp,
        execution_ms=execution_ms,
    )

    return {
        "status": "ok",
        "message": "Follow-up worker executed",
        "timestamp": timestamp,
        "execution_ms": execution_ms,
    }


@dev_router.post("/create-test")
async def manual_create_test_followup(simulate_failure: bool = Body(default=False, embed=True)) -> dict[str, Any]:
    """DEV ONLY: create an immediately-due test follow-up for dashboard testing."""
    if not settings.DEBUG:
        raise HTTPException(status_code=403, detail="Forbidden")

    session = SessionLocal()
    try:
        email_row: Any = (
            session.query(Email)
            .order_by(Email.received_at.desc(), Email.id.desc())
            .first()
        )

        if email_row is None:
            return {
                "status": "error",
                "message": "No emails available to attach follow-up",
            }

        scheduled_for = datetime.now(timezone.utc)
        db_service = DatabaseService(db=session)
        followup = await db_service.create_followup(
            email_id=int(getattr(email_row, "id")),
            followup_type=FollowUpTypeEnum.REMINDER,
            scheduled_for=scheduled_for,
            simulate_failure=simulate_failure,
        )

        followup_id = int(getattr(followup, "id"))
        email_id = int(getattr(followup, "email_id"))
        followup_type = _enum_or_str(getattr(followup, "followup_type", None))
        scheduled_for_iso = _to_iso(getattr(followup, "scheduled_for", scheduled_for))

        _log_structured_event(
            "manual_test_followup_created",
            followup_id=followup_id,
            email_id=email_id,
            followup_type=followup_type,
            scheduled_for=scheduled_for_iso,
            simulate_failure=simulate_failure,
        )

        return {
            "status": "ok",
            "message": "Test follow-up created",
            "followup_id": followup_id,
            "email_id": email_id,
            "scheduled_for": scheduled_for_iso,
        }
    finally:
        session.close()
