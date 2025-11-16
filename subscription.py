# subscription.py
import logging
from typing import Optional, Union

from aiogram import Dispatcher, F, Bot
from aiogram import types
from aiogram.filters import Command
from aiogram.enums import ChatMemberStatus
from aiogram.types import CallbackQuery, Message

from config import CHANNEL_ID, CHANNEL_USERNAME
from database import db
from keyboards import (
    main_menu_keyboard,
    subscribe_keyboard,
)
from utils import (
    safe_answer,
    safe_send_message,
    safe_edit_text,
)

logger = logging.getLogger(__name__)


# ТЕКСТ ГЛАВНОГО МЕНЮ

MAIN_MENU_TEXT = (
    "🎛 Главное меню\n\n"
    "Добро пожаловать!\n"
    "Здесь вы можете создать видео с помощью самых мощных моделей Sora 2 и Veo 3.1\n\n"
    "Выберите действие ниже:\n\n"
    "🎥 Создать видео — генерация роликов по тексту или фото\n\n"
    "💰 Баланс — показывает количество оставшихся токенов\n\n"
    "💳 Пополнить баланс — получение токенов, оплата в Рублях или Звездах"
)


# ВСПОМОГАТЕЛЬНЫЕ

def _channel_ref() -> Optional[Union[int, str]]:
    """
    Возвращает идентификатор канала для проверки подписки:
    - если CHANNEL_ID != 0 → числовой ID
    - иначе, если есть CHANNEL_USERNAME → username
    - иначе None (подписка не требуется)
    """
    if CHANNEL_ID != 0:
        return CHANNEL_ID
    if CHANNEL_USERNAME:
        return CHANNEL_USERNAME
    return None


async def is_user_subscribed(bot: Bot, user_id: int) -> bool:
    """
    Проверка, подписан ли пользователь на канал.
    Если канал не задан в конфиге — возвращает True.
    """
    chat = _channel_ref()
    if not chat:
        return True  # подписка не нужна

    try:
        member = await bot.get_chat_member(chat_id=chat, user_id=user_id)
        status = member.status
        return status in {
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        }
    except Exception as e:
        logger.exception(f"is_user_subscribed: get_chat_member failed: {e}")
        return False


# ХЕНДЛЕРЫ

async def cmd_start(message: Message):
    """
    /start:
    - создаёт пользователя в БД, если нет
    - проверяет подписку
    - выводит главное меню
    """
    bot = message.bot
    uid = message.from_user.id

    # создаём пользователя, если его нет
    user = await db.get_user(uid)
    if not user:
        await db.create_user(uid)

    # проверка подписки
    if not await is_user_subscribed(bot, uid):
        await safe_answer(
            message,
            "Чтобы пользоваться ботом, подпишитесь на наш канал и нажмите «✅ Я подписался».",
            reply_markup=subscribe_keyboard(),
        )
        return

    # выводим единый текст меню
    await safe_answer(
        message,
        MAIN_MENU_TEXT,
        reply_markup=main_menu_keyboard(),
    )


async def cmd_menu(message: Message):
    """
    /menu — просто выводит главное меню.
    """
    await safe_answer(
        message,
        MAIN_MENU_TEXT,
        reply_markup=main_menu_keyboard(),
    )


async def on_check_sub(callback: CallbackQuery):
    """
    Обработка кнопки '✅ Я подписался'
    """
    bot = callback.message.bot
    uid = callback.from_user.id

    if await is_user_subscribed(bot, uid):
        await safe_edit_text(
            callback.message,
            "✅ Спасибо за подписку! Доступ к боту открыт.",
        )

        # отправляем главное меню
        await safe_send_message(
            bot,
            uid,
            MAIN_MENU_TEXT,
            reply_markup=main_menu_keyboard(),
        )
    else:
        try:
            await callback.answer(
                "Похоже, вы ещё не подписались 🤔",
                show_alert=True,
            )
        except Exception:
            pass


async def back_to_main_cb(callback: CallbackQuery):
    """
    Обработка '🔙 Назад' → главное меню.
    callback_data = 'back_to_main'
    """
    await safe_edit_text(
        callback.message,
        MAIN_MENU_TEXT,
        reply_markup=main_menu_keyboard(),
    )


# РЕГИСТРАЦИЯ ОБЩИХ ХЕНДЛЕРОВ

def register_common_handlers(dp: Dispatcher) -> None:
    """
    Регистрирует общие хендлеры:
    - /start
    - /menu
    - проверка подписки
    - 'Назад в главное'
    """
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_menu, Command("menu"))

    dp.callback_query.register(on_check_sub, F.data == "check_sub")
    dp.callback_query.register(back_to_main_cb, F.data == "back_to_main")
