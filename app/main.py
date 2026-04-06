from __future__ import annotations

import asyncio
import logging

from app.bot import build_bot, build_dispatcher
from app.config import load_settings
from app.db.session import create_engine_and_session, create_tables
from app.services.storage import Storage
from app.utils.logging import setup_logging

logger = logging.getLogger(__name__)


async def run() -> None:
    settings = load_settings()
    setup_logging(settings.log_level)

    engine, session_factory = create_engine_and_session(settings.sqlite_path)
    create_tables(engine)

    storage = Storage(session_factory)
    bot = build_bot(settings.bot_token)
    dp = build_dispatcher(storage, settings.admin_telegram_id)

    logger.info("Starting bot with long polling")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run())
