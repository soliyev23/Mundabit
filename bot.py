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
    User as TgUser,
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
from texts import BOT, fmt_date, t
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


class Settings(StatesGroup):
    """Sozlamalar orqali ma'lumotni o'zgartirish holatlari."""
    name = State()
    birth_date = State()
    gender = State()
    lang = State()


LANG_NAMES = {"uz": "O'zbekcha", "ru": "Русский"}


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


def user_lang(user: dict | None, tg_user: TgUser | None = None) -> str:
    """Til: bazadagi tanlov, u yo'q bo'lsa — Telegram interfeysi tili."""
    if user and user.get("lang"):
        return user["lang"]
    code = (tg_user.language_code or "") if tg_user else ""
    return "ru" if code.startswith("ru") else "uz"


def btn_variants(key: str) -> set[str]:
    """Tugma matni foydalanuvchi tilidan qat'i nazar tanilsin."""
    return {BOT[lang][key] for lang in BOT}


def main_keyboard(lang: str, user_id: int) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=t(lang, "btn_settings"))]]
    if user_id in ADMIN_IDS:
        rows.append([KeyboardButton(text=t(lang, "btn_admin"))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def settings_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_name"))],
            [KeyboardButton(text=t(lang, "btn_birth"))],
            [KeyboardButton(text=t(lang, "btn_gender"))],
            [KeyboardButton(text=t(lang, "btn_lang"))],
            [KeyboardButton(text=t(lang, "btn_back"))],
        ],
        resize_keyboard=True,
    )


def back_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t(lang, "btn_back"))]], resize_keyboard=True
    )


def gender_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_male")),
             KeyboardButton(text=t(lang, "btn_female"))],
            [KeyboardButton(text=t(lang, "btn_back"))],
        ],
        resize_keyboard=True,
    )


def lang_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_uz")),
             KeyboardButton(text=t(lang, "btn_ru"))],
            [KeyboardButton(text=t(lang, "btn_back"))],
        ],
        resize_keyboard=True,
    )


def settings_text(user: dict) -> str:
    lang = user.get("lang") or "uz"
    gender = {"m": t(lang, "btn_male"), "f": t(lang, "btn_female")}.get(
        user.get("gender") or "", "—"
    )
    return t(lang, "settings").format(
        name=html.escape(user["name"]),
        birth=fmt_date(date.fromisoformat(user["birth_date"]), lang),
        gender=gender,
        lang=LANG_NAMES.get(lang, lang),
    )


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
        lang = user.get("lang") or "uz"
        await send_calendar(message.bot, user)
        await message.answer(
            t(lang, "menu"),
            reply_markup=main_keyboard(lang, message.from_user.id),
        )
        return
    await message.answer(
        "Tilni tanlang / Выберите язык:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=t("uz", "btn_uz"), callback_data="setlang:uz"),
            InlineKeyboardButton(text=t("uz", "btn_ru"), callback_data="setlang:ru"),
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
    await callback.message.answer(
        t(lang, "saved"),
        reply_markup=main_keyboard(lang, callback.from_user.id),
    )
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
        await message.answer(t(user_lang(user, message.from_user), "not_registered"))
        return
    await send_calendar(message.bot, user)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    user = db.get_user(message.from_user.id)
    lang = user_lang(user, message.from_user)
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
    lang = user_lang(user, callback.from_user)
    db.set_week_rating(callback.from_user.id, week_index, rating)
    await callback.answer(t(lang, "rating_saved"))
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


# ── Sozlamalar ───────────────────────────────────────────────────────────────

async def show_settings(message: Message, state: FSMContext, prefix: str = "") -> None:
    """Sozlamalar menyusi: joriy ma'lumot + o'zgartirish tugmalari."""
    await state.clear()
    user = db.get_user(message.from_user.id)
    if not user:
        await message.answer(t(user_lang(None, message.from_user), "not_registered"))
        return
    lang = user.get("lang") or "uz"
    text = settings_text(user)
    if prefix:
        text = f"{prefix}\n\n{text}"
    await message.answer(text, reply_markup=settings_keyboard(lang))


async def ask_settings_field(message: Message, state: FSMContext, field: State,
                             key: str, keyboard) -> None:
    """Sozlamada bir maydonni so'rash: holatni o'rnatib, savol yuboradi."""
    user = db.get_user(message.from_user.id)
    if not user:
        await message.answer(t(user_lang(None, message.from_user), "not_registered"))
        return
    lang = user.get("lang") or "uz"
    await state.set_state(field)
    await message.answer(t(lang, key), reply_markup=keyboard(lang))


@router.message(Command("sozlamalar"))
@router.message(F.text.in_(btn_variants("btn_settings")))
async def settings_menu(message: Message, state: FSMContext) -> None:
    await show_settings(message, state)


@router.message(F.text.in_(btn_variants("btn_name")))
async def settings_ask_name(message: Message, state: FSMContext) -> None:
    await ask_settings_field(message, state, Settings.name, "ask_new_name",
                             back_keyboard)


@router.message(F.text.in_(btn_variants("btn_birth")))
async def settings_ask_birth(message: Message, state: FSMContext) -> None:
    await ask_settings_field(message, state, Settings.birth_date, "ask_new_birth",
                             back_keyboard)


@router.message(F.text.in_(btn_variants("btn_gender")))
async def settings_ask_gender(message: Message, state: FSMContext) -> None:
    await ask_settings_field(message, state, Settings.gender, "ask_gender",
                             gender_keyboard)


@router.message(F.text.in_(btn_variants("btn_lang")))
async def settings_ask_lang(message: Message, state: FSMContext) -> None:
    await ask_settings_field(message, state, Settings.lang, "ask_lang",
                             lang_keyboard)


@router.message(Settings.name, F.text)
async def settings_save_name(message: Message, state: FSMContext) -> None:
    if message.text in btn_variants("btn_back"):
        await show_settings(message, state)
        return
    user = db.get_user(message.from_user.id)
    lang = user_lang(user, message.from_user)
    name = message.text.strip()
    if not name or len(name) > 64:
        await message.answer(t(lang, "name_too_long"))
        return
    db.update_user(message.from_user.id, name=name)
    await show_settings(message, state, prefix=t(lang, "updated"))


@router.message(Settings.birth_date, F.text)
async def settings_save_birth(message: Message, state: FSMContext) -> None:
    if message.text in btn_variants("btn_back"):
        await show_settings(message, state)
        return
    user = db.get_user(message.from_user.id)
    lang = user_lang(user, message.from_user)
    birth = parse_birth_date(message.text)
    if birth is None:
        await message.answer(t(lang, "bad_birth"))
        return
    db.update_user(message.from_user.id, birth_date=birth.isoformat())
    await show_settings(message, state, prefix=t(lang, "updated"))
    await send_calendar(message.bot, db.get_user(message.from_user.id))


@router.message(Settings.gender, F.text)
async def settings_save_gender(message: Message, state: FSMContext) -> None:
    if message.text in btn_variants("btn_back"):
        await show_settings(message, state)
        return
    user = db.get_user(message.from_user.id)
    lang = user_lang(user, message.from_user)
    if message.text in btn_variants("btn_male"):
        gender = "m"
    elif message.text in btn_variants("btn_female"):
        gender = "f"
    else:
        await message.answer(t(lang, "ask_gender"), reply_markup=gender_keyboard(lang))
        return
    db.update_user(message.from_user.id, gender=gender)
    await show_settings(message, state, prefix=t(lang, "updated"))
    await send_calendar(message.bot, db.get_user(message.from_user.id))


@router.message(Settings.lang, F.text)
async def settings_save_lang(message: Message, state: FSMContext) -> None:
    user = db.get_user(message.from_user.id)
    lang = user_lang(user, message.from_user)
    if message.text in btn_variants("btn_back"):
        await show_settings(message, state)
        return
    if message.text in btn_variants("btn_uz"):
        new_lang = "uz"
    elif message.text in btn_variants("btn_ru"):
        new_lang = "ru"
    else:
        await message.answer(t(lang, "ask_lang"), reply_markup=lang_keyboard(lang))
        return
    db.update_user(message.from_user.id, lang=new_lang)
    # Bundan keyingi barcha javoblar — kalendar posteri ham — yangi tilda
    await show_settings(message, state, prefix=t(new_lang, "updated"))
    await send_calendar(message.bot, db.get_user(message.from_user.id))


@router.message(Settings.name)
@router.message(Settings.birth_date)
@router.message(Settings.gender)
@router.message(Settings.lang)
async def settings_non_text(message: Message) -> None:
    user = db.get_user(message.from_user.id)
    await message.answer(t(user_lang(user, message.from_user), "text_only"))


@router.message(F.text.in_(btn_variants("btn_back")))
async def go_back(message: Message, state: FSMContext) -> None:
    """Sozlamalardan ham, admin paneldan ham asosiy menyuga qaytaradi."""
    await state.clear()
    user = db.get_user(message.from_user.id)
    lang = user_lang(user, message.from_user)
    await message.answer(t(lang, "menu"),
                         reply_markup=main_keyboard(lang, message.from_user.id))


# ── Admin ────────────────────────────────────────────────────────────────────

USERS_PER_PAGE = 20


def admin_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_users")),
             KeyboardButton(text=t(lang, "btn_stats"))],
            [KeyboardButton(text=t(lang, "btn_back"))],
        ],
        resize_keyboard=True,
    )


def age_of(u: dict) -> int:
    today = date.today()
    b = date.fromisoformat(u["birth_date"])
    return today.year - b.year - ((today.month, today.day) < (b.month, b.day))


def admin_summary(lang: str) -> str:
    users = db.get_all_users()
    counts = db.get_rating_counts()
    males = [u for u in users if u.get("gender") == "m"]
    females = [u for u in users if u.get("gender") == "f"]
    unknown = [u for u in users if not u.get("gender")]

    def avg_age(group: list[dict]) -> str:
        return f"{sum(age_of(u) for u in group) / len(group):.1f}" if group else "—"

    return t(lang, "stats").format(
        total=len(users),
        males=len(males),
        females=len(females),
        unknown=len(unknown),
        uz=sum(1 for u in users if u.get("lang") == "uz"),
        ru=sum(1 for u in users if u.get("lang") == "ru"),
        avg=avg_age(users),
        avg_m=avg_age(males),
        avg_f=avg_age(females),
        good=counts.get("good", 0),
        bad=counts.get("bad", 0),
    )


def users_table(page: int, lang: str) -> tuple[str, InlineKeyboardMarkup | None]:
    """Tartibli jadval: № · Ism · Yosh · Jins · Til (user ID ko'rsatilmaydi)."""
    users = db.get_all_users()
    pages = max(1, (len(users) + USERS_PER_PAGE - 1) // USERS_PER_PAGE)
    page = max(0, min(page, pages - 1))
    chunk = users[page * USERS_PER_PAGE:(page + 1) * USERS_PER_PAGE]

    header = (f"{'№':<4}{t(lang, 'col_name'):<15}{t(lang, 'col_age'):<6}"
              f"{t(lang, 'col_gender'):<6}{t(lang, 'col_lang')}")
    rows = []
    for i, u in enumerate(chunk, start=page * USERS_PER_PAGE + 1):
        # Tekislash buzilmasligi uchun avval bo'shliq qo'shiladi, keyin escape
        name = html.escape(u["name"][:14].ljust(15))
        g = {"m": t(lang, "g_m"), "f": t(lang, "g_f")}.get(u.get("gender") or "", "—")
        rows.append(f"{i:<4}{name}{age_of(u):<6}{g:<6}{u.get('lang') or '—'}")

    title = t(lang, "users_title").format(total=len(users))
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
    lang = user_lang(db.get_user(ADMIN_ID))          # xabar admin tilida yoziladi
    text = t(lang, "new_user").format(
        name=html.escape(user["name"]),
        age=age_of(user),
        gender={"m": t(lang, "g_m"), "f": t(lang, "g_f")}.get(user.get("gender") or "", "?"),
        lang=user.get("lang") or "?",
        handle=f"@{username}" if username else t(lang, "no_username"),
        total=len(db.get_all_users()),
    )
    try:
        await bot.send_message(ADMIN_ID, text)
    except Exception as e:
        log.warning("Admin xabari yuborilmadi: %s", e)


@router.message(Command("admin"))
@router.message(F.text.in_(btn_variants("btn_admin")))
async def admin_panel(message: Message) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    lang = user_lang(db.get_user(message.from_user.id), message.from_user)
    await message.answer(t(lang, "admin_title"), reply_markup=admin_keyboard(lang))


@router.message(F.text.in_(btn_variants("btn_users")))
async def admin_users(message: Message) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    lang = user_lang(db.get_user(message.from_user.id), message.from_user)
    text, kb = users_table(0, lang)
    await message.answer(text, reply_markup=kb)


@router.message(F.text.in_(btn_variants("btn_stats")))
async def admin_stats(message: Message) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    lang = user_lang(db.get_user(message.from_user.id), message.from_user)
    await message.answer(admin_summary(lang))


@router.callback_query(F.data.startswith("adm:users:"))
async def admin_users_nav(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    lang = user_lang(db.get_user(callback.from_user.id), callback.from_user)
    text, kb = users_table(int(callback.data.split(":")[2]), lang)
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

    # Buyruqlar ro'yxati Telegram interfeysi tiliga qarab ko'rsatiladi
    await bot.set_my_commands([
        BotCommand(command="start", description="Boshlash"),
        BotCommand(command="hayot", description="Hayot kalendari"),
        BotCommand(command="help", description="Yordam"),
    ])
    await bot.set_my_commands([
        BotCommand(command="start", description="Начать"),
        BotCommand(command="hayot", description="Календарь жизни"),
        BotCommand(command="help", description="Помощь"),
    ], language_code="ru")
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
