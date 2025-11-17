# sora_handlers.py
import asyncio
import json
import logging
from typing import Optional

import aiohttp
from aiogram import Dispatcher, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from config import (
    JOBS_CREATE,
    JOBS_STATUS,
    KIE_API_KEY,
    SORA2_COST_10S,
    SORA2_COST_15S,
    SORA2_PRO_STD_10S,
    SORA2_PRO_STD_15S,
    SORA2_PRO_HD_10S,
    SORA2_PRO_HD_15S,
)
from database import db
from keyboards import (
    main_menu_keyboard,
    engine_select_keyboard,
    get_prompt_type_keyboard,
    get_model_tier_keyboard,
    get_quality_keyboard,
    get_duration_orientation_keyboard,
    get_confirmation_keyboard,
    back_btn,
)
from states import VideoCreationStates
from subscription import is_user_subscribed
from utils import (
    safe_answer,
    safe_send_message,
    safe_send_video,
    safe_edit_text,
    safe_edit_reply_markup,
)

logger = logging.getLogger(__name__)

# Текст

text_chose_model = (
    """
Sora 2

Продвинутая модель от OpenAI, которая делает очень реалистичные и плавные видео. Отлично подходит для красивых, кинематографичных роликов.

Veo 3.1

Современная модель от Google, которая быстро создаёт чёткие видео по тексту или фото. Идеальна для коротких и динамичных роликов.

Цены:

Sora 2:
        - Standart 10s = 30 
        - Standart 15s = 35
Sora 2 Pro:
        - Standart 10s = 90 
        - Standart 15s = 135
        - HD 10s = 200
        - HS 15s = 400
Veo 3.1:
        - Fast = 60
        - Quality = 250

    """
)

text_chose_sora = (
    """
✨ Sora 2

Стандартная версия модели от OpenAI. Создаёт реалистичные, плавные и красивые видео по тексту или фото. Отличный выбор для большинства задач.

🚀 Sora 2 Pro

Продвинутая версия с улучшенной детализацией, более точной анимацией и повышенным качеством картинки. Подходит, когда нужно максимально кинематографичное и эффектное видео.

⚠️ Обратите внимание:
Видео в режиме Sora 2 Pro может генерироваться дольше обычного — до 45 минут.
Это связано с повышенным качеством и более сложной обработкой сцены.
    """
)

text_chose_type = (
    """
📝 Текст → Видео

Опишите сцену словами — Sora создаст видео полностью по вашему тексту.
Подходит для любых идей, даже если у вас нет изображений.

📷 Фото → Видео

Загрузите фото, и Sora создаст видео на его основе.
⚠️ Важно: у OpenAI жёсткие ограничения на использование изображений.
Фотографии людей, лица, персональные данные и многое другое могут быть отклонены или сильно изменены моделью.
        """
)

text_chose_quality = (
    """
⚡ Стандартное качество

Быстрая генерация и хорошая детализация. Подходит для большинства обычных роликов — оптимальный баланс скорости и качества.

✨ Высокое качество

Улучшенная картинка, больше деталей и более плавные движения.
Подходит для важных и визуально насыщенных видео.
⚠️ Генерация может занимать больше времени.
    """
)

#  УТИЛИТЫ ДЛЯ РАСЧЁТА ЦЕН

def calc_cost_credits(tier: str, quality: Optional[str], duration: int) -> int:
    """
    Стоимость генерации в токенах для Sora.
    tier: 'sora2' или 'sora2_pro'
    quality: None / 'std' / 'high'
    duration: 10 или 15
    """
    if tier == "sora2":
        if duration == 10:
            return SORA2_COST_10S
        return SORA2_COST_15S

    # Sora 2 Pro
    if quality == "high":
        # HD
        if duration == 10:
            return SORA2_PRO_HD_10S
        return SORA2_PRO_HD_15S
    else:
        # Standard
        if duration == 10:
            return SORA2_PRO_STD_10S
        return SORA2_PRO_STD_15S


def duration_price_text(tier: Optional[str], quality: Optional[str]) -> str:
    """
    Текст для шага выбора длительности и ориентации.
    """
    if not tier:
        return "Выберите длительность и ориентацию:"

    if tier == "sora2":
        return (
            "Выберите длительность и ориентацию:\n\n"
            f"🧠 *Sora 2*:\n"
            f"• 10 с — *{SORA2_COST_10S}* токенов\n"
            f"• 15 с — *{SORA2_COST_15S}* токенов"
        )

    # Sora 2 Pro
    if quality == "high":
        # HD
        return (
            "Выберите длительность и ориентацию:\n\n"
            "💎 *Sora 2 Pro (HD)*:\n"
            f"• 10 с — *{SORA2_PRO_HD_10S}* токенов\n"
            f"• 15 с — *{SORA2_PRO_HD_15S}* токенов\n\n"
            "⚠️ Видео в Sora 2 Pro может создаваться до *45 минут*."
        )
    else:
        # Standard
        return (
            "Выберите длительность и ориентацию:\n\n"
            "⚡ *Sora 2 Pro (Standard)*:\n"
            f"• 10 с — *{SORA2_PRO_STD_10S}* токенов\n"
            f"• 15 с — *{SORA2_PRO_STD_15S}* токенов\n\n"
            "⚠️ Видео в Sora 2 Pro может создаваться до *45 минут*."
        )


#  МАППИНГ ДЛЯ KIE

def _kie_headers() -> dict:
    return {
        "Authorization": f"Bearer {KIE_API_KEY}",
        "Content-Type": "application/json",
    }


def _map_aspect_ratio(orientation: str) -> str:
    """
    '9:16' → 'portrait', '16:9' → 'landscape'
    """
    if orientation.strip() == "9:16":
        return "portrait"
    return "landscape"


def _map_n_frames(duration: int) -> str:
    """
    На основе длительности выставляем число кадров (примерная логика).
    """
    return "15" if int(duration) >= 15 else "10"


def _build_kie_model(prompt_type: str, tier: str, quality: Optional[str]) -> str:
    """
    Возвращает имя модели KIE для Sora.
    prompt_type: 't2v' | 'i2v'
    tier: 'sora2' | 'sora2_pro'
    """
    if prompt_type == "t2v" and tier == "sora2":
        return "sora-2-text-to-video"
    if prompt_type == "i2v" and tier == "sora2":
        return "sora-2-image-to-video"
    if prompt_type == "t2v" and tier == "sora2_pro":
        return "sora-2-pro-text-to-video"
    if prompt_type == "i2v" and tier == "sora2_pro":
        return "sora-2-pro-image-to-video"
    # запасной вариант
    return "sora-2-text-to-video"


def _input_payload(
    prompt: str,
    duration: int,
    orientation: str,
    image_url: Optional[str],
    tier: str,
    quality: Optional[str],
) -> dict:
    """
    Формирует поле "input" для запроса KIE.
    """
    payload: dict = {
        "prompt": prompt,
        "n_frames": _map_n_frames(duration),
        "remove_watermark": True,
        "aspect_ratio": _map_aspect_ratio(orientation),
    }
    if image_url:
        payload["image_urls"] = [image_url]

    if tier == "sora2_pro":
        payload["size"] = "high" if quality == "high" else "standard"

    return payload


#  МЕНЮ: СОЗДАТЬ ВИДЕО → ВЫБОР ДВИЖКА

async def menu_create_cb(callback: CallbackQuery, state: FSMContext):
    """
    Обработка кнопки '🎬 Создать видео' из главного меню (callback_data='menu_create'):
    - проверяет подписку
    - проверяет наличие токенов
    - показывает выбор движка (Sora / Veo)
    """
    bot = callback.message.bot
    uid = callback.from_user.id

    if not await is_user_subscribed(bot, uid):
        await safe_answer(
            callback.message,
            "Чтобы создать видео, сначала подпишись на канал.",
            reply_markup=subscribe_keyboard(),
        )
        return

    user = await db.get_user(uid)
    if not user or user["generations_left"] <= 0:
        await safe_edit_text(
            callback.message,
            "❌ У вас нет токенов. Нажмите «💳 Пополнить баланс».",
            reply_markup=main_menu_keyboard(),
        )
        await state.clear()
        return

    await state.clear()
    await safe_edit_text(
        callback.message,
        text_chose_model,
        reply_markup=engine_select_keyboard(),
    )


from keyboards import subscribe_keyboard


#  НАЧАЛО SORA-FSM (выбор движка = Sora)

async def engine_sora_cb(callback: CallbackQuery, state: FSMContext):
    """
    Выбор движка Sora (engine_sora) после 'Создать видео'.
    """
    await state.set_state(VideoCreationStates.waiting_for_prompt_type)
    await state.update_data(
        engine="sora",
        prompt_type=None,
        tier=None,
        quality=None,
        duration=None,
        orientation=None,
        image_url=None,
        prompt=None,
        cost=None,
        kie_model=None,
    )

    await safe_edit_text(
        callback.message,
        text_chose_type,
        reply_markup=get_prompt_type_keyboard(),
    )


#  SORA: ВЫБОР ТИПА ПРОМПТА

async def choose_prompt_type(callback: CallbackQuery, state: FSMContext):
    """
    ptype_t2v / ptype_i2v
    """
    ptype = "t2v" if callback.data == "ptype_t2v" else "i2v"
    await state.update_data(prompt_type=ptype)
    await state.set_state(VideoCreationStates.waiting_for_model_tier)

    await safe_edit_text(
        callback.message,
        text_chose_sora,
        reply_markup=get_model_tier_keyboard(selected=None),
    )


async def back_to_prompt_type(callback: CallbackQuery, state: FSMContext):
    await state.set_state(VideoCreationStates.waiting_for_prompt_type)
    await safe_edit_text(
        callback.message,
        text_chose_type,
        reply_markup=get_prompt_type_keyboard(),
    )


#  SORA: ВЫБОР МОДЕЛИ (Sora2 / Sora2 Pro)

async def choose_tier(callback: CallbackQuery, state: FSMContext):
    tier = "sora2" if callback.data == "tier_sora2" else "sora2_pro"
    await state.update_data(tier=tier)

    if tier == "sora2_pro":
        await state.set_state(VideoCreationStates.waiting_for_quality)
        await safe_edit_text(
            callback.message,
            text_chose_quality,
            reply_markup=get_quality_keyboard(selected=None),
        )
    else:
        await state.set_state(VideoCreationStates.waiting_for_duration_orientation)
        await safe_edit_text(
            callback.message,
            duration_price_text(tier, None),
            reply_markup=get_duration_orientation_keyboard(
                selected_duration=None,
                selected_orientation=None,
            ),
            parse_mode="Markdown",
        )


async def back_to_model_tier(callback: CallbackQuery, state: FSMContext):
    await state.set_state(VideoCreationStates.waiting_for_model_tier)
    await safe_edit_text(
        callback.message,
        text_chose_sora,
        reply_markup=get_model_tier_keyboard(selected=None),
    )


#  SORA: ВЫБОР КАЧЕСТВА (Pro)

async def choose_quality(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    if callback.data in {"qual_std", "qual_high"}:
        q = "std" if callback.data == "qual_std" else "high"
        await state.update_data(quality=q)
        await safe_edit_reply_markup(
            callback.message,
            reply_markup=get_quality_keyboard(selected=q),
        )
        return

    # quality_next
    tier = data.get("tier")
    q = data.get("quality")
    await state.set_state(VideoCreationStates.waiting_for_duration_orientation)
    await safe_edit_text(
        callback.message,
        duration_price_text(tier, q),
        reply_markup=get_duration_orientation_keyboard(
            selected_duration=None,
            selected_orientation=None,
        ),
        parse_mode="Markdown",
    )


#  SORA: ДЛИТЕЛЬНОСТЬ / ОРИЕНТАЦИЯ

async def back_to_quality_or_tier(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    tier = data.get("tier")
    quality = data.get("quality")

    if tier == "sora2_pro":
        await state.set_state(VideoCreationStates.waiting_for_quality)
        await safe_edit_text(
            callback.message,
            text_chose_quality,
            reply_markup=get_quality_keyboard(selected=quality),
        )
    else:
        await state.set_state(VideoCreationStates.waiting_for_model_tier)
        await safe_edit_text(
            callback.message,
            text_chose_sora,
            reply_markup=get_model_tier_keyboard(selected=tier),
        )


async def duration_cb(callback: CallbackQuery, state: FSMContext):
    dur = int(callback.data.split("_")[1])  # duration_10 / duration_15
    await state.update_data(duration=dur)

    data = await state.get_data()
    orientation = data.get("orientation")

    await safe_edit_reply_markup(
        callback.message,
        reply_markup=get_duration_orientation_keyboard(
            selected_duration=dur,
            selected_orientation=orientation,
        ),
    )


async def orientation_cb(callback: CallbackQuery, state: FSMContext):
    # orientation_9_16 / orientation_16_9
    parts = callback.data.split("_")
    orientation = f"{parts[1]}:{parts[2]}"
    await state.update_data(orientation=orientation)

    data = await state.get_data()
    duration = data.get("duration")

    await safe_edit_reply_markup(
        callback.message,
        reply_markup=get_duration_orientation_keyboard(
            selected_duration=duration,
            selected_orientation=orientation,
        ),
    )


async def back_to_duration(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    tier = data.get("tier")
    quality = data.get("quality")
    duration = data.get("duration")
    orientation = data.get("orientation")

    await state.set_state(VideoCreationStates.waiting_for_duration_orientation)
    await safe_edit_text(
        callback.message,
        duration_price_text(tier, quality),
        reply_markup=get_duration_orientation_keyboard(
            selected_duration=duration,
            selected_orientation=orientation,
        ),
        parse_mode="Markdown",
    )


async def continue_video(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    duration = data.get("duration")
    orientation = data.get("orientation")
    prompt_type = data.get("prompt_type")

    if not duration or not orientation:
        try:
            await callback.answer("❌ Выберите длительность и ориентацию!", show_alert=True)
        except Exception:
            pass
        return

    if prompt_type == "i2v":
        await state.set_state(VideoCreationStates.waiting_for_image)
        await safe_edit_text(
            callback.message,
            "📷 Отправьте изображение (как фото, не файлом).",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[back_btn("back_to_duration")]]
            ),
        )
    else:
        await state.set_state(VideoCreationStates.waiting_for_prompt)
        await safe_edit_text(
            callback.message,
            "✍️ Введите описание для видео:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[back_btn("back_to_duration")]]
            ),
        )


from aiogram.types import InlineKeyboardMarkup


#  SORA: ПРИЁМ КАРТИНКИ

async def got_image(message: Message, state: FSMContext):
    """
    Принимает фото для режима Image→Video.
    """
    ph = message.photo[-1]
    bot = message.bot
    file = await bot.get_file(ph.file_id)
    img_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"

    await state.update_data(image_url=img_url)
    await state.set_state(VideoCreationStates.waiting_for_prompt)

    await safe_answer(
        message,
        "✍️ Теперь отправьте текстовое описание для видео.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[back_btn("back_to_duration")]]
        ),
    )


async def got_not_image(message: Message, state: FSMContext):
    await safe_answer(
        message,
        "Пожалуйста, отправьте именно *фото*, не файл.",
        parse_mode="Markdown",
    )


#  SORA: ПРИЁМ ПРОМПТА, ПОДТВЕРЖДЕНИЕ

async def prompt_msg(message: Message, state: FSMContext):
    """
    Получаем текстовое описание, считаем стоимость, строим модель и показываем
    финальное подтверждение.
    """
    prompt = message.text
    await state.update_data(prompt=prompt)

    data = await state.get_data()
    prompt_type = data.get("prompt_type")
    tier = data.get("tier")
    quality = data.get("quality")
    duration = data.get("duration")
    orientation = data.get("orientation")

    kie_model = _build_kie_model(prompt_type, tier, quality)
    cost = calc_cost_credits(tier, quality, duration)
    await state.update_data(kie_model=kie_model, cost=cost)

    tier_human = "Sora 2 Pro" if tier == "sora2_pro" else "Sora 2"
    quality_human = ""
    if tier == "sora2_pro":
        quality_human = " (HD)" if quality == "high" else " (Standard)"

    mode_human = "Text→Video" if prompt_type == "t2v" else "Image→Video"

    info_lines = []
    if tier == "sora2_pro":
        info_lines.append("⚠️ В *Sora 2 Pro* видео может создаваться до *45 минут*.")
    info_lines.append("⏳ Обычно генерация занимает до 10–15 минут.")
    info_lines.append("📋 Подтвердите параметры:")
    info_lines.extend(
        [
            f"Тип: {mode_human}",
            f"Модель: {tier_human}{quality_human}",
            f"Длительность: {duration} с",
            f"Ориентация: {orientation}",
            f"💳 Стоимость: {cost} токенов",
            "",
            f"📝 {prompt}",
        ]
    )

    await safe_answer(
        message,
        "\n".join(info_lines),
        reply_markup=get_confirmation_keyboard(),
        parse_mode="Markdown",
    )


async def back_to_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(VideoCreationStates.waiting_for_prompt)
    await safe_edit_text(
        callback.message,
        "✍️ Измените описание:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[back_btn("back_to_duration")]]
        ),
    )


async def change_video(callback: CallbackQuery, state: FSMContext):
    """
    Кнопка '✏️ Изменить' → возвращаемся на шаг выбора длительности/ориентации.
    """
    data = await state.get_data()
    tier = data.get("tier")
    quality = data.get("quality")
    duration = data.get("duration")
    orientation = data.get("orientation")

    await state.set_state(VideoCreationStates.waiting_for_duration_orientation)
    await safe_edit_text(
        callback.message,
        duration_price_text(tier, quality),
        reply_markup=get_duration_orientation_keyboard(
            selected_duration=duration,
            selected_orientation=orientation,
        ),
        parse_mode="Markdown",
    )


#  SORA: ПОДТВЕРЖДЕНИЕ, СПИСАНИЕ, ЗАПУСК ЗАДАЧИ

async def confirm_video(callback: CallbackQuery, state: FSMContext):
    """
    Списываем токены, отправляем задачу в KIE и запускаем опрос статуса.
    """
    bot = callback.message.bot
    uid = callback.from_user.id

    data = await state.get_data()
    cost = int(data.get("cost") or 0)

    user = await db.get_user(uid)
    if not user or user["generations_left"] < cost:
        bal = user["generations_left"] if user else 0
        await safe_edit_text(
            callback.message,
            f"❌ Недостаточно токенов.\nНужно {cost}, у вас {bal}.",
        )
        await state.clear()
        return

    # списываем токены
    await db.update_user_generations(uid, user["generations_left"] - cost)

    await safe_edit_text(
        callback.message,
        f"🎬 Видео создаётся…\n💳 Списано {cost} токенов.",
    )

    try:
        await send_to_kie_api(
            bot=bot,
            uid=uid,
            model=data["kie_model"],
            prompt=data["prompt"],
            duration=data["duration"],
            orientation=data.get("orientation"),
            image_url=data.get("image_url"),
            cost=cost,
            tier=data.get("tier"),
            quality=data.get("quality"),
            prompt_type=data.get("prompt_type"),
        )
    except Exception as e:
        logger.exception(f"confirm_video: send_to_kie_api failed: {e}")
        # на всякий случай возвращаем токены
        await db.add_generations(uid, cost)
        await safe_send_message(
            bot,
            uid,
            "❌ Ошибка при отправке задачи в KIE. Токены возвращены.",
        )
    finally:
        await state.clear()


#  ИНТЕГРАЦИЯ С KIE (SORA)

async def send_to_kie_api(
    bot,
    uid: int,
    model: str,
    prompt: str,
    duration: int,
    orientation: str,
    image_url: Optional[str],
    cost: int,
    tier: str,
    quality: Optional[str],
    prompt_type: str,
):
    """
    Отправляет задачу в KIE jobs API и запускает опрос статуса.
    """
    payload = {
        "model": model,
        "input": _input_payload(
            prompt=prompt,
            duration=duration,
            orientation=orientation,
            image_url=image_url,
            tier=tier,
            quality=quality,
        ),
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                JOBS_CREATE,
                json=payload,
                headers=_kie_headers(),
                timeout=120,
            ) as resp:
                data = await resp.json(content_type=None)
                if resp.status != 200 or data.get("code") != 200:
                    await db.add_generations(uid, cost)
                    raise RuntimeError(f"KIE createTask error: status={resp.status}, body={data}")

                d = data.get("data") or {}
                task_id = d.get("taskId") or d.get("task_id")
                if not task_id:
                    await db.add_generations(uid, cost)
                    raise RuntimeError(f"KIE createTask: нет taskId в ответе: {data}")
    except Exception as e:
        logger.exception(f"send_to_kie_api: error: {e}")
        await db.add_generations(uid, cost)
        await safe_send_message(
            bot,
            uid,
            "❌ Не удалось создать задачу в KIE. Токены возвращены.",
        )
        raise

    # запускаем фоновой опрос статуса
    asyncio.create_task(
        check_video_status(
            bot=bot,
            uid=uid,
            task_id=task_id,
            duration=duration,
            orientation=orientation,
            cost=cost,
            tier=tier,
        )
    )


async def check_video_status(
    bot,
    uid: int,
    task_id: str,
    duration: int,
    orientation: str,
    cost: int,
    tier: str,
):
    """
    Периодически опрашивает KIE jobs/status (recordInfo) и:
    - при успехе отправляет видео пользователю
    - при ошибке/таймауте возвращает токены
    """
    # Sora 2 Pro — до 45 минут (360 * 8с ≈ 48 минут)
    max_iters = 360 if tier == "sora2_pro" else 90

    try:
        async with aiohttp.ClientSession() as session:
            for _ in range(max_iters):
                async with session.get(
                    JOBS_STATUS,
                    params={"taskId": task_id},
                    headers=_kie_headers(),
                    timeout=30,
                ) as resp:
                    result = await resp.json(content_type=None)
                    if resp.status != 200 or result.get("code") != 200:
                        await asyncio.sleep(8)
                        continue

                    d = result.get("data") or {}
                    state = (d.get("state") or "").lower()
                    flag = d.get("successFlag")

                    # still generating / in queue
                    if state in ("", "wait", "queueing", "generating") or flag == 0:
                        await asyncio.sleep(8)
                        continue

                    if state == "success" or flag == 1:
                        video_url = None
                        resp_obj = d.get("response") or {}
                        video_url = resp_obj.get("videoUrl")

                        urls = resp_obj.get("resultUrls")
                        if not video_url and isinstance(urls, list) and urls:
                            video_url = urls[0]

                        # пробуем распарсить resultJson
                        if not video_url and d.get("resultJson"):
                            try:
                                rj = d["resultJson"]
                                rj = json.loads(rj) if isinstance(rj, str) else rj
                                video_url = rj.get("result")
                                if not video_url:
                                    r_urls = rj.get("resultUrls")
                                    if isinstance(r_urls, list) and r_urls:
                                        video_url = r_urls[0]
                            except Exception:
                                pass

                        line_orient = f", 📱 {orientation}" if orientation else ""
                        await safe_send_message(
                            bot,
                            uid,
                            f"🎉 Ваше видео готово! ⏱️ {duration} с{line_orient}",
                        )

                        if video_url:
                            await safe_send_video(
                                bot,
                                uid,
                                video=video_url,
                                caption="🎬 Готовый ролик",
                            )
                            await safe_send_message(bot, uid, "🏠 Главное меню:", reply_markup=main_menu_keyboard())
                        else:
                            await safe_send_message(
                                bot,
                                uid,
                                "⚠️ Видео готово, но URL не найден в ответе KIE.",
                            )
                        return

                    # ошибка
                    fail_msg = (
                        d.get("failMsg")
                        or d.get("errorMessage")
                        or "Ошибка генерации"
                    )
                    await db.add_generations(uid, cost)
                    await safe_send_message(
                        bot,
                        uid,
                        f"❌ Генерация не удалась: {fail_msg}. Токены возвращены.",
                    )
                    return

                await asyncio.sleep(8)

            # таймаут
            await db.add_generations(uid, cost)
            await safe_send_message(
                bot,
                uid,
                "⏳ Истекло время ожидания от KIE. Токены возвращены.",
            )

    except Exception as e:
        logger.exception(f"check_video_status: error: {e}")
        await db.add_generations(uid, cost)
        await safe_send_message(
            bot,
            uid,
            "❌ Ошибка при проверке статуса видео. Токены возвращены.",
        )


#  РЕГИСТРАЦИЯ ХЕНДЛЕРОВ

def register_sora_handlers(dp: Dispatcher) -> None:
    """
    Регистрирует все хендлеры, связанные с:
    - кнопкой 'Создать видео'
    - выбором движка Sora
    - Sora FSM (тип промпта, модель, качество, дюрация, промпт, подтверждение)
    """
    # Меню → выбор движка
    dp.callback_query.register(menu_create_cb, F.data == "menu_create")

    # Движок Sora
    dp.callback_query.register(engine_sora_cb, F.data == "engine_sora")

    # Тип промпта
    dp.callback_query.register(
        choose_prompt_type,
        F.data.in_({"ptype_t2v", "ptype_i2v"}),
    )
    dp.callback_query.register(
        back_to_prompt_type,
        F.data == "back_to_prompt_type",
    )

    # Модель
    dp.callback_query.register(
        choose_tier,
        F.data.in_({"tier_sora2", "tier_sora2pro"}),
    )
    dp.callback_query.register(
        back_to_model_tier,
        F.data == "back_to_model_tier",
    )

    # Качество (Pro)
    dp.callback_query.register(
        choose_quality,
        F.data.in_({"qual_std", "qual_high", "quality_next"}),
    )

    # Длительность и ориентация
    dp.callback_query.register(
        back_to_quality_or_tier,
        F.data == "back_to_quality_or_tier",
    )
    dp.callback_query.register(
        duration_cb,
        F.data.startswith("duration_"),
    )
    dp.callback_query.register(
        orientation_cb,
        F.data.startswith("orientation_"),
    )
    dp.callback_query.register(
        back_to_duration,
        F.data == "back_to_duration",
    )
    dp.callback_query.register(
        continue_video,
        F.data == "continue_video",
    )

    from states import VideoCreationStates as VS

    dp.message.register(
        got_image,
        VS.waiting_for_image,
        F.photo,
    )
    dp.message.register(
        got_not_image,
        VS.waiting_for_image,
    )

    # Промпт
    dp.message.register(
        prompt_msg,
        VS.waiting_for_prompt,
    )

    # Подтверждение
    dp.callback_query.register(
        back_to_prompt,
        F.data == "back_to_prompt",
    )
    dp.callback_query.register(
        change_video,
        F.data == "change_video",
    )
    dp.callback_query.register(
        confirm_video,
        F.data == "confirm_video",
    )
