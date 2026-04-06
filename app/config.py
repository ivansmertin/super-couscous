from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_telegram_id: int
    sqlite_path: str
    log_level: str



def load_settings() -> Settings:
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    admin_id_raw = os.getenv("ADMIN_TELEGRAM_ID", "").strip()
    sqlite_path = os.getenv("SQLITE_PATH", "./data/bot.db").strip()
    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()

    if not bot_token:
        raise ValueError("BOT_TOKEN is required")
    if not admin_id_raw:
        raise ValueError("ADMIN_TELEGRAM_ID is required")

    try:
        admin_telegram_id = int(admin_id_raw)
    except ValueError as exc:
        raise ValueError("ADMIN_TELEGRAM_ID must be an integer") from exc

    db_path = Path(sqlite_path)
    if db_path.parent and str(db_path.parent) != ".":
        db_path.parent.mkdir(parents=True, exist_ok=True)

    return Settings(
        bot_token=bot_token,
        admin_telegram_id=admin_telegram_id,
        sqlite_path=sqlite_path,
        log_level=log_level,
    )
