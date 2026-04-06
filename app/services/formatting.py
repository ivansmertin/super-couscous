from __future__ import annotations

from html import escape

from aiogram.types import User as TgUser


def safe_name(user: TgUser) -> str:
    return escape(user.full_name)


def safe_username(user: TgUser) -> str:
    if user.username:
        return f"@{escape(user.username)}"
    return "(нет username)"


def detect_message_type(message: object) -> str:
    content_type = getattr(message, "content_type", None)
    if content_type is None:
        return "unknown"
    return str(content_type)
