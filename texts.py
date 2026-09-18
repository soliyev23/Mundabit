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


# Eslatma: hafta kunlari (0 = dushanba, datetime.weekday() bilan bir xil)
WEEKDAYS_FULL = {
    "uz": ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba",
           "Yakshanba"],
    "ru": ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота",
           "Воскресенье"],
}
WEEKDAYS_EVERY = {
    "uz": ["har dushanba", "har seshanba", "har chorshanba", "har payshanba",
           "har juma", "har shanba", "har yakshanba"],
    # Ruscha «каждый/каждую/каждое» jins bo'yicha o'zgaradi — «по …» shakli bir xil
    "ru": ["по понедельникам", "по вторникам", "по средам", "по четвергам",
           "по пятницам", "по субботам", "по воскресеньям"],
}


def fmt_day_month(d: date, lang: str, today: date | None = None) -> str:
    """«25 sentyabr»; joriy yildan boshqa bo'lsa yil ham qo'shiladi."""
    today = today or date.today()
    s = f"{d.day} {MONTHS[lang][d.month - 1]}"
    return s if d.year == today.year else f"{s} {d.year}"


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
            "⏰ Eslatma — kerakli vaqtda eslatib turish\n"
            "✉️ Murojaat — savol, taklif yoki fikr yuborish\n"
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
            "Til: <b>{lang}</b>\n"
            "English: <b>{english}</b>\n\n"
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
        "reminders_empty": "⏰ Eslatmalar yo'q.",
        "reminders_list": "⏰ <b>Eslatmalar</b>\n\n{items}",
        "reminder_item": "{n}. <b>{time}</b> · {when} — {text}",
        "btn_rm_del": "➖ O'chirish",
        "ask_rm_delete": "Qaysi eslatmani o'chiramiz?",
        "reminders_max": "Ko'pi bilan {n} ta eslatma. Avval birini o'chiring.",
        "ask_rm_text": "Eslatma nomini yozing.\nMasalan: <i>Kitob o'qish</i>",
        "rm_text_too_long": "Qisqaroq yozing (100 belgigacha).",
        "rm_name_first": "Avval eslatma nomini yozing 🙏",
        "ask_rm_photo": "Rasm yuboring yoki o'tkazib yuboring:",
        "btn_skip": "⏭ O'tkazib yuborish",
        "rm_photo_or_skip": "Rasm yuboring yoki «⏭ O'tkazib yuborish» ni bosing 👇",
        "use_keyboard": "Quyidagi tugmalardan birini tanlang 👇",
        "rm_photo_mark": "🖼",
        "ask_rm_time": (
            "Soat nechada? Format: <code>SS:DD</code> — masalan: <code>21:00</code> "
            "(Toshkent vaqti)"
        ),
        "bad_time": (
            "❗ Vaqt noto'g'ri. <code>SS:DD</code> formatida yozing, "
            "masalan: <code>21:00</code>"
        ),
        "ask_rm_freq": "Qanchada bir takrorlansin?",
        "freq_daily": "Har kuni",
        "freq_weekdays": "Ish kunlari",
        "freq_weekly": "Haftada bir",
        "freq_monthly": "Oyda bir",
        "freq_once": "Bir marta",
        "when_daily": "har kuni",
        "when_weekdays": "ish kunlari",
        "when_monthly": "har oy {d}-sanada",
        "ask_rm_weekday": "Haftaning qaysi kuni?",
        "ask_rm_monthday": "Oyning nechanchi sanasida?",
        "ask_rm_date": "Qaysi sana? Format: <code>KK.OO</code> — masalan: <code>25.09</code>",
        "bad_rm_date": (
            "❗ Sana noto'g'ri yoki o'tib ketgan. <code>KK.OO</code> formatida "
            "yozing, masalan: <code>25.09</code>"
        ),
        "rm_past": "❗ Bu vaqt o'tib ketgan. Keyinroq vaqtni yozing.",
        "rm_deleted": "🗑 O'chirildi",
        "reminder_msg": "⏰ {text}",
        # Murojaat
        "btn_suggest": "✉️ Murojaat",
        "ask_suggestion": "Murojaat yoki takliflaringiz bo'lsa, o'z fikringizni yozib qoldiring:",
        "suggestion_sent": "Rahmat! Murojaatingiz adminga yetkazildi ✅",
        "admin_suggestion": "✉️ <b>Murojaat</b>\n\n{name} · {handle}\n\n{text}",
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
        # English
        "btn_english": "🇬🇧 English",
        "btn_en_on": "🇬🇧 English'ni yoqish",
        "btn_en_off": "🇬🇧 English'ni o'chirish",
        "en_state_on": "yoqilgan",
        "en_state_off": "o'chirilgan",
        "en_enabled": "✅ English yoqildi. Asosiy menyuda «🇬🇧 English» tugmasi paydo bo'ldi.",
        "en_disabled": "English o'chirildi.",
        "en_is_off": "🇬🇧 English o'chirilgan. Uni ⚙️ Sozlamalardan yoqish mumkin.",
        "en_intro": (
            "🇬🇧 <b>English</b>\n\n"
            "Har kuni 3 ta yangi so'z: ertalab {time} da keladi. "
            "O'rganilgan so'zlar vaqti-vaqti bilan takrorlanadi.\n\n"
            "Lug'atda {total} ta so'z:\n{levels}\n\n"
            "Maqsad: <b>B2</b> darajasi — IELTS 6.0 uchun yetarli so'z boyligi.\n\n"
            "Avval darajangizni aniqlaymiz: {questions} tagacha savol."
        ),
        "en_level_line": "{level} — {n} ta",
        "btn_en_start": "▶️ Testni boshlash",
        "btn_en_retest": "🎯 Darajani aniqlash",
        "btn_en_vocab": "📚 Vocabulary",
        "en_title": "🇬🇧 <b>English</b>",
        "en_next_test": "Keyingi test: {date}",
        "en_retest_locked": "🎯 Darajani qayta aniqlash {date}dan ochiladi.",
        "btn_dont_know": "🤷 Bilmayman",
        "en_test_q": "🎯 Savol {n}\n\nMa'nosini tanlang: <b>{word}</b>",
        "en_test_done": "🎯 Test yakunlandi",
        "en_level_result": "Darajangiz: <b>{level}</b>",
        "en_test_score": "{level} — {total} tadan {ok} ta to'g'ri",
        "en_test_mistakes": "Xato javoblar:",
        "en_today_title": "🇬🇧 <b>Bugungi so'zlar</b> · {level}",
        "en_all_done": "🎉 Lug'atdagi barcha so'zlarni o'rgandingiz.",
        "en_review_q": "🔁 Takrorlash {i}/{n}\n\nMa'nosini tanlang: <b>{word}</b>",
        "en_right": "✅ To'g'ri",
        "en_wrong": "❌ <b>{word}</b> — {tr}",
        "en_reviews_hint": "🔁 Takrorlash uchun {n} ta so'z bor — «🇬🇧 English» → «📚 Vocabulary».",
        "en_reviews_done": "🔁 Takrorlash tugadi.",
        "en_announce": (
            "🇬🇧 <b>Yangi: English</b>\n\n"
            "Har kuni ertalab 3 ta inglizcha so'z — darajangizga mos, takrorlash bilan.\n\n"
            "Yoqish: ⚙️ Sozlamalar → 🇬🇧 English'ni yoqish"
        ),
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
            "⏰ Напоминание — напомнит в нужное время\n"
            "✉️ Обращение — вопрос, предложение или отзыв\n"
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
            "Язык: <b>{lang}</b>\n"
            "English: <b>{english}</b>\n\n"
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
        "reminders_empty": "⏰ Напоминаний нет.",
        "reminders_list": "⏰ <b>Напоминания</b>\n\n{items}",
        "reminder_item": "{n}. <b>{time}</b> · {when} — {text}",
        "btn_rm_del": "➖ Удалить",
        "ask_rm_delete": "Какое напоминание удалить?",
        "reminders_max": "Не больше {n} напоминаний. Сначала удалите одно.",
        "ask_rm_text": "Напишите название напоминания.\nНапример: <i>Читать книгу</i>",
        "rm_text_too_long": "Напишите короче (до 100 символов).",
        "rm_name_first": "Сначала напишите название 🙏",
        "ask_rm_photo": "Отправьте фото или пропустите:",
        "btn_skip": "⏭ Пропустить",
        "rm_photo_or_skip": "Отправьте фото или нажмите «⏭ Пропустить» 👇",
        "use_keyboard": "Выберите вариант на клавиатуре ниже 👇",
        "rm_photo_mark": "🖼",
        "ask_rm_time": (
            "Во сколько? Формат: <code>ЧЧ:ММ</code> — например: <code>21:00</code> "
            "(время Ташкента)"
        ),
        "bad_time": (
            "❗ Неверное время. Введите в формате <code>ЧЧ:ММ</code>, "
            "например: <code>21:00</code>"
        ),
        "ask_rm_freq": "Как часто повторять?",
        "freq_daily": "Каждый день",
        "freq_weekdays": "По будням",
        "freq_weekly": "Раз в неделю",
        "freq_monthly": "Раз в месяц",
        "freq_once": "Один раз",
        "when_daily": "каждый день",
        "when_weekdays": "по будням",
        "when_monthly": "каждый месяц {d}-го числа",
        "ask_rm_weekday": "В какой день недели?",
        "ask_rm_monthday": "Какого числа?",
        "ask_rm_date": "Какая дата? Формат: <code>ДД.ММ</code> — например: <code>25.09</code>",
        "bad_rm_date": (
            "❗ Неверная или прошедшая дата. Введите в формате <code>ДД.ММ</code>, "
            "например: <code>25.09</code>"
        ),
        "rm_past": "❗ Это время уже прошло. Укажите более позднее.",
        "rm_deleted": "🗑 Удалено",
        "reminder_msg": "⏰ {text}",
        # Обращение
        "btn_suggest": "✉️ Обращение",
        "ask_suggestion": "Если у вас есть обращение или предложение, оставьте своё сообщение:",
        "suggestion_sent": "Спасибо! Ваше обращение передано администратору ✅",
        "admin_suggestion": "✉️ <b>Обращение</b>\n\n{name} · {handle}\n\n{text}",
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
        # English
        "btn_english": "🇬🇧 English",
        "btn_en_on": "🇬🇧 Включить English",
        "btn_en_off": "🇬🇧 Выключить English",
        "en_state_on": "включён",
        "en_state_off": "выключен",
        "en_enabled": "✅ English включён. В главном меню появилась кнопка «🇬🇧 English».",
        "en_disabled": "English выключен.",
        "en_is_off": "🇬🇧 English выключен. Его можно включить в ⚙️ Настройках.",
        "en_intro": (
            "🇬🇧 <b>English</b>\n\n"
            "Каждый день 3 новых слова: приходят утром в {time}. "
            "Изученные слова время от времени повторяются.\n\n"
            "В словаре {total} слов:\n{levels}\n\n"
            "Цель: уровень <b>B2</b> — словарный запас, достаточный для IELTS 6.0.\n\n"
            "Сначала определим ваш уровень: до {questions} вопросов."
        ),
        "en_level_line": "{level} — {n}",
        "btn_en_start": "▶️ Начать тест",
        "btn_en_retest": "🎯 Определить уровень",
        "btn_en_vocab": "📚 Vocabulary",
        "en_title": "🇬🇧 <b>English</b>",
        "en_next_test": "Следующий тест: {date}",
        "en_retest_locked": "🎯 Повторный тест откроется {date}.",
        "btn_dont_know": "🤷 Не знаю",
        "en_test_q": "🎯 Вопрос {n}\n\nВыберите перевод: <b>{word}</b>",
        "en_test_done": "🎯 Тест завершён",
        "en_level_result": "Ваш уровень: <b>{level}</b>",
        "en_test_score": "{level} — верно {ok} из {total}",
        "en_test_mistakes": "Ошибки:",
        "en_today_title": "🇬🇧 <b>Слова на сегодня</b> · {level}",
        "en_all_done": "🎉 Вы изучили все слова словаря.",
        "en_review_q": "🔁 Повторение {i}/{n}\n\nВыберите перевод: <b>{word}</b>",
        "en_right": "✅ Верно",
        "en_wrong": "❌ <b>{word}</b> — {tr}",
        "en_reviews_hint": "🔁 На повторение {n} слов — «🇬🇧 English» → «📚 Vocabulary».",
        "en_reviews_done": "🔁 Повторение завершено.",
        "en_announce": (
            "🇬🇧 <b>Новое: English</b>\n\n"
            "Каждое утро 3 английских слова — по вашему уровню, с повторением.\n\n"
            "Включить: ⚙️ Настройки → 🇬🇧 Включить English"
        ),
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


# Nomi o'zgargan tugmalarning eski matnlari. Foydalanuvchida eski klaviatura
# qolib ketgan bo'lishi mumkin — bosganda baribir tanilsin. Ko'rsatilmaydi.
LEGACY_BUTTONS = {
    "btn_suggest": {"💡 Taklif", "💡 Предложение"},   # 2026-09-17: → Murojaat
    # 2026-09-17: «🗑 N» → «O'chirish N» → «O'chirish» → «➖ O'chirish». Eski
    # raqamli tugmalar raqam bo'yicha o'chirmaydi, faqat tanlov ro'yxatini ochadi.
    "btn_rm_del": {f"{p} {n}" for p in ("🗑", "O'chirish", "Удалить")
                   for n in range(1, 6)} | {"O'chirish", "Удалить"},
}


# English: so'z turkumlari
POS_NAMES = {
    "uz": {"n": "ot", "v": "fe'l", "adj": "sifat", "adv": "ravish",
           "pv": "frazali fe'l", "phr": "ibora"},
    "ru": {"n": "сущ.", "v": "глагол", "adj": "прил.", "adv": "нареч.",
           "pv": "фразовый глагол", "phr": "выражение"},
}


def t(lang: str, key: str) -> str:
    return BOT.get(lang, BOT["uz"])[key]
