# brian_appkit

Reusable Python library for config loading and structured logging. Designed to be
**vendored into other projects** via [ventwig](https://github.com/brian-pond/ventwig),
giving every CLI tool and daemon the same solid foundation without reinventing it each time.

One call — `bootstrap_app()` — validates your settings, wires up logging, and returns
both, ready to use.

---

## Install

**Via ventwig** (recommended for consumer projects):
```
ventwig add brian_appkit
```

**Via pip** (for direct use or editable dev):
```
pip install git+https://github.com/brian-pond/brian_appkit_config_py.git
```

**Dependencies** (installed automatically):
- `pydantic-settings >= 2.6`
- `platformdirs >= 4.3`
- `structlog >= 24.4`
- Python 3.11+

---

## Quick start

```python
import sys
from brian_appkit import AppEnv, ConfigurationError, XdgSettings, bootstrap_app
from pydantic import Field

class MySettings(XdgSettings):
    # Mandatory: no default — ConfigurationError if absent from all config sources
    database_url: str = Field(description="Postgres DSN")

    # Optional with range constraint
    worker_count: int = Field(default=4, ge=1, le=64)

    # Optional free-form
    api_key: str | None = Field(default=None)

def main() -> int:
    try:
        settings, log = bootstrap_app(MySettings, app_name="my-service")
    except ConfigurationError as exc:
        print(exc, file=sys.stderr)
        return 1

    log.info("started", workers=settings.worker_count, env=settings.app_env)
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

`settings` is a fully validated `MySettings` instance; `log` is a structlog
`BoundLogger` already configured and writing to stdout.

---

## Built-in environment variables

Every app using `bootstrap_app()` gets these fields — and their corresponding
environment variables — for free. No declaration needed in the subclass.

The prefix is derived from `app_name`: hyphens become underscores, everything
uppercased. For `app_name="my-service"` the prefix is `MY_SERVICE_`.

| Field | Type | Default | Env var | Notes |
|-------|------|---------|---------|-------|
| `app_env` | `AppEnv` | `"production"` | `MY_SERVICE_APP_ENV` | See auto log-format switching below |
| `log_format` | `LogFormat` | auto | `MY_SERVICE_LOG_FORMAT` | Auto-selected from `app_env` if not set |
| `log_level` | `LogLevel` | `"INFO"` | `MY_SERVICE_LOG_LEVEL` | |

### `app_env` values

| Value | Meaning |
|-------|---------|
| `development` | Local developer workstation |
| `staging` | Pre-production / QA environment |
| `production` | Live deployment (default) |

The default is `production` — the safe direction. A misconfigured or unset value
in a real deployment won't accidentally behave like a development environment.

### Auto log-format switching

When `log_format` is **not** explicitly configured (not set in env, `.env`, or
as an override kwarg), `bootstrap_app` selects the format automatically based on
`app_env`:

| `app_env` | Auto-selected `log_format` |
|-----------|---------------------------|
| `development` | `text` — colorized, human-readable |
| `staging` | `json` — structured, for aggregators |
| `production` | `json` — structured, for aggregators |

If you explicitly set `MY_SERVICE_LOG_FORMAT`, that value is always respected
regardless of `app_env`.

---

## Config precedence

Highest source wins. All layers use the same `KEY=VALUE` syntax.

| Priority | Source |
|----------|--------|
| 1 | Explicit kwargs: `bootstrap_app(MySettings, app_name="x", worker_count=8)` |
| 2 | Environment variables: `MY_SERVICE_WORKER_COUNT=8` |
| 3 | `.env` in the current working directory |
| 4 | `~/.config/my-service/.env` (XDG fallback; respects `$XDG_CONFIG_HOME`) |
| 5 | Field defaults declared on the settings class |

The env var prefix is derived from `app_name` automatically — hyphens become
underscores, everything uppercased. A daemon fed by a systemd `EnvironmentFile=`
never touches the XDG file at all; real env vars always win.

### Example: `.env` file format

```
MY_SERVICE_APP_ENV=development
MY_SERVICE_DATABASE_URL=postgresql://user:pass@localhost/mydb
MY_SERVICE_WORKER_COUNT=8
MY_SERVICE_LOG_LEVEL=DEBUG
```

---

## Nested config

Fields can be nested `pydantic.BaseModel` instances. Populate them from the
environment using `__` (double underscore) as the nesting delimiter:

```python
from pydantic import BaseModel

class DatabaseConfig(BaseModel):
    host: str
    port: int = 5432
    name: str

class MySettings(XdgSettings):
    database: DatabaseConfig
```

```
MY_SERVICE_DATABASE__HOST=db.internal
MY_SERVICE_DATABASE__PORT=5433
MY_SERVICE_DATABASE__NAME=mydb
```

---

## Logging

- **Always stdout** — never stderr or files. Container runtimes, systemd, and K8s own
  log collection; the app should not.
- **Format** — controlled by `log_format` / `MY_SERVICE_LOG_FORMAT` (or auto-selected
  from `app_env`):
  - `text` — colorized, human-readable console output (colors only when attached to a
    TTY; piped output is plain)
  - `json` — one JSON object per line, for log aggregators (Loki, ELK, Datadog,
    CloudWatch, etc.)
- **Level** — controlled by `log_level` / `MY_SERVICE_LOG_LEVEL`. Default: `INFO`.
- **Timestamps** — UTC ISO 8601, always.
- **Logger name** — included in every log line; use `structlog.get_logger(__name__)`
  in modules to identify the source component.
- **Exceptions** — rendered as a structured dict in JSON mode (queryable by aggregators)
  and as a human-readable traceback in text mode.
- **Call sites are format-agnostic** — `log.info("event", key=value)` is identical
  regardless of which renderer is active.

---

## API reference

### `XdgSettings`

Base class for app settings. Subclass this — do not subclass `BaseSettings` directly.

Built-in fields are documented in [Built-in environment variables](#built-in-environment-variables) above.

---

### `bootstrap_app(settings_cls, app_name, dump_config=False, **overrides) → (settings, log)`

The single entry point. Call once at startup.

| Parameter | Description |
|-----------|-------------|
| `settings_cls` | Your `XdgSettings` subclass (the class itself, not an instance) |
| `app_name` | Canonical app name, e.g. `"my-service"`. Drives env var prefix and XDG path. |
| `dump_config` | If `True`, logs all effective settings at `DEBUG` level after startup. Fields whose names contain `secret`, `password`, `token`, `key`, `credential`, or `auth` are automatically redacted. |
| `**overrides` | Optional field values; take highest precedence over all config sources. Must not collide with `dump_config`. |

Returns `(settings, log)` where `settings` is a fully validated instance of
`settings_cls` and `log` is a `structlog.stdlib.BoundLogger`.

Raises `ConfigurationError` if any mandatory field is absent or any value fails
type or range validation. The error message names each failing field and its
corresponding environment variable. Does **not** call `sys.exit()` — the caller
owns that decision.

Does **not** mutate `settings_cls` — safe to call multiple times (e.g., in tests).

---

### `ConfigurationError`

Raised by `bootstrap_app()` on validation failure. The message is pre-formatted
for human consumption — field names, plain-English descriptions, and the
corresponding env var are all included. Catch it at the application boundary:

```python
try:
    settings, log = bootstrap_app(MySettings, app_name="my-service")
except ConfigurationError as exc:
    print(exc, file=sys.stderr)
    sys.exit(1)
```

---

### `AppEnv`

```python
class AppEnv(StrEnum):
    DEVELOPMENT = "development"
    STAGING     = "staging"
    PRODUCTION  = "production"
```

---

### `LogFormat`

```python
class LogFormat(StrEnum):
    TEXT = "text"
    JSON = "json"
```

---

### `LogLevel`

```python
class LogLevel(StrEnum):
    DEBUG    = "DEBUG"
    INFO     = "INFO"
    WARNING  = "WARNING"
    ERROR    = "ERROR"
    CRITICAL = "CRITICAL"
```

---

### `configure_logging(settings)`

Lower-level function used internally by `bootstrap_app`. Available directly if you
need to call it independently. Accepts any object with `log_format: LogFormat` and
`log_level: LogLevel` attributes.

---

## Vendoring

Every module in `src/brian_appkit/` carries this header:

```python
# VENDORED — part of brian_appkit (github.com/brian-pond/brian_appkit_config_py)
# Placed here by ventwig (github.com/brian-pond/ventwig). Edit at source, not in consumer projects.
```

When ventwig copies files into a consumer project, that header travels with them.
It tells any developer who opens the file: this is not local code, do not edit it
here, find the source and change it there.

---

## Development

```
# Install dev dependencies (includes ruff and pytest)
pip install -e ".[dev]"

# Run tests
pytest tests/

# Lint
ruff check src/ examples/
ruff format src/ examples/

# Run examples (with deps installed)
MY_SERVICE_APP_ENV=development PYTHONPATH=src python3 examples/foo_main.py
```

Ruff configuration is in `pyproject.toml` under `[tool.ruff]`.
