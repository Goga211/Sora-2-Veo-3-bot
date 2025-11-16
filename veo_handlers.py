# veo_handlers.py
import json
import logging
import random
import asyncio
from typing import List, Optional

import aiohttp
from aiogram import Dispatcher, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext

from config import (
    VEO_URL,
    KIE_API_KEY,
    VEO_FAST_COST,
    VEO_QUALITY_COST,
    VEO_STATUS,
)
from database import db
from keyboards import (
    veo_mode_keyboard,
    veo_quality_keyboard,
    get_veo_confirmation_keyboard,
    engine_select_keyboard,
    back_btn,
)
from states import VeoStates
from utils import (
    safe_answer,
    safe_send_message,
    safe_send_video,
    safe_edit_text,
)

logger = logging.getLogger(__name__)


# =====================================================
#                   ВСПОМОГАТЕЛЬНЫЕ
# =====================================================

def _veo_headers() -> dict:
    return {
        "Authorization": f"Bearer {KIE_API_KEY}",
        "Content-Type": "application/json",
    }


def _generation_type_for_mode(mode: str) -> str:
    if mode == "t2v":
        return "TEXT_2_VIDEO"
    if mode == "i2v":
        return "FIRST_AND_LAST_FRAMES_2_VIDEO"
    return "REFERENCE_2_VIDEO"


def _human_model_name(model: str) -> str:
    return "Veo 3.1 Fast" if model == "veo3_fast" else "Veo 3.1 Quality"


def _cost_for_model(model: str) -> int:
    return VEO_FAST_COST if model == "veo3_fast" else VEO_QUALITY_COST


# =====================================================
#               ОПРОС СТАТУСА VEO (taskId)
# =====================================================

async def check_veo_status(bot, uid: int, task_id: str, cost: int) -> None:

    try:
        async with aiohttp.ClientSession() as session:
            for _ in range(90):  # 12 минут ожидания

                try:
                    async with session.get(
                        VEO_STATUS,
                        params={"taskId": task_id},
                        headers=_veo_headers(),
                        timeout=30,
                    ) as resp:

                        try:
                            result = await resp.json(content_type=None)
                        except:
                            result = {"raw": await resp.text()}

                        if resp.status != 200 or result.get("code") != 200:
                            await asyncio.sleep(8)
                            continue

                        data = result.get("data") or {}
                        flag = data.get("successFlag")
                        response = data.get("response")

                        # --- генерируется ---
                        if flag == 0:
                            await asyncio.sleep(8)
                            continue

                        # --- завершено ---
                        if flag == 1:
                            video_url = None

                            if isinstance(response, dict):
                                # основной рабочий путь
                                urls = response.get("resultUrls")
                                if isinstance(urls, list) and len(urls) > 0:
                                    video_url = urls[0]

                                # запасной путь (если будет videoUrl)
                                if not video_url:
                                    video_url = (
                                        response.get("videoUrl")
                                        or response.get("video_url")
                                    )

                            if not video_url:
                                await safe_send_message(
                                    bot, uid,
                                    "⚠️ Veo 3.1 завершилось, но ссылка не найдена.\n"
                                    f"<code>{json.dumps(result, ensure_ascii=False)[:3000]}</code>"
                                )
                                return

                            # УСПЕШНО
                            await safe_send_message(bot, uid, "🎉 Ваше видео Veo 3.1 готово!")
                            await safe_send_video(
                                bot,
                                uid,
                                video_url,
                                caption="🎬 Готовый ролик (Veo 3.1)"
                            )
                            return

                        # --- ошибка ---
                        fail_msg = (
                            data.get("errorMessage")
                            or result.get("msg")
                            or "Неизвестная ошибка Veo"
                        )

                        await db.add_generations(uid, cost)
                        await safe_send_message(
                            bot, uid,
                            f"❌ Ошибка Veo 3.1: {fail_msg}. Токены возвращены."
                        )
                        return

                except Exception as e:
                    print("Polling error:", e)
                    await asyncio.sleep(8)

        # --- Таймаут ---
        await db.add_generations(uid, cost)
        await safe_send_message(
            bot, uid, "⏳ Время ожидания Veo истекло. Токены возвращены."
        )

    except Exception as e:
        await db.add_generations(uid, cost)
        await safe_send_message(bot, uid, f"❌ Критическая ошибка Veo: {e}. Токены возвращены.")




# =====================================================
#                ОСНОВНАЯ ЛОГИКА FSM
# =====================================================

async def engine_veo_cb(callback: CallbackQuery, state: FSMContext):
    await state.set_state(VeoStates.choosing_mode)
    await state.update_data(
        engine="veo",
        veo_mode=None,
        veo_model=None,
        veo_images=[],
        veo_prompt=None,
        veo_cost=None,
    )
    await safe_edit_text(
        callback.message,
        "🎥 Veo 3.1 — выберите режим:",
        reply_markup=veo_mode_keyboard(),
    )


async def back_to_engine_cb(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit_text(
        callback.message,
        "Выберите движок генерации:",
        reply_markup=engine_select_keyboard(),
    )


# =====================================================
#                      ВЫБОР РЕЖИМА
# =====================================================

async def veo_choose_mode(callback: CallbackQuery, state: FSMContext):
    mode = callback.data.replace("veo_mode_", "")
    await state.update_data(veo_mode=mode, veo_images=[], veo_model=None)

    if mode in ("t2v", "i2v"):
        await state.set_state(VeoStates.choosing_quality)
        await safe_edit_text(
            callback.message,
            "Выберите качество Veo 3.1:",
            reply_markup=veo_quality_keyboard(),
        )
    else:
        # REFERENCE_2_VIDEO = всегда veo3_fast
        await state.update_data(veo_model="veo3_fast")
        await state.set_state(VeoStates.collecting_images)
        await safe_edit_text(
            callback.message,
            "📷 Режим: Видео по референсу.\n"
            "Отправьте 1–3 фото подряд, затем текст.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[back_btn("back_to_engine")]],
            ),
        )


async def back_to_veo_mode(callback: CallbackQuery, state: FSMContext):
    await state.set_state(VeoStates.choosing_mode)
    await state.update_data(
        veo_mode=None,
        veo_model=None,
        veo_images=[],
        veo_prompt=None,
        veo_cost=None,
    )
    await safe_edit_text(
        callback.message,
        "🎥 Veo 3.1 — выберите режим:",
        reply_markup=veo_mode_keyboard(),
    )


# =====================================================
#                   ВЫБОР КАЧЕСТВА
# =====================================================

async def veo_choose_quality(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    mode = data.get("veo_mode")

    model = "veo3_fast" if callback.data == "veo_q_fast" else "veo3"
    await state.update_data(veo_model=model)

    if mode == "t2v":
        await state.set_state(VeoStates.waiting_for_prompt)
        await safe_edit_text(
            callback.message,
            f"✍️ Режим: Текст → Видео\nМодель: {_human_model_name(model)}\nВведите описание:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[back_btn("back_to_veo_mode")], [back_btn("back_to_engine")]],
            ),
        )
    else:
        await state.set_state(VeoStates.collecting_images)
        await safe_edit_text(
            callback.message,
            f"🖼 Режим: Фото → Видео\nМодель: {_human_model_name(model)}\n"
            "Отправьте 1–2 фото подряд, затем текст.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[back_btn("back_to_veo_mode")], [back_btn("back_to_engine")]],
            ),
        )


# =====================================================
#                     СБОР ФОТО
# =====================================================

async def veo_collect_image(message: Message, state: FSMContext):
    bot = message.bot
    data = await state.get_data()
    mode = data.get("veo_mode")
    images = data.get("veo_images") or []

    max_images = 2 if mode == "i2v" else 3

    if len(images) >= max_images:
        await safe_answer(message, "📷 Лимит фото достигнут. Теперь отправьте текст.")
        return

    ph = message.photo[-1]
    file = await bot.get_file(ph.file_id)
    url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"

    images.append(url)
    await state.update_data(veo_images=images)

    await safe_answer(message, f"Фото {len(images)}/{max_images} сохранено.\nТеперь отправьте текст.")


async def veo_prompt_after_images(message: Message, state: FSMContext):
    data = await state.get_data()
    model = data.get("veo_model")
    images = data.get("veo_images") or []

    if not images:
        await safe_answer(message, "Сначала отправьте фото.")
        return

    prompt = message.text
    cost = _cost_for_model(model)

    await state.update_data(veo_prompt=prompt, veo_cost=cost)
    await state.set_state(VeoStates.waiting_for_confirmation)

    await safe_answer(
        message,
        f"📋 Veo 3.1\nМодель: {_human_model_name(model)}\n"
        f"Фото: {len(images)}\n💳 Стоимость: {cost}\n\n📝 {prompt}",
        reply_markup=get_veo_confirmation_keyboard(),
    )


# =====================================================
#                 ПРОМПТ TEXT → VIDEO
# =====================================================

async def veo_prompt_t2v(message: Message, state: FSMContext):
    data = await state.get_data()
    model = data.get("veo_model")
    prompt = message.text

    cost = _cost_for_model(model)
    await state.update_data(veo_prompt=prompt, veo_cost=cost)
    await state.set_state(VeoStates.waiting_for_confirmation)

    await safe_answer(
        message,
        f"📋 Veo 3.1\nМодель: {_human_model_name(model)}\n"
        f"💳 Стоимость: {cost}\n\n📝 {prompt}",
        reply_markup=get_veo_confirmation_keyboard(),
    )


# =====================================================
#                  ПОДТВЕРЖДЕНИЕ
# =====================================================

async def change_veo(callback: CallbackQuery, state: FSMContext):
    await back_to_veo_mode(callback, state)


async def confirm_veo(callback: CallbackQuery, state: FSMContext):
    bot = callback.message.bot
    uid = callback.from_user.id
    data = await state.get_data()

    cost = data.get("veo_cost")
    model = data.get("veo_model")
    mode = data.get("veo_mode")
    images = data.get("veo_images") or []
    prompt = data.get("veo_prompt")

    # Проверка баланса
    user = await db.get_user(uid)
    if not user or user["generations_left"] < cost:
        await safe_edit_text(
            callback.message,
            f"❌ Недостаточно токенов. Нужно {cost}, у вас {user['generations_left']}.",
        )
        await state.clear()
        return

    # Списываем
    await db.update_user_generations(uid, user["generations_left"] - cost)

    await safe_edit_text(
        callback.message,
        f"🎬 Veo 3.1: видео создаётся…\n💳 Списано {cost} токенов.",
    )

    try:
        await send_to_veo_api(
            bot=bot,
            uid=uid,
            mode=mode,
            model=model,
            images=images,
            prompt=prompt,
            cost=cost,
        )
    except Exception as e:
        logger.exception(f"confirm_veo error: {e}")
        await db.add_generations(uid, cost)
        await safe_send_message(bot, uid, "❌ Ошибка Veo. Токены возвращены.")
    finally:
        await state.clear()


# =====================================================
#                ОТПРАВКА ЗАДАЧИ В VEO
# =====================================================

async def send_to_veo_api(
    bot,
    uid: int,
    mode: str,
    model: str,
    images: List[str],
    prompt: str,
    cost: int,
) -> None:

    generation_type = _generation_type_for_mode(mode)

    # REFERENCE всегда fast + 16:9
    aspect_ratio = "16:9"
    if mode == "ref":
        model = "veo3_fast"

    if mode in ("i2v", "ref") and not images:
        await db.add_generations(uid, cost)
        await safe_send_message(bot, uid, "❌ Фото не переданы. Токены возвращены.")
        return

    payload = {
        "prompt": prompt,
        "model": model,
        "aspectRatio": aspect_ratio,
        "enableTranslation": True,
        "generationType": generation_type,
        "seeds": random.randint(10000, 99999),
    }

    if images:
        payload["imageUrls"] = images

    # ——————————— HTTP запрос ———————————
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                VEO_URL,
                json=payload,
                headers=_veo_headers(),
                timeout=300,
            ) as resp:

                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    data = {"raw": await resp.text()}

                if resp.status != 200:
                    await db.add_generations(uid, cost)
                    await safe_send_message(
                        bot,
                        uid,
                        f"❌ Veo HTTP {resp.status}. Токены возвращены.\n<code>{data}</code>",
                    )
                    return

    except Exception as e:
        logger.exception(f"send_to_veo_api network error: {e}")
        await db.add_generations(uid, cost)
        await safe_send_message(bot, uid, f"❌ Ошибка сети Veo. Токены возвращены.\n{e}")
        return

    # ——————————— taskId ———————————
    root = data
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        root = data["data"]

    task_id = None
    if isinstance(root, dict):
        task_id = root.get("taskId") or root.get("task_id")

    if task_id:
        await safe_send_message(
            bot,
            uid,
            "✅ Задача Veo 3.1 принята.\n"
            "Я пришлю ролик, как только он будет готов.",
        )
        asyncio.create_task(check_veo_status(bot, uid, task_id, cost))
        return

    # ——————————— Пробуем прямой videoUrl ———————————
    video_url: Optional[str] = None

    if isinstance(root, dict):
        video_url = (
            root.get("videoUrl")
            or root.get("video_url")
            or root.get("url")
            or root.get("result")
        )

        if not video_url:
            urls = root.get("resultUrls") or root.get("result_urls")
            if isinstance(urls, list) and urls:
                video_url = urls[0]

    if video_url:
        await safe_send_message(bot, uid, "🎉 Ваше видео Veo 3.1 готово!")
        await safe_send_video(bot, uid, video_url, caption="🎬 Готовый ролик (Veo 3.1)")
        return

    # Ничего не нашли
    await safe_send_message(
        bot,
        uid,
        "⚠️ Veo 3.1: задача выполнена, но URL не найден.\n"
        f"<code>{json.dumps(data, ensure_ascii=False)[:3000]}</code>",
    )


# =====================================================
#                    РЕГИСТРАЦИЯ
# =====================================================

def register_veo_handlers(dp: Dispatcher) -> None:
    dp.callback_query.register(engine_veo_cb, F.data == "engine_veo")
    dp.callback_query.register(back_to_engine_cb, F.data == "back_to_engine")

    dp.callback_query.register(
        veo_choose_mode,
        VeoStates.choosing_mode,
        F.data.in_({"veo_mode_t2v", "veo_mode_i2v", "veo_mode_ref"}),
    )
    dp.callback_query.register(back_to_veo_mode, F.data == "back_to_veo_mode")

    dp.callback_query.register(
        veo_choose_quality,
        VeoStates.choosing_quality,
        F.data.in_({"veo_q_fast", "veo_q_quality"}),
    )

    dp.message.register(veo_collect_image, VeoStates.collecting_images, F.photo)
    dp.message.register(veo_prompt_after_images, VeoStates.collecting_images, F.text)

    dp.message.register(veo_prompt_t2v, VeoStates.waiting_for_prompt)

    dp.callback_query.register(change_veo, F.data == "change_veo")
    dp.callback_query.register(confirm_veo, F.data == "confirm_veo")
