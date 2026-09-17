# Mundabit — intizom va vaqtni anglash boti

Telegram bot: umringizni haftalarga bo'lib ("Hayot Kalendari"), qancha
yashaganingiz va O'zbekiston o'rtacha umr yoshigacha (erkak 72 / ayol 76 /
belgilanmagan 74) qancha qolganini ko'rsatadi. Ikki til: o'zbek va rus.

Oqim: `/start` → til → ism → tug'ilgan sana → jins → kalendar. Ism va tug'ilgan
sana Telegram profilidan olinib, tasdiqlash uchun taklif qilinadi (sana — faqat
foydalanuvchi uni hammaga ochiq qilgan va yilni ko'rsatgan bo'lsa); rad etilsa
qo'lda kiritiladi.

- **Dushanba 08:00–09:00** — "O'tgan hafta qanday o'tdi?" so'rovi
  (🟢 Samarali / 🔴 Behuda); javob kalendardagi katakni yashil yoki qizil
  qiladi. Baholanmagan o'tmish — kulrang katak va ustida ✕.
- **Juma 13:00–14:00** — barcha foydalanuvchilarga yangilangan kalendar.

Ikkala tarqatish ham bir zumda emas, **shu oyna bo'ylab yoyib** yuboriladi
(`BROADCAST_WINDOW_MINUTES`). Sur'at o'zini to'g'irlaydi: foydalanuvchi kam
bo'lsa bir necha soniyada tugaydi, ko'p bo'lsa oynaga tekis taqsimlanadi.
Shuning uchun protsessor tiqilib qolmaydi va bot tarqatish paytida ham
odatdagidek javob beradi.

## Foydalanuvchi interfeysi

Ro'yxatdan o'tgach doimiy klaviatura chiqadi:

- **⏰ Eslatma** — shaxsiy eslatma. Tartib: nom (100 belgigacha) → rasm
  (ixtiyoriy, o'tkazib yuborsa bo'ladi) → takrorlanish → kerak bo'lsa kun yoki
  sana → soat (`SS:DD`, Toshkent vaqti). Barcha tanlovlar pastki klaviaturada.
  Takrorlanish: har kuni, ish kunlari (Du–Ju), haftada bir (kun tanlanadi),
  oyda bir (1–31 sana; qisqa oyda oxirgi kuni keladi), bir marta (`KK.OO`
  sana; yuborilgach o'chadi). Bir foydalanuvchida ko'pi bilan 5 ta.
  Ro'yxat raqamlangan. «➖ O'chirish» bosilsa klaviaturada eslatmalar nomlari
  chiqadi, tanlangani o'chiriladi.
- **✉️ Murojaat** — foydalanuvchi savol, taklif yoki fikrini yozadi, u ismi va username'i bilan
  adminga boradi. Admin xabardagi **✍️ Javob yozish** tugmasi orqali o'sha
  odamga javob qaytaradi; javob unga "📩 Admin javobi" ko'rinishida yetadi.
- **⚙️ Sozlamalar** — ism, jins va tilni o'zgartirish. Joriy ma'lumot ham shu
  yerda ko'rinadi. Jins yoki til o'zgarsa kalendar darhol qayta yuboriladi.
- **🛠 Admin Panel** — faqat `ADMIN_IDS` ichidagilarga:
  - **👥 Foydalanuvchilar** — sahifalanadigan jadval (№ · ism · yosh · jins · til)
  - **📊 Statistika** — jami / jins / til / yosh / hafta baholari / ro'yxatdan
    o'tish kesimida, foizlar va diagramma bilan
  - **📣 Xabar yuborish** — barcha faol foydalanuvchilarga. Admin xabarni
    yozadi (rasm, formatlash ham bo'ladi — xabar `copy_message` bilan
    ko'chiriladi), tasdiqlagach yuboriladi va oxirida hisobot qaytadi.
  - **🗑 Foydalanuvchini o'chirish** — ro'yxatdan tanlanadi, tasdiqlangach
    foydalanuvchi, uning baholari va eslatmalari bazadan o'chadi. Qayta
    `/start` bossa, yangidan ro'yxatdan o'tadi. Adminning o'zi o'chmaydi.

Tug'ilgan sanani foydalanuvchi o'zi o'zgartira olmaydi — bu keyinchalik faqat
admin orqali qilinadi. Sana o'zgarganda `db.change_birth_date()` eski baholarni
**haqiqiy kalendar haftalariga qarab qayta raqamlaydi**, ya'ni baholangan real
haftalar o'z joyida qoladi.

Botni bloklagan foydalanuvchi avtomatik belgilanadi va tarqatishga
qo'shilmaydi; qaytib yozsa, o'zi tiklanadi.

## Buyruqlar

| Buyruq | Vazifasi |
|---|---|
| `/start` | Ro'yxatdan o'tish; keyinchalik — kalendar va menyu |
| `/help` | Yordam |
| `/hayot` | Kalendarni qayta ko'rish (ro'yxatda ko'rsatilmaydi) |
| `/sozlamalar` | Sozlamalar menyusi (ro'yxatda ko'rsatilmaydi) |
| `/admin` | Admin panel (faqat `ADMIN_IDS`) |

## Ishga tushirish

1. [@BotFather](https://t.me/BotFather) dan token oling.
2. `.env` faylini yarating: `cp .env.example .env`, ichiga tokenni yozing.
3. Bog'liqliklar va ishga tushirish:

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   .venv/bin/python bot.py
   ```

## Mini App

`webapp/index.html` — Telegram Web App: hayot haftalari canvas'da, foizlar va
progress; Telegram temasiga (light/dark) va foydalanuvchi tiliga moslashadi.

Bot ishga tushganda `WEBAPP_PORT` (8080) da server ochiladi. Telegram ichida
ko'rinishi uchun HTTPS manzil kerak:

```bash
cloudflared tunnel --url http://localhost:8080
# chiqqan https://....trycloudflare.com manzilini .env dagi WEBAPP_URL ga yozing
```

`WEBAPP_URL` to'ldirilgach, har bir poster ostida "Ilovada ko'rish" tugmasi va
chatda menyu tugmasi paydo bo'ladi. Bo'sh qolsa, bot Mini App'siz ishlayveradi.

Brauzerda tez ko'rish (namunaviy ma'lumot bilan): `http://localhost:8080/`

## Serverda (Oracle, Oracle Cloud)

Bot `/opt/mundabit` da systemd xizmati sifatida ishlaydi:

```bash
sudo systemctl status mundabit       # holat
sudo journalctl -u mundabit -f       # jonli loglar
sudo systemctl restart mundabit      # qayta ishga tushirish
```

`start.sh` avval `cloudflared` quick tunnel ochib, chiqqan HTTPS manzilni
`WEBAPP_URL` sifatida botga beradi, keyin botni ishga tushiradi. Har restartda
tunnel manzili yangilanadi — eski xabarlardagi Mini App tugmalari ishlamay
qoladi. Doimiy domen ulangach, tunnel o'rniga nginx/Caddy + Let's Encrypt.

## Kod yuklash — git orqali

Markaziy (bare) repo shu serverning o'zida: `/home/opc/git/mundabit.git`.
Server va Mac shunga ulanadi, GitHub ishlatilmaydi.

```bash
# Mac'ni birinchi marta ulash
git remote add origin oracle-test:git/mundabit.git
git fetch origin && git checkout -b main --track origin/main
```

Ish tartibi (ikkala tomonda ham):

```bash
git pull                                   # tahrirdan OLDIN
# ... tahrir ...
git add -A && git commit -m "..." && git push
sudo systemctl restart mundabit            # serverda, bot kodi o'zgargan bo'lsa
```

> **`rsync` ishlatilmaydi.** Eski `rsync --delete` buyrug'ining exclude
> ro'yxatida `.git` yo'q edi — u serverdagi repo'ni o'chirib yuboradi.

## Tuzilma

- `bot.py` — handlerlar, FSM, sozlamalar, admin panel, tarqatish
- `visual.py` — statistika hisoblash va "Life in Weeks" PNG poster (Pillow)
- `texts.py` — barcha matnlar, o'zbek va rus tillarida
- `db.py` — SQLite baza (foydalanuvchilar, hafta baholari, eslatmalar)
- `webserver.py` — Mini App server: statik sahifa + initData imzosi tekshiruvi
- `webapp/index.html` — Mini App frontend
- `config.py` — sozlamalar (`.env` orqali)
- `deploy/` — systemd unit va ishga tushirish skripti

## Sozlamalar (.env)

| O'zgaruvchi | Standart | Izoh |
|---|---|---|
| `BOT_TOKEN` | — | @BotFather dan |
| `LIFE_EXPECTANCY_MALE` / `_FEMALE` / `_DEFAULT` | 72 / 76 / 74 | o'rtacha umr yoshi |
| `TIMEZONE` | `Asia/Tashkent` | |
| `NOTIFY_DAY_OF_WEEK` / `_HOUR` / `_MINUTE` | mon / 8 / 0 | hafta yakuni so'rovi |
| `CALENDAR_DAY_OF_WEEK` / `_HOUR` / `_MINUTE` | fri / 13 / 0 | kalendar oynasi boshlanishi |
| `BROADCAST_WINDOW_MINUTES` | 60 | tarqatish shu oyna bo'ylab yoyiladi |
| `ADMIN_IDS` | egasi | vergul bilan; birinchisiga yangi user xabari boradi. Standart — faqat egasi |
| `WEBAPP_URL` / `WEBAPP_PORT` | — / 8080 | Mini App |
| `DB_PATH` | `mundabit.db` | |
