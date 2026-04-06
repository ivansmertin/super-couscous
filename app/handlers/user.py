from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.services.formatting import detect_message_type, safe_name, safe_username
from app.services.relay import CooldownService
from app.services.storage import Storage

logger = logging.getLogger(__name__)
router = Router(name="user")

WELCOME_TEXT = (
    "Здравствуйте. Здесь вы можете оставить заявку или задать вопрос.\n"
    "Переписка в боте конфиденциальна.\n"
    "Просто отправьте сообщение — я отвечу вам лично."
)

HELP_TEXT = (
    "Напишите в этот бот ваш вопрос или заявку — сообщение будет передано администратору.\n"
    "Когда администратор ответит, вы получите ответ прямо здесь."
)

CONFIRMATION_TEXT = "Сообщение отправлено. Я получил его и отвечу вам здесь."


@router.message(Command("start"))
async def cmd_start(message: Message, admin_id: int) -> None:
    if message.from_user and message.from_user.id == admin_id:
        await message.answer("Вы администратор этого бота.")
        return
    await message.answer(WELCOME_TEXT)


@router.message(Command("help"))
async def cmd_help(message: Message, admin_id: int) -> None:
    if message.from_user and message.from_user.id == admin_id:
        await message.answer("Команды администратора: /id, /users, /broadcast <текст>")
        return
    await message.answer(HELP_TEXT)


@router.message()
async def relay_user_message(
    message: Message,
    bot: Bot,
    storage: Storage,
    admin_id: int,
    cooldown: CooldownService,
) -> None:
    if not message.from_user:
        return
    if message.from_user.id == admin_id:
        return

    if message.text and message.text.startswith("/"):
        return

    user = message.from_user
    message_type = detect_message_type(message)

    storage.upsert_user(user.id, user.full_name, user.username)
    storage.save_inbound_message(user.id, message.message_id, message_type)

    header = (
        "📩 Новое сообщение\n"
        f"Имя: {safe_name(user)}\n"
        f"Username: {safe_username(user)}\n"
        f"Telegram ID: {user.id}\n"
        f"Тип: {message_type}"
    )

    await bot.send_message(admin_id, header)
    relayed = await bot.copy_message(
        chat_id=admin_id,
        from_chat_id=message.chat.id,
        message_id=message.message_id,
    )
    storage.save_admin_relay_mapping(relayed.message_id, user.id)

    if cooldown.allow(user.id) and storage.should_send_confirmation(user.id):
        await message.answer(CONFIRMATION_TEXT)
        storage.mark_confirmation_sent(user.id)

    logger.info("Relayed user message user_id=%s type=%s", user.id, message_type)
