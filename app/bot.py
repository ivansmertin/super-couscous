from __future__ import annotations

from aiogram import Bot, Dispatcher

from app.handlers.admin import router as admin_router
from app.handlers.user import router as user_router
from app.services.relay import CooldownService
from app.services.storage import Storage


def build_dispatcher(storage: Storage, admin_id: int) -> Dispatcher:
    dp = Dispatcher()
    cooldown = CooldownService(cooldown_seconds=2)

    dp["storage"] = storage
    dp["admin_id"] = admin_id
    dp["cooldown"] = cooldown

    dp.include_router(admin_router)
    dp.include_router(user_router)
    return dp


def build_bot(token: str) -> Bot:
    return Bot(token=token)
