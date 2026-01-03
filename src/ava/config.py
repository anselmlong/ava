from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


REQUIRED_ENV_VARS = [
    "TELEGRAM_BOT_TOKEN",
    "DATABASE_URL",
]


@dataclass
class AppConfig:
    telegram_bot_token: str
    database_url: str
    gemini_api_key: Optional[str] = None
    google_credentials_path: Optional[str] = None
    env: str = "development"

    @classmethod
    def from_env(cls) -> "AppConfig":
        missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
        if missing:
            raise RuntimeError(
                f"Missing required environment variables: {', '.join(missing)}"
            )

        return cls(
            telegram_bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
            database_url=os.environ["DATABASE_URL"],
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
            google_credentials_path=os.getenv("GOOGLE_CREDENTIALS_PATH"),
            env=os.getenv("AVA_ENV", "development"),
        )


def load_config() -> AppConfig:
    """Load application configuration from environment variables.

    This helper is a convenient single entrypoint used by the rest of the app.
    """

    return AppConfig.from_env()
