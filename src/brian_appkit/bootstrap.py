# VENDORED — part of brian_appkit (github.com/brian-pond/brian_appkit_config_py)
# Placed here by ventwig (github.com/brian-pond/ventwig). Edit at source, not in consumer projects.

"""
bootstrap.py — single entry point for every new app.

Usage:
    from brian_appkit import XdgSettings, bootstrap_app
    from pydantic import Field

    class MySettings(XdgSettings):
        database_url: str = Field(...)                    # mandatory
        worker_count: int = Field(default=4, ge=1, le=64) # optional, ranged

    settings, log = bootstrap_app(MySettings, app_name="my-service")
    log.info("started", workers=settings.worker_count)

Config precedence (highest wins):
    1. Explicit kwargs passed to bootstrap_app(..., key=value)
    2. Environment variables, e.g. MY_SERVICE_DATABASE_URL
    3. .env in the current working directory
    4. ~/.config/my-service/.env  (XDG fallback; respects $XDG_CONFIG_HOME)
    5. Field defaults
"""

from pathlib import Path
from typing import Any, TypeVar

import structlog
from platformdirs import user_config_dir
from pydantic import ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ._logging import configure_logging
from ._types import AppEnv, ConfigurationError, LogFormat, LogLevel

T = TypeVar("T", bound="XdgSettings")

# Field names containing any of these substrings are redacted in config dumps.
# Keeps secrets out of log output without requiring callers to mark every field.
_SENSITIVE_SUBSTRINGS = frozenset(
    {"secret", "password", "passwd", "token", "key", "credential", "auth"}
)


def _is_sensitive(field_name: str) -> bool:
    lower = field_name.lower()
    return any(sub in lower for sub in _SENSITIVE_SUBSTRINGS)


def _redact(value: object, key: str) -> object:
    if _is_sensitive(key):
        return "***"
    if isinstance(value, dict):
        return {k: _redact(v, k) for k, v in value.items()}
    return value


def _dump_effective_config(
    settings: "XdgSettings", log: structlog.stdlib.BoundLogger, prefix: str
) -> None:
    redacted = {k: _redact(v, k) for k, v in settings.model_dump().items()}
    log.debug("effective configuration", env_prefix=prefix[:-1], **redacted)


class XdgSettings(BaseSettings):
    """Base class for app settings. Subclass this, declare your fields,
    pass the subclass to bootstrap_app().
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        env_nested_delimiter="__",
    )

    app_env: AppEnv = AppEnv.PRODUCTION
    log_format: LogFormat | None = None
    log_level: LogLevel = LogLevel.INFO

    @field_validator("app_env", "log_format", mode="before")
    @classmethod
    def _normalize_lowercase(cls, v: object) -> object:
        if isinstance(v, str):
            return v.lower()
        return v

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, v: object) -> object:
        if isinstance(v, str):
            return v.upper()
        return v


def bootstrap_app(
    settings_cls: type[T],
    app_name: str,
    dump_config: bool = False,
    **overrides: Any,
) -> tuple[T, structlog.stdlib.BoundLogger]:
    """Validate config and wire up logging in one call.

    Returns (settings, log) — both ready to use immediately.
    Does not mutate settings_cls; creates a throwaway subclass internally.
    Raises ConfigurationError (not sys.exit) on validation failure so the
    caller controls the error boundary.

    dump_config: if True, logs all effective settings at DEBUG level after
        startup. Fields whose names contain 'secret', 'password', 'token',
        'key', 'credential', or 'auth' are automatically redacted.
        Note: dump_config is consumed here and must not match a settings field
        name; pass such overrides via environment variable instead.
    """
    xdg_fallback = str(Path(user_config_dir(app_name)) / ".env")
    prefix = f"{app_name.upper().replace('-', '_')}_"

    patched_config = SettingsConfigDict(
        **{
            **settings_cls.model_config,
            "env_prefix": prefix,
            "env_file": (xdg_fallback, ".env"),
        }
    )
    ephemeral_cls = type(settings_cls.__name__, (settings_cls,), {"model_config": patched_config})

    try:
        settings: T = ephemeral_cls(**overrides)
    except ValidationError as exc:
        lines = [f"Configuration error — {settings_cls.__name__}:"]
        for error in exc.errors():
            field = ".".join(str(part) for part in error["loc"])
            env_var = f"{prefix}{'__'.join(str(part) for part in error['loc']).upper()}"
            lines.append(f"  {field}: {error['msg']}  [{env_var}]")
        raise ConfigurationError("\n".join(lines)) from exc
    # None means the caller did not explicitly configure log_format. Auto-select
    # from app_env: DEVELOPMENT gets human-readable TEXT; all other envs get
    # machine-parseable JSON for log aggregators.
    if settings.log_format is None:
        auto_format = LogFormat.TEXT if settings.app_env is AppEnv.DEVELOPMENT else LogFormat.JSON
        settings = settings.model_copy(update={"log_format": auto_format})

    configure_logging(settings)
    log = structlog.get_logger(app_name)
    if dump_config:
        _dump_effective_config(settings, log, prefix)
    return settings, log
