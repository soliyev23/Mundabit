"""Dev Camp o'quv rejasi — faqat admin uchun. Sof mantiq, Telegram'siz.

Reja kodda emas, `devcamp/study_plan.json` da: kun, mavzu, nima o'qish,
masalalar va tadbirlar. Faylni tahrirlab, botni qayta ishga tushirish kifoya
(reja `lru_cache` bilan bir marta o'qiladi).

Reja tugagach (oxirgi kundan keyin) `day_for()` None qaytaradi — eslatmalar
shu sababli o'z-o'zidan to'xtaydi, alohida o'chirish kerak emas.
"""
import json
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from pathlib import Path

PLAN_PATH = Path(__file__).parent / "devcamp" / "study_plan.json"

WEEKDAYS = ("Dushanba", "Seshanba", "Chorshanba", "Payshanba",
            "Juma", "Shanba", "Yakshanba")

# Kun holati: bajarildi / qisman / bajarilmadi; None — hali belgilanmagan
STATUSES = ("done", "partial", "missed")
STATUS_ICON = {"done": "✅", "partial": "⚠️", "missed": "❌"}
STATUS_WORD = {"done": "bajarildi", "partial": "qisman", "missed": "bajarilmadi"}
PENDING_ICON = "▫️"


@lru_cache(maxsize=1)
def _plan() -> dict:
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def meta() -> dict:
    return _plan()["meta"]


@lru_cache(maxsize=1)
def days() -> tuple[dict, ...]:
    return tuple(sorted(_plan()["days"], key=lambda d: d["date"]))


@lru_cache(maxsize=1)
def _by_date() -> dict[str, dict]:
    return {d["date"]: d for d in days()}


def day_for(d: date) -> dict | None:
    """Shu sanadagi kun yoki None (reja boshlanmagan/tugagan)."""
    return _by_date().get(d.isoformat())


def first_date() -> date:
    return date.fromisoformat(days()[0]["date"])


def last_date() -> date:
    return date.fromisoformat(days()[-1]["date"])


def finished(d: date) -> bool:
    """Reja shu sanada tugaganmi — eslatmalar to'xtaydi."""
    return d > last_date()


def weekday_name(d: date) -> str:
    return WEEKDAYS[d.weekday()]


def position(d: date) -> tuple[int, int]:
    """Nechanchi kun / jami (reja ichida bo'lmasa (0, jami))."""
    for n, day in enumerate(days(), 1):
        if day["date"] == d.isoformat():
            return n, len(days())
    return 0, len(days())


def events_on(d: date) -> list[dict]:
    day = day_for(d)
    return list(day["events"]) if day else []


def event_at(d: date, ev: dict) -> datetime:
    """Tadbir vaqti (mahalliy, naive) — eslatmani rejalashtirish uchun."""
    hh, mm = (int(x) for x in ev["time"].split(":"))
    return datetime.combine(d, time(hh, mm))


def upcoming_events(now: datetime, lead_minutes: int) -> list[tuple[datetime, date, dict]]:
    """Hali o'tmagan tadbirlar: (eslatma vaqti, kun, tadbir).

    Eslatma vaqti allaqachon o'tgan bo'lsa, tadbir ro'yxatga tushmaydi — bot
    qayta ishga tushganda eski eslatmalar takrorlanmasin.
    """
    out = []
    for day in days():
        d = date.fromisoformat(day["date"])
        for ev in day["events"]:
            remind = event_at(d, ev) - timedelta(minutes=lead_minutes)
            if remind > now:
                out.append((remind, d, ev))
    return sorted(out, key=lambda x: x[0])
