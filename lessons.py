"""Boshlang'ich darslar: alifbo va asosiy grammatika — sof mantiq.

Kontent `english/lessons.json` da, audio `english/audio/` da. Audio bir
martalik `tools/gen_lesson_audio.py` bilan yaratilgan — bot uni faqat
yuboradi, TTS kutubxonalari ishlab chiqarishga o'rnatilmaydi.

Lug'atdan farqi: bu yerda mashqni kod yasamaydi, u qo'lda yozilgan
(`tasks`) — grammatika savolini avtomatik yasab bo'lmaydi.
"""
import json
from functools import lru_cache
from pathlib import Path

LESSONS_PATH = Path(__file__).parent / "english" / "lessons.json"
AUDIO_DIR = Path(__file__).parent / "english" / "audio"

PASS_RATIO = 0.8          # darsni o'tish uchun kerakli ulush


@lru_cache(maxsize=1)
def lessons() -> tuple[dict, ...]:
    data = json.loads(LESSONS_PATH.read_text(encoding="utf-8"))
    return tuple(sorted(data["lessons"], key=lambda x: x["order"]))


@lru_cache(maxsize=1)
def _index() -> dict[int, dict]:
    return {x["id"]: x for x in lessons()}


def total() -> int:
    return len(lessons())


def get(lesson_id: int) -> dict | None:
    return _index().get(lesson_id)


def position(lesson_id: int) -> int:
    """Darsning ro'yxatdagi tartib raqami (1 dan)."""
    for n, les in enumerate(lessons(), 1):
        if les["id"] == lesson_id:
            return n
    return 0


def next_lesson(done: set[int]) -> dict | None:
    """Birinchi bajarilmagan dars; hammasi bajarilgan bo'lsa — None."""
    for les in lessons():
        if les["id"] not in done:
            return les
    return None


def need_correct(task_count: int) -> int:
    """Darsni o'tish uchun kamida nechta to'g'ri javob kerak."""
    return max(1, -(-int(task_count * PASS_RATIO * 100) // 100))


def passed(score: int, task_count: int) -> bool:
    return score >= need_correct(task_count)


def task_options(task: dict, lang: str) -> list[str]:
    """Variantlar odatda tildan mustaqil (harflar, inglizcha so'zlar), lekin
    tushunchani so'raydigan mashqlarda tarjima kerak — u holda {"uz": [...],
    "ru": [...]} ko'rinishida yoziladi."""
    o = task["options"]
    return list(o[lang]) if isinstance(o, dict) else list(o)


def task_answer(task: dict, lang: str) -> str:
    a = task["answer"]
    return a[lang] if isinstance(a, dict) else a


def lesson_audio(lesson_id: int) -> Path | None:
    p = AUDIO_DIR / f"lesson_{lesson_id}.ogg"
    return p if p.exists() else None


def task_audio(lesson_id: int, n: int) -> Path | None:
    """n — mashqning dars ichidagi raqami (1 dan)."""
    p = AUDIO_DIR / f"task_{lesson_id}_{n}.ogg"
    return p if p.exists() else None
