"""Tests for _types.py enums and ConfigurationError, and the private
redaction helpers in bootstrap.py."""

import pytest

from brian_appkit import AppEnv, ConfigurationError, LogFormat, LogLevel
from brian_appkit.bootstrap import _is_sensitive, _redact


class TestIsSensitive:
    def test_password(self):
        assert _is_sensitive("password") is True

    def test_api_key(self):
        assert _is_sensitive("api_key") is True

    def test_secret(self):
        assert _is_sensitive("secret") is True

    def test_token(self):
        assert _is_sensitive("access_token") is True

    def test_credential(self):
        assert _is_sensitive("credential") is True

    def test_auth(self):
        assert _is_sensitive("auth_header") is True

    def test_passwd(self):
        assert _is_sensitive("passwd") is True

    def test_compound_sensitive(self):
        assert _is_sensitive("db_password") is True
        assert _is_sensitive("secret_key") is True

    def test_case_insensitive(self):
        assert _is_sensitive("PASSWORD") is True
        assert _is_sensitive("API_KEY") is True
        assert _is_sensitive("Auth_Token") is True

    def test_non_sensitive(self):
        assert _is_sensitive("database_url") is False
        assert _is_sensitive("worker_count") is False
        assert _is_sensitive("host") is False
        assert _is_sensitive("port") is False
        assert _is_sensitive("app_env") is False


class TestRedact:
    def test_sensitive_top_level_redacted(self):
        assert _redact("hunter2", "password") == "***"

    def test_non_sensitive_top_level_passthrough(self):
        assert _redact("localhost", "host") == "localhost"
        assert _redact(5432, "port") == 5432

    def test_nested_dict_sensitive_key_redacted(self):
        result = _redact({"host": "db.internal", "password": "secret"}, "database")
        assert result == {"host": "db.internal", "password": "***"}

    def test_nested_dict_non_sensitive_passthrough(self):
        result = _redact({"host": "db.internal", "port": 5432}, "database")
        assert result == {"host": "db.internal", "port": 5432}

    def test_deeply_nested_redaction(self):
        value = {"inner": {"api_key": "abc123", "name": "test"}}
        result = _redact(value, "config")
        assert result == {"inner": {"api_key": "***", "name": "test"}}

    def test_top_level_sensitive_dict_fully_redacted(self):
        # If the top-level key is sensitive, the entire value is replaced
        result = _redact({"host": "db", "port": 5432}, "secret_config")
        assert result == "***"

    def test_non_dict_non_sensitive_passthrough(self):
        assert _redact(42, "count") == 42
        assert _redact(None, "optional") is None
        assert _redact(["a", "b"], "items") == ["a", "b"]


class TestConfigurationError:
    def test_is_exception(self):
        assert issubclass(ConfigurationError, Exception)

    def test_message_preserved(self):
        err = ConfigurationError("something went wrong")
        assert str(err) == "something went wrong"

    def test_catchable_as_exception(self):
        with pytest.raises(Exception):
            raise ConfigurationError("test")


class TestAppEnv:
    def test_values_are_lowercase(self):
        assert AppEnv.DEVELOPMENT == "development"
        assert AppEnv.STAGING == "staging"
        assert AppEnv.PRODUCTION == "production"

    def test_is_str(self):
        assert isinstance(AppEnv.PRODUCTION, str)


class TestLogFormat:
    def test_values(self):
        assert LogFormat.TEXT == "text"
        assert LogFormat.JSON == "json"

    def test_is_str(self):
        assert isinstance(LogFormat.JSON, str)


class TestLogLevel:
    def test_values_are_uppercase(self):
        assert LogLevel.DEBUG == "DEBUG"
        assert LogLevel.INFO == "INFO"
        assert LogLevel.WARNING == "WARNING"
        assert LogLevel.ERROR == "ERROR"
        assert LogLevel.CRITICAL == "CRITICAL"

    def test_is_str(self):
        assert isinstance(LogLevel.INFO, str)
