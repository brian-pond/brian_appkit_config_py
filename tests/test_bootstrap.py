"""Tests for XdgSettings and bootstrap_app."""

import logging

import pytest
import structlog
from pydantic import BaseModel, Field, ValidationError

from brian_appkit import (
    AppEnv,
    ConfigurationError,
    LogFormat,
    LogLevel,
    XdgSettings,
    bootstrap_app,
)
from brian_appkit.bootstrap import _dump_effective_config


# ── Settings fixtures used across tests ──────────────────────────────────────

class _Minimal(XdgSettings):
    pass


class _WithRequired(XdgSettings):
    required_field: str


class _DBConfig(BaseModel):
    host: str
    password: str = "default_pass"


class _WithNested(XdgSettings):
    db: _DBConfig


class _WithSecrets(XdgSettings):
    api_key: str | None = Field(default=None)
    db_password: str | None = Field(default=None)
    normal_field: str = "hello"


# ── XdgSettings defaults ──────────────────────────────────────────────────────

class TestXdgSettingsDefaults:
    def test_default_app_env(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        s = _Minimal()
        assert s.app_env is AppEnv.PRODUCTION

    def test_default_log_format_is_none(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        s = _Minimal()
        assert s.log_format is None

    def test_default_log_level(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        s = _Minimal()
        assert s.log_level is LogLevel.INFO


# ── Case normalization ────────────────────────────────────────────────────────

class TestCaseNormalization:
    def test_log_level_lowercase_accepted(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("TEST_APP_LOG_LEVEL", "debug")
        settings, _ = bootstrap_app(_Minimal, app_name="test-app")
        assert settings.log_level is LogLevel.DEBUG

    def test_log_level_mixed_case_accepted(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("TEST_APP_LOG_LEVEL", "Warning")
        settings, _ = bootstrap_app(_Minimal, app_name="test-app")
        assert settings.log_level is LogLevel.WARNING

    def test_app_env_uppercase_accepted(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("TEST_APP_APP_ENV", "DEVELOPMENT")
        settings, _ = bootstrap_app(_Minimal, app_name="test-app")
        assert settings.app_env is AppEnv.DEVELOPMENT

    def test_app_env_mixed_case_accepted(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("TEST_APP_APP_ENV", "Staging")
        settings, _ = bootstrap_app(_Minimal, app_name="test-app")
        assert settings.app_env is AppEnv.STAGING

    def test_log_format_uppercase_accepted(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("TEST_APP_LOG_FORMAT", "JSON")
        settings, _ = bootstrap_app(_Minimal, app_name="test-app")
        assert settings.log_format is LogFormat.JSON

    def test_log_format_mixed_case_accepted(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("TEST_APP_LOG_FORMAT", "Text")
        settings, _ = bootstrap_app(_Minimal, app_name="test-app")
        assert settings.log_format is LogFormat.TEXT


# ── bootstrap_app: return values ──────────────────────────────────────────────

class TestBootstrapAppReturnValues:
    def test_returns_settings_instance(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        settings, _ = bootstrap_app(_Minimal, app_name="test-app")
        assert isinstance(settings, _Minimal)

    def test_returns_logger(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _, log = bootstrap_app(_Minimal, app_name="test-app")
        assert log is not None

    def test_does_not_mutate_settings_cls(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        original_config = dict(_Minimal.model_config)
        bootstrap_app(_Minimal, app_name="test-app")
        assert dict(_Minimal.model_config) == original_config

    def test_returned_settings_is_instance_of_cls(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        settings, _ = bootstrap_app(_Minimal, app_name="test-app")
        assert isinstance(settings, _Minimal)


# ── bootstrap_app: ConfigurationError ────────────────────────────────────────

class TestConfigurationError:
    def test_missing_required_field_raises(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ConfigurationError):
            bootstrap_app(_WithRequired, app_name="test-app")

    def test_error_is_not_validation_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ConfigurationError):
            bootstrap_app(_WithRequired, app_name="test-app")

    def test_error_chained_from_validation_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ConfigurationError) as exc_info:
            bootstrap_app(_WithRequired, app_name="test-app")
        assert isinstance(exc_info.value.__cause__, ValidationError)

    def test_error_message_contains_field_name(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ConfigurationError) as exc_info:
            bootstrap_app(_WithRequired, app_name="test-app")
        assert "required_field" in str(exc_info.value)

    def test_error_message_contains_flat_env_var(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ConfigurationError) as exc_info:
            bootstrap_app(_WithRequired, app_name="test-app")
        assert "TEST_APP_REQUIRED_FIELD" in str(exc_info.value)

    def test_error_message_nested_field_uses_double_underscore(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # Provide db={} so pydantic validates the sub-model and reports
        # loc=("db", "host") — an absent outer field gives loc=("db",) only.
        with pytest.raises(ConfigurationError) as exc_info:
            bootstrap_app(_WithNested, app_name="test-app", db={})
        assert "TEST_APP_DB__HOST" in str(exc_info.value)

    def test_error_message_nested_field_no_dot(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ConfigurationError) as exc_info:
            bootstrap_app(_WithNested, app_name="test-app", db={})
        # Dot notation is wrong — double underscore is correct
        assert "DB.HOST" not in str(exc_info.value)


# ── bootstrap_app: env var prefix ────────────────────────────────────────────

class TestEnvVarPrefix:
    def test_hyphen_becomes_underscore(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("MY_SERVICE_LOG_LEVEL", "DEBUG")
        settings, _ = bootstrap_app(_Minimal, app_name="my-service")
        assert settings.log_level is LogLevel.DEBUG

    def test_prefix_is_uppercased(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("MYAPP_LOG_LEVEL", "WARNING")
        settings, _ = bootstrap_app(_Minimal, app_name="myapp")
        assert settings.log_level is LogLevel.WARNING

    def test_unprefixed_env_var_ignored(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        settings, _ = bootstrap_app(_Minimal, app_name="test-app")
        assert settings.log_level is LogLevel.INFO  # default, not overridden


# ── bootstrap_app: config precedence ─────────────────────────────────────────

class TestConfigPrecedence:
    def test_override_kwarg_beats_env_var(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("TEST_APP_LOG_LEVEL", "ERROR")
        settings, _ = bootstrap_app(_Minimal, app_name="test-app", log_level=LogLevel.DEBUG)
        assert settings.log_level is LogLevel.DEBUG

    def test_env_var_beats_default(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("TEST_APP_LOG_LEVEL", "WARNING")
        settings, _ = bootstrap_app(_Minimal, app_name="test-app")
        assert settings.log_level is LogLevel.WARNING

    def test_dotenv_file_loaded(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text("TEST_APP_LOG_LEVEL=ERROR\n")
        settings, _ = bootstrap_app(_Minimal, app_name="test-app")
        assert settings.log_level is LogLevel.ERROR

    def test_env_var_beats_dotenv(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text("TEST_APP_LOG_LEVEL=ERROR\n")
        monkeypatch.setenv("TEST_APP_LOG_LEVEL", "WARNING")
        settings, _ = bootstrap_app(_Minimal, app_name="test-app")
        assert settings.log_level is LogLevel.WARNING


# ── bootstrap_app: auto log format selection ──────────────────────────────────

class TestAutoLogFormat:
    def test_development_gets_text(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        settings, _ = bootstrap_app(_Minimal, app_name="test-app", app_env=AppEnv.DEVELOPMENT)
        assert settings.log_format is LogFormat.TEXT

    def test_production_gets_json(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        settings, _ = bootstrap_app(_Minimal, app_name="test-app", app_env=AppEnv.PRODUCTION)
        assert settings.log_format is LogFormat.JSON

    def test_staging_gets_json(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        settings, _ = bootstrap_app(_Minimal, app_name="test-app", app_env=AppEnv.STAGING)
        assert settings.log_format is LogFormat.JSON

    def test_explicit_log_format_overrides_auto(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        settings, _ = bootstrap_app(
            _Minimal, app_name="test-app",
            app_env=AppEnv.PRODUCTION, log_format=LogFormat.TEXT,
        )
        assert settings.log_format is LogFormat.TEXT

    def test_default_app_env_production_gives_json(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        settings, _ = bootstrap_app(_Minimal, app_name="test-app")
        assert settings.log_format is LogFormat.JSON


# ── bootstrap_app: dump_config ────────────────────────────────────────────────

class TestDumpConfig:
    def test_dump_config_true_runs_without_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        bootstrap_app(_Minimal, app_name="test-app", dump_config=True, log_level=LogLevel.DEBUG)

    def test_dump_config_false_runs_without_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        bootstrap_app(_Minimal, app_name="test-app", dump_config=False)

    def test_dump_effective_config_redacts_top_level_sensitive(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        settings, _ = bootstrap_app(
            _WithSecrets, app_name="test-app", api_key="supersecret",
        )
        with structlog.testing.capture_logs() as cap:
            _dump_effective_config(settings, structlog.get_logger("test"), "TEST_APP_")
        events = [e for e in cap if e.get("event") == "effective configuration"]
        assert len(events) == 1
        assert events[0]["api_key"] == "***"
        assert events[0]["normal_field"] == "hello"

    def test_dump_effective_config_redacts_nested_sensitive(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        settings, _ = bootstrap_app(
            _WithNested, app_name="test-app", db={"host": "db.internal", "password": "hunter2"},
        )
        with structlog.testing.capture_logs() as cap:
            _dump_effective_config(settings, structlog.get_logger("test"), "TEST_APP_")
        events = [e for e in cap if e.get("event") == "effective configuration"]
        assert len(events) == 1
        assert events[0]["db"]["password"] == "***"
        assert events[0]["db"]["host"] == "db.internal"

    def test_dump_effective_config_includes_env_prefix(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        settings, _ = bootstrap_app(_Minimal, app_name="test-app")
        with structlog.testing.capture_logs() as cap:
            _dump_effective_config(settings, structlog.get_logger("test"), "TEST_APP_")
        events = [e for e in cap if e.get("event") == "effective configuration"]
        assert events[0]["env_prefix"] == "TEST_APP"


# ── bootstrap_app: reconfiguration ───────────────────────────────────────────

class TestReconfiguration:
    def test_second_call_does_not_accumulate_handlers(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        bootstrap_app(_Minimal, app_name="test-app")
        bootstrap_app(_Minimal, app_name="test-app")
        root = logging.getLogger()
        appkit_handlers = [
            h for h in root.handlers
            if isinstance(
                getattr(h, "formatter", None), structlog.stdlib.ProcessorFormatter
            )
        ]
        assert len(appkit_handlers) == 1

    def test_reconfigure_changes_log_level(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        bootstrap_app(_Minimal, app_name="test-app", log_level=LogLevel.WARNING)
        assert logging.getLogger().level == logging.WARNING
        bootstrap_app(_Minimal, app_name="test-app", log_level=LogLevel.DEBUG)
        assert logging.getLogger().level == logging.DEBUG


# ── XDG directory properties ──────────────────────────────────────────────────

class TestXdgDirs:
    def test_app_name_set_on_settings(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        settings, _ = bootstrap_app(_Minimal, app_name="test-app")
        assert settings.app_name == "test-app"

    def test_config_dir_contains_app_name(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        settings, _ = bootstrap_app(_Minimal, app_name="test-app")
        assert "test-app" in str(settings.config_dir)

    def test_data_dir_contains_app_name(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        settings, _ = bootstrap_app(_Minimal, app_name="test-app")
        assert "test-app" in str(settings.data_dir)

    def test_cache_dir_contains_app_name(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        settings, _ = bootstrap_app(_Minimal, app_name="test-app")
        assert "test-app" in str(settings.cache_dir)

    def test_runtime_dir_contains_app_name(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        settings, _ = bootstrap_app(_Minimal, app_name="test-app")
        assert "test-app" in str(settings.runtime_dir)

    def test_dirs_return_path_objects(self, tmp_path, monkeypatch):
        from pathlib import Path
        monkeypatch.chdir(tmp_path)
        settings, _ = bootstrap_app(_Minimal, app_name="test-app")
        assert isinstance(settings.config_dir, Path)
        assert isinstance(settings.data_dir, Path)
        assert isinstance(settings.cache_dir, Path)
        assert isinstance(settings.runtime_dir, Path)

    def test_dirs_differ_from_each_other(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        settings, _ = bootstrap_app(_Minimal, app_name="test-app")
        dirs = [settings.config_dir, settings.data_dir, settings.cache_dir, settings.runtime_dir]
        assert len(set(dirs)) == len(dirs)
