"""Tests for configure_logging() in isolation."""

import logging

import structlog

from brian_appkit import LogFormat, LogLevel
from brian_appkit._logging import configure_logging


class _Config:
    """Minimal object satisfying the _LoggingConfig Protocol."""
    def __init__(
        self,
        log_format: LogFormat | None = LogFormat.TEXT,
        log_level: LogLevel = LogLevel.INFO,
    ) -> None:
        self.log_format = log_format
        self.log_level = log_level


class TestHandlerManagement:
    def test_adds_processor_formatter_handler(self):
        configure_logging(_Config())
        root = logging.getLogger()
        appkit_handlers = [
            h for h in root.handlers
            if isinstance(
                getattr(h, "formatter", None), structlog.stdlib.ProcessorFormatter
            )
        ]
        assert len(appkit_handlers) == 1

    def test_preserves_existing_non_appkit_handler(self):
        sentinel = logging.NullHandler()
        logging.getLogger().addHandler(sentinel)
        configure_logging(_Config())
        assert sentinel in logging.getLogger().handlers

    def test_second_call_does_not_duplicate_handler(self):
        configure_logging(_Config())
        configure_logging(_Config())
        root = logging.getLogger()
        appkit_handlers = [
            h for h in root.handlers
            if isinstance(
                getattr(h, "formatter", None), structlog.stdlib.ProcessorFormatter
            )
        ]
        assert len(appkit_handlers) == 1

    def test_replaces_own_handler_on_reconfigure(self):
        configure_logging(_Config(log_format=LogFormat.TEXT))
        first_handler = next(
            h for h in logging.getLogger().handlers
            if isinstance(
                getattr(h, "formatter", None), structlog.stdlib.ProcessorFormatter
            )
        )
        configure_logging(_Config(log_format=LogFormat.JSON))
        second_handler = next(
            h for h in logging.getLogger().handlers
            if isinstance(
                getattr(h, "formatter", None), structlog.stdlib.ProcessorFormatter
            )
        )
        assert first_handler is not second_handler


class TestLogLevel:
    def test_sets_debug_level(self):
        configure_logging(_Config(log_level=LogLevel.DEBUG))
        assert logging.getLogger().level == logging.DEBUG

    def test_sets_warning_level(self):
        configure_logging(_Config(log_level=LogLevel.WARNING))
        assert logging.getLogger().level == logging.WARNING

    def test_sets_error_level(self):
        configure_logging(_Config(log_level=LogLevel.ERROR))
        assert logging.getLogger().level == logging.ERROR

    def test_sets_info_level(self):
        configure_logging(_Config(log_level=LogLevel.INFO))
        assert logging.getLogger().level == logging.INFO


class TestNoneLogFormat:
    def test_none_format_falls_back_to_text(self):
        # None is valid — configure_logging treats it as TEXT
        configure_logging(_Config(log_format=None))
        root = logging.getLogger()
        appkit_handlers = [
            h for h in root.handlers
            if isinstance(
                getattr(h, "formatter", None), structlog.stdlib.ProcessorFormatter
            )
        ]
        assert len(appkit_handlers) == 1


class TestStructlogReset:
    def test_reconfigure_resets_cached_loggers(self):
        configure_logging(_Config(log_format=LogFormat.TEXT))
        configure_logging(_Config(log_format=LogFormat.JSON))
        # After reset_defaults() + reconfigure, a fresh logger should work
        log = structlog.get_logger("test")
        # No assertion on format — just verify it doesn't raise
        assert log is not None
