# utils.py
import asyncio
import logging
from typing import Optional

from aiogram import Bot
from aiogram.types import Message
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter

logger = logging.getLogger(__name__)


#  ВСПОМОГАТЕЛЬНОЕ

async def _retry_after_sleep(e: TelegramRetryAfter) -> None:
    """
    Аккуратно поспать, если Telegram попросил подождать (429 Too Many Requests).
    """
    try:
        delay = int(getattr(e, "retry_after", 1))  # на всякий случай
    except Exception:
        delay = 1
    if delay < 0:
        delay = 1
    await asyncio.sleep(delay)



#  SAFE SEND / EDIT / DELETE

async def safe_send_message(
    bot: Bot,
    chat_id: int,
    text: str,
    **kwargs,
) -> bool:
    """
    Безопасно отправить текстовое сообщение:
    - обрабатывает TelegramRetryAfter (повтор)
    - глотает Forbidden/BadRequest (например, пользователю нельзя писать)
    - логирует неожиданные ошибки
    """
    try:
        await bot.send_message(chat_id, text, **kwargs)
        return True
    except TelegramRetryAfter as e:
        await _retry_after_sleep(e)
        try:
            await bot.send_message(chat_id, text, **kwargs)
            return True
        except Exception as err:
            logger.warning(f"safe_send_message: retry failed: {err}")
            return False
    except (TelegramForbiddenError, TelegramBadRequest) as e:
        logger.info(f"safe_send_message: forbidden/badrequest for chat {chat_id}: {e}")
        return False
    except Exception as e:
        logger.exception(f"safe_send_message: unexpected error for chat {chat_id}: {e}")
        return False


async def safe_answer(
    message: Message,
    text: str,
    **kwargs,
) -> bool:
    """
    Удобный шорткат: ответить в тот же чат, что и message.chat.id.
    """
    return await safe_send_message(message.bot, message.chat.id, text, **kwargs)


async def safe_send_video(
    bot: Bot,
    chat_id: int,
    video: str,
    **kwargs,
) -> bool:
    """
    Безопасная отправка видео по URL/файлу.
    """
    try:
        await bot.send_video(chat_id=chat_id, video=video, **kwargs)
        return True
    except TelegramRetryAfter as e:
        await _retry_after_sleep(e)
        try:
            await bot.send_video(chat_id=chat_id, video=video, **kwargs)
            return True
        except Exception as err:
            logger.warning(f"safe_send_video: retry failed: {err}")
            return False
    except (TelegramForbiddenError, TelegramBadRequest) as e:
        logger.info(f"safe_send_video: forbidden/badrequest for chat {chat_id}: {e}")
        return False
    except Exception as e:
        logger.exception(f"safe_send_video: unexpected error for chat {chat_id}: {e}")
        return False


async def safe_send_invoice(
    bot: Bot,
    **kwargs,
) -> Optional[Message]:
    """
    Безопасная отправка инвойса (Stars / платежи).
    Возвращает Message с инвойсом или None при ошибке.
    """
    try:
        msg = await bot.send_invoice(**kwargs)
        return msg
    except TelegramRetryAfter as e:
        await _retry_after_sleep(e)
        try:
            msg = await bot.send_invoice(**kwargs)
            return msg
        except Exception as err:
            logger.warning(f"safe_send_invoice: retry failed: {err}")
            return None
    except (TelegramForbiddenError, TelegramBadRequest) as e:
        logger.info(f"safe_send_invoice: forbidden/badrequest: {e}")
        return None
    except Exception as e:
        logger.exception(f"safe_send_invoice: unexpected error: {e}")
        return None


async def safe_edit_text(
    message: Message,
    text: str,
    **kwargs,
) -> bool:
    """
    Безопасно отредактировать текст уже существующего сообщения.
    """
    try:
        await message.edit_text(text, **kwargs)
        return True
    except TelegramRetryAfter as e:
        await _retry_after_sleep(e)
        try:
            await message.edit_text(text, **kwargs)
            return True
        except Exception as err:
            logger.warning(f"safe_edit_text: retry failed: {err}")
            return False
    except TelegramBadRequest as e:
        # Например: "message is not modified" или нельзя редактировать старое сообщение.
        logger.info(f"safe_edit_text: badrequest: {e}")
        return False
    except TelegramForbiddenError as e:
        logger.info(f"safe_edit_text: forbidden: {e}")
        return False
    except Exception as e:
        logger.exception(f"safe_edit_text: unexpected error: {e}")
        return False


async def safe_edit_reply_markup(
    message: Message,
    **kwargs,
) -> bool:
    """
    Безопасное редактирование только разметки (клавиатуры) сообщения.
    """
    try:
        await message.edit_reply_markup(**kwargs)
        return True
    except TelegramRetryAfter as e:
        await _retry_after_sleep(e)
        try:
            await message.edit_reply_markup(**kwargs)
            return True
        except Exception as err:
            logger.warning(f"safe_edit_reply_markup: retry failed: {err}")
            return False
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        logger.info(f"safe_edit_reply_markup: badrequest/forbidden: {e}")
        return False
    except Exception as e:
        logger.exception(f"safe_edit_reply_markup: unexpected error: {e}")
        return False


async def safe_delete_message(
    bot: Bot,
    chat_id: int,
    message_id: int,
) -> bool:
    """
    Безопасное удаление сообщения.
    """
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        logger.info(f"safe_delete_message: badrequest/forbidden for chat {chat_id}: {e}")
        return False
    except Exception as e:
        logger.exception(f"safe_delete_message: unexpected error for chat {chat_id}: {e}")
        return False
