"""Mundabit — intizom va vaqtni anglash boti.

/start → til (uz/ru) → ism → tug'ilgan sana → jins → "Hayot Kalendari".
Ism va tug'ilgan sana Telegram profilidan olinib, tasdiqlash uchun taklif
qilinadi (sana — foydalanuvchi uni ochiq qilgan va yil ko'rsatilgan bo'lsa).
Dushanba: o'tgan hafta haqida so'rov (yashil/qizil). Juma 13:00: kalendar.
"""
import asyncio
import html
import logging
import time
from datetime import date, datetime, timedelta

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
from aiogram.exceptions import TelegramForbiddenError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import db
from config import (
    ADMIN_ID,
    ADMIN_IDS,
    BOT_TOKEN,
    BROADCAST_WINDOW_MINUTES,
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


@router.message.outer_middleware()
async def clear_blocked_flag(handler, event, data):
    """Foydalanuvchi yozdi — demak bot bloklanmagan. Bloklangan deb
    belgilanganlar tarqatishdan chiqarilgan; yozgan zahoti qaytariladi."""
    user = db.get_user(event.from_user.id)
    if user and user.get("blocked"):
        db.set_blocked(event.from_user.id, False)
        log.info("Blokdan chiqdi: user_id=%s", event.from_user.id)
    return await handler(event, data)


class Onboarding(StatesGroup):
    lang = State()
    confirm_name = State()     # profildagi ism taklif qilingan, tasdiq kutilmoqda
    name = State()
    confirm_birth = State()    # profildagi sana taklif qilingan, tasdiq kutilmoqda
    birth_date = State()
    gender = State()


class Settings(StatesGroup):
    """Sozlamalar orqali ma'lumotni o'zgartirish holatlari.

    Tug'ilgan sana ataylab yo'q — u faqat admin orqali o'zgartiriladi
    (o'zgarganda db.change_birth_date baholarni real kalendar haftalariga
    qarab ko'chiradi).
    """
    name = State()
    gender = State()
    lang = State()


LANG_NAMES = {"uz": "O'zbekcha", "ru": "Русский"}


def valid_birth(d: date) -> bool:
    return d < date.today() and d.year >= 1900


def parse_birth_date(text: str) -> date | None:
    text = text.strip().replace("/", ".").replace("-", ".")
    try:
        d = datetime.strptime(text, "%d.%m.%Y").date()
    except ValueError:
        return None
    return d if valid_birth(d) else None


def webapp_keyboard(lang: str) -> InlineKeyboardMarkup | None:
    if not WEBAPP_URL:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "webapp_btn"), web_app=WebAppInfo(url=WEBAPP_URL))
    ]])


def confirm_keyboard(lang: str, prefix: str, other_key: str) -> InlineKeyboardMarkup:
    """«✅ Ha» / «✏️ Boshqa …» — callback: '<prefix>:ok' | '<prefix>:edit'."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "btn_yes"), callback_data=f"{prefix}:ok"),
        InlineKeyboardButton(text=t(lang, other_key), callback_data=f"{prefix}:edit"),
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
    # Render ~120 ms CPU oladi; alohida oqimda bajarilsa bot shu vaqtda ham
    # boshqa xabarlarga javob bera oladi.
    png = await asyncio.to_thread(
        render_life_poster, stats, db.get_week_ratings(user["user_id"]), lang,
        user.get("gender"),
    )
    caption = stats_caption(stats, lang)
    if prefix:
        caption = f"{prefix}\n\n{caption}"
    await bot.send_photo(
        user["user_id"],
        BufferedInputFile(png, filename="hayot_kalendari.png"),
        caption=caption,
        reply_markup=webapp_keyboard(lang),
    )


async def profile_birth_date(bot: Bot, user_id: int) -> date | None:
    """Telegram profilidagi tug'ilgan sana. Faqat foydalanuvchi uni hammaga
    ochiq qilgan (maxfiylik: «Everybody») va yilni ko'rsatgan bo'lsa keladi;
    aks holda None — sana qo'lda so'raladi."""
    try:
        chat = await bot.get_chat(user_id)
    except Exception as e:
        log.warning("get_chat user_id=%s: %s", user_id, e)
        return None
    bd = chat.birthdate
    if not bd or not bd.year:
        return None
    try:
        d = date(bd.year, bd.month, bd.day)
    except ValueError:
        return None
    return d if valid_birth(d) else None


async def ask_birth(message: Message, state: FSMContext, lang: str, user_id: int) -> None:
    """Tug'ilgan sana: profilda bo'lsa tasdiqlash taklif qilinadi, bo'lmasa
    qo'lda so'raladi. `message` bot xabari ham bo'lishi mumkin (callback),
    shuning uchun user_id alohida beriladi."""
    birth = await profile_birth_date(message.bot, user_id)
    if birth:
        await state.update_data(birth=birth.isoformat())
        await message.answer(
            t(lang, "confirm_birth").format(birth=fmt_date(birth, lang)),
            reply_markup=confirm_keyboard(lang, "birth", "btn_other_birth"),
        )
        await state.set_state(Onboarding.confirm_birth)
        return
    await message.answer(t(lang, "ask_birth"))
    await state.set_state(Onboarding.birth_date)


async def ask_gender(message: Message, state: FSMContext, lang: str) -> None:
    await message.answer(
        t(lang, "ask_gender"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=t(lang, "btn_male"), callback_data="setgender:m"),
            InlineKeyboardButton(text=t(lang, "btn_female"), callback_data="setgender:f"),
        ]]),
    )
    await state.set_state(Onboarding.gender)


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
    name = callback.from_user.full_name.strip()[:64]
    if name:
        await state.update_data(name=name)
        await callback.message.answer(
            f"{t(lang, 'greeting')}\n\n"
            f"{t(lang, 'confirm_name').format(name=html.escape(name))}",
            reply_markup=confirm_keyboard(lang, "name", "btn_other_name"),
        )
        await state.set_state(Onboarding.confirm_name)
        return
    await callback.message.answer(f"{t(lang, 'greeting')}\n\n{t(lang, 'ask_name')}")
    await state.set_state(Onboarding.name)


@router.callback_query(Onboarding.confirm_name, F.data.startswith("name:"))
async def process_name_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    lang = data.get("lang", "uz")
    await callback.answer()
    try:
        await callback.message.delete()  # "Ismingiz … mi?" xabari o'chadi
    except Exception:
        pass
    if callback.data == "name:ok":
        await ask_birth(callback.message, state, lang, callback.from_user.id)
        return
    await callback.message.answer(t(lang, "ask_name"))
    await state.set_state(Onboarding.name)


@router.callback_query(Onboarding.confirm_birth, F.data.startswith("birth:"))
async def process_birth_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    lang = data.get("lang", "uz")
    await callback.answer()
    try:
        await callback.message.delete()  # "Tug'ilgan sanangiz … mi?" xabari o'chadi
    except Exception:
        pass
    if callback.data == "birth:ok":
        await ask_gender(callback.message, state, lang)   # sana state'da allaqachon bor
        return
    await callback.message.answer(t(lang, "ask_birth"))
    await state.set_state(Onboarding.birth_date)


@router.message(Onboarding.name, F.text)
@router.message(Onboarding.confirm_name, F.text)
async def process_name(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = data.get("lang", "uz")
    name = message.text.strip()
    if not name or len(name) > 64:
        await message.answer(t(lang, "name_too_long"))
        return
    await state.update_data(name=name)
    await ask_birth(message, state, lang, message.from_user.id)


@router.message(Onboarding.birth_date, F.text)
@router.message(Onboarding.confirm_birth, F.text)
async def process_birth_date(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = data.get("lang", "uz")
    birth = parse_birth_date(message.text)
    if birth is None:
        await message.answer(t(lang, "bad_birth"))
        return
    await state.update_data(birth=birth.isoformat())
    await ask_gender(message, state, lang)


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


@router.message(Onboarding.confirm_name)
@router.message(Onboarding.name)
@router.message(Onboarding.confirm_birth)
@router.message(Onboarding.birth_date)
async def onboarding_non_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await message.answer(t(data.get("lang", "uz"), "text_only"))


# ── Buyruqlar ────────────────────────────────────────────────────────────────

@router.message(Command("hayot"))
async def cmd_hayot(message: Message) -> None:
    user = db.get_user(message.from_user.id)
    if not user:
        await message.answer(t(user_lang(None, message.from_user), "not_registered"))
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


BAR_W = 6          # diagramma uzunligi
LABEL_W = 12       # chapdagi nom ustuni
NUM_W = 5          # raqam ustuni — barcha bo'limlarda bir xil tekislanadi


def _bar(pct: float) -> str:
    filled = int(round(pct / 100 * BAR_W))
    return "\u2588" * filled + "\u2591" * (BAR_W - filled)


def _row(label: str, count: int, total: int) -> str:
    """Nom · son · foiz · diagramma."""
    pct = count / total * 100 if total else 0
    return f"{label:<{LABEL_W}}{count:>{NUM_W}} {pct:>3.0f}%  {_bar(pct)}"


def _plain_row(label: str, value) -> str:
    """Diagrammasiz qator (yosh, ro'yxatdan o'tish)."""
    return f"{label:<{LABEL_W}}{value:>{NUM_W}}"


def admin_summary(lang: str) -> str:
    users = db.get_all_users()
    total = len(users)
    if not total:
        return f"{t(lang, 'stats_title')}\n\n{t(lang, 'stats_empty')}"

    males = [u for u in users if u.get("gender") == "m"]
    females = [u for u in users if u.get("gender") == "f"]
    unknown = [u for u in users if not u.get("gender")]
    ratings = db.get_rating_summary()
    rated_total = ratings["good"] + ratings["bad"]

    def avg_age(group: list[dict]) -> str:
        return f"{sum(age_of(u) for u in group) / len(group):.1f}" if group else "\u2014"

    def joined_within(days: int) -> int:
        edge = date.today() - timedelta(days=days)
        return sum(1 for u in users
                   if u.get("created_at") and
                   date.fromisoformat(u["created_at"][:10]) >= edge)

    lines = [
        _plain_row(t(lang, "stats_total"), total),
        _plain_row(t(lang, "st_blocked"), sum(1 for u in users if u.get("blocked"))),
        "",
        t(lang, "sec_gender"),
        _row(t(lang, "st_male"), len(males), total),
        _row(t(lang, "st_female"), len(females), total),
        _row(t(lang, "st_unknown"), len(unknown), total),
        "",
        t(lang, "sec_lang"),
        _row(LANG_NAMES["uz"], sum(1 for u in users if u.get("lang") == "uz"), total),
        _row(LANG_NAMES["ru"], sum(1 for u in users if u.get("lang") == "ru"), total),
        "",
        t(lang, "sec_age"),
        _plain_row(t(lang, "st_avg"), avg_age(users)),
        _plain_row(t(lang, "st_male"), avg_age(males)),
        _plain_row(t(lang, "st_female"), avg_age(females)),
        "",
        t(lang, "sec_weeks"),
        _row(t(lang, "st_good"), ratings["good"], rated_total),
        _row(t(lang, "st_bad"), ratings["bad"], rated_total),
        _plain_row(t(lang, "st_rated"), f'{ratings["raters"]}/{total}'),
        "",
        t(lang, "sec_new"),
        _plain_row(t(lang, "st_today"), joined_within(0)),
        _plain_row(t(lang, "st_7d"), joined_within(7)),
        _plain_row(t(lang, "st_30d"), joined_within(30)),
    ]
    return f"{t(lang, 'stats_title')}\n\n<pre>" + "\n".join(lines) + "</pre>"


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


# ── Tushunilmagan xabarlar ─────────────────────────────────────────────────────
# Eng oxirida turishi shart: undan yuqoridagi handlerlarning hech biri mos
# kelmasa, shu ishlaydi. Ilgari bunday xabarga bot umuman javob bermasdi.

@router.message(Onboarding.lang)
@router.message(Onboarding.gender)
async def onboarding_use_buttons(message: Message, state: FSMContext) -> None:
    """Til va jins tugma orqali tanlanadi — matn yozilsa eslatib qo'yiladi."""
    data = await state.get_data()
    lang = data.get("lang") or user_lang(None, message.from_user)
    await message.answer(t(lang, "use_buttons"))


@router.message()
async def unknown_message(message: Message) -> None:
    user = db.get_user(message.from_user.id)
    lang = user_lang(user, message.from_user)
    if not user:
        await message.answer(t(lang, "not_registered"))
        return
    await message.answer(t(lang, "unknown"),
                         reply_markup=main_keyboard(lang, message.from_user.id))


# ── Rejalashtirilgan yuborishlar ─────────────────────────────────────────────

BROADCAST_MIN_DELAY = 0.1     # eng tez sur'at, userlar ko'p bo'lganda


async def spread_send(bot: Bot, users: list[dict], send_one, label: str) -> None:
    """Xabarlarni belgilangan oyna bo'ylab tekis yoyib yuboradi.

    Har xabardan keyin "qolgan vaqt ÷ qolgan foydalanuvchi" qadar kutiladi —
    sur'at o'zini to'g'irlaydi: 5 ta user bo'lsa bir necha soniyada tugaydi,
    1 000 ta bo'lsa soatga tekis yoyiladi, oynaga sig'masa minimal oraliqda
    davom etadi. Yoyilgani uchun protsessor bir joyda tiqilib qolmaydi va bot
    tarqatish paytida ham odatdagidek javob beradi.

    Botni bloklagan foydalanuvchi belgilanadi va keyingi tarqatishlarga
    qo'shilmaydi (qaytib yozsa, avtomatik tiklanadi).
    """
    window = BROADCAST_WINDOW_MINUTES * 60
    started = time.monotonic()
    sent = blocked = failed = 0
    for idx, user in enumerate(users):
        try:
            await send_one(bot, user)
            sent += 1
        except TelegramForbiddenError:
            db.set_blocked(user["user_id"], True)
            blocked += 1
        except Exception as e:
            failed += 1
            log.warning("%s yuborilmadi user_id=%s: %s", label, user["user_id"], e)
        left = len(users) - idx - 1
        if not left:
            break
        remaining = window - (time.monotonic() - started)
        await asyncio.sleep(max(BROADCAST_MIN_DELAY, remaining / left))
    log.info("%s yakunlandi: %d yuborildi, %d bloklagan, %d xato, %.1f daqiqa",
             label, sent, blocked, failed, (time.monotonic() - started) / 60)


async def monday_feedback(bot: Bot) -> None:
    """Dushanba 08:00–09:00: o'tgan hafta haqida so'rov."""
    users = db.get_active_users()
    log.info("Dushanba so'rovi boshlandi: %d ta foydalanuvchi", len(users))

    async def send_one(bot: Bot, user: dict) -> None:
        lang = user.get("lang") or "uz"
        last_week = user_stats(user).weeks_lived - 1
        if last_week < 0:
            return
        await bot.send_message(user["user_id"], t(lang, "weekly_q"),
                               reply_markup=rate_keyboard(lang, last_week))

    await spread_send(bot, users, send_one, "Dushanba so'rovi")


async def friday_calendar(bot: Bot) -> None:
    """Juma 13:00–14:00: hayot kalendarini yuborish."""
    users = db.get_active_users()
    log.info("Juma kalendari boshlandi: %d ta foydalanuvchi", len(users))
    await spread_send(bot, users, send_calendar, "Juma kalendari")


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
        BotCommand(command="help", description="Yordam"),
    ])
    await bot.set_my_commands([
        BotCommand(command="start", description="Начать"),
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
