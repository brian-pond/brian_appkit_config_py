"""
Template: minimal entrypoint for a CLI app or daemon using brian_appkit.
"""
import sys

from foo_settings import FooSettings  # adjust to your project's import path

from brian_appkit import ConfigurationError, bootstrap_app


def main() -> int:
    # ConfigurationError is raised (not sys.exit'd) by bootstrap_app so that
    # application code — not library code — owns the decision to exit.
    # Print the pre-formatted message and return a non-zero code here.
    try:
        settings, log = bootstrap_app(FooSettings, app_name="foo")
    except ConfigurationError as exc:
        print(exc, file=sys.stderr)
        return 1

    log.info("started", workers=settings.worker_count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
