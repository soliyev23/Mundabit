# Mundabit — Claude Code uchun yo'riqnoma

Telegram bot: umrni haftalarga bo'lib ko'rsatadi ("Hayot Kalendari"), har juma
kalendar, har dushanba o'tgan hafta haqida so'rov yuboradi. Ikki til: uz/ru.
Foydalanuvchilar asosan O'zbekistonda.

## Eng muhimi: deploy git orqali, rsync ISHLATILMAYDI

Bot Oracle serverida `/opt/mundabit` da systemd xizmati sifatida ishlaydi va
o'sha papkaning o'zi git ish nusxasi. Markaziy bare repo ham shu serverda:
`/home/opc/git/mundabit.git` (GitHub yo'q). Mac va server ikkalasi shunga
ulanadi: `oracle-test:git/mundabit.git`.

> **`rsync -az --delete ... oracle-test:/opt/mundabit/` buyrug'ini HECH QACHON
> ishlatmang.** Uning exclude ro'yxatida `.git` yo'q — u serverdagi repo'ni
> o'chirib yuboradi va serverda qilingan commit'lar yo'qoladi. Eski README'da
> shu buyruq bor edi, endi olib tashlangan.

Ish tartibi ikkala tomonda ham:

```bash
git pull                                    # tahrirdan OLDIN, har safar
# ... tahrir ...
git add -A && git commit -m "..." && git push
```

Serverda, bot kodi o'zgargan bo'lsa — `sudo systemctl restart mundabit`, keyin
`journalctl -u mundabit -n 20` bilan xatosiz ko'tarilganini tekshirish.
Foydalanuvchi buning uchun doimiy ruxsat bergan, har safar so'rash shart emas.
Mac'da restart qilib bo'lmaydi — u yerdan faqat push qilinadi.

## Git'ga hech qachon kirmasligi kerak

`.env` (bot tokeni), `mundabit.db` (foydalanuvchilar bazasi), `.venv/`,
`__pycache__/`, `tunnel.log`. Hammasi `.gitignore` da. Commit'dan oldin
staged ro'yxatni tekshiring — token bir marta tarixga tushsa, tozalash og'ir.
(2026-09-12 da `.env.example` dagi haqiqiy token `filter-branch` bilan butun
tarixdan olib tashlangan; shuning uchun eski klonlar yaroqsiz, yangidan
klon qilish kerak.)

## Tuzilma

| Fayl | Vazifasi |
|---|---|
| `bot.py` | handlerlar, FSM, sozlamalar menyusi, admin panel, tarqatish |
| `visual.py` | statistika hisoblash va PNG poster (Pillow) |
| `texts.py` | **barcha** foydalanuvchi matnlari, uz va ru |
| `db.py` | SQLite: `users`, `week_ratings` |
| `webserver.py` | Mini App uchun aiohttp server, initData imzosi tekshiriladi |
| `webapp/index.html` | Mini App frontend (canvas) |
| `config.py` | `.env` dan sozlamalar |
| `deploy/` | systemd unit va `start.sh` |

## Kod bo'yicha qoidalar

**Matn qattiq yozilmaydi.** Foydalanuvchiga ko'rinadigan har bir satr
`texts.py` dagi `BOT` lug'atida, **ikkala tilda** bo'lishi shart. Kodda
`t(lang, "kalit")` orqali olinadi. `BOT["uz"]` va `BOT["ru"]` kalitlari
to'liq mos bo'lishi kerak.

**Til aniqlash:** `user_lang(user, tg_user)` — avval bazadagi tanlov, u yo'q
bo'lsa Telegram interfeysi tili. Hech qachon `t("uz", ...)` deb qotirmang.

**Tugmalar ikki tilda taniladi:** reply-klaviatura tugmalari
`F.text.in_(btn_variants("kalit"))` bilan ushlanadi, chunki foydalanuvchi
tilni almashtirgach eski klaviatura qolib ketishi mumkin.

**Handler tartibi muhim.** `unknown_message` (fallback) eng oxirida turishi
shart — u hech bir handlerga tushmagan xabarni ushlaydi. Yangi handler
qo'shsangiz, uni fallback'dan **yuqoriga** qo'ying, aks holda ishlamaydi.

**Og'ir hisob event loop'ni bloklamasin.** Poster renderi ~117 ms CPU oladi va
`asyncio.to_thread` orqali chaqiriladi. Shunga o'xshash ishlarni ham shunday
qiling.

**Tarqatish `spread_send()` orqali.** Xabarlar `BROADCAST_WINDOW_MINUTES` (60)
oynasi bo'ylab yoyiladi, sur'at o'zini to'g'irlaydi. Botni bloklaganlar
avtomatik belgilanadi va chiqariladi. Yangi ommaviy yuborish qo'shsangiz,
to'g'ridan-to'g'ri sikl yozmang — shu funksiyadan foydalaning.

**Tug'ilgan sana faqat `db.change_birth_date()` orqali.** U eski baholarni
haqiqiy kalendar haftalariga qarab qayta raqamlaydi. `db.update_user()` sanani
qabul qilmaydi — ataylab.

## Sinash

Repo'da test yo'q. O'zgarishni tekshirish uchun soxta aiogram session yozib,
haqiqiy `Dispatcher` orqali update yuborish usuli ishlaydi: `BaseSession`
merosxo'ri `make_request` ni ushlab qoladi, tarmoq kerak emas.
Bazani sinaganda **`mundabit.db` ning nusxasida** ishlang:
`DB_PATH=/tmp/test.db` va oldin `db.init_db()` ni chaqiring (migratsiya uchun).

Poster o'zgarsa, eski va yangi natijani `PIL.ImageChops.difference` bilan
solishtirib, piksel-piksel bir xilligini tekshirish mumkin.

## Qabul qilingan qarorlar (qayta ko'tarmang)

- Poster o'lchami **1282×1758 qoladi**. Kichraytirish taklif qilingan va rad
  etilgan; tezlik kataklarni tayyor nusxadan qo'yish bilan yechilgan.
- Rus tilida yosh **"23 лет"** shaklida — grammatik "года/год" kerak emas.
- Telegram buyruqlar ro'yxatida faqat `/start` va `/help`.
  `/hayot`, `/sozlamalar`, `/admin` ishlaydi, lekin ro'yxatda ko'rsatilmaydi.
- Tarqatish: juma 13:00–14:00, dushanba 08:00–09:00, oyna bo'ylab yoyib.
- Tug'ilgan sanani foydalanuvchi o'zi o'zgartira olmaydi — keyinchalik faqat
  admin orqali (UI hali yozilmagan).
- Admin panel faqat egasiga (`000000000`, `config.py` dagi standart). Boshqa
  admin kerak bo'lsa faqat `.env` dagi `ADMIN_IDS` orqali — kodga qattiq
  yozilmaydi (bir marta boshqa foydalanuvchi ID'si standartda qolib, unga
  admin panel ko'ringan).
- Ro'yxatdan o'tishda ism va tug'ilgan sana Telegram profilidan taklif qilinadi
  (`get_chat().birthdate`, faqat maxfiylik «Everybody» va yil bor bo'lsa).
  `/start` matnida bot shiori yo'q, faqat salom va tasdiq savoli.
- Dushanba so'roviga javob berilgach savol xabari butunlay o'chiriladi (faqat
  tugmalar emas). 48 soatdan kech javobda o'chirish rad etiladi — u holda
  tugmalar olib tashlanadi.

## Ochiq ishlar

- Namoz vaqtlari funksiyasi rejalashtirilmoqda. Tahlil qilingan: offline
  hisoblash (`adhanpy`) tavsiya etilgan, **hanafiy mazhab + ISNA burchaklari**
  O'zbekiston rasmiy vaqtlariga 1–4 daqiqa aniqlikda mos keladi. Mazhabni
  noto'g'ri qo'ysangiz asr 55 daqiqaga adashadi. `islomapi.uz` ishonchsiz
  (502 qaytardi).
- Mini App hozir `cloudflared` quick tunnel'da — har restartda manzil
  o'zgaradi. Doimiy domen olingach nginx/Caddy + Let's Encrypt.
- Server 2 OCPU / 12 GB (Oracle A1, 2026-09-15 da kattalashtirilgan). Always
  Free kvotasi 4 OCPU / 24 GB gacha. `journald` vaqtinchalik: loglar reboot'da
  o'chadi (`/var/log/journal` yo'q).
- `users.notify` ustuni o'lik, ishlatilmaydi.
