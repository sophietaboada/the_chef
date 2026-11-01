"""Runtime configuration, read from environment variables (and an optional .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader so we don't need an extra dependency. Never overrides real env vars."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    db_path: str
    model: str
    ai_enabled: bool
    secure_cookies: bool
    allow_signup: bool
    spoonacular_key: str | None = None
    session_days: int = 30

    @classmethod
    def from_env(cls) -> "Settings":
        _load_dotenv(ROOT / ".env")
        return cls(
            db_path=os.environ.get("THECHEF_DB_PATH", str(ROOT / "data" / "thechef.db")),
            model=os.environ.get("THECHEF_MODEL", "claude-opus-5-5"),
            ai_enabled=bool(
                os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
            ),
            secure_cookies=_bool("THECHEF_SECURE_COOKIES", False),
            allow_signup=_bool("THECHEF_ALLOW_SIGNUP", True),
            spoonacular_key=os.environ.get("SPOONACULAR_API_KEY") or None,
        )
