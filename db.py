"""SQLite baza: foydalanuvchilar va haftalik baholar."""
import calendar
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta

from config import DB_PATH


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id    INTEGER PRIMARY KEY,
                name       TEXT NOT NULL,
                birth_date TEXT NOT NULL,          -- ISO: YYYY-MM-DD
                notify     INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS week_ratings (
                user_id    INTEGER NOT NULL,
                week_index INTEGER NOT NULL,       -- hayotdagi hafta raqami (0 dan)
                rating     TEXT NOT NULL CHECK (rating IN ('good', 'bad')),
                rated_at   TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, week_index)
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                text       TEXT NOT NULL,
                time       TEXT NOT NULL,             -- 'HH:MM', TIMEZONE (Toshkent)
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_reminders_time ON reminders(time)")
        # Migratsiya: eski jadvalga til va jins ustunlarini qo'shish
        cols = {row[1] for row in c.execute("PRAGMA table_info(users)")}
        if "lang" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN lang TEXT NOT NULL DEFAULT 'uz'")
        if "gender" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN gender TEXT")  # 'm' | 'f' | NULL
        # Eslatmalarning takrorlanishi: daily | weekdays | weekly | monthly | once
        rcols = {row[1] for row in c.execute("PRAGMA table_info(reminders)")}
        if "freq" not in rcols:
            c.execute("ALTER TABLE reminders ADD COLUMN freq TEXT NOT NULL DEFAULT 'daily'")
        if "weekday" not in rcols:
            c.execute("ALTER TABLE reminders ADD COLUMN weekday INTEGER")   # 0=Du … 6=Ya
        if "monthday" not in rcols:
            c.execute("ALTER TABLE reminders ADD COLUMN monthday INTEGER")  # 1 … 31
        if "date" not in rcols:
            c.execute("ALTER TABLE reminders ADD COLUMN date TEXT")         # once: YYYY-MM-DD
        if "photo" not in rcols:
            c.execute("ALTER TABLE reminders ADD COLUMN photo TEXT")        # Telegram file_id
        # English: yoqilganmi (standart — o'chiq, har kim o'zi yoqadi) va daraja
        if "english" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN english INTEGER NOT NULL DEFAULT 0")
        if "en_level" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN en_level TEXT")   # A1…C1 | NULL
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS en_words (
                user_id INTEGER NOT NULL,
                word_id INTEGER NOT NULL,        -- english/words.json dagi id
                box     INTEGER NOT NULL DEFAULT 0,   -- nechta ketma-ket to'g'ri takror
                due     TEXT,                    -- keyingi takror sanasi; NULL — yodlangan
                added   TEXT,                    -- kunlik so'z sifatida berilgan sana
                known   INTEGER NOT NULL DEFAULT 0,   -- testda topdi — o'rgatilmaydi
                PRIMARY KEY (user_id, word_id)
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_en_words_added ON en_words(user_id, added)")
        if "blocked" not in cols:
            # Botni bloklagan foydalanuvchi: tarqatishga qo'shilmaydi
            c.execute("ALTER TABLE users ADD COLUMN blocked INTEGER NOT NULL DEFAULT 0")
        # Olib tashlangan challenge bo'limining jadvallarini tozalash
        for table in ("challenge_checkins", "challenge_members", "challenges",
                      "space_members", "spaces"):
            c.execute(f"DROP TABLE IF EXISTS {table}")


def save_user(user_id: int, name: str, birth_date: date, lang: str, gender: str) -> None:
    with _conn() as c:
        c.execute(
            """
            INSERT INTO users (user_id, name, birth_date, lang, gender)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                name = excluded.name,
                birth_date = excluded.birth_date,
                lang = excluded.lang,
                gender = excluded.gender
            """,
            (user_id, name, birth_date.isoformat(), lang, gender),
        )


def update_user(user_id: int, **fields) -> None:
    """Faqat berilgan ustunlarni yangilaydi (sozlamalar uchun)."""
    allowed = ("name", "lang", "gender", "blocked",    # birth_date → change_birth_date()
               "english", "en_level")
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    assignments = ", ".join(f"{k} = ?" for k in cols)
    with _conn() as c:
        c.execute(
            f"UPDATE users SET {assignments} WHERE user_id = ?",
            (*cols.values(), user_id),
        )


def get_user(user_id: int) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_all_users() -> list[dict]:
    """Hammasi, ro'yxatdan o'tish tartibida (eng birinchi user — 1-o'rinda)."""
    with _conn() as c:
        rows = c.execute("SELECT * FROM users ORDER BY created_at, user_id").fetchall()
        return [dict(r) for r in rows]


def get_active_users() -> list[dict]:
    """Tarqatish uchun: botni bloklaganlar chiqarib tashlanadi."""
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM users WHERE blocked = 0 ORDER BY created_at, user_id"
        ).fetchall()
        return [dict(r) for r in rows]


def set_blocked(user_id: int, blocked: bool) -> None:
    with _conn() as c:
        c.execute("UPDATE users SET blocked = ? WHERE user_id = ?",
                  (1 if blocked else 0, user_id))


def delete_user(user_id: int) -> bool:
    """Foydalanuvchini barcha ma'lumotlari bilan o'chiradi (baholar, eslatmalar,
    English progressi). Qayta /start bossa, yangidan ro'yxatdan o'tadi."""
    with _conn() as c:
        c.execute("DELETE FROM week_ratings WHERE user_id = ?", (user_id,))
        c.execute("DELETE FROM reminders WHERE user_id = ?", (user_id,))
        c.execute("DELETE FROM en_words WHERE user_id = ?", (user_id,))
        cur = c.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        return cur.rowcount > 0


def change_birth_date(user_id: int, new_birth: date) -> int:
    """Tug'ilgan sanani o'zgartiradi va baholarni ko'chiradi.

    Baho hayotdagi hafta raqamiga bog'langan, raqam esa tug'ilgan sanadan
    hisoblanadi. Sana o'zgarsa raqamlar siljib, baholar boshqa haftaga tushib
    qolardi. Shuning uchun har bahoning haqiqiy kalendar sanasi topilib, yangi
    sanaga nisbatan qayta raqamlanadi — foydalanuvchi baholagan real haftalar
    o'z joyida qoladi. Yangi tug'ilgan sanadan oldinga tushib qolgan baholar
    o'chiriladi. Nechta baho saqlanib qolgani qaytariladi.
    """
    with _conn() as c:
        row = c.execute("SELECT birth_date FROM users WHERE user_id = ?",
                        (user_id,)).fetchone()
        if row is None:
            return 0
        old_birth = date.fromisoformat(row["birth_date"])
        ratings = c.execute(
            "SELECT week_index, rating FROM week_ratings WHERE user_id = ?", (user_id,)
        ).fetchall()

        moved: dict[int, str] = {}
        for r in ratings:
            week_start = old_birth + timedelta(days=r["week_index"] * 7)
            new_index = (week_start - new_birth).days // 7
            if new_index >= 0:
                moved[new_index] = r["rating"]

        c.execute("DELETE FROM week_ratings WHERE user_id = ?", (user_id,))
        c.executemany(
            "INSERT INTO week_ratings (user_id, week_index, rating) VALUES (?, ?, ?)",
            [(user_id, i, rt) for i, rt in moved.items()],
        )
        c.execute("UPDATE users SET birth_date = ? WHERE user_id = ?",
                  (new_birth.isoformat(), user_id))
        return len(moved)


def set_week_rating(user_id: int, week_index: int, rating: str) -> None:
    with _conn() as c:
        c.execute(
            """
            INSERT INTO week_ratings (user_id, week_index, rating)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, week_index) DO UPDATE SET
                rating = excluded.rating,
                rated_at = datetime('now')
            """,
            (user_id, week_index, rating),
        )


def get_week_ratings(user_id: int) -> dict[int, str]:
    with _conn() as c:
        rows = c.execute(
            "SELECT week_index, rating FROM week_ratings WHERE user_id = ?", (user_id,)
        ).fetchall()
        return {r["week_index"]: r["rating"] for r in rows}


def get_rating_summary() -> dict[str, int]:
    """Baholar soni va nechta foydalanuvchi baho bergani."""
    with _conn() as c:
        row = c.execute(
            """
            SELECT COALESCE(SUM(rating = 'good'), 0) AS good,
                   COALESCE(SUM(rating = 'bad'), 0)  AS bad,
                   COUNT(DISTINCT user_id)           AS raters
            FROM week_ratings
            """
        ).fetchone()
        return {"good": row["good"], "bad": row["bad"], "raters": row["raters"]}


# ── Eslatmalar ───────────────────────────────────────────────────────────────

REMINDER_FREQS = ("daily", "weekdays", "weekly", "monthly", "once")


def get_reminders(user_id: int) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            """
            SELECT id, text, time, freq, weekday, monthday, date, photo
            FROM reminders WHERE user_id = ?
            ORDER BY time, id
            """,
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def add_reminder(user_id: int, text: str, time: str, freq: str = "daily",
                 weekday: int | None = None, monthday: int | None = None,
                 on_date: date | None = None, photo: str | None = None) -> int:
    """freq bo'yicha kerakli maydon: weekly → weekday, monthly → monthday,
    once → on_date. Qolganlari e'tiborga olinmaydi. `photo` — Telegram
    file_id (fayl serverga yuklanmaydi; file_id shu botga tegishli)."""
    assert freq in REMINDER_FREQS, freq
    with _conn() as c:
        cur = c.execute(
            """
            INSERT INTO reminders (user_id, text, time, freq, weekday, monthday, date, photo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, text, time, freq,
             weekday if freq == "weekly" else None,
             monthday if freq == "monthly" else None,
             on_date.isoformat() if freq == "once" and on_date else None,
             photo),
        )
        return cur.lastrowid


def delete_reminder(reminder_id: int, user_id: int) -> bool:
    """Faqat o'zining eslatmasini o'chira oladi."""
    with _conn() as c:
        cur = c.execute("DELETE FROM reminders WHERE id = ? AND user_id = ?",
                        (reminder_id, user_id))
        return cur.rowcount > 0


def reminders_due(moment: datetime) -> list[dict]:
    """`moment` daqiqasiga (TIMEZONE bo'yicha) to'g'ri keladigan eslatmalar,
    botni bloklamaganlar uchun.

    Oylik eslatma 29–31 ga qo'yilgan bo'lsa, bunday kun yo'q oyda oxirgi
    kunida keladi (masalan 31 → 30 aprel, 28/29 fevral).
    """
    last_day = calendar.monthrange(moment.year, moment.month)[1]
    params = {
        "hhmm": moment.strftime("%H:%M"),
        "wd": moment.weekday(),
        "day": moment.day,
        "is_last": 1 if moment.day == last_day else 0,
        "date": moment.date().isoformat(),
    }
    with _conn() as c:
        rows = c.execute(
            """
            SELECT r.id, r.user_id, r.text, r.time, r.freq, r.photo, u.lang
            FROM reminders r JOIN users u ON u.user_id = r.user_id
            WHERE r.time = :hhmm AND u.blocked = 0 AND (
                   r.freq = 'daily'
                OR (r.freq = 'weekdays' AND :wd < 5)
                OR (r.freq = 'weekly'   AND r.weekday = :wd)
                OR (r.freq = 'monthly'  AND (r.monthday = :day
                                             OR (:is_last AND r.monthday > :day)))
                OR (r.freq = 'once'     AND r.date = :date)
            )
            ORDER BY r.user_id, r.id
            """,
            params,
        ).fetchall()
        return [dict(r) for r in rows]


def delete_reminders(ids: list[int]) -> None:
    """Yuborilgan bir martalik eslatmalarni o'chirish."""
    if not ids:
        return
    with _conn() as c:
        c.executemany("DELETE FROM reminders WHERE id = ?", [(i,) for i in ids])


def purge_expired_once(before: datetime) -> int:
    """Vaqti `before` dan oldin bo'lgan bir martalik eslatmalar (bot o'chiq
    turgan paytga to'g'ri kelgan va yuborilmay qolganlar) tozalanadi."""
    with _conn() as c:
        cur = c.execute(
            "DELETE FROM reminders WHERE freq = 'once' AND (date || ' ' || time) < ?",
            (before.strftime("%Y-%m-%d %H:%M"),),
        )
        return cur.rowcount


# ── English ──────────────────────────────────────────────────────────────────

def en_word_ids(user_id: int) -> set[int]:
    """Foydalanuvchiga tegishli barcha so'zlar (berilgan yoki testda topilgan)."""
    with _conn() as c:
        rows = c.execute("SELECT word_id FROM en_words WHERE user_id = ?", (user_id,))
        return {r["word_id"] for r in rows}


def en_today(user_id: int, day: date) -> list[int]:
    """Shu kuni berilgan so'zlar, berilgan tartibda."""
    with _conn() as c:
        rows = c.execute(
            "SELECT word_id FROM en_words WHERE user_id = ? AND added = ? ORDER BY rowid",
            (user_id, day.isoformat()),
        )
        return [r["word_id"] for r in rows]


def en_add_new(user_id: int, word_ids: list[int], day: date, due: date) -> None:
    """Kunlik so'zlarni yozadi. Bir vaqtda ikki joydan (05:00 va tugma)
    chaqirilsa ham takrorlanmaydi — kalit (user_id, word_id)."""
    with _conn() as c:
        c.executemany(
            """
            INSERT OR IGNORE INTO en_words (user_id, word_id, box, due, added)
            VALUES (?, ?, 0, ?, ?)
            """,
            [(user_id, w, due.isoformat(), day.isoformat()) for w in word_ids],
        )


def en_mark_known(user_id: int, word_ids: list[int]) -> None:
    with _conn() as c:
        c.executemany(
            """
            INSERT INTO en_words (user_id, word_id, known) VALUES (?, ?, 1)
            ON CONFLICT(user_id, word_id) DO UPDATE SET known = 1
            """,
            [(user_id, w) for w in word_ids],
        )


def en_due(user_id: int, day: date, max_box: int, limit: int) -> list[int]:
    """Takrorlash vaqti kelgan so'zlar (bugun berilganlari hali emas)."""
    with _conn() as c:
        rows = c.execute(
            """
            SELECT word_id FROM en_words
            WHERE user_id = ? AND known = 0 AND box < ? AND due IS NOT NULL
              AND due <= ? AND added < ?
            ORDER BY due, added, rowid
            LIMIT ?
            """,
            (user_id, max_box, day.isoformat(), day.isoformat(), limit),
        )
        return [r["word_id"] for r in rows]


def en_box(user_id: int, word_id: int) -> int:
    with _conn() as c:
        row = c.execute("SELECT box FROM en_words WHERE user_id = ? AND word_id = ?",
                        (user_id, word_id)).fetchone()
        return row["box"] if row else 0


def en_set_box(user_id: int, word_id: int, box: int, due: date | None) -> None:
    with _conn() as c:
        c.execute(
            "UPDATE en_words SET box = ?, due = ? WHERE user_id = ? AND word_id = ?",
            (box, due.isoformat() if due else None, user_id, word_id),
        )


def en_push_users() -> list[dict]:
    """05:00 da so'z oladiganlar: English yoqilgan, darajasi aniq, bloklamagan."""
    with _conn() as c:
        rows = c.execute(
            """
            SELECT * FROM users
            WHERE english = 1 AND en_level IS NOT NULL AND blocked = 0
            ORDER BY created_at, user_id
            """
        ).fetchall()
        return [dict(r) for r in rows]
