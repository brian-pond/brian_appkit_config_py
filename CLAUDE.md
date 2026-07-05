# brian_appkit — Claude Rules

## Purpose

This is a reusable Python library for config loading and logging bootstrap.
It is designed to be **vendored into other projects** using
[ventwig](https://github.com/brian-pond/ventwig), not imported as a PyPI package.

---

## Vendoring notice — mandatory in every Python file

Every Python module under `src/brian_appkit/` **must** begin with these two comment lines,
before any docstring or imports:

```python
# VENDORED — part of brian_appkit (github.com/brian-pond/brian_appkit_config_py)
# Placed here by ventwig (github.com/brian-pond/ventwig). Edit at source, not in consumer projects.
```

This applies to new files too. When creating any `.py` file inside `src/brian_appkit/`,
add this header first, unconditionally.

---

## Package structure rules

- Library code lives in `src/brian_appkit/`. Internal modules use a `_` prefix (`_types.py`, `_logging.py`).
- Consumer-facing templates live in `examples/`. Never put template or demo code in `src/brian_appkit/`.
- `__init__.py` controls the public API. Exported names: `XdgSettings`, `bootstrap_app`,
  `AppEnv`, `ConfigurationError`, `LogFormat`, `LogLevel`, `configure_logging`.
  Do not export internal modules.

## API rules

- `bootstrap_app()` must never mutate `settings_cls`. Use a throwaway `type()` subclass.
- `configure_logging()` accepts a structural `Protocol` (`_LoggingConfig`), not a concrete class.
- `XdgSettings` is the only public base class. Do not add a second base class without discussion.

## Linting

Run `ruff check src/ examples/` before committing. Configuration is in `pyproject.toml`.
Fix all ruff errors; do not add `# noqa` suppressions without a clear written reason.
