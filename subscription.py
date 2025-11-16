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


# ===========================
#  ВСПОМОГАТЕЛЬНОЕ
# ===========================

def _channel_ref() -> Optional[Union[int, str]]:
    """
    Возвращает идентификатор канала для проверки подписки:
    - если CHANNEL_ID != 0 → числовой ID
    - иначе, если есть CHANNEL_USERNAME → username
    - иначе None (подписка не проверяется)
    """
    if CHANNEL_ID != 0:
        return CHANNEL_ID
    if CHANNEL_USERNAME:
        return CHANNEL_USERNAME
    return None


async def is_user_subscribed(bot: Bot, user_id: int) -> bool:
    """
    Проверка, подписан ли пользователь на канал.
    Если канал не задан в конфиге — возвращает True (подписка не требуется).
    """
    chat = _channel_ref()
    if not chat:
        # Канал не настроен → подписку не проверяем
        return True

    try:
        member = await bot.get_chat_member(chat_id=chat, user_id=user_id)
        status = member.status
        return status in {
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        }
    except Exception as e:
        # Лучше залогировать, но по безопасности — не пускать
        logger.exception(f"is_user_subscribed: get_chat_member failed: {e}")
        return False


# ===========================
#  ХЕНДЛЕРЫ
# ===========================

async def cmd_start(message: Message):
    """
    /start:
    - создаёт пользователя в БД, если нет
    - проверяет подписку
    - показывает главное меню
    """
    bot = message.bot
    uid = message.from_user.id

    # создаём пользователя, если его ещё нет
    user = await db.get_user(uid)
    if not user:
        await db.create_user(uid)

    # проверка подписки
    if not await is_user_subscribed(bot, uid):
        await safe_answer(
            message,
            "Чтобы пользоваться ботом, подпишись на наш канал и нажми «✅ Я подписался».",
            reply_markup=subscribe_keyboard(),
        )
        return

    text = (
        "👋 Привет! Я делаю видео с помощью моделей Sora 2 и Veo 3.1.\n\n"
        "Нажми «🎬 Создать видео», чтобы начать.\n"
        "Баланс и пополнение — отдельными кнопками ниже."
    )
    await safe_answer(message, text, reply_markup=main_menu_keyboard())


async def cmd_menu(message: Message):
    """
    /menu — просто выводит главное меню.
    """
    text = "🏠 Главное меню. Выберите действие:"
    await safe_answer(message, text, reply_markup=main_menu_keyboard())


async def on_check_sub(callback: CallbackQuery):
    """
    Обработка кнопки '✅ Я подписался':
    - если подписка появилась → редактируем сообщение и даём главное меню
    - если нет → показываем алерт
    """
    bot = callback.message.bot
    uid = callback.from_user.id

    if await is_user_subscribed(bot, uid):
        # обновляем сообщение с проверкой
        await safe_edit_text(
            callback.message,
            "✅ Спасибо за подписку! Доступ к боту открыт.\n\n"
            "Теперь можете пользоваться кнопками ниже.",
        )
        # отправляем главное меню отдельным сообщением
        await safe_send_message(
            bot,
            uid,
            "🏠 Главное меню.",
            reply_markup=main_menu_keyboard(),
        )
    else:
        try:
            await callback.answer(
                "Похоже, вы ещё не подписались на канал 🤔",
                show_alert=True,
            )
        except Exception:
            # если не удалось показать алерт — просто молча игнорируем
            pass


async def back_to_main_cb(callback: CallbackQuery):
    """
    Обработка '🔙 Назад' → главное меню.
    (callback_data = 'back_to_main')
    """
    # Сброс FSM делается в других модулях (там, где есть state),
    # тут только визуально возвращаем в главное меню.
    await safe_edit_text(
        callback.message,
        "🏠 Главное меню.",
        reply_markup=main_menu_keyboard(),
    )


# ===========================
#  РЕГИСТРАЦИЯ ХЕНДЛЕРОВ
# ===========================

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
