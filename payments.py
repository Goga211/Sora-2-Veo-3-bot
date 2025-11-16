# payments.py
import asyncio
import json
import logging
from typing import Dict, Optional

from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    LabeledPrice,
    PreCheckoutQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from yookassa import Configuration, Payment

from config import (
    YOOKASSA_SHOP_ID,
    YOOKASSA_SECRET_KEY,
    YOOKASSA_RETURN_URL,
    ADMIN_IDS,
)
from database import db
from keyboards import main_menu_keyboard, back_btn
from states import BalanceStates
from utils import (
    safe_answer,
    safe_send_message,
    safe_send_invoice,
    safe_edit_text,
    safe_delete_message,
)

logger = logging.getLogger(__name__)

# YooKassa настройка

if YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY:
    Configuration.account_id = YOOKASSA_SHOP_ID
    Configuration.secret_key = YOOKASSA_SECRET_KEY
else:
    logger.warning("YooKassa не настроена: нет YOOKASSA_SHOP_ID/YOOKASSA_SECRET_KEY")


# Пакеты Stars и RUB

# Stars → токены
STAR_PACKS: Dict[str, Dict[str, int | str]] = {
    "20":  {"stars": 20,  "tokens": 30,  "title": "⭐ 20 звёзд → 30 токенов"},
    "60":  {"stars": 60,  "tokens": 100, "title": "⭐ 60 звёзд → 100 токенов"},
    "120": {"stars": 120, "tokens": 200, "title": "⭐ 120 звёзд → 200 токенов"},
    "300": {"stars": 300, "tokens": 500, "title": "⭐ 300 звёзд → 500 токенов"},
}

# RUB → токены
RUB_PACKS: Dict[str, Dict[str, int]] = {
    "30":  {"rubles": 30,  "tokens": 30},
    "100": {"rubles": 100, "tokens": 100},
    "200": {"rubles": 200, "tokens": 200},
    "500": {"rubles": 500, "tokens": 500},
}

# Последний инвойс Stars для удаления
LAST_INVOICE_MSG: Dict[int, int] = {}

# Fallback, если нет идемпотентного метода в БД
APPLIED_CHARGES: set[str] = set()


# Баланс / Пополнение

async def menu_balance_cb(callback: CallbackQuery):
    """
    Кнопка '💰 Баланс' (callback_data='menu_balance').
    """
    uid = callback.from_user.id
    user = await db.get_user(uid)
    txt = (
        f"💰 Ваш баланс:\n\n🪙 Токенов: {user['generations_left']}"
        if user else
        "❌ Пользователь не найден в базе."
    )
    await safe_edit_text(
        callback.message,
        txt,
        reply_markup=main_menu_keyboard(),
    )


async def menu_topup_cb(callback: CallbackQuery, state: FSMContext):
    """
    Кнопка '💳 Пополнить баланс' (callback_data='menu_topup').
    Выбор способа: Stars / YooKassa.
    """
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Звёзды", callback_data="pay_stars")],
            [InlineKeyboardButton(text="💵 Рубли (YooKassa)", callback_data="pay_rub")],
            [back_btn("back_to_main")],
        ]
    )
    await safe_edit_text(
        callback.message,
        "💳 Выберите способ пополнения:",
        reply_markup=kb,
    )
    await state.set_state(BalanceStates.waiting_for_payment_method)


# ─────────────────────────── /get_id и /give_tokens ───────────────────────────

async def cmd_get_id(message: Message):
    uid = message.from_user.id
    await safe_answer(
        message,
        f"🆔 Ваш Telegram ID: <b>{uid}</b>",
        parse_mode="HTML",
    )


async def cmd_give_tokens(message: Message):
    """
    /give_tokens user_id amount — только для админов.
    """
    uid = message.from_user.id
    if uid not in ADMIN_IDS:
        await safe_answer(message, "❌ У вас нет прав для использования этой команды.")
        return

    parts = message.text.split()
    if len(parts) != 3:
        await safe_answer(
            message,
            "⚙️ Использование: <code>/give_tokens user_id amount</code>",
            parse_mode="HTML",
        )
        return

    try:
        target_id = int(parts[1])
        amount = int(parts[2])
    except ValueError:
        await safe_answer(message, "❌ ID и количество должны быть числами.")
        return

    user = await db.get_user(target_id)
    if not user:
        await safe_answer(message, "⚠️ Пользователь с таким ID не найден в базе.")
        return

    await db.add_generations(target_id, amount)
    await safe_answer(
        message,
        f"✅ Пользователю <b>{target_id}</b> начислено <b>{amount}</b> токенов.",
        parse_mode="HTML",
    )
    await safe_send_message(
        message.bot,
        target_id,
        f"🎁 Вам начислено <b>{amount}</b> токенов администратором.",
        parse_mode="HTML",
    )


# ─────────────────────────── Stars: выбор пакета ───────────────────────────

async def pay_stars_cb(callback: CallbackQuery, state: FSMContext):
    """
    Кнопка '⭐ Звёзды' (pay_stars) — выбор пакета.
    """
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=STAR_PACKS["20"]["title"],  callback_data="stars_20")],
            [InlineKeyboardButton(text=STAR_PACKS["60"]["title"],  callback_data="stars_60")],
            [InlineKeyboardButton(text=STAR_PACKS["120"]["title"], callback_data="stars_120")],
            [InlineKeyboardButton(text=STAR_PACKS["300"]["title"], callback_data="stars_300")],
            [back_btn("menu_topup")],
        ]
    )
    await safe_edit_text(
        callback.message,
        "⭐ Выберите пакет для пополнения:\n"
        "Дешево звёзды можно купить тут — @cheapiest_star_bot",
        reply_markup=kb,
    )


async def stars_package_cb(callback: CallbackQuery):
    """
    Выбор конкретного пакета звёзд (stars_20 / stars_60 / ...).
    """
    bot = callback.message.bot
    uid = callback.from_user.id
    pack = callback.data.split("_")[1]  # "20" | "60" | "120" | "300"

    if pack not in STAR_PACKS:
        try:
            await callback.answer("❌ Неверный пакет", show_alert=True)
        except Exception:
            pass
        return

    pkg = STAR_PACKS[pack]

    payload = json.dumps({
        "kind": "stars_pack",
        "pack": pack,
        "stars": pkg["stars"],
        "tokens": pkg["tokens"],
        "uid": uid,
    })

    prices = [
        LabeledPrice(
            label=f"{pkg['stars']} ⭐",
            amount=pkg["stars"],
        )
    ]

    msg = await safe_send_invoice(
        bot,
        chat_id=uid,
        title="Пополнение токенов",
        description=f"{pkg['stars']} ⭐ → {pkg['tokens']} токенов",
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=prices,
        start_parameter=f"stars_{pack}_{uid}",
        is_flexible=False,
    )

    if msg:
        LAST_INVOICE_MSG[uid] = msg.message_id


# Stars: pre-checkout + успешная оплата 

async def on_pre_checkout(pcq: PreCheckoutQuery):
    """
    Pre-checkout для платежей Telegram (Stars).
    """
    try:
        await pcq.bot.answer_pre_checkout_query(pcq.id, ok=True)
    except Exception:
        logger.exception("pre_checkout answer error")


async def on_successful_stars_payment(message: Message):
    """
    Обработка успешной оплаты (successful_payment) для Stars.
    """
    sp = message.successful_payment
    if not sp or sp.currency != "XTR":
        return

    uid = message.from_user.id

    try:
        payload = json.loads(sp.invoice_payload or "{}")
    except Exception:
        payload = {}

    stars_paid = int(sp.total_amount)
    charge_id = sp.telegram_payment_charge_id
    tokens = int(payload.get("tokens") or 0)
    pack_stars_declared = int(payload.get("stars") or 0)

    if pack_stars_declared and pack_stars_declared != stars_paid:
        logger.warning(
            f"Stars mismatch: declared={pack_stars_declared}, "
            f"paid={stars_paid}, payload={payload}"
        )

    applied = False
    try:
        if hasattr(db, "apply_star_payment"):
            applied = await db.apply_star_payment(
                user_id=uid,
                telegram_payment_charge_id=charge_id,
                stars=stars_paid,
                tokens=tokens,
                raw_payload=payload,
            )
        else:
            # Fallback: сами следим за charge_id
            if charge_id in APPLIED_CHARGES:
                applied = False
            else:
                await db.add_generations(uid, tokens)
                APPLIED_CHARGES.add(charge_id)
                applied = True
    except Exception:
        logger.exception("apply_star_payment error")
        try:
            await db.add_generations(uid, tokens)
            applied = True
        except Exception:
            logger.exception("add_generations fallback error")

    if applied:
        await safe_answer(
            message,
            f"✅ Оплата получена: {stars_paid} ⭐\n"
            f"🪙 Начислено: {tokens} токенов\nСпасибо! 🎉",
        )
    else:
        await safe_answer(
            message,
            "ℹ️ Этот платёж уже был учтён ранее.",
        )

    # Удаляем чек (текущее сообщение) и инвойс Stars
    await safe_delete_message(message.bot, message.chat.id, message.message_id)
    mid = LAST_INVOICE_MSG.pop(uid, None)
    if mid:
        await safe_delete_message(message.bot, message.chat.id, mid)


# YooKassa: создание платежа

def create_yookassa_payment(amount_rub: int, user_id: int, tokens: int):
    """
    Создаёт платёж в YooKassa (синхронный вызов).
    """
    payment = Payment.create({
        "amount": {
            "value": f"{amount_rub:.2f}",
            "currency": "RUB",
        },
        "confirmation": {
            "type": "redirect",
            "return_url": YOOKASSA_RETURN_URL,
        },
        "capture": True,
        "description": f"Пополнение {amount_rub}₽ ({tokens} токенов) пользователем {user_id}",
        "metadata": {
            "user_id": user_id,
            "tokens": tokens,
        },
        "receipt": {
            "customer": {
                "email": "antipingv2003@gmail.com"
            },
            "items": [{
                "description": f"{tokens} токенов",
                "quantity": "1.0",
                "amount": {
                    "value": f"{amount_rub:.2f}",
                    "currency": "RUB",
                },
                "vat_code": "1",
            }],
        },
    })
    return payment.confirmation.confirmation_url, payment.id


# YooKassa: хендлеры

async def pay_rub_cb(callback: CallbackQuery, state: FSMContext):
    """
    Кнопка '💵 Рубли (YooKassa)' — выбор рублёвого пакета.
    """
    if not (YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY):
        try:
            await callback.answer("YooKassa не настроена", show_alert=True)
        except Exception:
            pass
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"💵 {RUB_PACKS['30']['rubles']}₽ → {RUB_PACKS['30']['tokens']} токенов",
                callback_data="rubles_30"
            )],
            [InlineKeyboardButton(
                text=f"💵 {RUB_PACKS['100']['rubles']}₽ → {RUB_PACKS['100']['tokens']} токенов",
                callback_data="rubles_100"
            )],
            [InlineKeyboardButton(
                text=f"💵 {RUB_PACKS['200']['rubles']}₽ → {RUB_PACKS['200']['tokens']} токенов",
                callback_data="rubles_200"
            )],
            [InlineKeyboardButton(
                text=f"💵 {RUB_PACKS['500']['rubles']}₽ → {RUB_PACKS['500']['tokens']} токенов",
                callback_data="rubles_500"
            )],
            [back_btn("menu_topup")],
        ]
    )
    await safe_edit_text(
        callback.message,
        "💵 Выберите пакет для пополнения (YooKassa):",
        reply_markup=kb,
    )


async def rubles_package_cb(callback: CallbackQuery):
    """
    Выбор пакета RUB → токены (rubles_30 / rubles_100 / ...).
    """
    bot = callback.message.bot

    if not (YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY):
        try:
            await callback.answer("YooKassa не настроена", show_alert=True)
        except Exception:
            pass
        return

    uid = callback.from_user.id
    pack = callback.data.split("_")[1]

    if pack not in RUB_PACKS:
        try:
            await callback.answer("❌ Неверный пакет", show_alert=True)
        except Exception:
            pass
        return

    pkg = RUB_PACKS[pack]

    try:
        pay_url, pay_id = await asyncio.to_thread(
            create_yookassa_payment,
            pkg["rubles"],
            uid,
            pkg["tokens"],
        )

        await safe_edit_text(
            callback.message,
            f"💳 Счёт на {pkg['rubles']}₽ создан.\n"
            "Перейдите по кнопке ниже, чтобы оплатить.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="💰 Оплатить в YooKassa", url=pay_url)],
                    [back_btn("pay_rub")],
                ]
            ),
        )

        # фоновая проверка статуса
        async def _check():
            try:
                for _ in range(30):
                    payment = await asyncio.to_thread(Payment.find_one, pay_id)
                    status = getattr(payment, "status", None)

                    if status == "succeeded":
                        await db.add_generations(uid, pkg["tokens"])
                        await safe_send_message(
                            bot,
                            uid,
                            f"✅ Оплата {payment.amount.value}₽ получена.\n"
                            f"🪙 Начислено {pkg['tokens']} токенов.",
                        )
                        return

                    if status in ("canceled", "expired"):
                        await safe_send_message(
                            bot,
                            uid,
                            "❌ Оплата не завершена или отменена.",
                        )
                        return

                    await asyncio.sleep(10)

                await safe_send_message(
                    bot,
                    uid,
                    "⌛ Время ожидания оплаты истекло. Если оплатили — напишите в поддержку.",
                )
            except Exception:
                logger.exception("Ошибка при проверке статуса YooKassa")
                await safe_send_message(
                    bot,
                    uid,
                    "❌ Ошибка при проверке оплаты. Если списало — свяжитесь с поддержкой.",
                )

        asyncio.create_task(_check())

    except Exception:
        logger.exception("Ошибка при создании платежа YooKassa")
        await safe_edit_text(
            callback.message,
            "❌ Не удалось создать платёж. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[back_btn("pay_rub")]],
            ),
        )


# ─────────────────────────── Регистрация хендлеров ───────────────────────────

def register_payment_handlers(dp: Dispatcher) -> None:
    """
    Регистрирует:
    - баланс / пополнение
    - Stars (инвойсы, успешные платежи)
    - YooKassa
    - /get_id, /give_tokens
    """
    # Меню: баланс / пополнение
    dp.callback_query.register(menu_balance_cb, F.data == "menu_balance")
    dp.callback_query.register(menu_topup_cb, F.data == "menu_topup")

    # Stars
    dp.callback_query.register(pay_stars_cb, F.data == "pay_stars")
    dp.callback_query.register(stars_package_cb, F.data.startswith("stars_"))
    dp.pre_checkout_query.register(on_pre_checkout)
    dp.message.register(on_successful_stars_payment, F.successful_payment)

    # YooKassa
    dp.callback_query.register(pay_rub_cb, F.data == "pay_rub")
    dp.callback_query.register(rubles_package_cb, F.data.startswith("rubles_"))

    # Команды
    dp.message.register(cmd_get_id, Command("get_id"))
    dp.message.register(cmd_give_tokens, Command("give_tokens"))
