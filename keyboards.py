# keyboards.py
from typing import Optional

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import CHANNEL_URL, CHANNEL_USERNAME


#  БАЗОВЫЕ КНОПКИ

def back_btn(callback_data: str) -> InlineKeyboardButton:
    """
    Универсальная кнопка 'Назад' с заданным callback_data.
    """
    return InlineKeyboardButton(text="🔙 Назад", callback_data=callback_data)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Главное меню под сообщением:
    - Создать видео
    - Баланс
    - Пополнить баланс
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎬 Создать видео", callback_data="menu_create")],
            [InlineKeyboardButton(text="💰 Баланс",        callback_data="menu_balance")],
            [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="menu_topup")],
        ]
    )


#  ПОДПИСКА НА КАНАЛ

def subscribe_keyboard() -> InlineKeyboardMarkup:
    """
    Кнопки для проверки подписки:
    - перейти в канал
    - 'Я подписался'
    """

    if CHANNEL_URL:
        url = CHANNEL_URL
    else:
        url = f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"


    buttons = [
        [InlineKeyboardButton(text="📢 Подписаться на канал", url=url)],
        [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


#  ВЫБОР ДВИЖКА: SORA 2 / VEO 3.1

def engine_select_keyboard() -> InlineKeyboardMarkup:
    """
    Выбор между Sora 2 и Veo 3.1.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧠 Sora 2",  callback_data="engine_sora")],
            [InlineKeyboardButton(text="🎥 Veo 3.1", callback_data="engine_veo")],
            [back_btn("back_to_main")],
        ]
    )


#  SORA 2 — КЛАВИАТУРЫ FSM

def get_prompt_type_keyboard(selected: Optional[str] = None) -> InlineKeyboardMarkup:
    """
    Выбор типа промпта:
    - текст → видео
    - фото → видео
    selected: 't2v' или 'i2v'
    """
    t2v_text = "✅ Текст → Видео" if selected == "t2v" else "Текст → Видео"
    i2v_text = "✅ Фото → Видео"  if selected == "i2v" else "Фото → Видео"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t2v_text, callback_data="ptype_t2v"),
                InlineKeyboardButton(text=i2v_text, callback_data="ptype_i2v"),
            ],
            [back_btn("back_to_main")],
        ]
    )


def get_model_tier_keyboard(selected: Optional[str] = None) -> InlineKeyboardMarkup:
    """
    Выбор модели:
    - Sora 2
    - Sora 2 Pro
    selected: 'sora2' или 'sora2_pro'
    """
    sora2_text   = "✅ Sora 2"      if selected == "sora2"     else "Sora 2"
    sora2p_text  = "✅ Sora 2 Pro"  if selected == "sora2_pro" else "Sora 2 Pro"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=sora2_text,  callback_data="tier_sora2"),
                InlineKeyboardButton(text=sora2p_text, callback_data="tier_sora2pro"),
            ],
            [back_btn("back_to_prompt_type")],
        ]
    )


def get_quality_keyboard(selected: Optional[str] = None) -> InlineKeyboardMarkup:
    """
    Качество для Sora 2 Pro:
    - standard
    - high
    selected: 'std' или 'high'
    """
    std_text  = "✅ Стандарт"  if selected == "std"  else "Стандарт"
    high_text = "✅ Высокое"   if selected == "high" else "Высокое"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=std_text,  callback_data="qual_std"),
                InlineKeyboardButton(text=high_text, callback_data="qual_high"),
            ],
            [InlineKeyboardButton(text="➡️ Далее", callback_data="quality_next")],
            [back_btn("back_to_model_tier")],
        ]
    )


def get_duration_orientation_keyboard(
    selected_duration: Optional[int] = None,
    selected_orientation: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """
    Выбор длительности и ориентации видео.
    selected_duration: 10 или 15
    selected_orientation: '9:16' или '16:9'
    """
    d10_text = "✅ 10 с" if selected_duration == 10 else "10 с"
    d15_text = "✅ 15 с" if selected_duration == 15 else "15 с"

    o916_text = "✅ 9:16 (верт.)" if selected_orientation == "9:16" else "9:16 (верт.)"
    o169_text = "✅ 16:9 (гор.)" if selected_orientation == "16:9" else "16:9 (гор.)"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=d10_text, callback_data="duration_10"),
                InlineKeyboardButton(text=d15_text, callback_data="duration_15"),
            ],
            [
                InlineKeyboardButton(text=o916_text, callback_data="orientation_9_16"),
                InlineKeyboardButton(text=o169_text, callback_data="orientation_16_9"),
            ],
            [InlineKeyboardButton(text="✅ Продолжить", callback_data="continue_video")],
            [back_btn("back_to_quality_or_tier")],
        ]
    )


def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    """
    Финальное подтверждение параметров генерации (Sora 2).
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_video")],
            [InlineKeyboardButton(text="✏️ Изменить",    callback_data="change_video")],
            [back_btn("back_to_prompt")],
        ]
    )


#  VEO 3.1 — КЛАВИАТУРЫ FSM

def veo_mode_keyboard() -> InlineKeyboardMarkup:
    """
    Выбор режима Veo 3.1:
    - текст → видео
    - фото → видео
    - видео по референсу
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Текст → Видео",      callback_data="veo_mode_t2v")],
            [InlineKeyboardButton(text="🖼 Фото → Видео",       callback_data="veo_mode_i2v")],
            [InlineKeyboardButton(text="🎯 Видео по референсу", callback_data="veo_mode_ref")],
            [back_btn("back_to_engine")],
        ]
    )
    
def veo_aspect_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📺 16 : 9", callback_data="veo_ar_169"),
                InlineKeyboardButton(text="📱 9 : 16", callback_data="veo_ar_916"),
            ],
            [back_btn("back_to_veo_mode")],
        ]
    )

def veo_quality_keyboard() -> InlineKeyboardMarkup:
    """
    Выбор качества Veo 3.1:
    - Fast
    - Quality
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚡ Veo 3.1 Fast",    callback_data="veo_q_fast")],
            [InlineKeyboardButton(text="✨ Veo 3.1 Quality", callback_data="veo_q_quality")],
            [back_btn("back_to_veo_mode")],
        ]
    )


def get_veo_confirmation_keyboard() -> InlineKeyboardMarkup:
    """
    Финальное подтверждение параметров генерации (Veo 3.1).
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_veo")],
            [InlineKeyboardButton(text="✏️ Изменить",    callback_data="change_veo")],
            [back_btn("back_to_engine")],
        ]
    )
