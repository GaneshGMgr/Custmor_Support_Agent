"""Monitoring and alert helpers for FollowUp worker observability."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from server_side.core.config import settings
from server_side.core.logger import logger


_last_worker_run: Optional[datetime] = None
_last_worker_run_start: Optional[datetime] = None
_worker_run_count: int = 0
_last_alert_at: dict[str, float] = {}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def record_worker_heartbeat(started: bool = False) -> None:
    """Record worker heartbeat timestamps for health endpoint."""
    global _last_worker_run, _last_worker_run_start, _worker_run_count

    now = _utc_now()
    if started:
        _last_worker_run_start = now
        return

    _last_worker_run = now
    _worker_run_count += 1


def get_worker_health(interval_seconds: int) -> dict[str, Any]:
    """Return worker health snapshot from heartbeat data."""
    now = _utc_now()

    if _last_worker_run is None:
        return {
            "worker_status": "idle",
            "last_run_time": None,
            "time_since_last_run": None,
            "missed_cycles_count": 0,
            "run_count": _worker_run_count,
        }

    delta_seconds = max(0.0, (now - _last_worker_run).total_seconds())
    missed_cycles = 0
    if interval_seconds > 0:
        missed_cycles = max(0, int(delta_seconds // interval_seconds) - 1)

    stale_threshold_seconds = interval_seconds * 3
    worker_status = "healthy" if delta_seconds <= stale_threshold_seconds else "stale"

    return {
        "worker_status": worker_status,
        "last_run_time": _last_worker_run.isoformat(),
        "time_since_last_run": delta_seconds,
        "missed_cycles_count": missed_cycles,
        "run_count": _worker_run_count,
        "last_run_started_at": _last_worker_run_start.isoformat() if _last_worker_run_start else None,
    }


def _should_emit_alert(alert_key: str) -> bool:
    now_ts = time.time()
    cooldown = max(1, int(settings.FOLLOWUP_ALERT_COOLDOWN_SECONDS))
    last_ts = _last_alert_at.get(alert_key)
    if last_ts is not None and (now_ts - last_ts) < cooldown:
        return False

    _last_alert_at[alert_key] = now_ts
    return True


async def _send_webhook_alert(payload: dict[str, Any]) -> None:
    webhook_url = settings.FOLLOWUP_ALERT_WEBHOOK_URL
    if not webhook_url:
        return

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()
    except Exception as e:
        logger.error("FollowUp alert webhook failed: {}", str(e))


async def evaluate_followup_alerts(stats: dict[str, Any], health: dict[str, Any]) -> None:
    """Emit warning logs and optional webhook alerts for abnormal states."""
    alerts: list[dict[str, Any]] = []

    if health.get("worker_status") == "stale" and _should_emit_alert("worker_stale"):
        alerts.append({
            "alert_type": "worker_stale",
            "message": "FollowUp worker heartbeat is stale",
            "health": health,
        })

    total = int(stats.get("total_followups", 0) or 0)
    failed = int(stats.get("failed", 0) or 0)
    failure_rate = (failed / total) if total > 0 else 0.0
    if failure_rate >= float(settings.FOLLOWUP_FAILURE_RATE_ALERT_THRESHOLD) and _should_emit_alert("failure_rate"):
        alerts.append({
            "alert_type": "high_failure_rate",
            "message": "FollowUp failure rate exceeded threshold",
            "failure_rate": failure_rate,
            "threshold": float(settings.FOLLOWUP_FAILURE_RATE_ALERT_THRESHOLD),
            "stats": stats,
        })

    retrying = int(stats.get("retrying", 0) or 0)
    if retrying >= int(settings.FOLLOWUP_RETRY_QUEUE_ALERT_THRESHOLD) and _should_emit_alert("retry_queue"):
        alerts.append({
            "alert_type": "retry_queue_growth",
            "message": "FollowUp retry queue size exceeded threshold",
            "retrying": retrying,
            "threshold": int(settings.FOLLOWUP_RETRY_QUEUE_ALERT_THRESHOLD),
            "stats": stats,
        })

    for alert in alerts:
        logger.warning("{}", json.dumps(alert, default=str))
        await _send_webhook_alert(alert)
