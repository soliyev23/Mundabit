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
from zoneinfo import ZoneInfo

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
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import db
import english
from config import (
    ADMIN_ID,
    ADMIN_IDS,
    BOT_TOKEN,
    BROADCAST_WINDOW_MINUTES,
    CALENDAR_DAY_OF_WEEK,
    CALENDAR_HOUR,
    CALENDAR_MINUTE,
    EN_HOUR,
    EN_MINUTE,
    NOTIFY_DAY_OF_WEEK,
    NOTIFY_HOUR,
    NOTIFY_MINUTE,
    TIMEZONE,
    WEBAPP_URL,
    expectancy_for,
)
from texts import (BOT, LEGACY_BUTTONS, POS_NAMES, WEEKDAYS_EVERY, WEEKDAYS_FULL,
                   fmt_date, fmt_day_month, t)
from visual import life_stats, render_life_poster, stats_caption
from webserver import start_webserver

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("mundabit")
# Eslatma vazifasi har daqiqada ishlaydi — APScheduler har safar ikki satr
# yozadi (kuniga ~2 900 ta). Jurnal cheklangani uchun faqat ogohlantirishlar.
logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)

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


class Suggest(StatesGroup):
    """Foydalanuvchi murojaati — adminga yuboriladi."""
    text = State()


class AdminReply(StatesGroup):
    """Admin murojaatga javob yozmoqda; FSM'da kimga yozilayotgani saqlanadi."""
    text = State()


class Broadcast(StatesGroup):
    """Admin barchaga xabar: avval xabar, keyin tasdiq."""
    message = State()
    confirm = State()


class Reminder(StatesGroup):
    """Eslatmalar menyusi, o'chirish va qo'shish: nom → rasm (ixtiyoriy) →
    takrorlanish → (hafta kuni | oy sanasi | sana) → soat."""
    menu = State()     # ro'yxat ko'rsatilgan
    delete = State()   # nomlar klaviaturada; FSM'da tugma matni → id
    text = State()
    photo = State()
    freq = State()
    weekday = State()
    monthday = State()
    date = State()
    time = State()


class EnglishTest(StatesGroup):
    """Daraja testi: tanishtiruv → savollar. FSM'da test holati (english.new_test)."""
    intro = State()
    question = State()


class EnglishReview(StatesGroup):
    """Takrorlash savollari; FSM'da navbat va joriy savol."""
    question = State()


LANG_NAMES = {"uz": "O'zbekcha", "ru": "Русский"}
MAX_REMINDERS = 5
REMINDER_TEXT_MAX = 100
SUGGESTION_MAX = 1000


def valid_birth(d: date) -> bool:
    return d < date.today() and d.year >= 1900


def esc(text: str) -> str:
    """Xabar matnini HTML uchun xavfsiz qiladi: faqat <, > va & qochiriladi.

    `html.escape` apostrofni ham `&#x27;` ga aylantiradi — o'zbekcha matnda
    apostrof ko'p (o'qish, tug'ilgan), shuning uchun qo'shtirnoqlar tegilmaydi.
    Matn faqat xabar ichida ishlatiladi, HTML atributida emas.
    """
    return html.escape(text, quote=False)


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
    """Tugma matni foydalanuvchi tilidan qat'i nazar tanilsin (nomi
    o'zgargan tugmaning eski matni ham — LEGACY_BUTTONS)."""
    return {BOT[lang][key] for lang in BOT} | LEGACY_BUTTONS.get(key, set())


def main_keyboard(lang: str, user_id: int) -> ReplyKeyboardMarkup:
    user = db.get_user(user_id)
    second = [KeyboardButton(text=t(lang, "btn_settings"))]
    if user and user.get("english"):
        second.insert(0, KeyboardButton(text=t(lang, "btn_english")))
    rows = [
        [KeyboardButton(text=t(lang, "btn_reminder")),
         KeyboardButton(text=t(lang, "btn_suggest"))],
        second,
    ]
    if user_id in ADMIN_IDS:
        rows.append([KeyboardButton(text=t(lang, "btn_admin"))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def settings_keyboard(lang: str, english_on: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_name"))],
            [KeyboardButton(text=t(lang, "btn_gender"))],
            [KeyboardButton(text=t(lang, "btn_lang"))],
            [KeyboardButton(text=t(lang, "btn_en_off" if english_on else "btn_en_on"))],
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
        name=esc(user["name"]),
        birth=fmt_date(date.fromisoformat(user["birth_date"]), lang),
        gender=gender,
        lang=LANG_NAMES.get(lang, lang),
        english=t(lang, "en_state_on" if user.get("english") else "en_state_off"),
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
            f"{t(lang, 'confirm_name').format(name=esc(name))}",
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
    # Savol xabari butunlay o'chiriladi (chat toza qolsin). Telegram bot xabarini
    # 48 soatgacha o'chirishga ruxsat beradi; kechroq javob berilsa o'chirish
    # rad etiladi — u holda hech bo'lmasa tugmalar olib tashlanadi.
    try:
        await callback.message.delete()
    except Exception:
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
    await message.answer(text, reply_markup=settings_keyboard(lang, bool(user.get("english"))))


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
    """Sozlamalardan ham, admin paneldan ham asosiy menyuga qaytaradi.
    Eslatma qo'shish jarayonidan esa eslatmalar ro'yxatiga."""
    current = await state.get_state()
    user = db.get_user(message.from_user.id)
    lang = user_lang(user, message.from_user)
    if user and current and current.startswith("Reminder:") \
            and current != Reminder.menu.state:
        await show_reminders(message, state, lang)
        return
    await state.clear()
    await message.answer(t(lang, "menu"),
                         reply_markup=main_keyboard(lang, message.from_user.id))


# ── Murojaat ─────────────────────────────────────────────────────────────────
# Foydalanuvchi murojaat yoki taklifini yozadi → adminga ismi bilan boradi → admin «Javob
# yozish» tugmasi orqali o'sha odamga javob qaytaradi. Alohida jadval kerak
# emas: kimga javob berilayotgani callback ma'lumotida saqlanadi.

@router.message(F.text.in_(btn_variants("btn_suggest")))
async def suggest_start(message: Message, state: FSMContext) -> None:
    user = db.get_user(message.from_user.id)
    if not user:
        await message.answer(t(user_lang(None, message.from_user), "not_registered"))
        return
    lang = user.get("lang") or "uz"
    await state.set_state(Suggest.text)
    await message.answer(t(lang, "ask_suggestion"), reply_markup=back_keyboard(lang))


@router.message(Suggest.text, F.text)
async def suggest_save(message: Message, state: FSMContext) -> None:
    user = db.get_user(message.from_user.id)
    lang = user_lang(user, message.from_user)
    text = message.text.strip()[:SUGGESTION_MAX]
    await state.clear()
    handle = f"@{message.from_user.username}" if message.from_user.username \
        else t(lang, "no_username")
    admin_lang = user_lang(db.get_user(ADMIN_ID))
    try:
        await message.bot.send_message(
            ADMIN_ID,
            t(admin_lang, "admin_suggestion").format(
                name=esc(user["name"] if user else message.from_user.full_name),
                handle=esc(handle),
                text=esc(text),
            ),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=t(admin_lang, "btn_reply"),
                                     callback_data=f"sg:reply:{message.from_user.id}"),
            ]]),
        )
    except Exception as e:
        log.warning("Murojaat adminga yetmadi: %s", e)
    await message.answer(t(lang, "suggestion_sent"),
                         reply_markup=main_keyboard(lang, message.from_user.id))


@router.callback_query(F.data.startswith("sg:reply:"))
async def suggest_reply_start(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    target_id = int(callback.data.split(":")[2])
    target = db.get_user(target_id)
    lang = user_lang(db.get_user(callback.from_user.id), callback.from_user)
    await callback.answer()
    if not target:
        await callback.message.answer(t(lang, "del_missing"))
        return
    await state.set_state(AdminReply.text)
    await state.update_data(reply_to=target_id, reply_name=target["name"])
    await callback.message.answer(
        t(lang, "ask_reply").format(name=esc(target["name"])),
        reply_markup=back_keyboard(lang),
    )


@router.message(AdminReply.text, F.text)
async def suggest_reply_send(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    lang = user_lang(db.get_user(message.from_user.id), message.from_user)
    target_id = data.get("reply_to")
    await state.clear()
    target = db.get_user(target_id) if target_id else None
    if not target:
        await message.answer(t(lang, "del_missing"),
                             reply_markup=admin_keyboard(lang))
        return
    target_lang = target.get("lang") or "uz"
    try:
        await message.bot.send_message(
            target_id,
            t(target_lang, "admin_reply").format(text=esc(message.text.strip())),
        )
        await message.answer(t(lang, "reply_sent"), reply_markup=admin_keyboard(lang))
    except TelegramForbiddenError:
        db.set_blocked(target_id, True)
        await message.answer(t(lang, "reply_failed"), reply_markup=admin_keyboard(lang))
    except Exception as e:
        log.warning("Javob yuborilmadi user_id=%s: %s", target_id, e)
        await message.answer(t(lang, "reply_failed"), reply_markup=admin_keyboard(lang))


# ── Eslatma ──────────────────────────────────────────────────────────────────
# Eslatma: nom + ixtiyoriy rasm + takrorlanish + soat (Toshkent vaqti).
# Takrorlanish: har kuni, ish kunlari (Du–Ju), haftada bir (kun tanlanadi),
# oyda bir (sana tanlanadi), bir marta (sana yoziladi, yuborilgach o'chadi).
# Barcha tanlovlar pastki (reply) klaviaturada — inline tugma ishlatilmaydi.
# Har daqiqada ishlaydigan vazifa o'sha daqiqaga to'g'ri kelganlarini yuboradi.

FREQS = ("daily", "weekdays", "weekly", "monthly", "once")


def parse_hhmm(text: str) -> str | None:
    """«21:00», «21.00», «9:5», «21» → «21:00». Noto'g'ri bo'lsa None."""
    raw = text.strip().replace(".", ":").replace(" ", "")
    if ":" not in raw:
        raw += ":00"
    parts = raw.split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        return None
    hh, mm = int(parts[0]), int(parts[1])
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        return None
    return f"{hh:02d}:{mm:02d}"


def now_local() -> datetime:
    return datetime.now(ZoneInfo(TIMEZONE))


def parse_reminder_date(text: str, today: date) -> date | None:
    """«25.09» yoki «25.09.2027» → sana, bugundan oldin bo'lmasa.
    Yil yozilmasa — eng yaqin kelajakdagi sana (bu yil yoki keyingi yil)."""
    raw = text.strip().replace("/", ".").replace("-", ".")
    parts = raw.split(".")
    if not all(p.isdigit() for p in parts):
        return None
    try:
        if len(parts) == 3:
            d = date(int(parts[2]), int(parts[1]), int(parts[0]))
            return d if d >= today else None
        if len(parts) == 2:
            day, month = int(parts[0]), int(parts[1])
            for year in range(today.year, today.year + 5):   # 29.02 uchun
                try:
                    d = date(year, month, day)
                except ValueError:
                    continue
                if d >= today:
                    return d
    except ValueError:
        return None
    return None


def reminder_when(r: dict, lang: str) -> str:
    """Takrorlanishning qisqa tavsifi: «har kuni», «har dushanba», …"""
    freq = r.get("freq") or "daily"
    if freq == "weekly" and r.get("weekday") is not None:
        return WEEKDAYS_EVERY[lang][r["weekday"]]
    if freq == "monthly" and r.get("monthday"):
        return t(lang, "when_monthly").format(d=r["monthday"])
    if freq == "once" and r.get("date"):
        return fmt_day_month(date.fromisoformat(r["date"]), lang, now_local().date())
    if freq == "weekdays":
        return t(lang, "when_weekdays")
    return t(lang, "when_daily")


def reminder_label(r: dict, lang: str) -> str:
    """Ro'yxatdagi ko'rinish: «🖼 Kitob o'qish» (rasm bo'lsa belgi bilan)."""
    parts = [t(lang, "rm_photo_mark")] if r.get("photo") else []
    if r.get("text"):
        parts.append(esc(r["text"]))
    return " ".join(parts)


# Albom (bir nechta rasm bir yo'la) har element uchun alohida update bo'lib
# keladi, polling esa ularni parallel va tartibsiz ishlaydi — izoh qaysi
# elementga tushgani ham noma'lum. Shuning uchun albom qisqa muddat yig'iladi
# va bir marta, butunicha ko'rib chiqiladi. Lug'at tekshiruvlari orasida await
# yo'q — parallel handlerlar orasida poyga bo'lmaydi.
ALBUM_WAIT = 0.7                             # soniya
_albums: dict[str, list[Message]] = {}       # yig'ilayotganlar
_albums_done: dict[str, float] = {}          # ishlanganlar — kechikkanlari jim


async def album_items(message: Message) -> list[Message] | None:
    """Oddiy xabar → [xabar]. Albom → birinchi kelgan handlerga butun albom
    (message_id tartibida), qolganlariga None (ular javob bermaydi)."""
    gid = message.media_group_id
    if not gid:
        return [message]
    now = time.monotonic()
    for k in [k for k, v in _albums_done.items() if now - v > 120]:
        del _albums_done[k]
    if gid in _albums_done:
        return None
    if gid in _albums:
        _albums[gid].append(message)
        return None
    _albums[gid] = [message]
    await asyncio.sleep(ALBUM_WAIT)
    _albums_done[gid] = time.monotonic()
    return sorted(_albums.pop(gid), key=lambda m: m.message_id)


def first_caption(items: list[Message]) -> str:
    return next((m.caption.strip() for m in items if m.caption and m.caption.strip()), "")


# ── klaviaturalar ──

def _kb(rows: list[list[str]], lang: str) -> ReplyKeyboardMarkup:
    """Matnlar qatorlari + oxirida «⬅️ Orqaga»."""
    rows = rows + [[t(lang, "btn_back")]]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=x) for x in row] for row in rows],
        resize_keyboard=True,
    )


def reminders_keyboard(lang: str, count: int) -> ReplyKeyboardMarkup:
    row = []
    if count < MAX_REMINDERS:
        row.append(t(lang, "btn_add"))
    if count:
        row.append(t(lang, "btn_rm_del"))
    return _kb([row] if row else [], lang)


def delete_choices(items: list[dict], lang: str) -> dict[str, int]:
    """O'chirish uchun tugma matni → eslatma id. Matn — eslatma nomi; nomi
    takrorlansa soati qo'shiladi, baribir bir xil bo'lsa raqam. Nomsiz
    (faqat rasmli, eski) eslatma — «🖼 · 21:00»."""
    bases = [r["text"] or t(lang, "rm_photo_mark") for r in items]
    choices: dict[str, int] = {}
    for r, base in zip(items, bases):
        label = base
        if not r["text"] or bases.count(base) > 1:
            label = f"{base} · {r['time']}"
        key, k = label, 2
        while key in choices:
            key, k = f"{label} ({k})", k + 1
        choices[key] = r["id"]
    return choices


def delete_keyboard(lang: str, choices: dict[str, int]) -> ReplyKeyboardMarkup:
    return _kb([[label] for label in choices], lang)


def photo_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return _kb([[t(lang, "btn_skip")]], lang)


def freq_keyboard(lang: str) -> ReplyKeyboardMarkup:
    f = lambda k: t(lang, f"freq_{k}")
    return _kb([[f("daily"), f("weekdays")],
                [f("weekly"), f("monthly")],
                [f("once")]], lang)


def weekday_keyboard(lang: str) -> ReplyKeyboardMarkup:
    names = WEEKDAYS_FULL[lang]
    return _kb([names[0:3], names[3:6], names[6:7]], lang)


def monthday_keyboard(lang: str) -> ReplyKeyboardMarkup:
    days = [str(d) for d in range(1, 32)]
    return _kb([days[i:i + 7] for i in range(0, 31, 7)], lang)


# Tugma matni → qiymat (ikkala tilda ham taniladi)
FREQ_LABELS = {t(lg, f"freq_{f}"): f for lg in BOT for f in FREQS}
WEEKDAY_LABELS = {name.lower(): i for lg in WEEKDAYS_FULL
                  for i, name in enumerate(WEEKDAYS_FULL[lg])}


# ── ro'yxat ──

def reminders_text(items: list[dict], lang: str) -> str:
    if not items:
        return t(lang, "reminders_empty")
    listing = "\n".join(
        t(lang, "reminder_item").format(n=i, time=r["time"],
                                        when=reminder_when(r, lang),
                                        text=reminder_label(r, lang))
        for i, r in enumerate(items, start=1)
    )
    return t(lang, "reminders_list").format(items=listing)


async def show_reminders(message: Message, state: FSMContext, lang: str,
                         prefix: str = "") -> None:
    """Ro'yxat + klaviatura («➕ Qo'shish», «O'chirish», «⬅️ Orqaga»)."""
    items = db.get_reminders(message.chat.id)
    await state.clear()
    await state.set_state(Reminder.menu)
    text = reminders_text(items, lang)
    if prefix:
        text = f"{prefix}\n\n{text}"
    await message.answer(text, reply_markup=reminders_keyboard(lang, len(items)))


def _lang(message: Message) -> str:
    return user_lang(db.get_user(message.from_user.id), message.from_user)


@router.message(F.text.in_(btn_variants("btn_reminder")))
async def reminders_menu(message: Message, state: FSMContext) -> None:
    user = db.get_user(message.from_user.id)
    if not user:
        await message.answer(t(user_lang(None, message.from_user), "not_registered"))
        return
    await show_reminders(message, state, user.get("lang") or "uz")


@router.message(F.text.in_(btn_variants("btn_add")))
async def reminder_add_start(message: Message, state: FSMContext) -> None:
    user = db.get_user(message.from_user.id)
    if not user:
        await message.answer(t(user_lang(None, message.from_user), "not_registered"))
        return
    lang = user.get("lang") or "uz"
    if len(db.get_reminders(message.from_user.id)) >= MAX_REMINDERS:
        await show_reminders(message, state, lang,
                             prefix=t(lang, "reminders_max").format(n=MAX_REMINDERS))
        return
    await state.clear()
    await state.set_state(Reminder.text)
    await message.answer(t(lang, "ask_rm_text"), reply_markup=back_keyboard(lang))


@router.message(F.text.in_(btn_variants("btn_rm_del")))
async def reminder_delete_start(message: Message, state: FSMContext) -> None:
    """«O'chirish» → klaviaturada eslatmalar nomlari. Tugma matni → id
    moslamasi FSM'da — ro'yxat oradan o'zgarsa ham boshqasi o'chmaydi."""
    user = db.get_user(message.from_user.id)
    if not user:
        await message.answer(t(user_lang(None, message.from_user), "not_registered"))
        return
    lang = user.get("lang") or "uz"
    items = db.get_reminders(message.from_user.id)
    if not items:
        await show_reminders(message, state, lang)
        return
    choices = delete_choices(items, lang)
    await state.clear()
    await state.set_state(Reminder.delete)
    await state.update_data(rm_del=choices)
    await message.answer(t(lang, "ask_rm_delete"),
                         reply_markup=delete_keyboard(lang, choices))


@router.message(Reminder.delete, F.text)
async def reminder_delete_pick(message: Message, state: FSMContext) -> None:
    lang = _lang(message)
    choices = (await state.get_data()).get("rm_del") or {}
    rid = choices.get(message.text)
    if rid is None:
        await message.answer(t(lang, "use_keyboard"),
                             reply_markup=delete_keyboard(lang, choices))
        return
    db.delete_reminder(rid, message.from_user.id)
    await show_reminders(message, state, lang, prefix=t(lang, "rm_deleted"))


@router.callback_query(F.data.startswith(("rm:", "rmf:", "rmw:", "rmd:")))
async def reminder_legacy_inline(callback: CallbackQuery, state: FSMContext) -> None:
    """Eski xabarlardagi inline tugmalar: tugmalar olinadi, yangi menyu
    ko'rsatiladi."""
    await callback.answer()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    user = db.get_user(callback.from_user.id)
    if user:
        await show_reminders(callback.message, state, user.get("lang") or "uz")


# ── qo'shish: nom → rasm → takrorlanish → … → soat ──

async def ask_reminder_freq(message: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(Reminder.freq)
    await message.answer(t(lang, "ask_rm_freq"), reply_markup=freq_keyboard(lang))


async def ask_reminder_time(message: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(Reminder.time)
    await message.answer(t(lang, "ask_rm_time"), reply_markup=back_keyboard(lang))


@router.message(Reminder.text, F.text)
async def reminder_save_text(message: Message, state: FSMContext) -> None:
    lang = _lang(message)
    text = message.text.strip()
    if not text or len(text) > REMINDER_TEXT_MAX:
        await message.answer(t(lang, "rm_text_too_long"))
        return
    await state.update_data(rm_text=text, rm_photo=None)
    await state.set_state(Reminder.photo)
    await message.answer(t(lang, "ask_rm_photo"), reply_markup=photo_keyboard(lang))


@router.message(Reminder.text)
async def reminder_name_media(message: Message, state: FSMContext) -> None:
    """Nom so'ralganda matn o'rniga boshqa narsa keldi. Izohli rasm (yoki
    izohli albom) — izoh nom, birinchi rasm rasm bo'ladi, rasm qadami
    o'tkaziladi. Qolgan hammasi — avval nom kerak."""
    items = await album_items(message)
    if items is None:
        return
    lang = _lang(message)
    photos = [m for m in items if m.photo]
    text = first_caption(items)
    if not photos or not text:
        await message.answer(t(lang, "rm_name_first"))
        return
    if len(text) > REMINDER_TEXT_MAX:
        await message.answer(t(lang, "rm_text_too_long"))
        return
    await state.update_data(rm_text=text, rm_photo=photos[0].photo[-1].file_id)
    await ask_reminder_freq(message, state, lang)


@router.message(Reminder.photo, F.text.in_(btn_variants("btn_skip")))
async def reminder_skip_photo(message: Message, state: FSMContext) -> None:
    await ask_reminder_freq(message, state, _lang(message))


@router.message(Reminder.photo)
async def reminder_photo_media(message: Message, state: FSMContext) -> None:
    """Rasm qadami: birinchi rasmning eng katta o'lchami saqlanadi (izoh
    e'tiborga olinmaydi — nom yozilgan). Rasm bo'lmasa — eslatma."""
    items = await album_items(message)
    if items is None:
        return
    lang = _lang(message)
    photos = [m for m in items if m.photo]
    if not photos:
        await message.answer(t(lang, "rm_photo_or_skip"), reply_markup=photo_keyboard(lang))
        return
    await state.update_data(rm_photo=photos[0].photo[-1].file_id)
    await ask_reminder_freq(message, state, lang)


@router.message(Reminder.freq, F.text)
async def reminder_pick_freq(message: Message, state: FSMContext) -> None:
    lang = _lang(message)
    freq = FREQ_LABELS.get(message.text)
    if freq is None:
        await message.answer(t(lang, "use_keyboard"), reply_markup=freq_keyboard(lang))
        return
    await state.update_data(rm_freq=freq)
    if freq == "weekly":
        await state.set_state(Reminder.weekday)
        await message.answer(t(lang, "ask_rm_weekday"),
                             reply_markup=weekday_keyboard(lang))
    elif freq == "monthly":
        await state.set_state(Reminder.monthday)
        await message.answer(t(lang, "ask_rm_monthday"),
                             reply_markup=monthday_keyboard(lang))
    elif freq == "once":
        await state.set_state(Reminder.date)
        await message.answer(t(lang, "ask_rm_date"), reply_markup=back_keyboard(lang))
    else:
        await ask_reminder_time(message, state, lang)


@router.message(Reminder.weekday, F.text)
async def reminder_pick_weekday(message: Message, state: FSMContext) -> None:
    lang = _lang(message)
    wd = WEEKDAY_LABELS.get(message.text.strip().lower())
    if wd is None:
        await message.answer(t(lang, "use_keyboard"), reply_markup=weekday_keyboard(lang))
        return
    await state.update_data(rm_weekday=wd)
    await ask_reminder_time(message, state, lang)


@router.message(Reminder.monthday, F.text)
async def reminder_pick_monthday(message: Message, state: FSMContext) -> None:
    lang = _lang(message)
    raw = message.text.strip()
    md = int(raw) if raw.isdigit() else 0
    if not 1 <= md <= 31:
        await message.answer(t(lang, "use_keyboard"), reply_markup=monthday_keyboard(lang))
        return
    await state.update_data(rm_monthday=md)
    await ask_reminder_time(message, state, lang)


@router.message(Reminder.date, F.text)
async def reminder_save_date(message: Message, state: FSMContext) -> None:
    lang = _lang(message)
    d = parse_reminder_date(message.text, now_local().date())
    if d is None:
        await message.answer(t(lang, "bad_rm_date"))
        return
    await state.update_data(rm_date=d.isoformat())
    await ask_reminder_time(message, state, lang)


@router.message(Reminder.time, F.text)
async def reminder_save_time(message: Message, state: FSMContext) -> None:
    lang = _lang(message)
    hhmm = parse_hhmm(message.text)
    if hhmm is None:
        await message.answer(t(lang, "bad_time"))
        return
    data = await state.get_data()
    freq = data.get("rm_freq", "daily")
    on_date = date.fromisoformat(data["rm_date"]) if data.get("rm_date") else None
    if freq == "once" and on_date:
        now = now_local()
        if (on_date.isoformat(), hhmm) <= (now.date().isoformat(), now.strftime("%H:%M")):
            await message.answer(t(lang, "rm_past"))
            return
    if len(db.get_reminders(message.from_user.id)) >= MAX_REMINDERS:
        await show_reminders(message, state, lang,
                             prefix=t(lang, "reminders_max").format(n=MAX_REMINDERS))
        return
    db.add_reminder(message.from_user.id, data.get("rm_text", ""), hhmm, freq,
                    weekday=data.get("rm_weekday"), monthday=data.get("rm_monthday"),
                    on_date=on_date, photo=data.get("rm_photo"))
    await show_reminders(message, state, lang, prefix=t(lang, "updated"))


@router.message(Reminder.menu)
async def reminder_menu_other(message: Message, state: FSMContext) -> None:
    """Ro'yxat ochiq turganda boshqa narsa yozilsa — menyu klaviaturasi qoladi."""
    if await album_items(message) is None:
        return
    lang = _lang(message)
    count = len(db.get_reminders(message.from_user.id))
    await message.answer(t(lang, "use_keyboard"),
                         reply_markup=reminders_keyboard(lang, count))


@router.message(Reminder.delete)
@router.message(Reminder.freq)
@router.message(Reminder.weekday)
@router.message(Reminder.monthday)
async def reminder_use_keyboard(message: Message) -> None:
    """O'chiriladigan eslatma, takrorlanish, hafta kuni va oy sanasi
    klaviaturadan tanlanadi."""
    if await album_items(message) is None:
        return          # albomning qolgan elementlari — javobsiz
    await message.answer(t(_lang(message), "use_keyboard"))


@router.message(Suggest.text)
@router.message(AdminReply.text)
@router.message(Reminder.date)
@router.message(Reminder.time)
async def new_flows_non_text(message: Message) -> None:
    await message.answer(t(_lang(message), "text_only"))


# ── English ──────────────────────────────────────────────────────────────────
# Sozlamalardan yoqiladi (standart — o'chiq). Birinchi kirishda lug'at haqida
# ma'lumot va daraja testi; keyin har kuni 3 ta so'z (ertalab avtomatik ham
# keladi) va vaqti kelgan so'zlarni takrorlash. Hamma tanlov pastki
# klaviaturada. Mantiq english.py da.

def english_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return _kb([[t(lang, "btn_en_retest")]], lang)


def question_keyboard(lang: str, options: list[str]) -> ReplyKeyboardMarkup:
    return _kb([[o] for o in options] + [[t(lang, "btn_dont_know")]], lang)


def english_intro_text(lang: str) -> str:
    counts = english.level_counts()
    levels = "\n".join(t(lang, "en_level_line").format(level=lv, n=_fmt_num(n))
                       for lv, n in counts.items())
    return t(lang, "en_intro").format(
        time=f"{EN_HOUR:02d}:{EN_MINUTE:02d}",
        total=_fmt_num(sum(counts.values())),
        levels=levels,
    )


def _fmt_num(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def english_today_text(user: dict, lang: str, today: date) -> str:
    """Bugungi so'zlar (kerak bo'lsa shu yerda tanlanadi)."""
    ids = english.today_words(user["user_id"], user["en_level"], today)
    parts = [t(lang, "en_today_title").format(level=user["en_level"])]
    for wid in ids:
        w = english.words()[wid]
        parts.append(
            f"<b>{esc(w['word'])}</b> · {POS_NAMES[lang][w['pos']]}\n"
            f"{esc(english.translation(wid, lang))}\n"
            f"<i>{esc(w['ex'])}</i>"
        )
    if not ids:
        parts.append(t(lang, "en_all_done"))
    return "\n\n".join(parts)


async def english_session(message: Message, state: FSMContext, user: dict,
                          lang: str, prefix: str = "") -> None:
    """Avval vaqti kelgan takrorlashlar, keyin bugungi so'zlar."""
    today = now_local().date()
    english.today_words(user["user_id"], user["en_level"], today)
    queue = english.due_reviews(user["user_id"], today)
    if queue:
        await state.clear()
        await state.set_state(EnglishReview.question)
        await state.update_data(queue=queue, i=0)
        await ask_review(message, state, lang, prefix)
        return
    await state.clear()
    text = english_today_text(user, lang, today)
    if prefix:
        text = f"{prefix}\n\n{text}"
    await message.answer(text, reply_markup=english_keyboard(lang))


async def ask_review(message: Message, state: FSMContext, lang: str,
                     prefix: str = "") -> None:
    data = await state.get_data()
    queue, i = data["queue"], data["i"]
    q = english.make_question(queue[i], lang)
    await state.update_data(options=q.options, answer=q.answer)
    text = t(lang, "en_review_q").format(i=i + 1, n=len(queue), word=esc(q.word))
    if prefix:
        text = f"{prefix}\n\n{text}"
    await message.answer(text, reply_markup=question_keyboard(lang, q.options))


async def ask_test_question(message: Message, state: FSMContext, lang: str,
                            prefix: str = "") -> None:
    data = await state.get_data()
    st = data["test"]
    wid = english.test_pick_word(st)
    q = english.make_question(wid, lang)
    await state.update_data(test=st, word_id=wid, options=q.options, answer=q.answer)
    text = t(lang, "en_test_q").format(n=st["n"], word=esc(q.word))
    if prefix:
        text = f"{prefix}\n\n{text}"
    await message.answer(text, reply_markup=question_keyboard(lang, q.options))


async def start_english_test(message: Message, state: FSMContext, lang: str) -> None:
    await state.clear()
    await state.set_state(EnglishTest.question)
    await state.update_data(test=english.new_test())
    await ask_test_question(message, state, lang)


def _english_user(message: Message) -> tuple[dict | None, str]:
    user = db.get_user(message.from_user.id)
    return user, user_lang(user, message.from_user)


@router.message(F.text.in_(btn_variants("btn_english")))
async def english_open(message: Message, state: FSMContext) -> None:
    user, lang = _english_user(message)
    if not user:
        await message.answer(t(lang, "not_registered"))
        return
    if not user.get("english"):
        await state.clear()
        await message.answer(t(lang, "en_is_off"),
                             reply_markup=main_keyboard(lang, message.from_user.id))
        return
    if not user.get("en_level"):
        await state.clear()
        await state.set_state(EnglishTest.intro)
        await message.answer(english_intro_text(lang),
                             reply_markup=_kb([[t(lang, "btn_en_start")]], lang))
        return
    await english_session(message, state, user, lang)


@router.message(F.text.in_(btn_variants("btn_en_retest")))
@router.message(EnglishTest.intro, F.text.in_(btn_variants("btn_en_start")))
async def english_test_start(message: Message, state: FSMContext) -> None:
    user, lang = _english_user(message)
    if not user:
        await message.answer(t(lang, "not_registered"))
        return
    if not user.get("english"):
        await message.answer(t(lang, "en_is_off"),
                             reply_markup=main_keyboard(lang, message.from_user.id))
        return
    await start_english_test(message, state, lang)


@router.message(F.text.in_(btn_variants("btn_en_on")))
@router.message(F.text.in_(btn_variants("btn_en_off")))
async def english_toggle(message: Message, state: FSMContext) -> None:
    """Tugma matni qaysi amalni bildirsa, o'sha bajariladi (eski klaviatura
    qolgan bo'lsa ham holat teskarisiga aylanib ketmaydi)."""
    user, lang = _english_user(message)
    if not user:
        await message.answer(t(lang, "not_registered"))
        return
    on = message.text in btn_variants("btn_en_on")
    db.update_user(message.from_user.id, english=1 if on else 0)
    await show_settings(message, state, prefix=t(lang, "en_enabled" if on else "en_disabled"))


@router.message(EnglishTest.question, F.text)
async def english_test_answer(message: Message, state: FSMContext) -> None:
    user, lang = _english_user(message)
    data = await state.get_data()
    options = data.get("options") or []
    if message.text not in options and message.text not in btn_variants("btn_dont_know"):
        await message.answer(t(lang, "use_keyboard"),
                             reply_markup=question_keyboard(lang, options))
        return
    correct = message.text == data.get("answer")
    st = data["test"]
    wid = data["word_id"]
    feedback = t(lang, "en_right") if correct else t(lang, "en_wrong").format(
        word=esc(english.words()[wid]["word"]), tr=esc(data["answer"]))
    level = english.test_answer(st, wid, correct)
    if level is None:
        await state.update_data(test=st)
        await ask_test_question(message, state, lang, prefix=feedback)
        return
    db.update_user(message.from_user.id, en_level=level)
    db.en_mark_known(message.from_user.id, st["known"])
    user = db.get_user(message.from_user.id)
    result = t(lang, "en_level_result").format(level=level)
    await english_session(message, state, user, lang, prefix=f"{feedback}\n\n{result}")


@router.message(EnglishReview.question, F.text)
async def english_review_answer(message: Message, state: FSMContext) -> None:
    user, lang = _english_user(message)
    data = await state.get_data()
    options = data.get("options") or []
    if message.text not in options and message.text not in btn_variants("btn_dont_know"):
        await message.answer(t(lang, "use_keyboard"),
                             reply_markup=question_keyboard(lang, options))
        return
    queue, i = data["queue"], data["i"]
    wid = queue[i]
    correct = message.text == data.get("answer")
    today = now_local().date()
    english.apply_review(message.from_user.id, wid, correct, today)
    feedback = t(lang, "en_right") if correct else t(lang, "en_wrong").format(
        word=esc(english.words()[wid]["word"]), tr=esc(data["answer"]))
    if i + 1 < len(queue):
        await state.update_data(i=i + 1)
        await ask_review(message, state, lang, prefix=feedback)
        return
    await state.clear()
    text = english_today_text(user, lang, today)
    await message.answer(f"{feedback}\n\n{text}", reply_markup=english_keyboard(lang))


@router.message(EnglishTest.intro)
@router.message(EnglishTest.question)
@router.message(EnglishReview.question)
async def english_use_keyboard(message: Message) -> None:
    if await album_items(message) is None:
        return
    await message.answer(t(_lang(message), "use_keyboard"))


# ── Admin ────────────────────────────────────────────────────────────────────

USERS_PER_PAGE = 20


def admin_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_users")),
             KeyboardButton(text=t(lang, "btn_stats"))],
            [KeyboardButton(text=t(lang, "btn_broadcast"))],
            [KeyboardButton(text=t(lang, "btn_delete_user"))],
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
        name = esc(u["name"][:14].ljust(15))
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
        name=esc(user["name"]),
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


# ── Admin: barchaga xabar ────────────────────────────────────────────────────
# Xabar copy_message bilan ko'chiriladi — admin yozgan formatlash, rasm yoki
# fayl o'z holicha boradi va HTML'ni qo'lda qochirish kerak bo'lmaydi.

broadcasting = False          # bir vaqtda bitta tarqatish


@router.message(F.text.in_(btn_variants("btn_broadcast")))
async def broadcast_start(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    lang = user_lang(db.get_user(message.from_user.id), message.from_user)
    await state.set_state(Broadcast.message)
    await message.answer(t(lang, "ask_broadcast"), reply_markup=back_keyboard(lang))


@router.message(Broadcast.message)
async def broadcast_preview(message: Message, state: FSMContext) -> None:
    lang = user_lang(db.get_user(message.from_user.id), message.from_user)
    await state.update_data(src_chat=message.chat.id, src_msg=message.message_id)
    await state.set_state(Broadcast.confirm)
    await message.reply(
        t(lang, "broadcast_preview").format(n=len(db.get_active_users())),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=t(lang, "btn_send"), callback_data="bc:send"),
            InlineKeyboardButton(text=t(lang, "btn_cancel"), callback_data="bc:cancel"),
        ]]),
    )


@router.callback_query(Broadcast.confirm, F.data.startswith("bc:"))
async def broadcast_run(callback: CallbackQuery, state: FSMContext) -> None:
    global broadcasting
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    lang = user_lang(db.get_user(callback.from_user.id), callback.from_user)
    data = await state.get_data()
    await state.clear()
    await callback.answer()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    if callback.data == "bc:cancel":
        await callback.message.answer(t(lang, "cancelled"),
                                      reply_markup=admin_keyboard(lang))
        return
    if broadcasting:
        await callback.message.answer(t(lang, "broadcast_busy"))
        return
    src_chat, src_msg = data.get("src_chat"), data.get("src_msg")
    users = db.get_active_users()
    await callback.message.answer(t(lang, "broadcast_started").format(n=len(users)),
                                  reply_markup=admin_keyboard(lang))

    async def send_one(bot: Bot, user: dict) -> None:
        await bot.copy_message(chat_id=user["user_id"],
                               from_chat_id=src_chat, message_id=src_msg)

    async def run() -> None:
        global broadcasting
        broadcasting = True
        try:
            res = await spread_send(callback.bot, users, send_one, "Admin xabari",
                                    window_minutes=0)
            await callback.bot.send_message(
                callback.from_user.id, t(lang, "broadcast_done").format(**res))
        finally:
            broadcasting = False

    asyncio.create_task(run())   # bot tarqatish paytida ham javob beraveradi


# ── Admin: foydalanuvchini o'chirish ─────────────────────────────────────────

DELETE_PER_PAGE = 8


def delete_picker(page: int, lang: str) -> tuple[str, InlineKeyboardMarkup]:
    users = db.get_all_users()
    pages = max(1, (len(users) + DELETE_PER_PAGE - 1) // DELETE_PER_PAGE)
    page = max(0, min(page, pages - 1))
    chunk = users[page * DELETE_PER_PAGE:(page + 1) * DELETE_PER_PAGE]
    rows = [[InlineKeyboardButton(
        text=f"{i}. {u['name'][:20]} · {age_of(u)}",
        callback_data=f"adm:delpick:{u['user_id']}",
    )] for i, u in enumerate(chunk, start=page * DELETE_PER_PAGE + 1)]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"adm:delpage:{page - 1}"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"adm:delpage:{page + 1}"))
    if nav:
        rows.append(nav)
    title = t(lang, "del_pick")
    if pages > 1:
        title += f" · {page + 1}/{pages}"
    return title, InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(F.text.in_(btn_variants("btn_delete_user")))
async def delete_user_menu(message: Message) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    lang = user_lang(db.get_user(message.from_user.id), message.from_user)
    text, kb = delete_picker(0, lang)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("adm:delpage:"))
async def delete_user_page(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    lang = user_lang(db.get_user(callback.from_user.id), callback.from_user)
    text, kb = delete_picker(int(callback.data.split(":")[2]), lang)
    await callback.answer()
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm:delpick:"))
async def delete_user_confirm(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    lang = user_lang(db.get_user(callback.from_user.id), callback.from_user)
    target_id = int(callback.data.split(":")[2])
    await callback.answer()
    if target_id == callback.from_user.id:
        await callback.message.answer(t(lang, "del_self"))
        return
    target = db.get_user(target_id)
    if not target:
        await callback.message.answer(t(lang, "del_missing"))
        return
    try:
        await callback.message.edit_text(
            t(lang, "del_confirm").format(name=esc(target["name"]),
                                          age=age_of(target)),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=t(lang, "btn_del_yes"),
                                     callback_data=f"adm:delok:{target_id}"),
                InlineKeyboardButton(text=t(lang, "btn_cancel"),
                                     callback_data="adm:delno"),
            ]]),
        )
    except Exception:
        pass


@router.callback_query(F.data == "adm:delno")
async def delete_user_cancel(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    lang = user_lang(db.get_user(callback.from_user.id), callback.from_user)
    await callback.answer()
    text, kb = delete_picker(0, lang)
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm:delok:"))
async def delete_user_run(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    lang = user_lang(db.get_user(callback.from_user.id), callback.from_user)
    target_id = int(callback.data.split(":")[2])
    target = db.get_user(target_id)
    await callback.answer()
    if target_id == callback.from_user.id:
        await callback.message.answer(t(lang, "del_self"))
        return
    if not target or not db.delete_user(target_id):
        await callback.message.answer(t(lang, "del_missing"))
        return
    log.info("Foydalanuvchi o'chirildi: user_id=%s (admin=%s)",
             target_id, callback.from_user.id)
    try:
        await callback.message.edit_text(
            t(lang, "del_done").format(name=esc(target["name"])))
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


async def spread_send(bot: Bot, users: list[dict], send_one, label: str,
                      window_minutes: int | None = None) -> dict[str, int]:
    """Xabarlarni belgilangan oyna bo'ylab tekis yoyib yuboradi.

    Har xabardan keyin "qolgan vaqt ÷ qolgan foydalanuvchi" qadar kutiladi —
    sur'at o'zini to'g'irlaydi: 5 ta user bo'lsa bir necha soniyada tugaydi,
    1 000 ta bo'lsa soatga tekis yoyiladi, oynaga sig'masa minimal oraliqda
    davom etadi. Yoyilgani uchun protsessor bir joyda tiqilib qolmaydi va bot
    tarqatish paytida ham odatdagidek javob beradi.

    Botni bloklagan foydalanuvchi belgilanadi va keyingi tarqatishlarga
    qo'shilmaydi (qaytib yozsa, avtomatik tiklanadi).

    `window_minutes` berilmasa BROADCAST_WINDOW_MINUTES ishlatiladi; 0 berilsa
    imkon qadar tez (minimal oraliq bilan) yuboriladi — admin xabari va
    eslatmalar shunday, ular vaqtida yetib borishi kerak.
    """
    window = (BROADCAST_WINDOW_MINUTES if window_minutes is None
              else window_minutes) * 60
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
    return {"sent": sent, "blocked": blocked, "failed": failed}


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


async def english_morning(bot: Bot) -> None:
    """Har kuni EN_HOUR:EN_MINUTE da: bugungi so'zlar (English yoqilgan va
    darajasi aniq bo'lganlarga). Takrorlash kerak bo'lsa — eslatma qatori."""
    users = db.en_push_users()
    log.info("English so'zlari boshlandi: %d ta foydalanuvchi", len(users))
    today = now_local().date()

    async def send_one(bot: Bot, user: dict) -> None:
        lang = user.get("lang") or "uz"
        text = english_today_text(user, lang, today)
        due = len(english.due_reviews(user["user_id"], today))
        if due:
            text += "\n\n" + t(lang, "en_reviews_hint").format(n=due)
        await bot.send_message(user["user_id"], text)

    await spread_send(bot, users, send_one, "English so'zlari", window_minutes=0)


_last_reminder_minute: datetime | None = None
REMINDER_CATCHUP_MINUTES = 5


async def reminder_tick(bot: Bot) -> None:
    """Har daqiqada: shu daqiqaga to'g'ri keladigan eslatmalarni yuboradi.

    Vazifa kechikib ishga tushsa oradagi daqiqalar ham tekshiriladi (ko'pi
    bilan 5 ta) — qisqa kechikishda eslatma yo'qolmaydi. Bir daqiqa ikki
    marta ishlov berilmaydi. Bot qayta ishga tushsa, o'tib ketgan daqiqalar
    takrorlanmaydi. Bir martalik eslatma yuborilgach o'chiriladi.
    """
    global _last_reminder_minute
    now = now_local().replace(second=0, microsecond=0)
    last = _last_reminder_minute
    minutes, cursor = [], now
    for _ in range(REMINDER_CATCHUP_MINUTES + 1):
        if last is not None and cursor <= last:
            break
        minutes.append(cursor)
        if last is None:
            break
        cursor -= timedelta(minutes=1)
    minutes.reverse()
    _last_reminder_minute = now if last is None else max(last, now)

    for moment in minutes:
        due = db.reminders_due(moment)
        if not due:
            continue
        label = f"Eslatma {moment:%H:%M}"
        log.info("%s: %d ta", label, len(due))

        async def send_one(bot: Bot, row: dict) -> None:
            lang = row.get("lang") or "uz"
            body = t(lang, "reminder_msg").format(text=esc(row["text"])).strip()
            if row.get("photo"):
                try:
                    await bot.send_photo(row["user_id"], row["photo"], caption=body)
                    return
                except TelegramBadRequest as e:
                    # file_id yaroqsiz (masalan bot tokeni almashgan) — eslatma
                    # yo'qolmasin, matn bilan yuboriladi
                    log.warning("Eslatma rasmi yuborilmadi id=%s: %s", row["id"], e)
                    if not row["text"]:
                        body = f"{body} {t(lang, 'rm_photo_mark')}"
            await bot.send_message(row["user_id"], body)

        await spread_send(bot, due, send_one, label, window_minutes=0)
        db.delete_reminders([r["id"] for r in due if r["freq"] == "once"])

    # Bot o'chiq turgan paytga tushib, yuborilmay qolgan bir martaliklar
    db.purge_expired_once(now - timedelta(minutes=REMINDER_CATCHUP_MINUTES + 1))


# ── Ishga tushirish ──────────────────────────────────────────────────────────

async def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit(
            "BOT_TOKEN topilmadi. @BotFather dan token oling va .env faylga yozing."
        )
    db.init_db()
    log.info("English lug'ati: %d ta so'z", len(english.words()))

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
    scheduler.add_job(
        english_morning,
        CronTrigger(hour=EN_HOUR, minute=EN_MINUTE, timezone=TIMEZONE),
        args=[bot],
        misfire_grace_time=600,
    )
    scheduler.add_job(
        reminder_tick,
        CronTrigger(minute="*", timezone=TIMEZONE),
        args=[bot],
        misfire_grace_time=55,
    )
    scheduler.start()

    log.info("Bot ishga tushdi.")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
