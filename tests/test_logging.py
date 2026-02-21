"""Tests for the logging configuration module."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from idea_factory.logging_cfg import setup_logging


class TestSetupLogging:
    def setup_method(self):
        """Reset the module-level flag before each test."""
        import idea_factory.logging_cfg as mod
        mod._CONFIGURED = False
        # Remove existing handlers
        logger = logging.getLogger("idea_factory")
        logger.handlers.clear()

    def test_creates_logger(self):
        setup_logging(level="DEBUG")
        logger = logging.getLogger("idea_factory")
        assert logger.level == logging.DEBUG
        assert len(logger.handlers) >= 1

    def test_file_handler_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = str(Path(tmpdir) / "test.log")
            setup_logging(level="INFO", log_file=log_file)
            logger = logging.getLogger("idea_factory.test")
            logger.warning("test message")
            assert Path(log_file).exists()

    def test_idempotent(self):
        setup_logging(level="INFO")
        logger = logging.getLogger("idea_factory")
        handler_count = len(logger.handlers)
        # Reset flag to test idempotency guard
        import idea_factory.logging_cfg as mod
        mod._CONFIGURED = True
        setup_logging(level="DEBUG")
        # Should not add more handlers
        assert len(logger.handlers) == handler_count
