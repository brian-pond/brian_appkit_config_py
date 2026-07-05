import logging
import signal
import sys

import pytest
import structlog


@pytest.fixture(autouse=True)
def restore_globals():
    """Restore global state mutated by bootstrap_app() after every test.

    Covers: root logger handlers/level, structlog config, sys.excepthook,
    and SIGTERM/SIGINT signal handlers.
    """
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    original_excepthook = sys.excepthook
    original_sigterm = signal.getsignal(signal.SIGTERM)
    original_sigint = signal.getsignal(signal.SIGINT)
    yield
    root.handlers = original_handlers
    root.setLevel(original_level)
    structlog.reset_defaults()
    sys.excepthook = original_excepthook
    signal.signal(signal.SIGTERM, original_sigterm)
    signal.signal(signal.SIGINT, original_sigint)
