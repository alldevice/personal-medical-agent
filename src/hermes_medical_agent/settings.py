from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_ENV_FILE = Path("/srv/hermes-medical/config/.env")


class Settings(BaseSettings):
    medical_data_dir: Path = Path("/srv/hermes-medical/data")
    medical_db_path: Path = Path("/srv/hermes-medical/data/db/medical.sqlite")

    # Optional provider keys are not needed for basic ingest/timeline CLI.
    # They are reserved for future extraction/retrieval helpers if the Hermes profile
    # chooses to call this package directly instead of using existing Hermes credentials.
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    model_config = SettingsConfigDict(env_file=None, extra="ignore")


def load_settings(env_file: Path | None = None) -> Settings:
    selected_env = env_file or Path(os.environ.get("MEDICAL_AGENT_ENV_FILE", DEFAULT_ENV_FILE))
    if selected_env.exists():
        load_dotenv(selected_env, override=False)
    return Settings()
