"""Tests for verbose logging configuration.

Tests for:
1. AUTOPOD_DEBUG environment variable
2. Default console log level (WARNING)
3. File log level (DEBUG)
"""

import pytest
import logging
import os
from unittest.mock import patch, MagicMock
from autopod.logging import setup_logging


class TestVerboseLogging:
    """Test verbose logging configuration."""

    def test_default_console_level_is_warning(self):
        """Test that default console level is WARNING (not INFO)."""
        with patch.dict(os.environ, {}, clear=True):
            # Clear AUTOPOD_DEBUG if it exists
            os.environ.pop('AUTOPOD_DEBUG', None)

            logger = setup_logging()

            # Find console handler
            console_handler = None
            for handler in logger.handlers:
                if isinstance(handler, logging.StreamHandler) and not hasattr(handler, 'baseFilename'):
                    console_handler = handler
                    break

            assert console_handler is not None
            assert console_handler.level == logging.WARNING

    def test_debug_env_var_enables_verbose(self):
        """Test that AUTOPOD_DEBUG=1 enables INFO level console logging."""
        with patch.dict(os.environ, {'AUTOPOD_DEBUG': '1'}):
            logger = setup_logging()

            # Find console handler
            console_handler = None
            for handler in logger.handlers:
                if isinstance(handler, logging.StreamHandler) and not hasattr(handler, 'baseFilename'):
                    console_handler = handler
                    break

            assert console_handler is not None
            assert console_handler.level == logging.INFO

    def test_debug_env_var_case_insensitive(self):
        """Test that AUTOPOD_DEBUG environment variable is case-insensitive."""
        test_values = ['1', 'true', 'TRUE', 'True', 'yes', 'YES', 'Yes']

        for value in test_values:
            with patch.dict(os.environ, {'AUTOPOD_DEBUG': value}):
                logger = setup_logging()

                # Find console handler
                console_handler = None
                for handler in logger.handlers:
                    if isinstance(handler, logging.StreamHandler) and not hasattr(handler, 'baseFilename'):
                        console_handler = handler
                        break

                assert console_handler is not None
                assert console_handler.level == logging.INFO, f"Failed for value: {value}"

    def test_file_handler_always_debug(self):
        """Test that file handler always logs at DEBUG level."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop('AUTOPOD_DEBUG', None)

            logger = setup_logging()

            # Find file handler
            file_handler = None
            for handler in logger.handlers:
                if hasattr(handler, 'baseFilename'):
                    file_handler = handler
                    break

            assert file_handler is not None
            assert file_handler.level == logging.DEBUG

    def test_explicit_console_level_overrides_debug(self):
        """Test that explicit console_level parameter overrides AUTOPOD_DEBUG."""
        with patch.dict(os.environ, {'AUTOPOD_DEBUG': '1'}):
            # Even with DEBUG=1, explicit console_level should win
            logger = setup_logging(console_level=logging.ERROR)

            # Find console handler
            console_handler = None
            for handler in logger.handlers:
                if isinstance(handler, logging.StreamHandler) and not hasattr(handler, 'baseFilename'):
                    console_handler = handler
                    break

            assert console_handler is not None
            assert console_handler.level == logging.ERROR

    def test_logger_captures_all_levels(self):
        """Test that root logger captures all levels (handlers do the filtering)."""
        logger = setup_logging()

        # Root logger should be set to DEBUG to capture everything
        assert logger.level == logging.DEBUG

    def test_false_debug_values_use_warning(self):
        """Test that false-y AUTOPOD_DEBUG values use WARNING level."""
        false_values = ['0', 'false', 'FALSE', 'no', 'NO', '', 'random']

        for value in false_values:
            with patch.dict(os.environ, {'AUTOPOD_DEBUG': value}):
                logger = setup_logging()

                # Find console handler
                console_handler = None
                for handler in logger.handlers:
                    if isinstance(handler, logging.StreamHandler) and not hasattr(handler, 'baseFilename'):
                        console_handler = handler
                        break

                assert console_handler is not None
                assert console_handler.level == logging.WARNING, f"Failed for value: {value}"
