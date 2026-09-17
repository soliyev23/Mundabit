"""English: lug'at, daraja testi, kunlik so'zlar va takrorlash (sof mantiq).

Lug'at `english/words.json` da. Har bir so'zning `id` si barqaror —
foydalanuvchi progressi (`en_words` jadvali) shunga bog'langan, shuning uchun
mavjud id'larni o'zgartirmang va qayta ishlatmang; yangi so'zga yangi id bering.

Telegram handlerlari `bot.py` da; bu modul faqat hisoblaydi va bazaga yozadi.
"""
import json
import random
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import db

WORDS_PATH = Path(__file__).parent / "english" / "words.json"

LEVELS = ("A1", "A2", "B1", "B2", "C1")
DAILY_NEW = 3
# Leitner: yangi so'z ertaga takrorlanadi; har to'g'ri javobdan keyin oraliq
# uzayadi. To'rt marta ketma-ket topilgan so'z — yodlangan (due = NULL).
REVIEW_INTERVALS = (1, 3, 7, 21)
LEARNED_BOX = len(REVIEW_INTERVALS)
REVIEW_LIMIT = 10          # bir o'tirishda ko'pi bilan

# Daraja testi: B1 dan boshlanadi; har darajada 4 tagacha savol, 3 ta to'g'ri —
# o'tdi, 2 ta xato — o'tmadi. O'tsa yuqoriga, o'tmasa pastga. Ko'pi bilan
# 3 daraja × 4 savol = 12.
TEST_START = "B1"
TEST_PER_LEVEL = 4
TEST_PASS = 3
OPTIONS = 4


# ── lug'at ───────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def words() -> dict[int, dict]:
    data = json.loads(WORDS_PATH.read_text(encoding="utf-8"))
    return {w["id"]: w for w in data["words"]}


@lru_cache(maxsize=1)
def _by_level() -> dict[str, tuple[int, ...]]:
    out: dict[str, list[int]] = {lv: [] for lv in LEVELS}
    for wid, w in words().items():
        out[w["level"]].append(wid)
    return {lv: tuple(sorted(ids)) for lv, ids in out.items()}


@lru_cache(maxsize=None)
def _by_level_pos(level: str, pos: str) -> tuple[int, ...]:
    return tuple(i for i in _by_level()[level] if words()[i]["pos"] == pos)


@lru_cache(maxsize=None)
def _by_pos(pos: str) -> tuple[int, ...]:
    return tuple(sorted(i for i, w in words().items() if w["pos"] == pos))


def level_counts() -> dict[str, int]:
    return {lv: len(ids) for lv, ids in _by_level().items()}


def translation(word_id: int, lang: str) -> str:
    w = words()[word_id]
    return w.get(lang) or w["uz"]


def user_order(user_id: int, level: str) -> list[int]:
    """Daraja ichidagi so'zlar — har foydalanuvchiga o'z aralash tartibi.
    Fayldagi tartib (A2 dan yuqorida alifbo bo'yicha) ishlatilmaydi.
    Satr urug'i bilan `random` jarayonlar orasida ham bir xil natija beradi."""
    ids = list(_by_level()[level])
    random.Random(f"{user_id}:{level}").shuffle(ids)
    return ids


def next_new_words(user_id: int, level: str, exclude: set[int],
                   n: int = DAILY_NEW) -> list[int]:
    """Foydalanuvchi darajasidan boshlab, hali berilmagan so'zlar."""
    out: list[int] = []
    for lv in LEVELS[LEVELS.index(level):]:
        for wid in user_order(user_id, lv):
            if wid not in exclude:
                out.append(wid)
                if len(out) == n:
                    return out
    return out


# ── savol ────────────────────────────────────────────────────────────────────

@dataclass
class Question:
    word_id: int
    word: str
    options: list[str]
    answer: str


def _meanings(text: str) -> set[str]:
    return {m.strip().lower() for m in text.split(",") if m.strip()}


def make_question(word_id: int, lang: str, rng: random.Random | None = None) -> Question:
    """Inglizcha so'z + 4 ta tarjima varianti. Chalg'ituvchilar — avval shu
    daraja va turkumdan, yetmasa shu turkumdan.

    Sinonimlar bir xil tarjimaga ega bo'ladi (very/really → «juda»), shuning
    uchun variantlar orasida birorta ham umumiy ma'no bo'lmasligi shart —
    aks holda savolda ikkita to'g'ri javob chiqadi. Xuddi shu inglizcha so'zning
    boshqa turkumi (work — ot/fe'l) ham chalg'ituvchi bo'lmaydi."""
    rng = rng or random.Random()
    w = words()[word_id]
    head = w["word"].lower()
    answer = translation(word_id, lang)
    options = [answer]
    used = _meanings(answer)
    for pool in (_by_level_pos(w["level"], w["pos"]), _by_pos(w["pos"]), tuple(words())):
        candidates = [i for i in pool if i != word_id]
        rng.shuffle(candidates)
        for i in candidates:
            if words()[i]["word"].lower() == head:
                continue
            tr = translation(i, lang)
            m = _meanings(tr)
            if m & used:
                continue
            options.append(tr)
            used |= m
            if len(options) == OPTIONS:
                break
        if len(options) == OPTIONS:
            break
    rng.shuffle(options)
    return Question(word_id, w["word"], options, answer)


# ── daraja testi ─────────────────────────────────────────────────────────────

def new_test() -> dict:
    """FSM'da saqlanadigan test holati (oddiy dict — JSON'ga ham sig'adi)."""
    return {"level": TEST_START, "ok": 0, "bad": 0, "dir": None,
            "n": 0, "asked": [], "known": []}


def test_pick_word(st: dict, rng: random.Random | None = None) -> int:
    rng = rng or random.Random()
    asked = set(st["asked"])
    pool = [i for i in _by_level()[st["level"]] if i not in asked]
    wid = rng.choice(pool)
    st["asked"].append(wid)
    st["n"] += 1
    return wid


def test_answer(st: dict, word_id: int, correct: bool) -> str | None:
    """Javobni hisobga oladi. Test tugasa — aniqlangan daraja, aks holda None."""
    if correct:
        st["ok"] += 1
        st["known"].append(word_id)
    else:
        st["bad"] += 1
    passed = st["ok"] >= TEST_PASS
    failed = st["bad"] > TEST_PER_LEVEL - TEST_PASS
    if not (passed or failed):
        return None
    i = LEVELS.index(st["level"])
    st["dir"] = st["dir"] or ("up" if passed else "down")
    if st["dir"] == "up":
        if failed or i == len(LEVELS) - 1:
            return st["level"]
        nxt = LEVELS[i + 1]
    else:
        if passed:
            return LEVELS[i + 1]
        if i == 0:
            return st["level"]
        nxt = LEVELS[i - 1]
    st.update(level=nxt, ok=0, bad=0)
    return None


# ── kunlik so'zlar va takrorlash ─────────────────────────────────────────────

def today_words(user_id: int, level: str, today: date) -> list[int]:
    """Bugungi so'zlar; hali berilmagan bo'lsa — tanlab yoziladi. Tanlov
    deterministik, shuning uchun 05:00 va tugma bir vaqtda chaqirsa ham
    bir xil so'zlar chiqadi (bazada kalit takrorni to'sadi)."""
    ids = db.en_today(user_id, today)
    if ids:
        return ids
    new = next_new_words(user_id, level, db.en_word_ids(user_id))
    db.en_add_new(user_id, new, today, today + timedelta(days=REVIEW_INTERVALS[0]))
    return db.en_today(user_id, today)


def due_reviews(user_id: int, today: date, limit: int = REVIEW_LIMIT) -> list[int]:
    return db.en_due(user_id, today, LEARNED_BOX, limit)


def apply_review(user_id: int, word_id: int, correct: bool, today: date) -> int:
    """To'g'ri — keyingi oraliq (oxirgisidan keyin yodlangan), xato — boshidan."""
    box = db.en_box(user_id, word_id)
    if not correct:
        new_box, due = 0, today + timedelta(days=REVIEW_INTERVALS[0])
    else:
        new_box = box + 1
        due = (today + timedelta(days=REVIEW_INTERVALS[new_box])
               if new_box < LEARNED_BOX else None)
    db.en_set_box(user_id, word_id, new_box, due)
    return new_box
