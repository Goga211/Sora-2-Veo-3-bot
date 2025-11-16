# main.py
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import TOKEN, DEBUG
from database import db
from subscription import register_common_handlers
from sora_handlers import register_sora_handlers
from veo_handlers import register_veo_handlers
from payments import register_payment_handlers


async def main():
    # Логирование
    logging.basicConfig(
        level=logging.DEBUG if DEBUG else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger(__name__)
    logger.info("Starting bot...")

    # Бот и диспетчер
    bot = Bot(token=TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Подключаем БД
    await db.connect()
    logger.info("DB connected")

    # Регистрируем группы хендлеров
    register_common_handlers(dp)   # /start, /menu, подписка, back_to_main
    register_sora_handlers(dp)     # Sora 2 / Sora 2 Pro
    register_veo_handlers(dp)      # Veo 3.1
    register_payment_handlers(dp)  # баланс, пополнение, /get_id, /give_tokens

    try:
        await dp.start_polling(bot)
    finally:
        await db.close()
        logger.info("DB closed")


if __name__ == "__main__":
    asyncio.run(main())
