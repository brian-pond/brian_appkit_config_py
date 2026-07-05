"""
Template: define your app's settings by subclassing XdgSettings.
Copy into your project, rename the class, and add your fields.
"""

from pydantic import Field

from brian_appkit import XdgSettings


class FooSettings(XdgSettings):
    # Mandatory: no default — ValidationError names this field if absent
    database_url: str = Field(description="Postgres DSN, e.g. postgresql://user:pass@host/db")

    # Optional with range constraint
    worker_count: int = Field(default=4, ge=1, le=64)

    # Optional free-form
    api_key: str | None = Field(default=None)
