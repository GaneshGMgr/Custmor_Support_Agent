
# server_side/core/logger.py

import sys
from pathlib import Path

from loguru import logger as _logger

from server_side.core.config import settings


class GlobalLogger:
    """
    Combines Loguru console/file logging with structured JSON support.
    - Console: colored, human-readable
    - File: JSON structured logs with ISO 8601 timestamp
    - Supports dynamic metadata: user_id, email_id, model_name, etc.
    """

    def __init__(self):
        self._setup_logger()

    def _setup_logger(self):
        _logger.remove()

        log_file_path = Path(settings.LOG_FILE)
        log_file_path.parent.mkdir(parents=True, exist_ok=True)

        _logger.add(
            sys.stdout,
            level=settings.LOG_LEVEL,
            colorize=True,
            format="<level>{level: <8}</level> | "
                   "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                   "<level>{message}</level>"
        )

        _logger.add(
            log_file_path,
            level=settings.LOG_LEVEL,
            format="{time:YYYY-MM-DDTHH:mm:ssZ} | {level} | {name}:{function}:{line} | {extra}",
            serialize=True,
            rotation="500 MB",
            retention="7 days",
            enqueue=True,
        )

    def get_logger(self, **extra):
        """
        Return a logger instance that can attach extra metadata.
        Usage:
            log = GLOBAL_LOGGER.get_logger(user_id=123, model_name="qwen3")
            log.info("Started processing email")
        """
        return _logger.bind(**extra)


GLOBAL_LOGGER = GlobalLogger().get_logger()
logger = GLOBAL_LOGGER


def setup_logging():
    """Initialize and return the shared application logger."""
    return GLOBAL_LOGGER
