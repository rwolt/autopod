"""Tests for logging system."""

import logging
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from autopod.logging import (
    SensitiveDataFilter,
    get_log_dir,
    get_log_path,
    setup_logging,
    get_logger,
)


@pytest.fixture
def temp_log_dir(tmp_path, monkeypatch):
    """Create a temporary log directory for testing."""
    log_dir = tmp_path / ".autopod" / "logs"
    monkeypatch.setattr("autopod.logging.get_log_dir", lambda: log_dir)
    return log_dir


def test_get_log_dir_returns_path():
    """Test that get_log_dir returns a Path object."""
    log_dir = get_log_dir()
    assert isinstance(log_dir, Path)
    assert log_dir.name == "logs"


def test_get_log_path_returns_log_file():
    """Test that get_log_path returns autopod.log path."""
    log_path = get_log_path()
    assert isinstance(log_path, Path)
    assert log_path.name == "autopod.log"


def test_sensitive_data_filter_redacts_api_key():
    """Test that SensitiveDataFilter redacts API keys."""
    filter_obj = SensitiveDataFilter()

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg='Connecting with api_key="abc123xyz"',
        args=(),
        exc_info=None
    )

    filter_obj.filter(record)

    assert "abc123xyz" not in record.getMessage()
    assert "***REDACTED***" in record.getMessage()


def test_sensitive_data_filter_redacts_password():
    """Test that SensitiveDataFilter redacts passwords."""
    filter_obj = SensitiveDataFilter()

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg='Login with password="secret123"',
        args=(),
        exc_info=None
    )

    filter_obj.filter(record)

    assert "secret123" not in record.getMessage()
    assert "***REDACTED***" in record.getMessage()


def test_sensitive_data_filter_redacts_bearer_token():
    """Test that SensitiveDataFilter redacts Bearer tokens."""
    filter_obj = SensitiveDataFilter()

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg='Authorization: Bearer abc.def.ghi',
        args=(),
        exc_info=None
    )

    filter_obj.filter(record)

    assert "abc.def.ghi" not in record.getMessage()
    assert "***REDACTED***" in record.getMessage()


def test_sensitive_data_filter_redacts_private_key():
    """Test that SensitiveDataFilter redacts private keys."""
    filter_obj = SensitiveDataFilter()

    private_key = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA...
-----END RSA PRIVATE KEY-----"""

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=f'SSH key: {private_key}',
        args=(),
        exc_info=None
    )

    filter_obj.filter(record)

    assert "BEGIN RSA PRIVATE KEY" not in record.getMessage()
    assert "***PRIVATE KEY REDACTED***" in record.getMessage()


def test_sensitive_data_filter_returns_true():
    """Test that SensitiveDataFilter always returns True."""
    filter_obj = SensitiveDataFilter()

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg='Normal log message',
        args=(),
        exc_info=None
    )

    result = filter_obj.filter(record)
    assert result is True


def test_setup_logging_creates_log_directory(temp_log_dir):
    """Test that setup_logging creates the log directory."""
    assert not temp_log_dir.exists()

    setup_logging()

    assert temp_log_dir.exists()


def test_setup_logging_returns_logger(temp_log_dir):
    """Test that setup_logging returns a logger instance."""
    logger = setup_logging()

    assert isinstance(logger, logging.Logger)
    assert logger.name == "autopod"


def test_setup_logging_configures_handlers(temp_log_dir):
    """Test that setup_logging configures file and console handlers."""
    logger = setup_logging()

    # Should have 2 handlers (file and console)
    assert len(logger.handlers) == 2

    handler_types = [type(h).__name__ for h in logger.handlers]
    assert "RotatingFileHandler" in handler_types
    assert "StreamHandler" in handler_types


def test_setup_logging_sets_log_levels(temp_log_dir):
    """Test that setup_logging sets correct log levels."""
    logger = setup_logging(
        level=logging.INFO,
        console_level=logging.WARNING,
        file_level=logging.DEBUG
    )

    # Find handlers
    file_handler = None
    console_handler = None

    for handler in logger.handlers:
        if isinstance(handler, logging.handlers.RotatingFileHandler):
            file_handler = handler
        elif isinstance(handler, logging.StreamHandler):
            console_handler = handler

    assert file_handler is not None
    assert console_handler is not None

    assert file_handler.level == logging.DEBUG
    assert console_handler.level == logging.WARNING


def test_setup_logging_adds_sensitive_data_filter(temp_log_dir):
    """Test that setup_logging adds SensitiveDataFilter to handlers."""
    logger = setup_logging()

    for handler in logger.handlers:
        # Check if SensitiveDataFilter is in the handler's filters
        filter_types = [type(f).__name__ for f in handler.filters]
        assert "SensitiveDataFilter" in filter_types


def test_setup_logging_idempotent(temp_log_dir):
    """Test that setup_logging can be called multiple times without duplicate handlers."""
    setup_logging()
    setup_logging()

    logger = logging.getLogger("autopod")

    # Should still have only 2 handlers (not 4)
    assert len(logger.handlers) == 2


def test_get_logger_returns_autopod_logger(temp_log_dir):
    """Test that get_logger returns an autopod logger."""
    setup_logging()
    logger = get_logger()

    assert logger.name == "autopod"


def test_get_logger_with_name(temp_log_dir):
    """Test that get_logger with name returns namespaced logger."""
    setup_logging()
    logger = get_logger("mymodule")

    assert logger.name == "autopod.mymodule"


def test_get_logger_already_prefixed(temp_log_dir):
    """Test that get_logger doesn't double-prefix if name already starts with autopod."""
    setup_logging()
    logger = get_logger("autopod.mymodule")

    assert logger.name == "autopod.mymodule"
    assert logger.name.count("autopod") == 1
