"""Application settings, read from environment variables (or a local .env file)."""

import os
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
ROOT_DIR = BASE_DIR.parent  # repository root


def _load_dotenv() -> None:
    """Minimal .env loader so local development needs no extra package."""
    for candidate in (ROOT_DIR / ".env", BASE_DIR / ".env"):
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.database_url: str = self._normalize_db_url(
            os.getenv("DATABASE_URL") or f"sqlite:///{BASE_DIR / 'dev.db'}"
        )
        self.secret_key: str = os.getenv("SECRET_KEY", "dev-only-change-me")
        self.app_url: str = os.getenv("APP_URL", "http://localhost:8000").rstrip("/")
        self.vapid_public_key: str = os.getenv("VAPID_PUBLIC_KEY", "")
        self.vapid_private_key: str = os.getenv("VAPID_PRIVATE_KEY", "")
        self.vapid_subject: str = os.getenv("VAPID_SUBJECT", "mailto:admin@example.com")
        self.admin_emails: set[str] = {
            e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()
        }
        self.frontend_dir: Path = Path(os.getenv("FRONTEND_DIR", ROOT_DIR / "frontend"))
        self.session_days: int = int(os.getenv("SESSION_DAYS", "30"))
        self.dictionary_api: str = os.getenv(
            "DICTIONARY_API", "https://api.dictionaryapi.dev/api/v2/entries/en/"
        )

    @property
    def secure_cookies(self) -> bool:
        return self.app_url.startswith("https://")

    @staticmethod
    def _normalize_db_url(url: str) -> str:
        # Neon / Heroku style URLs -> SQLAlchemy psycopg3 driver
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
