"""Logging setup for autopod.

This module configures comprehensive logging with rotation, sensitive data redaction,
and both file and console handlers.
"""

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


class SensitiveDataFilter(logging.Filter):
    """Filter to redact sensitive data from log messages."""

    # Patterns to match sensitive data
    PATTERNS = [
        (re.compile(r'api[_-]?key["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_-]+)["\']?', re.IGNORECASE), 'api_key=***REDACTED***'),
        (re.compile(r'password["\']?\s*[:=]\s*["\']?([^"\'\s]+)["\']?', re.IGNORECASE), 'password=***REDACTED***'),
        (re.compile(r'token["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_.-]+)["\']?', re.IGNORECASE), 'token=***REDACTED***'),
        (re.compile(r'Bearer\s+([a-zA-Z0-9_.-]+)', re.IGNORECASE), 'Bearer ***REDACTED***'),
        (re.compile(r'-----BEGIN[A-Z\s]+PRIVATE KEY-----.*?-----END[A-Z\s]+PRIVATE KEY-----', re.DOTALL), '***PRIVATE KEY REDACTED***'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive data from log record.

        Args:
            record: The log record to filter

        Returns:
            True (always process the record, just modify it)
        """
        # Redact sensitive data from message
        message = record.getMessage()
        for pattern, replacement in self.PATTERNS:
            message = pattern.sub(replacement, message)

        # Update the record's message
        record.msg = message
        record.args = ()

        return True


def get_log_dir() -> Path:
    """Get the autopod logs directory path.

    Returns:
        Path to ~/.autopod/logs directory
    """
    return Path.home() / ".autopod" / "logs"


def get_log_path() -> Path:
    """Get the autopod log file path.

    Returns:
        Path to ~/.autopod/logs/autopod.log
    """
    return get_log_dir() / "autopod.log"


def setup_logging(
    level: int = logging.INFO,
    console_level: Optional[int] = None,
    file_level: Optional[int] = None
) -> logging.Logger:
    """Set up comprehensive logging for autopod.

    Configures both file and console logging with:
    - Rotating file handler (10MB max, 5 backups)
    - Sensitive data redaction
    - Structured log format with timestamps

    Args:
        level: Default logging level (default: INFO)
        console_level: Console handler level (default: same as level)
        file_level: File handler level (default: DEBUG for detailed logs)

    Returns:
        Configured logger instance

    Example:
        logger = setup_logging()
        logger.info("Starting autopod")
        logger.debug("Detailed debug information")
    """
    # Use default levels if not specified
    if console_level is None:
        console_level = level
    if file_level is None:
        file_level = logging.DEBUG  # File logs everything

    # Create logs directory if it doesn't exist
    log_dir = get_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)

    # Get or create logger
    logger = logging.getLogger("autopod")
    logger.setLevel(logging.DEBUG)  # Capture everything, handlers will filter

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create formatters
    file_formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_formatter = logging.Formatter(
        fmt='%(levelname)s: %(message)s'
    )

    # File handler with rotation (10MB max, 5 backups)
    log_path = get_log_path()
    file_handler = RotatingFileHandler(
        filename=log_path,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(file_formatter)
    file_handler.addFilter(SensitiveDataFilter())

    # Console handler for user-facing messages
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(SensitiveDataFilter())

    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.debug(f"Logging initialized - log file: {log_path}")

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name (default: "autopod")

    Returns:
        Logger instance

    Example:
        logger = get_logger(__name__)
        logger.info("Module started")
    """
    if name is None:
        name = "autopod"
    elif not name.startswith("autopod"):
        name = f"autopod.{name}"

    return logging.getLogger(name)
