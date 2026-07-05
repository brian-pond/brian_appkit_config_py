import logging

import pytest
import structlog


@pytest.fixture(autouse=True)
def restore_logging():
    """Restore root logger and structlog state after every test.

    configure_logging() mutates global state (root logger handlers, structlog
    config). Without this fixture, state leaks between tests and the order
    of execution affects results.
    """
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    yield
    root.handlers = original_handlers
    root.setLevel(original_level)
    structlog.reset_defaults()
