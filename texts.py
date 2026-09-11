"""Bot va poster matnlari — o'zbek va rus tillarida."""
from datetime import date

MONTHS = {
    "uz": ["yanvar", "fevral", "mart", "aprel", "may", "iyun",
           "iyul", "avgust", "sentyabr", "oktyabr", "noyabr", "dekabr"],
    "ru": ["января", "февраля", "марта", "апреля", "мая", "июня",
           "июля", "августа", "сентября", "октября", "ноября", "декабря"],
}


def fmt_date(d: date, lang: str) -> str:
    return f"{d.day} {MONTHS[lang][d.month - 1]} {d.year}"


def age_label(year: int, age: int, lang: str) -> str:
    # Rus tilida ham bitta shakl ishlatiladi ("лет") — aralash bo'lmasin
    return f"{year} · {age} yosh" if lang == "uz" else f"{year} · {age} лет"


BOT = {
    "uz": {
        "ask_name": (
            "Assalomu alaykum! 🌙\n\n"
            "<b>Mundabit</b> — vaqt qadrini anglatadigan bot.\n\n"
            "Ismingizni yozing:"
        ),
        "name_too_long": "Iltimos, ismingizni qisqaroq yozing (64 belgigacha).",
        "ask_birth": (
            "Rahmat! Endi <b>tug'ilgan sanangizni</b> kiriting.\n"
            "Format: <code>KK.OO.YYYY</code> — masalan: <code>15.06.2000</code>"
        ),
        "bad_birth": (
            "❗ Sana noto'g'ri. <code>KK.OO.YYYY</code> formatida kiriting "
            "(masalan: <code>15.06.2000</code>)."
        ),
        "ask_gender": "Jinsingizni tanlang:",
        "btn_male": "Erkak",
        "btn_female": "Ayol",
        "saved": (
            "🔔 Har juma 14:00 da hayot kalendaringiz yuboriladi, "
            "har dushanba o'tgan hafta haqida so'rayman.\n\n"
            "/hayot — kalendarni ko'rish"
        ),
        "weekly_q": "O'tgan hafta qanday o'tdi?",
        "btn_good": "🟢 Samarali",
        "btn_bad": "🔴 Behuda",
        "rating_saved": "Saqlandi ✅",
        "not_registered": "Avval ro'yxatdan o'ting: /start",
        "text_only": "Iltimos, matn ko'rinishida yozing 🙏",
        "help": (
            "<b>Mundabit</b> — vaqt qadrini anglash boti.\n\n"
            "/start — ro'yxatdan o'tish\n"
            "/hayot — hayot kalendarini ko'rish\n\n"
            "Har juma 14:00 — kalendar, har dushanba — hafta yakuni so'rovi."
        ),
        "webapp_btn": "Ilovada ko'rish",
        "caption": "Yashaldi: <b>{lived} hafta</b> — {p}%\nQoldi: <b>{left} hafta</b> — {q}%",
    },
    "ru": {
        "ask_name": (
            "Ассалому алайкум! 🌙\n\n"
            "<b>Mundabit</b> — бот, помогающий ценить время.\n\n"
            "Напишите ваше имя:"
        ),
        "name_too_long": "Пожалуйста, напишите имя короче (до 64 символов).",
        "ask_birth": (
            "Спасибо! Теперь введите <b>дату рождения</b>.\n"
            "Формат: <code>ДД.ММ.ГГГГ</code> — например: <code>15.06.2000</code>"
        ),
        "bad_birth": (
            "❗ Неверная дата. Введите в формате <code>ДД.ММ.ГГГГ</code> "
            "(например: <code>15.06.2000</code>)."
        ),
        "ask_gender": "Выберите пол:",
        "btn_male": "Мужской",
        "btn_female": "Женский",
        "saved": (
            "🔔 Каждую пятницу в 14:00 вы получите календарь жизни, "
            "каждый понедельник я спрошу о прошедшей неделе.\n\n"
            "/hayot — посмотреть календарь"
        ),
        "weekly_q": "Как прошла ваша неделя?",
        "btn_good": "🟢 Продуктивно",
        "btn_bad": "🔴 Впустую",
        "rating_saved": "Сохранено ✅",
        "not_registered": "Сначала зарегистрируйтесь: /start",
        "text_only": "Пожалуйста, напишите текстом 🙏",
        "help": (
            "<b>Mundabit</b> — бот, помогающий ценить время.\n\n"
            "/start — регистрация\n"
            "/hayot — календарь жизни\n\n"
            "Каждую пятницу в 14:00 — календарь, каждый понедельник — опрос о неделе."
        ),
        "webapp_btn": "Открыть приложение",
        "caption": "Прожито: <b>{lived} недель</b> — {p}%\nОсталось: <b>{left} недель</b> — {q}%",
    },
}

POSTER = {
    "uz": {
        "title1": "Hayot ",
        "title2": "Kalendari",
        "born_m": "Tug'ilgan",
        "born_f": "Tug'ilgan",
        "today": "Bugun",
        "stats_past": "O'tgan: ",
        "stats_left": "Qoldi: ",
        "stats_week": " hafta",
    },
    "ru": {
        "title1": "Календарь ",
        "title2": "жизни",
        "born_m": "Родился",
        "born_f": "Родилась",
        "today": "Сегодня",
        "stats_past": "Прожито: ",
        "stats_left": "Осталось: ",
        "stats_week": " недель",
    },
}


def t(lang: str, key: str) -> str:
    return BOT.get(lang, BOT["uz"])[key]
