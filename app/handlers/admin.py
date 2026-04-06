from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.services.storage import Storage

logger = logging.getLogger(__name__)
router = Router(name="admin")

ADMIN_ONLY_TEXT = "Эта команда доступна только администратору."


def is_admin(message: Message, admin_id: int) -> bool:
    return bool(message.from_user and message.from_user.id == admin_id)


@router.message(Command("id"))
async def cmd_id(message: Message, admin_id: int) -> None:
    if not is_admin(message, admin_id):
        await message.answer(ADMIN_ONLY_TEXT)
        return
    await message.answer(f"Ваш Telegram ID: {admin_id}")


@router.message(Command("users"))
async def cmd_users(message: Message, admin_id: int, storage: Storage) -> None:
    if not is_admin(message, admin_id):
        await message.answer(ADMIN_ONLY_TEXT)
        return
    count = storage.count_users()
    await message.answer(f"Всего пользователей: {count}")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, admin_id: int, storage: Storage, bot: Bot) -> None:
    if not is_admin(message, admin_id):
        await message.answer(ADMIN_ONLY_TEXT)
        return

    if not message.text:
        await message.answer("Использование: /broadcast <текст>")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Использование: /broadcast <текст>")
        return

    text = parts[1].strip()
    sent = 0
    failed = 0

    for user_id in storage.list_user_ids():
        try:
            await bot.send_message(user_id, text)
            sent += 1
        except Exception:
            failed += 1

    await message.answer(f"Рассылка завершена. Успешно: {sent}, ошибок: {failed}")


@router.message(F.reply_to_message)
async def relay_admin_reply(
    message: Message,
    admin_id: int,
    storage: Storage,
    bot: Bot,
) -> None:
    if not is_admin(message, admin_id):
        return

    if not message.reply_to_message:
        return

    target_message_id = message.reply_to_message.message_id
    target_user_id = storage.resolve_user_id_by_admin_message_id(target_message_id)

    if target_user_id is None:
        await message.answer(
            "Не удалось определить получателя. "
            "Ответьте реплаем на пересланное ботом сообщение пользователя."
        )
        return

    await bot.copy_message(
        chat_id=target_user_id,
        from_chat_id=message.chat.id,
        message_id=message.message_id,
    )
    logger.info("Relayed admin reply to user_id=%s", target_user_id)
