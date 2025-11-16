# config.py
import os
from dotenv import load_dotenv

load_dotenv()


TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise RuntimeError("TOKEN is not set in .env")

BOT_TOKEN = TOKEN


#  DATABASE
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set in .env")


#  KIE API (Sora 2 + Veo 3.1)
KIE_API_KEY = os.getenv("KIE_API_KEY")
if not KIE_API_KEY:
    raise RuntimeError("KIE_API_KEY is not set in .env")

# Базовый хост
KIE_API_BASE = os.getenv("KIE_API_BASE", "https://api.kie.ai")

# Эндпоинты Sora 2
JOBS_CREATE = os.getenv("JOBS_CREATE", f"{KIE_API_BASE}/api/v1/jobs/createTask")
JOBS_STATUS = os.getenv("JOBS_STATUS", f"{KIE_API_BASE}/api/v1/jobs/recordInfo")

# Эндпоинт Veo 3.1
VEO_URL = os.getenv("VEO_URL", f"{KIE_API_BASE}/api/v1/veo/generate")
VEO_STATUS = "https://api.kie.ai/api/v1/veo/record-info"

CHANNEL_ID_RAW = os.getenv("CHANNEL_ID", "0")
try:
    CHANNEL_ID = int(CHANNEL_ID_RAW)
except ValueError:
    raise RuntimeError(f"CHANNEL_ID must be integer chat id, got: {CHANNEL_ID_RAW!r}")

CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "")

CHANNEL_URL = os.getenv("CHANNEL_URL", "")


YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")
YOOKASSA_RETURN_URL = os.getenv("YOOKASSA_RETURN_URL")


def _int_env(name: str, default: int) -> int:
    """
    Удобный парсер int из .env с дефолтом и нормальной ошибкой.
    Например, SORA2_COST_10S=35.
    """
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        raise RuntimeError(f"{name} must be integer, got {value!r}")



SORA2_COST_10S = _int_env("SORA2_COST_10S", 30)
SORA2_COST_15S = _int_env("SORA2_COST_15S", 35)

SORA2_PRO_STD_10S = _int_env("SORA2_PRO_STD_10S", 90)
SORA2_PRO_STD_15S = _int_env("SORA2_PRO_STD_15S", 135)

SORA2_PRO_HD_10S  = _int_env("SORA2_PRO_HD_10S", 200)
SORA2_PRO_HD_15S  = _int_env("SORA2_PRO_HD_15S", 400)

VEO_FAST_COST    = _int_env("VEO_FAST_COST", 30)
VEO_QUALITY_COST = _int_env("VEO_QUALITY_COST", 45)


_admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = {683135069}
if _admin_ids_raw.strip():
    for part in _admin_ids_raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ADMIN_IDS.add(int(part))
        except ValueError:
            raise RuntimeError(f"ADMIN_IDS must be comma-separated integers, got fragment: {part!r}")


DEBUG = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes")
