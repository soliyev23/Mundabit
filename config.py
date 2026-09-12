"""Bot sozlamalari."""
import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# O'zbekiston bo'yicha o'rtacha umr ko'rish yoshi, jins bo'yicha
LIFE_EXPECTANCY_MALE = int(os.getenv("LIFE_EXPECTANCY_MALE", "72"))
LIFE_EXPECTANCY_FEMALE = int(os.getenv("LIFE_EXPECTANCY_FEMALE", "76"))
LIFE_EXPECTANCY_DEFAULT = int(os.getenv("LIFE_EXPECTANCY_DEFAULT", "74"))
WEEKS_PER_YEAR = 52


def expectancy_for(gender: str | None) -> int:
    return {
        "m": LIFE_EXPECTANCY_MALE,
        "f": LIFE_EXPECTANCY_FEMALE,
    }.get(gender or "", LIFE_EXPECTANCY_DEFAULT)


# Dushanba: hafta yakuni so'rovi
TIMEZONE = os.getenv("TIMEZONE", "Asia/Tashkent")
NOTIFY_DAY_OF_WEEK = os.getenv("NOTIFY_DAY_OF_WEEK", "mon")
NOTIFY_HOUR = int(os.getenv("NOTIFY_HOUR", "8"))
NOTIFY_MINUTE = int(os.getenv("NOTIFY_MINUTE", "0"))

# Juma: hayot kalendarini yuborish (oyna boshlanishi)
CALENDAR_DAY_OF_WEEK = os.getenv("CALENDAR_DAY_OF_WEEK", "fri")
CALENDAR_HOUR = int(os.getenv("CALENDAR_HOUR", "13"))
CALENDAR_MINUTE = int(os.getenv("CALENDAR_MINUTE", "0"))

# Tarqatish bir zumda emas, shu oyna bo'ylab yoyiladi (daqiqa).
# Juma 13:00 → 14:00, dushanba 08:00 → 09:00. Bot shu vaqtda ham javob beradi.
BROADCAST_WINDOW_MINUTES = int(os.getenv("BROADCAST_WINDOW_MINUTES", "60"))

# Adminlar (vergul bilan). Birinchisi — asosiy: yangi user haqida xabar unga boradi.
ADMIN_IDS = [
    int(x) for x in os.getenv("ADMIN_IDS", "000000000,000000000").split(",") if x.strip()
]
ADMIN_ID = ADMIN_IDS[0]

DB_PATH = os.getenv("DB_PATH", "mundabit.db")

# Mini App: HTTPS manzil (tunnel yoki hosting). Bo'sh bo'lsa tugma ko'rsatilmaydi.
WEBAPP_URL = os.getenv("WEBAPP_URL", "")
WEBAPP_PORT = int(os.getenv("WEBAPP_PORT", "8080"))
