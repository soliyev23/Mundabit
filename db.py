"""SQLite baza: foydalanuvchilar va haftalik baholar."""
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta

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
    allowed = ("name", "lang", "gender", "blocked")   # birth_date → change_birth_date()
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
    """Foydalanuvchini barcha ma'lumotlari bilan o'chiradi (baholar, eslatmalar).
    Qayta /start bossa, yangidan ro'yxatdan o'tadi."""
    with _conn() as c:
        c.execute("DELETE FROM week_ratings WHERE user_id = ?", (user_id,))
        c.execute("DELETE FROM reminders WHERE user_id = ?", (user_id,))
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

def get_reminders(user_id: int) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT id, text, time FROM reminders WHERE user_id = ? ORDER BY time, id",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def add_reminder(user_id: int, text: str, time: str) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO reminders (user_id, text, time) VALUES (?, ?, ?)",
            (user_id, text, time),
        )
        return cur.lastrowid


def delete_reminder(reminder_id: int, user_id: int) -> bool:
    """Faqat o'zining eslatmasini o'chira oladi."""
    with _conn() as c:
        cur = c.execute("DELETE FROM reminders WHERE id = ? AND user_id = ?",
                        (reminder_id, user_id))
        return cur.rowcount > 0


def reminders_due(hhmm: str) -> list[dict]:
    """Shu daqiqaga belgilangan eslatmalar, botni bloklamaganlar uchun."""
    with _conn() as c:
        rows = c.execute(
            """
            SELECT r.id, r.user_id, r.text, r.time, u.lang
            FROM reminders r JOIN users u ON u.user_id = r.user_id
            WHERE r.time = ? AND u.blocked = 0
            ORDER BY r.user_id, r.id
            """,
            (hhmm,),
        ).fetchall()
        return [dict(r) for r in rows]
