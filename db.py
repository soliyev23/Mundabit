"""SQLite baza: foydalanuvchilar va haftalik baholar."""
import sqlite3
from contextlib import contextmanager
from datetime import date

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
        # Migratsiya: eski jadvalga til va jins ustunlarini qo'shish
        cols = {row[1] for row in c.execute("PRAGMA table_info(users)")}
        if "lang" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN lang TEXT NOT NULL DEFAULT 'uz'")
        if "gender" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN gender TEXT")  # 'm' | 'f' | NULL
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
    allowed = ("name", "birth_date", "lang", "gender")
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
    """Ro'yxatdan o'tish tartibida (eng birinchi user — 1-o'rinda)."""
    with _conn() as c:
        rows = c.execute("SELECT * FROM users ORDER BY created_at, user_id").fetchall()
        return [dict(r) for r in rows]


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
