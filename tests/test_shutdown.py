"""Tests for graceful shutdown (signal handling) and unhandled exception logging."""

import signal
import sys
import threading

import structlog.testing

from brian_appkit import XdgSettings, bootstrap_app


class _Minimal(XdgSettings):
    pass


# ── shutdown_event property ───────────────────────────────────────────────────

class TestShutdownEvent:
    def test_shutdown_event_is_threading_event(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        settings, _ = bootstrap_app(_Minimal, app_name="test-app")
        assert isinstance(settings.shutdown_event, threading.Event)

    def test_shutdown_event_initially_clear(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        settings, _ = bootstrap_app(_Minimal, app_name="test-app")
        assert not settings.shutdown_event.is_set()

    def test_sigterm_sets_shutdown_event(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        settings, _ = bootstrap_app(_Minimal, app_name="test-app")
        signal.raise_signal(signal.SIGTERM)
        assert settings.shutdown_event.is_set()

    def test_sigint_sets_shutdown_event(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        settings, _ = bootstrap_app(_Minimal, app_name="test-app")
        signal.raise_signal(signal.SIGINT)
        assert settings.shutdown_event.is_set()

    def test_signal_logs_signal_name(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        settings, _ = bootstrap_app(_Minimal, app_name="test-app")
        with structlog.testing.capture_logs() as cap:
            signal.raise_signal(signal.SIGTERM)
        events = [e for e in cap if e.get("event") == "shutdown signal received"]
        assert events
        assert events[0]["signal"] == "SIGTERM"

    def test_handle_signals_false_skips_handler_installation(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        original_sigterm = signal.getsignal(signal.SIGTERM)
        bootstrap_app(_Minimal, app_name="test-app", handle_signals=False)
        assert signal.getsignal(signal.SIGTERM) is original_sigterm

    def test_no_signal_handlers_installed_when_disabled(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        original_sigint = signal.getsignal(signal.SIGINT)
        bootstrap_app(_Minimal, app_name="test-app", handle_signals=False)
        assert signal.getsignal(signal.SIGINT) is original_sigint


# ── excepthook ────────────────────────────────────────────────────────────────

class TestExcepthook:
    def test_excepthook_is_replaced(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        bootstrap_app(_Minimal, app_name="test-app")
        assert sys.excepthook is not sys.__excepthook__

    def test_handle_signals_false_leaves_excepthook(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        original = sys.excepthook
        bootstrap_app(_Minimal, app_name="test-app", handle_signals=False)
        assert sys.excepthook is original

    def test_unhandled_exception_logged_as_critical(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        bootstrap_app(_Minimal, app_name="test-app")
        with structlog.testing.capture_logs() as cap:
            try:
                raise RuntimeError("boom")
            except RuntimeError:
                exc_type, exc_value, exc_tb = sys.exc_info()
                sys.excepthook(exc_type, exc_value, exc_tb)
        events = [e for e in cap if e.get("event") == "unhandled exception"]
        assert events, "Expected an 'unhandled exception' log event"
        assert events[0]["log_level"] == "critical"

    def test_keyboard_interrupt_delegates_to_default_hook(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        bootstrap_app(_Minimal, app_name="test-app")
        called = []
        monkeypatch.setattr(sys, "__excepthook__", lambda *a: called.append(a))
        try:
            raise KeyboardInterrupt
        except KeyboardInterrupt:
            exc_type, exc_value, exc_tb = sys.exc_info()
            sys.excepthook(exc_type, exc_value, exc_tb)
        assert called, "Expected __excepthook__ to be called for KeyboardInterrupt"
