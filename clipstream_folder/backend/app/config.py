"""Settings, read from environment variables or from backend/.env when running locally.

In Azure, the same names are set in App Service → Configuration, so no .env file is needed there.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


@dataclass(frozen=True)
class Settings:
    cosmos_uri: str | None
    cosmos_key: str | None
    cosmos_database: str
    storage_account: str | None
    storage_key: str | None
    raw_container: str
    converted_container: str

    @property
    def use_cosmos(self) -> bool:
        return bool(self.cosmos_uri and self.cosmos_key)

    @property
    def use_blob(self) -> bool:
        return bool(self.storage_account and self.storage_key)


def load_settings() -> Settings:
    env = os.getenv
    return Settings(
        cosmos_uri=env("COSMOS_URI"),
        cosmos_key=env("COSMOS_KEY"),
        cosmos_database=env("COSMOS_DATABASE", "SharedDB"),
        storage_account=env("AZURE_STORAGE_ACCOUNT"),
        storage_key=env("AZURE_STORAGE_KEY"),
        raw_container=env("RAW_CONTAINER", "raw-uploads"),
        converted_container=env("CONVERTED_CONTAINER", "converted-videos"),
    )


def offline_settings() -> Settings:
    """No Azure at all. Used by the tests so they never touch real services."""
    return Settings(
        cosmos_uri=None,
        cosmos_key=None,
        cosmos_database="SharedDB",
        storage_account=None,
        storage_key=None,
        raw_container="raw-uploads",
        converted_container="converted-videos",
    )
