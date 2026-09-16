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
        "greeting": "Assalomu alaykum! 🌙",
        "confirm_name": "Ismingiz <b>{name}</b> mi?",
        "btn_yes": "✅ Ha",
        "btn_other_name": "✏️ Boshqa ism",
        "ask_name": "Ismingizni yozing:",
        "name_too_long": "Iltimos, ismingizni qisqaroq yozing (64 belgigacha).",
        "confirm_birth": "Tug'ilgan sanangiz <b>{birth}</b> mi?",
        "btn_other_birth": "✏️ Boshqa sana",
        "ask_birth": (
            "<b>Tug'ilgan sanangizni</b> kiriting.\n"
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
            "🔔 Har juma <b>13:00–14:00</b> oralig'ida hayot kalendaringiz yuboriladi, "
            "har dushanba ertalab o'tgan hafta haqida so'rayman.\n\n"
            "⚙️ Sozlamalar — ism, jins va tilni o'zgartirish."
        ),
        "weekly_q": "O'tgan hafta qanday o'tdi?",
        "btn_good": "🟢 Samarali",
        "btn_bad": "🔴 Behuda",
        "rating_saved": "Saqlandi ✅",
        "not_registered": "Avval ro'yxatdan o'ting: /start",
        "text_only": "Iltimos, matn ko'rinishida yozing 🙏",
        "help": (
            "<b>Mundabit</b> — vaqt qadrini anglash boti.\n\n"
            "/start — kalendarni ko'rish va menyuni ochish\n"
            "⏰ Eslatma — har kuni belgilangan vaqtda eslatma\n"
            "💡 Taklif — botga g'oya yuborish\n"
            "⚙️ Sozlamalar — ism, jins va til\n\n"
            "Har juma 13:00–14:00 — hayot kalendari.\n"
            "Har dushanba ertalab — o'tgan hafta qanday o'tdi degan so'rov."
        ),
        "webapp_btn": "Ilovada ko'rish",
        "btn_settings": "⚙️ Sozlamalar",
        "btn_name": "✏️ Ismni o'zgartirish",
        "btn_gender": "⚧ Jinsni o'zgartirish",
        "btn_lang": "🌐 Tilni o'zgartirish",
        "ask_lang": "Tilni tanlang:",
        "btn_uz": "🇺🇿 O'zbekcha",
        "btn_ru": "🇷🇺 Русский",
        "btn_back": "⬅️ Orqaga",
        "menu": "Asosiy menyu",
        "settings": (
            "⚙️ <b>Sozlamalar</b>\n\n"
            "Ism: <b>{name}</b>\n"
            "Tug'ilgan sana: <b>{birth}</b>\n"
            "Jins: <b>{gender}</b>\n"
            "Til: <b>{lang}</b>\n\n"
            "Nimani o'zgartiramiz?"
        ),
        "ask_new_name": "Yangi ismingizni yozing:",
        "updated": "✅ Saqlandi",
        "unknown": (
            "Tushunmadim 🙂\n"
            "Quyidagi tugmalardan foydalaning yoki /start bosing."
        ),
        "use_buttons": "Yuqoridagi tugmalardan birini tanlang 🙏",
        # Admin panel
        "btn_admin": "🛠 Admin Panel",
        "btn_users": "👥 Foydalanuvchilar",
        "btn_stats": "📊 Statistika",
        "admin_title": "🛠 <b>Admin Panel</b>",
        "stats_title": "📊 <b>Statistika</b>",
        "stats_empty": "Hali foydalanuvchi yo'q.",
        "stats_total": "JAMI",
        "st_blocked": "Bloklagan",
        "sec_gender": "JINS",
        "sec_lang": "TIL",
        "sec_age": "YOSH",
        "sec_weeks": "HAFTA BAHOLARI",
        "sec_new": "RO'YXATDAN O'TISH",
        "st_male": "Erkak",
        "st_female": "Ayol",
        "st_unknown": "Noma'lum",
        "st_avg": "O'rtacha",
        "st_good": "Samarali",
        "st_bad": "Behuda",
        "st_rated": "Baho bergan",
        "st_today": "Bugun",
        "st_7d": "7 kun",
        "st_30d": "30 kun",
        "users_title": "👥 <b>Foydalanuvchilar: {total}</b>",
        "col_name": "Ism",
        "col_age": "Yosh",
        "col_gender": "Jins",
        "col_lang": "Til",
        "g_m": "Erkak",
        "g_f": "Ayol",
        "new_user": (
            "🆕 <b>Yangi foydalanuvchi!</b>\n\n"
            "{name} · {age} yosh · {gender} · {lang}\n"
            "{handle}\n\n"
            "Jami: {total} ta"
        ),
        "no_username": "username yo'q",
        # Eslatma
        "btn_reminder": "⏰ Eslatma",
        "btn_add": "➕ Qo'shish",
        "reminders_empty": "⏰ Eslatmalar yo'q.\n\nHar kuni belgilangan vaqtda yuboriladi.",
        "reminders_list": "⏰ <b>Eslatmalar</b> — har kuni\n\n{items}",
        "reminder_item": "{time} — {text}",
        "btn_rm_del": "🗑 {time}",
        "reminders_max": "Ko'pi bilan {n} ta eslatma. Avval birini o'chiring.",
        "ask_rm_text": "Nimani eslatay? Qisqa yozing, masalan: <i>Kitob o'qish</i>",
        "rm_text_too_long": "Qisqaroq yozing (100 belgigacha).",
        "ask_rm_time": (
            "Soat nechada? Format: <code>SS:DD</code> — masalan: <code>21:00</code> "
            "(Toshkent vaqti)"
        ),
        "bad_time": (
            "❗ Vaqt noto'g'ri. <code>SS:DD</code> formatida yozing, "
            "masalan: <code>21:00</code>"
        ),
        "rm_added": "✅ Har kuni <b>{time}</b> da eslataman: {text}",
        "rm_deleted": "🗑 O'chirildi",
        "reminder_msg": "⏰ {text}",
        # Taklif
        "btn_suggest": "💡 Taklif",
        "ask_suggestion": "Botga qanday g'oya qo'shmoqchisiz? Yozing:",
        "suggestion_sent": "Rahmat! Taklifingiz adminga yetkazildi ✅",
        "admin_suggestion": "💡 <b>Taklif</b>\n\n{name} · {handle}\n\n{text}",
        "btn_reply": "✍️ Javob yozish",
        "ask_reply": "<b>{name}</b> uchun javobingizni yozing:",
        "reply_sent": "Javob yuborildi ✅",
        "reply_failed": "Yuborilmadi: foydalanuvchi botni bloklagan.",
        "admin_reply": "📩 <b>Admin javobi</b>\n\n{text}",
        # Admin: barchaga xabar, foydalanuvchini o'chirish
        "btn_broadcast": "📣 Xabar yuborish",
        "ask_broadcast": "Barcha foydalanuvchilarga yuboriladigan xabarni yozing:",
        "broadcast_preview": "Shu xabar <b>{n}</b> foydalanuvchiga yuboriladi.",
        "btn_send": "✅ Yuborish",
        "btn_cancel": "❌ Bekor qilish",
        "broadcast_started": "📣 Yuborish boshlandi: {n} foydalanuvchi",
        "broadcast_done": "📣 Yakunlandi: {sent} yuborildi, {blocked} bloklagan, {failed} xato",
        "broadcast_busy": "Oldingi tarqatish hali tugamagan, biroz kuting.",
        "cancelled": "Bekor qilindi",
        "btn_delete_user": "🗑 Foydalanuvchini o'chirish",
        "del_pick": "🗑 Kimni o'chiramiz?",
        "del_confirm": (
            "❗ <b>{name}</b> ({age} yosh) o'chirilsinmi?\n"
            "Barcha ma'lumotlari va baholari bazadan o'chadi."
        ),
        "btn_del_yes": "🗑 Ha, o'chirish",
        "del_done": "🗑 <b>{name}</b> o'chirildi. Qayta /start bossa, yangidan ro'yxatdan o'tadi.",
        "del_self": "O'zingizni o'chira olmaysiz.",
        "del_missing": "Bu foydalanuvchi allaqachon yo'q.",
        "caption": "Yashaldi: <b>{lived} hafta</b> — {p}%\nQoldi: <b>{left} hafta</b> — {q}%",
    },
    "ru": {
        "greeting": "Ассалому алайкум! 🌙",
        "confirm_name": "Вас зовут <b>{name}</b>?",
        "btn_yes": "✅ Да",
        "btn_other_name": "✏️ Другое имя",
        "ask_name": "Напишите ваше имя:",
        "name_too_long": "Пожалуйста, напишите имя короче (до 64 символов).",
        "confirm_birth": "Ваша дата рождения — <b>{birth}</b>?",
        "btn_other_birth": "✏️ Другая дата",
        "ask_birth": (
            "Введите <b>дату рождения</b>.\n"
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
            "🔔 Каждую пятницу с <b>13:00 до 14:00</b> вы получите календарь жизни, "
            "каждый понедельник утром спрошу о прошедшей неделе.\n\n"
            "⚙️ Настройки — имя, пол и язык."
        ),
        "weekly_q": "Как прошла ваша неделя?",
        "btn_good": "🟢 Продуктивно",
        "btn_bad": "🔴 Впустую",
        "rating_saved": "Сохранено ✅",
        "not_registered": "Сначала зарегистрируйтесь: /start",
        "text_only": "Пожалуйста, напишите текстом 🙏",
        "help": (
            "<b>Mundabit</b> — бот, помогающий ценить время.\n\n"
            "/start — посмотреть календарь и открыть меню\n"
            "⏰ Напоминание — каждый день в выбранное время\n"
            "💡 Предложение — идея для бота\n"
            "⚙️ Настройки — имя, пол и язык\n\n"
            "Каждую пятницу с 13:00 до 14:00 — календарь жизни.\n"
            "Каждый понедельник утром — опрос о прошедшей неделе."
        ),
        "webapp_btn": "Открыть приложение",
        "btn_settings": "⚙️ Настройки",
        "btn_name": "✏️ Изменить имя",
        "btn_gender": "⚧ Изменить пол",
        "btn_lang": "🌐 Изменить язык",
        "ask_lang": "Выберите язык:",
        "btn_uz": "🇺🇿 O'zbekcha",
        "btn_ru": "🇷🇺 Русский",
        "btn_back": "⬅️ Назад",
        "menu": "Главное меню",
        "settings": (
            "⚙️ <b>Настройки</b>\n\n"
            "Имя: <b>{name}</b>\n"
            "Дата рождения: <b>{birth}</b>\n"
            "Пол: <b>{gender}</b>\n"
            "Язык: <b>{lang}</b>\n\n"
            "Что изменим?"
        ),
        "ask_new_name": "Напишите новое имя:",
        "updated": "✅ Сохранено",
        "unknown": (
            "Не понял 🙂\n"
            "Воспользуйтесь кнопками ниже или нажмите /start."
        ),
        "use_buttons": "Выберите один из вариантов выше 🙏",
        # Админ-панель
        "btn_admin": "🛠 Админ-панель",
        "btn_users": "👥 Пользователи",
        "btn_stats": "📊 Статистика",
        "admin_title": "🛠 <b>Админ-панель</b>",
        "stats_title": "📊 <b>Статистика</b>",
        "stats_empty": "Пользователей пока нет.",
        "stats_total": "ВСЕГО",
        "st_blocked": "Заблокир.",
        "sec_gender": "ПОЛ",
        "sec_lang": "ЯЗЫК",
        "sec_age": "ВОЗРАСТ",
        "sec_weeks": "ОЦЕНКИ НЕДЕЛЬ",
        "sec_new": "РЕГИСТРАЦИИ",
        "st_male": "Мужчины",
        "st_female": "Женщины",
        "st_unknown": "Не указан",
        "st_avg": "Средний",
        "st_good": "Продуктивно",
        "st_bad": "Впустую",
        "st_rated": "Оценили",
        "st_today": "Сегодня",
        "st_7d": "7 дней",
        "st_30d": "30 дней",
        "users_title": "👥 <b>Пользователи: {total}</b>",
        "col_name": "Имя",
        "col_age": "Возр",
        "col_gender": "Пол",
        "col_lang": "Язык",
        "g_m": "Муж",
        "g_f": "Жен",
        "new_user": (
            "🆕 <b>Новый пользователь!</b>\n\n"
            "{name} · {age} лет · {gender} · {lang}\n"
            "{handle}\n\n"
            "Всего: {total}"
        ),
        "no_username": "без username",
        # Напоминание
        "btn_reminder": "⏰ Напоминание",
        "btn_add": "➕ Добавить",
        "reminders_empty": "⏰ Напоминаний нет.\n\nОни приходят каждый день в указанное время.",
        "reminders_list": "⏰ <b>Напоминания</b> — каждый день\n\n{items}",
        "reminder_item": "{time} — {text}",
        "btn_rm_del": "🗑 {time}",
        "reminders_max": "Не больше {n} напоминаний. Сначала удалите одно.",
        "ask_rm_text": "О чём напомнить? Коротко, например: <i>Читать книгу</i>",
        "rm_text_too_long": "Напишите короче (до 100 символов).",
        "ask_rm_time": (
            "Во сколько? Формат: <code>ЧЧ:ММ</code> — например: <code>21:00</code> "
            "(время Ташкента)"
        ),
        "bad_time": (
            "❗ Неверное время. Введите в формате <code>ЧЧ:ММ</code>, "
            "например: <code>21:00</code>"
        ),
        "rm_added": "✅ Буду напоминать каждый день в <b>{time}</b>: {text}",
        "rm_deleted": "🗑 Удалено",
        "reminder_msg": "⏰ {text}",
        # Предложение
        "btn_suggest": "💡 Предложение",
        "ask_suggestion": "Какую идею вы хотите предложить для бота? Напишите:",
        "suggestion_sent": "Спасибо! Ваше предложение передано администратору ✅",
        "admin_suggestion": "💡 <b>Предложение</b>\n\n{name} · {handle}\n\n{text}",
        "btn_reply": "✍️ Ответить",
        "ask_reply": "Напишите ответ для <b>{name}</b>:",
        "reply_sent": "Ответ отправлен ✅",
        "reply_failed": "Не отправлено: пользователь заблокировал бота.",
        "admin_reply": "📩 <b>Ответ администратора</b>\n\n{text}",
        # Админ: рассылка, удаление пользователя
        "btn_broadcast": "📣 Рассылка",
        "ask_broadcast": "Напишите сообщение для всех пользователей:",
        "broadcast_preview": "Это сообщение получат <b>{n}</b> пользователей.",
        "btn_send": "✅ Отправить",
        "btn_cancel": "❌ Отмена",
        "broadcast_started": "📣 Рассылка началась: {n} пользователей",
        "broadcast_done": "📣 Готово: {sent} отправлено, {blocked} заблокировали, {failed} ошибок",
        "broadcast_busy": "Предыдущая рассылка ещё идёт, подождите.",
        "cancelled": "Отменено",
        "btn_delete_user": "🗑 Удалить пользователя",
        "del_pick": "🗑 Кого удалить?",
        "del_confirm": (
            "❗ Удалить <b>{name}</b> ({age} лет)?\n"
            "Все данные и оценки будут удалены из базы."
        ),
        "btn_del_yes": "🗑 Да, удалить",
        "del_done": "🗑 <b>{name}</b> удалён. При новом /start пройдёт регистрацию заново.",
        "del_self": "Нельзя удалить себя.",
        "del_missing": "Этого пользователя уже нет.",
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
