from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    telegram_bot_token: str
    allowed_telegram_user_ids: str = ""
    medical_data_dir: Path = Path("/medical/data")
    medical_db_path: Path = Path("/medical/data/db/medical.sqlite")
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    @property
    def allowed_user_ids(self) -> set[int]:
        values: set[int] = set()
        for raw in self.allowed_telegram_user_ids.split(","):
            raw = raw.strip()
            if raw:
                values.add(int(raw))
        return values


def load_settings() -> Settings:
    return Settings()
