# Mundabit — intizom va vaqtni anglash boti

Telegram bot: umringizni haftalarga bo'lib ("Hayot Kalendari"), qancha yashaganingiz
va O'zbekiston o'rtacha umr yoshigacha (erkak 72 / ayol 76) qancha qolganini
ko'rsatadi. Ikki til: o'zbek/rus.

Oqim: /start → til → ism → tug'ilgan sana → jins → kalendar.

- **Dushanba 08:00** — "O'tgan hafta qanday o'tdi?" so'rovi (🟢 Samarali / 🔴 Behuda);
  javob kalendardagi katakni yashil/qizil qiladi. Baholanmagan o'tmish — kulrang + x.
- **Juma 13:30** — barcha foydalanuvchilarga yangilangan kalendar yuboriladi.
- **/admin** (faqat `ADMIN_ID`) — userlar soni/ro'yxati, jins va til kesimi,
  o'rtacha yosh, baholar statistikasi.

## Ishga tushirish

1. Telegram'da [@BotFather](https://t.me/BotFather) ga kiring → `/newbot` → bot nomi
   va username bering → **token** oling.

2. `.env` fayl yarating:

   ```bash
   cp .env.example .env
   # .env ichiga tokeningizni yozing
   ```

3. Bog'liqliklarni o'rnating va ishga tushiring:

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   .venv/bin/python bot.py
   ```

## Buyruqlar

| Buyruq | Vazifasi |
|---|---|
| `/start` | Ro'yxatdan o'tish: ism va tug'ilgan sana |
| `/hayot` | Hayot xaritasini qayta ko'rish |
| `/eslatma` | Haftalik eslatmani yoqish/o'chirish |
| `/help` | Yordam |

## Mini App

`webapp/index.html` — Telegram Web App: hayot haftalari animatsiyalangan canvas'da,
foizlar va progress. Telegram temasiga (light/dark) avtomatik moslashadi.

Bot ishga tushganda `WEBAPP_PORT` (8080) da server ochiladi. Telegram ichida
ko'rinishi uchun HTTPS manzil kerak — lokal test uchun tunnel oching:

```bash
cloudflared tunnel --url http://localhost:8080
# chiqqan https://....trycloudflare.com manzilini .env dagi WEBAPP_URL ga yozing
```

`WEBAPP_URL` to'ldirilgach, har bir poster ostida "Ilovada ko'rish" tugmasi va
chatda menyu tugmasi paydo bo'ladi. Bo'sh qolsa, bot Mini App'siz ishlayveradi.

Brauzerda tez ko'rish (Telegram'siz, namunaviy ma'lumot bilan):
`http://localhost:8080/` yoki qorong'i tema uchun `http://localhost:8080/?theme=dark`

## Serverda (Oracle Test, Oracle Cloud)

Bot `/opt/mundabit` da systemd xizmati sifatida ishlaydi (`ssh oracle-test`):

```bash
sudo systemctl status mundabit       # holat
sudo journalctl -u mundabit -f       # jonli loglar
sudo systemctl restart mundabit      # qayta ishga tushirish
```

`deploy/start.sh` avval `cloudflared` quick tunnel ochib, chiqqan HTTPS manzilni
`WEBAPP_URL` sifatida botga beradi (Mini App uchun), keyin botni ishga tushiradi.
Har restartda tunnel manzili yangilanadi — eski xabarlardagi tugmalar ishlamay
qoladi, `/hayot` bosib yangi tugma olinadi. Doimiy domen ulangach, tunnel o'rniga
nginx/Caddy + Let's Encrypt qo'yiladi.

Yangi kodni yuklash (Mac'dan):

```bash
rsync -az --delete -e ssh --exclude .venv --exclude __pycache__ --exclude 'namuna_*.png' \
  --exclude tunnel.log ./ oracle-test:/opt/mundabit/
ssh oracle-test "sudo systemctl restart mundabit"
```

Diqqat: `--delete` bilan rsync serverdagi `.env` va `mundabit.db` ni ham lokal
nusxa bilan almashtiradi — baza serverda o'zgargan bo'lsa, avval uni yuklab oling
(`rsync oracle-test:/opt/mundabit/mundabit.db ./`) yoki `--exclude mundabit.db --exclude .env` qo'shing.

## Tuzilma

- `bot.py` — asosiy bot: /start oqimi (FSM), buyruqlar, haftalik scheduler
- `visual.py` — statistika hisoblash va "Life in Weeks" PNG poster (Pillow)
- `webserver.py` — Mini App server: statik sahifa + initData imzosi tekshiriladigan API
- `webapp/index.html` — Mini App frontend
- `db.py` — SQLite baza (foydalanuvchilar)
- `config.py` — sozlamalar (.env orqali)

## Sozlamalar (.env)

- `LIFE_EXPECTANCY_YEARS` — o'rtacha umr yoshi (standart: 70)
- `TIMEZONE` — vaqt mintaqasi (standart: Asia/Tashkent)
- `NOTIFY_DAY_OF_WEEK`, `NOTIFY_HOUR`, `NOTIFY_MINUTE` — eslatma vaqti
  (standart: dushanba 08:00)
