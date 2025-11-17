# states.py
from aiogram.fsm.state import StatesGroup, State


class VideoCreationStates(StatesGroup):
    """
    FSM для Sora 2 / Sora 2 Pro (через KIE jobs API).
    """
    # 1) выбор типа промпта: текст→видео или фото→видео
    waiting_for_prompt_type = State()

    # 2) выбор модели: Sora 2 / Sora 2 Pro
    waiting_for_model_tier = State()

    # 3) выбор качества (только для Pro: standard / high)
    waiting_for_quality = State()

    # 4) выбор длительности и ориентации (10/15s, 9:16 / 16:9)
    waiting_for_duration_orientation = State()

    # 5) ожидание изображения (для image→video)
    waiting_for_image = State()

    # 6) ожидание текстового промпта
    waiting_for_prompt = State()

    # 7) финальное подтверждение параметров перед списанием токенов
    waiting_for_confirmation = State()


class VeoStates(StatesGroup):
    """
    FSM для Veo 3.1:
    - выбор режима (текст / фото / референс),
    - выбор качества (Fast / Quality),
    - сбор картинок (если надо),
    - ввод промпта,
    - подтверждение.
    """
    choosing_mode = State()

    choosing_quality = State()
        
    choosing_orientation = State()

    collecting_images = State()

    waiting_for_prompt = State()

    waiting_for_confirmation = State()


class BalanceStates(StatesGroup):
    """
    FSM для логики пополнения/оплаты (выбор способа и т.п.).
    """
    waiting_for_payment_method = State()
