from __future__ import annotations

import logging
import math
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.db.models import User
from app.services.storage import Storage

logger = logging.getLogger(__name__)
router = Router(name="admin")

ADMIN_ONLY_TEXT = "Эта команда доступна только администратору."
DIALOGS_PAGE_SIZE = 10

CB_DIALOGS_PAGE = "dialogs:page:"
CB_DIALOGS_OPEN = "dialogs:open:"
CB_DIALOGS_REPLY = "dialogs:reply:"
CB_DIALOGS_BACK = "dialogs:back:"
CB_REPLY_CANCEL = "reply:cancel"


class AdminReplyState(StatesGroup):
    active = State()


def is_admin(message: Message, admin_id: int) -> bool:
    return bool(message.from_user and message.from_user.id == admin_id)


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%d.%m.%Y %H:%M")


def _format_username(username: str | None) -> str:
    if not username:
        return "(нет username)"
    return f"@{username}"


def _dialog_button_text(user: User) -> str:
    username_part = f" {_format_username(user.username)}" if user.username else ""
    text = f"{user.full_name}{username_part} · {user.telegram_id}"
    if len(text) > 62:
        text = text[:59] + "..."
    return text


def _dialogs_keyboard(users: list[User], page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for user in users:
        rows.append(
            [
                InlineKeyboardButton(
                    text=_dialog_button_text(user),
                    callback_data=f"{CB_DIALOGS_OPEN}{user.telegram_id}:{page}",
                )
            ]
        )

    nav_row: list[InlineKeyboardButton] = []
    if page > 1:
        nav_row.append(
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=f"{CB_DIALOGS_PAGE}{page - 1}",
            )
        )
    if page < total_pages:
        nav_row.append(
            InlineKeyboardButton(
                text="Вперёд ➡️",
                callback_data=f"{CB_DIALOGS_PAGE}{page + 1}",
            )
        )
    if nav_row:
        rows.append(nav_row)

    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _send_dialogs_page(target: Message | CallbackQuery, storage: Storage, page: int) -> None:
    total_dialogs = storage.count_dialogs()
    if total_dialogs == 0:
        text = "Диалогов пока нет."
        if isinstance(target, CallbackQuery) and target.message:
            await target.message.edit_text(text)
        else:
            await target.answer(text)
        return

    total_pages = max(1, math.ceil(total_dialogs / DIALOGS_PAGE_SIZE))
    normalized_page = min(max(page, 1), total_pages)
    offset = (normalized_page - 1) * DIALOGS_PAGE_SIZE
    dialogs = storage.list_recent_dialogs(limit=DIALOGS_PAGE_SIZE, offset=offset)

    text = (
        "Выберите диалог:\n"
        f"Страница {normalized_page}/{total_pages}. "
        f"Всего диалогов: {total_dialogs}."
    )
    markup = _dialogs_keyboard(dialogs, normalized_page, total_pages)

    if isinstance(target, CallbackQuery) and target.message:
        await target.message.edit_text(text, reply_markup=markup)
    else:
        await target.answer(text, reply_markup=markup)


def _dialog_details_keyboard(telegram_id: int, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Ответить",
                    callback_data=f"{CB_DIALOGS_REPLY}{telegram_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Назад к диалогам",
                    callback_data=f"{CB_DIALOGS_BACK}{page}",
                )
            ],
        ]
    )


def _reply_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data=CB_REPLY_CANCEL)]]
    )


@router.message(Command("id"))
async def cmd_id(message: Message, admin_id: int) -> None:
    if not is_admin(message, admin_id):
        await message.answer(ADMIN_ONLY_TEXT)
        return
    user_id = message.from_user.id if message.from_user else admin_id
    await message.answer(f"chat_id={message.chat.id}\nuser_id={user_id}")


@router.message(Command("users"))
async def cmd_users(message: Message, admin_id: int, storage: Storage) -> None:
    if not is_admin(message, admin_id):
        await message.answer(ADMIN_ONLY_TEXT)
        return
    count = storage.count_users()
    await message.answer(f"Всего пользователей: {count}")


@router.message(Command("dialogs"))
async def cmd_dialogs(message: Message, admin_id: int, storage: Storage) -> None:
    if not is_admin(message, admin_id):
        await message.answer(ADMIN_ONLY_TEXT)
        return
    await _send_dialogs_page(message, storage, page=1)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, admin_id: int, state: FSMContext) -> None:
    if not is_admin(message, admin_id):
        await message.answer(ADMIN_ONLY_TEXT)
        return

    if await state.get_state() is None:
        await message.answer("Режим ответа не активен.")
        return

    await state.clear()
    await message.answer("Режим ответа отменён.")


@router.callback_query(F.data.startswith(CB_DIALOGS_PAGE))
async def cb_dialogs_page(
    callback: CallbackQuery,
    admin_id: int,
    storage: Storage,
) -> None:
    if not callback.from_user or callback.from_user.id != admin_id:
        await callback.answer(ADMIN_ONLY_TEXT, show_alert=True)
        return

    page_raw = callback.data.removeprefix(CB_DIALOGS_PAGE) if callback.data else "1"
    try:
        page = int(page_raw)
    except ValueError:
        page = 1

    await _send_dialogs_page(callback, storage, page=page)
    await callback.answer()


@router.callback_query(F.data.startswith(CB_DIALOGS_OPEN))
async def cb_open_dialog(
    callback: CallbackQuery,
    admin_id: int,
    storage: Storage,
) -> None:
    if not callback.from_user or callback.from_user.id != admin_id:
        await callback.answer(ADMIN_ONLY_TEXT, show_alert=True)
        return

    if not callback.data or not callback.message:
        await callback.answer()
        return

    payload = callback.data.removeprefix(CB_DIALOGS_OPEN)
    try:
        user_id_raw, page_raw = payload.split(":", maxsplit=1)
        telegram_id = int(user_id_raw)
        page = int(page_raw)
    except ValueError:
        await callback.answer("Не удалось открыть диалог.", show_alert=True)
        return

    user = storage.get_user_by_telegram_id(telegram_id)
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    summary = storage.get_dialog_summary(telegram_id)
    text = (
        "👤 Диалог с пользователем\n"
        f"Имя: {user.full_name}\n"
        f"Username: {_format_username(user.username)}\n"
        f"Telegram ID: {user.telegram_id}\n"
        f"Последняя активность: {_format_datetime(user.last_seen_at)}\n"
        f"Сообщений от пользователя: {summary.total_messages}\n"
        f"Последний тип сообщения: {summary.last_message_type or '—'}\n"
        f"Последнее входящее: {_format_datetime(summary.last_message_at)}"
    )

    await callback.message.edit_text(
        text,
        reply_markup=_dialog_details_keyboard(telegram_id=telegram_id, page=page),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(CB_DIALOGS_BACK))
async def cb_back_to_dialogs(
    callback: CallbackQuery,
    admin_id: int,
    storage: Storage,
) -> None:
    if not callback.from_user or callback.from_user.id != admin_id:
        await callback.answer(ADMIN_ONLY_TEXT, show_alert=True)
        return

    page_raw = callback.data.removeprefix(CB_DIALOGS_BACK) if callback.data else "1"
    try:
        page = int(page_raw)
    except ValueError:
        page = 1

    await _send_dialogs_page(callback, storage, page=page)
    await callback.answer()


@router.callback_query(F.data.startswith(CB_DIALOGS_REPLY))
async def cb_activate_reply_mode(
    callback: CallbackQuery,
    admin_id: int,
    storage: Storage,
    state: FSMContext,
) -> None:
    if not callback.from_user or callback.from_user.id != admin_id:
        await callback.answer(ADMIN_ONLY_TEXT, show_alert=True)
        return

    if not callback.data:
        await callback.answer()
        return

    user_id_raw = callback.data.removeprefix(CB_DIALOGS_REPLY)
    try:
        telegram_id = int(user_id_raw)
    except ValueError:
        await callback.answer("Не удалось включить режим ответа.", show_alert=True)
        return

    user = storage.get_user_by_telegram_id(telegram_id)
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    await state.set_state(AdminReplyState.active)
    await state.update_data(target_user_id=telegram_id, target_name=user.full_name)

    text = (
        "Режим ответа активирован. Следующее сообщение будет отправлено этому пользователю. "
        "Для отмены используйте /cancel.\n\n"
        f"Текущий получатель: {user.full_name} ({telegram_id})."
    )

    if callback.message:
        await callback.message.answer(text, reply_markup=_reply_cancel_keyboard())
    await callback.answer("Режим ответа включён.")


@router.callback_query(F.data == CB_REPLY_CANCEL)
async def cb_cancel_reply_mode(
    callback: CallbackQuery,
    admin_id: int,
    state: FSMContext,
) -> None:
    if not callback.from_user or callback.from_user.id != admin_id:
        await callback.answer(ADMIN_ONLY_TEXT, show_alert=True)
        return

    await state.clear()
    await callback.answer("Отменено")

    if callback.message:
        await callback.message.answer("Режим ответа отменён.")


@router.message(AdminReplyState.active)
async def relay_reply_mode_message(
    message: Message,
    admin_id: int,
    state: FSMContext,
    bot: Bot,
) -> None:
    if not is_admin(message, admin_id):
        return

    data = await state.get_data()
    target_user_id = data.get("target_user_id")

    if not isinstance(target_user_id, int):
        await state.clear()
        await message.answer("Режим ответа сброшен. Выберите диалог заново через /dialogs.")
        return

    if message.text and message.text.startswith("/"):
        await message.answer(
            "Сейчас активен режим ответа. Отправьте сообщение пользователю или завершите режим командой /cancel."
        )
        return

    try:
        await bot.copy_message(
            chat_id=target_user_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
    except Exception:
        logger.exception("Failed to relay admin message in reply mode user_id=%s", target_user_id)
        await message.answer("Не удалось отправить сообщение пользователю.")
        return

    await message.answer(
        "Сообщение отправлено пользователю.\n"
        f"Текущий получатель: {data.get('target_name', 'пользователь')} ({target_user_id}).\n"
        "Режим ответа активен. Для выхода используйте /cancel.",
        reply_markup=_reply_cancel_keyboard(),
    )


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


@router.message(StateFilter(None), F.reply_to_message)
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
