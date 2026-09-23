"""English: lug'at, daraja testi, kunlik so'zlar va takrorlash (sof mantiq).

Lug'at `english/words.json` da. Har bir so'zning `id` si barqaror —
foydalanuvchi progressi (`en_words` jadvali) shunga bog'langan, shuning uchun
mavjud id'larni o'zgartirmang va qayta ishlatmang; yangi so'zga yangi id bering.

Telegram handlerlari `bot.py` da; bu modul faqat hisoblaydi va bazaga yozadi.
"""
import bisect
import hashlib
import json
import random
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import db

WORDS_PATH = Path(__file__).parent / "english" / "words.json"
AUDIO_DIR = Path(__file__).parent / "english" / "audio" / "words"

LEVELS = ("A1", "A2", "B1", "B2", "C1")
DAILY_NEW = 3
# Leitner: yangi so'z ertaga takrorlanadi; har to'g'ri javobdan keyin oraliq
# uzayadi. To'rt marta ketma-ket topilgan so'z — yodlangan (due = NULL).
REVIEW_INTERVALS = (1, 3, 7, 21)
LEARNED_BOX = len(REVIEW_INTERVALS)
REVIEW_LIMIT = 10          # bir o'tirishda ko'pi bilan

# Daraja testi: B1 dan boshlanadi. Har darajada har doim 6 ta savol (erta
# to'xtash yo'q — ikki javob bilan daraja hal qilinmasin), kamida 5 tasi
# to'g'ri bo'lsa — o'tdi. O'tsa yuqoriga, o'tmasa pastga. Ikki yoki uch
# daraja tekshiriladi: 12 yoki 18 savol. Taxmin bilan o'tish ehtimoli ~0.5%.
TEST_START = "B1"
TEST_PER_LEVEL = 6
TEST_PASS = 5
TEST_MIN_QUESTIONS = 2 * TEST_PER_LEVEL
TEST_MAX_QUESTIONS = 3 * TEST_PER_LEVEL
OPTIONS = 4

# Darajani qayta aniqlash — haftada bir marta (birinchi test har doim ochiq).
RETEST_DAYS = 7

GAME_QUESTIONS = 10        # o'yin: bir o'yinda savollar soni


# ── lug'at ───────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def word_audio(word_id: int) -> Path | None:
    """So'z talaffuzi — tayyor .ogg (tools/gen_word_audio.py yaratgan).
    Fayl bo'lmasa None; audio ixtiyoriy, u yo'q bo'lsa matn baribir ketadi."""
    p = AUDIO_DIR / f"{word_id}.ogg"
    return p if p.exists() else None


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
    """FSM'da saqlanadigan test holati (oddiy dict — JSON'ga ham sig'adi).
    scores: {daraja: [to'g'ri, jami]} — so'ralgan tartibda."""
    return {"level": TEST_START, "dir": None, "n": 0, "asked": [],
            "known": [], "mistakes": [], "scores": {}}


def test_pick_word(st: dict, rng: random.Random | None = None) -> int:
    rng = rng or random.Random()
    asked = set(st["asked"])
    pool = [i for i in _by_level()[st["level"]] if i not in asked]
    wid = rng.choice(pool)
    st["asked"].append(wid)
    st["n"] += 1
    return wid


def test_answer(st: dict, word_id: int, correct: bool) -> str | None:
    """Javobni hisobga oladi. Test tugasa — aniqlangan daraja, aks holda None.
    Daraja bo'yicha qaror faqat shu darajaning barcha savollaridan keyin."""
    score = st["scores"].setdefault(st["level"], [0, 0])
    score[1] += 1
    if correct:
        score[0] += 1
        st["known"].append(word_id)
    else:
        st["mistakes"].append(word_id)
    if score[1] < TEST_PER_LEVEL:
        return None
    passed = score[0] >= TEST_PASS
    failed = not passed
    i = LEVELS.index(st["level"])
    st["dir"] = st["dir"] or ("up" if passed else "down")
    if st["dir"] == "up":
        if failed:
            return st["level"]
        if i + 1 >= len(LEVELS) - 1:
            # Eng yuqori darajani tekshirish natijani o'zgartirmaydi (o'tsa ham,
            # o'tmasa ham o'sha daraja chiqadi) — ortiqcha 6 savol so'ralmaydi.
            return LEVELS[-1]
        nxt = LEVELS[i + 1]
    else:
        if passed:
            return LEVELS[i + 1]
        if i == 0:
            return st["level"]
        nxt = LEVELS[i - 1]
    st["level"] = nxt
    return None


def next_test_date(user: dict, today: date) -> date | None:
    """Darajani qayta aniqlash qachon ochiladi; hozir ochiq bo'lsa — None.
    Daraja hali yo'q bo'lsa (birinchi test) har doim ochiq. Sana test
    boshlanganda yoziladi: boshlab tashlab ketilgan test ham imkonni sarflaydi."""
    if not user.get("en_level") or not user.get("en_tested"):
        return None
    opens = date.fromisoformat(user["en_tested"]) + timedelta(days=RETEST_DAYS)
    return opens if today < opens else None


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


# ── o'yin ────────────────────────────────────────────────────────────────────
# Orqadagi so'zlardan 10 savol: darajadan pastdagi hamma so'zlar (A2 bo'lsa —
# butun A1) va foydalanuvchiga berilgan yoki testda topilgan so'zlar. Ular
# aylana bo'ylab navbat bilan chiqadi — hammasi o'tmaguncha takrorlanmaydi.
# Topilmagan so'z qaytadan yodlashga tushadi (Leitner, boshidan).

def game_pool(user_id: int, level: str) -> set[int]:
    pool = {w for lv in LEVELS[:LEVELS.index(level)] for w in _by_level()[lv]}
    return pool | (db.en_word_ids(user_id) & words().keys())


def game_key(user_id: int, word_id: int) -> int:
    """So'zning foydalanuvchi aylanasidagi o'rni. Barqaror: hovuzga yangi so'z
    qo'shilsa ham qolganlarining tartibi o'zgarmaydi (SQLite INTEGER'ga sig'adi)."""
    h = hashlib.blake2b(f"{user_id}:{word_id}".encode(), digest_size=7).digest()
    return int.from_bytes(h, "big")


def game_words(user_id: int, level: str, last: int | None,
               n: int = GAME_QUESTIONS) -> list[int]:
    """Navbatdagi n ta so'z: oxirgi javob berilgan so'zdan (`last` — uning
    kaliti) keyingilari; aylana oxiriga yetsa boshidan davom etadi."""
    ranked = sorted((game_key(user_id, w), w) for w in game_pool(user_id, level))
    start = 0 if last is None else bisect.bisect_right([k for k, _ in ranked], last)
    ordered = ranked[start:] + ranked[:start]
    return [w for _, w in ordered[:n]]


def relearn(user_id: int, word_id: int, today: date) -> None:
    """O'yinda topilmagan so'z — qaytadan yodlashga: ertadan takrorlanadi."""
    db.en_relearn(user_id, word_id, today + timedelta(days=REVIEW_INTERVALS[0]))


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
