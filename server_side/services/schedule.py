# server_side/services/schedule.py
"""APScheduler wrapper used by the FastAPI lifespan lifecycle."""

from typing import Any, Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from server_side.core.logger import logger


class SchedulerService:
    """Service that manages an AsyncIOScheduler instance."""

    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler()

    async def start(self) -> None:
        """Start scheduler instance."""
        if self.scheduler.running:
            logger.info("Scheduler already running")
            return

        self.scheduler.start()
        logger.info("Scheduler started")

    async def stop(self) -> None:
        """Stop scheduler instance."""
        if not self.scheduler.running:
            logger.info("Scheduler already stopped")
            return

        self.scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

    def add_job(
        self,
        job_func: Callable[..., Any],
        interval: int,
        args: Optional[list[Any]] = None,
        kwargs: Optional[dict[str, Any]] = None,
        job_id: Optional[str] = None,
    ) -> str:
        """Register a recurring interval job.

        Args:
            job_func: Callable to run on interval
            interval: Run frequency in seconds
            args: Positional args passed to job
            kwargs: Keyword args passed to job
            job_id: Optional fixed job id

        Returns:
            The APScheduler job id
        """
        job = self.scheduler.add_job(
            job_func,
            trigger="interval",
            seconds=interval,
            id=job_id,
            replace_existing=True,
            args=args or [],
            kwargs=kwargs or {},
        )
        logger.info(
            "Scheduler job added: id={}, interval_seconds={}",
            job.id,
            interval,
        )
        return job.id

    def add_interval_job(
        self,
        job_func: Callable[..., Any],
        interval_seconds: int,
        job_id: Optional[str] = None,
        *args: Any,
        **kwargs: Any,
    ) -> str:
        """Backward-compatible wrapper around add_job."""
        return self.add_job(
            job_func=job_func,
            interval=interval_seconds,
            args=list(args) if args else None,
            kwargs=kwargs if kwargs else None,
            job_id=job_id,
        )


# Backwards-compatible alias for older imports.
ScheduleService = SchedulerService
