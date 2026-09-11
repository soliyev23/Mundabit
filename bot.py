"""Mundabit — intizom va vaqtni anglash boti.

/start → til (uz/ru) → ism → tug'ilgan sana → jins → "Hayot Kalendari".
Dushanba: o'tgan hafta haqida so'rov (yashil/qizil). Juma 13:30: kalendar.
"""
import asyncio
import html
import logging
from datetime import date, datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BotCommand,
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    MenuButtonWebApp,
    Message,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import db
from config import (
    ADMIN_ID,
    ADMIN_IDS,
    BOT_TOKEN,
    CALENDAR_DAY_OF_WEEK,
    CALENDAR_HOUR,
    CALENDAR_MINUTE,
    NOTIFY_DAY_OF_WEEK,
    NOTIFY_HOUR,
    NOTIFY_MINUTE,
    TIMEZONE,
    WEBAPP_URL,
    expectancy_for,
)
from texts import t
from visual import life_stats, render_life_poster, stats_caption
from webserver import start_webserver

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("mundabit")

router = Router()


class Onboarding(StatesGroup):
    lang = State()
    name = State()
    birth_date = State()
    gender = State()


def parse_birth_date(text: str) -> date | None:
    text = text.strip().replace("/", ".").replace("-", ".")
    try:
        d = datetime.strptime(text, "%d.%m.%Y").date()
    except ValueError:
        return None
    today = date.today()
    if d >= today or d.year < 1900:
        return None
    return d


def webapp_keyboard(lang: str) -> InlineKeyboardMarkup | None:
    if not WEBAPP_URL:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "webapp_btn"), web_app=WebAppInfo(url=WEBAPP_URL))
    ]])


def rate_keyboard(lang: str, week_index: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text=t(lang, "btn_good"),
                                 callback_data=f"rate:good:{week_index}"),
            InlineKeyboardButton(text=t(lang, "btn_bad"),
                                 callback_data=f"rate:bad:{week_index}"),
        ]]
    )


def user_stats(user: dict):
    birth = date.fromisoformat(user["birth_date"])
    return life_stats(birth, expectancy_for(user.get("gender")))


async def send_calendar(bot: Bot, user: dict, prefix: str = "") -> None:
    lang = user.get("lang") or "uz"
    stats = user_stats(user)
    png = render_life_poster(stats, db.get_week_ratings(user["user_id"]), lang,
                             user.get("gender"))
    caption = stats_caption(stats, lang)
    if prefix:
        caption = f"{prefix}\n\n{caption}"
    await bot.send_photo(
        user["user_id"],
        BufferedInputFile(png, filename="hayot_kalendari.png"),
        caption=caption,
        reply_markup=webapp_keyboard(lang),
    )


# ── Ro'yxatdan o'tish ────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = db.get_user(message.from_user.id)
    if user and user.get("gender") and user.get("lang"):
        await send_calendar(message.bot, user)
        if message.from_user.id in ADMIN_IDS:
            await message.answer("🛠 Admin Panel ↓", reply_markup=ADMIN_MAIN_KB)
        return
    await message.answer(
        "Tilni tanlang / Выберите язык:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="setlang:uz"),
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="setlang:ru"),
        ]]),
    )
    await state.set_state(Onboarding.lang)


@router.callback_query(Onboarding.lang, F.data.startswith("setlang:"))
async def process_lang(callback: CallbackQuery, state: FSMContext) -> None:
    lang = callback.data.split(":")[1]
    if lang not in ("uz", "ru"):
        await callback.answer()
        return
    await state.update_data(lang=lang)
    await callback.answer()
    try:
        await callback.message.delete()  # "Tilni tanlang" xabari o'chadi
    except Exception:
        pass
    await callback.message.answer(t(lang, "ask_name"))
    await state.set_state(Onboarding.name)


@router.message(Onboarding.name, F.text)
async def process_name(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = data.get("lang", "uz")
    name = message.text.strip()
    if not name or len(name) > 64:
        await message.answer(t(lang, "name_too_long"))
        return
    await state.update_data(name=name)
    await message.answer(t(lang, "ask_birth"))
    await state.set_state(Onboarding.birth_date)


@router.message(Onboarding.birth_date, F.text)
async def process_birth_date(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = data.get("lang", "uz")
    birth = parse_birth_date(message.text)
    if birth is None:
        await message.answer(t(lang, "bad_birth"))
        return
    await state.update_data(birth=birth.isoformat())
    await message.answer(
        t(lang, "ask_gender"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=t(lang, "btn_male"), callback_data="setgender:m"),
            InlineKeyboardButton(text=t(lang, "btn_female"), callback_data="setgender:f"),
        ]]),
    )
    await state.set_state(Onboarding.gender)


@router.callback_query(Onboarding.gender, F.data.startswith("setgender:"))
async def process_gender(callback: CallbackQuery, state: FSMContext) -> None:
    gender = callback.data.split(":")[1]
    if gender not in ("m", "f"):
        await callback.answer()
        return
    data = await state.get_data()
    lang = data.get("lang", "uz")
    is_new = db.get_user(callback.from_user.id) is None
    db.save_user(
        callback.from_user.id,
        data["name"],
        date.fromisoformat(data["birth"]),
        lang,
        gender,
    )
    await state.clear()
    await callback.answer()
    try:
        await callback.message.delete()  # "Jinsingizni tanlang" xabari o'chadi
    except Exception:
        pass

    user = db.get_user(callback.from_user.id)
    await send_calendar(callback.bot, user)
    await callback.message.answer(t(lang, "saved"))
    if is_new:
        await notify_admin_new_user(callback.bot, user, callback.from_user.username)


@router.message(Onboarding.name)
@router.message(Onboarding.birth_date)
async def onboarding_non_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await message.answer(t(data.get("lang", "uz"), "text_only"))


# ── Buyruqlar ────────────────────────────────────────────────────────────────

@router.message(Command("hayot"))
async def cmd_hayot(message: Message) -> None:
    user = db.get_user(message.from_user.id)
    if not user or not user.get("gender"):
        await message.answer(t("uz", "not_registered"))
        return
    await send_calendar(message.bot, user)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    user = db.get_user(message.from_user.id)
    lang = (user or {}).get("lang") or "uz"
    await message.answer(t(lang, "help"))


@router.callback_query(F.data.startswith("rate:"))
async def process_rating(callback: CallbackQuery) -> None:
    try:
        _, rating, idx_s = callback.data.split(":")
        week_index = int(idx_s)
        assert rating in ("good", "bad") and week_index >= 0
    except (ValueError, AssertionError):
        await callback.answer()
        return
    user = db.get_user(callback.from_user.id)
    lang = (user or {}).get("lang") or "uz"
    db.set_week_rating(callback.from_user.id, week_index, rating)
    await callback.answer(t(lang, "rating_saved"))
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


# ── Admin ────────────────────────────────────────────────────────────────────

USERS_PER_PAGE = 20
BTN_ADMIN = "🛠 Admin Panel"
BTN_USERS = "👥 Foydalanuvchilar"
BTN_STATS = "📊 Statistika"
BTN_BACK = "⬅️ Orqaga"

ADMIN_MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_ADMIN)]], resize_keyboard=True
)
ADMIN_PANEL_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_USERS), KeyboardButton(text=BTN_STATS)],
        [KeyboardButton(text=BTN_BACK)],
    ],
    resize_keyboard=True,
)


def age_of(u: dict) -> int:
    today = date.today()
    b = date.fromisoformat(u["birth_date"])
    return today.year - b.year - ((today.month, today.day) < (b.month, b.day))


def admin_summary() -> str:
    users = db.get_all_users()
    counts = db.get_rating_counts()
    males = [u for u in users if u.get("gender") == "m"]
    females = [u for u in users if u.get("gender") == "f"]
    unknown = [u for u in users if not u.get("gender")]

    def avg_age(group: list[dict]) -> str:
        return f"{sum(age_of(u) for u in group) / len(group):.1f}" if group else "—"

    return "\n".join([
        f"📊 <b>Statistika</b>\n",
        f"Foydalanuvchilar: <b>{len(users)}</b>",
        f"Erkak: {len(males)} · Ayol: {len(females)} · Belgilanmagan: {len(unknown)}",
        f"Til: uz {sum(1 for u in users if u.get('lang') == 'uz')} · "
        f"ru {sum(1 for u in users if u.get('lang') == 'ru')}",
        f"O'rtacha yosh: {avg_age(users)} (erkak {avg_age(males)} · ayol {avg_age(females)})",
        f"Hafta baholari: 🟢 {counts.get('good', 0)} · 🔴 {counts.get('bad', 0)}",
    ])


def users_table(page: int) -> tuple[str, InlineKeyboardMarkup | None]:
    """Tartibli jadval: № · Ism · Yosh · Jins · Til (user ID ko'rsatilmaydi)."""
    users = db.get_all_users()
    pages = max(1, (len(users) + USERS_PER_PAGE - 1) // USERS_PER_PAGE)
    page = max(0, min(page, pages - 1))
    chunk = users[page * USERS_PER_PAGE:(page + 1) * USERS_PER_PAGE]

    header = f"{'№':<4}{'Ism':<15}{'Yosh':<6}{'Jins':<7}{'Til'}"
    rows = []
    for i, u in enumerate(chunk, start=page * USERS_PER_PAGE + 1):
        name = html.escape(u["name"][:14])
        g = {"m": "Erkak", "f": "Ayol"}.get(u.get("gender") or "", "—")
        rows.append(f"{i:<4}{name:<15}{age_of(u):<6}{g:<7}{u.get('lang') or '—'}")

    title = f"👥 <b>Foydalanuvchilar: {len(users)}</b>"
    if pages > 1:
        title += f" · {page + 1}/{pages}"
    text = f"{title}\n<pre>{header}\n" + "\n".join(rows) + "</pre>"

    if pages == 1:
        return text, None
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"adm:users:{page - 1}"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"adm:users:{page + 1}"))
    return text, InlineKeyboardMarkup(inline_keyboard=[nav])


async def notify_admin_new_user(bot: Bot, user: dict, username: str | None) -> None:
    g = {"m": "Erkak", "f": "Ayol"}.get(user.get("gender") or "", "?")
    handle = f"@{username}" if username else "username yo'q"
    text = (
        f"🆕 <b>Yangi user!</b>\n\n"
        f"{html.escape(user['name'])} · {age_of(user)} yosh · {g} · {user.get('lang') or '?'}\n"
        f"{handle}\n\n"
        f"Jami: {len(db.get_all_users())} ta"
    )
    try:
        await bot.send_message(ADMIN_ID, text)
    except Exception as e:
        log.warning("Admin xabari yuborilmadi: %s", e)


@router.message(Command("admin"))
@router.message(F.text == BTN_ADMIN)
async def admin_panel(message: Message) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("🛠 <b>Admin Panel</b>", reply_markup=ADMIN_PANEL_KB)


@router.message(F.text == BTN_USERS)
async def admin_users(message: Message) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    text, kb = users_table(0)
    await message.answer(text, reply_markup=kb)


@router.message(F.text == BTN_STATS)
async def admin_stats(message: Message) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer(admin_summary())


@router.message(F.text == BTN_BACK)
async def admin_back(message: Message) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Asosiy menyu", reply_markup=ADMIN_MAIN_KB)


@router.callback_query(F.data.startswith("adm:users:"))
async def admin_users_nav(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    text, kb = users_table(int(callback.data.split(":")[2]))
    await callback.answer()
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass


# ── Rejalashtirilgan yuborishlar ─────────────────────────────────────────────

async def monday_feedback(bot: Bot) -> None:
    """Dushanba: o'tgan hafta haqida so'rov."""
    users = db.get_all_users()
    log.info("Dushanba so'rovi: %d ta foydalanuvchi", len(users))
    for user in users:
        if not user.get("gender"):
            continue
        lang = user.get("lang") or "uz"
        last_week = user_stats(user).weeks_lived - 1
        if last_week < 0:
            continue
        try:
            await bot.send_message(
                user["user_id"],
                t(lang, "weekly_q"),
                reply_markup=rate_keyboard(lang, last_week),
            )
        except Exception as e:
            log.warning("Dushanba yuborilmadi user_id=%s: %s", user["user_id"], e)
        await asyncio.sleep(0.1)


async def friday_calendar(bot: Bot) -> None:
    """Juma 13:30: hayot kalendarini yuborish."""
    users = db.get_all_users()
    log.info("Juma kalendari: %d ta foydalanuvchi", len(users))
    for user in users:
        if not user.get("gender"):
            continue
        try:
            await send_calendar(bot, user)
        except Exception as e:
            log.warning("Juma yuborilmadi user_id=%s: %s", user["user_id"], e)
        await asyncio.sleep(0.1)


# ── Ishga tushirish ──────────────────────────────────────────────────────────

async def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit(
            "BOT_TOKEN topilmadi. @BotFather dan token oling va .env faylga yozing."
        )
    db.init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    await bot.set_my_commands([
        BotCommand(command="start", description="Boshlash / Начать"),
        BotCommand(command="hayot", description="Hayot kalendari / Календарь жизни"),
        BotCommand(command="help", description="Yordam / Помощь"),
    ])
    if WEBAPP_URL:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Mundabit", web_app=WebAppInfo(url=WEBAPP_URL))
        )

    await start_webserver()

    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        monday_feedback,
        CronTrigger(day_of_week=NOTIFY_DAY_OF_WEEK, hour=NOTIFY_HOUR,
                    minute=NOTIFY_MINUTE, timezone=TIMEZONE),
        args=[bot],
    )
    scheduler.add_job(
        friday_calendar,
        CronTrigger(day_of_week=CALENDAR_DAY_OF_WEEK, hour=CALENDAR_HOUR,
                    minute=CALENDAR_MINUTE, timezone=TIMEZONE),
        args=[bot],
    )
    scheduler.start()

    log.info("Bot ishga tushdi.")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
