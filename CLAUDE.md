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

`.env` (bot tokeni, `GROQ_API_KEY`), `mundabit.db` (foydalanuvchilar bazasi), `.venv/`,
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
| `db.py` | SQLite: `users`, `week_ratings`, `reminders`, `en_words` |
| `english.py` | English: lug'at, daraja testi, kunlik so'z, takrorlash (sof mantiq) |
| `english/words.json` | English lug'ati: so'z, turkum, daraja, uz/ru tarjima, misol |
| `grammar.py` | English: tuzilgan gapni Groq (LLM) orqali tekshirish |
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
to'g'ridan-to'g'ri sikl yozmang — shu funksiyadan foydalaning. Vaqtida yetishi
kerak bo'lgan yuborishlar (admin xabari, eslatmalar) `window_minutes=0` bilan
chaqiriladi — oyna bo'ylab yoyilmaydi, minimal oraliqda ketadi.

**HTML qochirish `esc()` orqali, `html.escape()` emas.** `html.escape` apostrofni
`&#x27;` ga aylantiradi, o'zbekcha matnda esa apostrof ko'p. `esc()` faqat
`<`, `>` va `&` ni qochiradi; matn HTML atributiga emas, xabar ichiga tushadi.

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
- Eslatma: nom → rasm (ixtiyoriy, «⏭ O'tkazib yuborish») → takrorlanish →
  (hafta kuni | oy sanasi | sana) → `SS:DD`, ko'pi bilan 5 ta. Nom majburiy,
  rasm faqat nom bilan birga (foydalanuvchi "rasm yoki nom emas" degan). `reminders.freq`: `daily`, `weekdays` (Du–Ju), `weekly`
  (`weekday` 0=Du), `monthly` (`monthday` 1–31; oyda bunday kun bo'lmasa
  oxirgi kunida), `once` (`date`; yuborilgach o'chadi, bot o'chiq paytda
  o'tib ketganlari tozalanadi). Qaysi eslatma qachon kelishini faqat
  `db.reminders_due(moment)` hal qiladi. Eski eslatmalar migratsiyada
  `daily` bo'lib qolgan.
- **Eslatma bo'limida inline tugma yo'q** — foydalanuvchiga yoqmagan, hamma
  tanlov pastki (reply) klaviaturada: ro'yxat ostida «➕ Qo'shish»,
  «➖ O'chirish» (bitta), «⬅️ Orqaga»; takrorlanish, hafta kunlari (to'liq nomi), 1–31 sanalar ham
  klaviaturada. Tugma matnlari ikkala tilda taniladi (`DEL_LABELS`,
  `FREQ_LABELS`, `WEEKDAY_LABELS`). Eski xabarlardagi inline tugmalar
  (`rm:`, `rmf:`, …) bosilsa — olib tashlanadi va yangi menyu chiqadi.
- O'chirish: «➖ O'chirish» → klaviaturada eslatmalar **nomlari** (har biri
  alohida qatorda) → tanlangani o'chadi, yangilangan ro'yxat chiqadi. Nom
  takrorlansa yoniga soati qo'shiladi (`delete_choices`). Tugma matni → id
  moslamasi FSM'da (`Reminder.delete`, `rm_del`). Eski raqamli tugmalar
  («🗑 N», «O'chirish N») va emojisiz «O'chirish» faqat nomlar ro'yxatini
  ochadi, o'chirmaydi.
  O'chirish va qo'shish jarayonida «⬅️ Orqaga» eslatmalar ro'yxatiga qaytaradi.
- Eslatmaga rasm: faylning o'zi saqlanmaydi — `reminders.photo` da eng katta
  o'lchamning Telegram `file_id` si (u shu bot tokeniga bog'liq). Yuborishda
  `file_id` yaroqsiz chiqsa eslatma matn bilan ketadi. Nom so'ralganda izohli
  rasm kelsa izoh nom bo'ladi va rasm qadami o'tkaziladi.
- Albom: polling elementlarini parallel va **tartibsiz** ishlaydi, izoh
  istalgan elementda bo'lishi mumkin. `album_items()` albomni `ALBUM_WAIT`
  (0.7 s) yig'ib, butunicha bitta handlerga beradi; qolganlari va kechikkanlar
  javobsiz. Birinchi element tanlanadi (`message_id` bo'yicha).
- `reminder_tick` har daqiqada ishlaydi; kechikkan bo'lsa oxirgi 5 daqiqani
  ham tekshiradi, bir daqiqani ikki marta ishlamaydi, bot qayta ishga
  tushganda o'tib ketganlar takrorlanmaydi.
- Admin tarqatishi `copy_message` bilan — admin yozgan formatlash va rasm o'z
  holicha boradi, HTML'ni qochirish kerak emas. Bir vaqtda bitta tarqatish
  (`broadcasting` bayrog'i), fon vazifasida ishlaydi.
- Murojaat (ilgari "Taklif", 2026-09-17 da nomi o'zgartirildi) uchun alohida
  jadval yo'q: kimga javob berilayotgani callback ma'lumotida
  (`sg:reply:<user_id>`) saqlanadi. Kod ichidagi nomlar (`Suggest`,
  `btn_suggest`, `sg:`) o'zgarmagan. Tugma nomi o'zgarsa eski matni
  `texts.LEGACY_BUTTONS` ga qo'shiladi — eski klaviaturali foydalanuvchi uchun.
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

## English

- Sozlamalarda yoqiladi, **standart — o'chiq** (foydalanuvchi qarori). Yoqilsa
  asosiy menyuda «🇬🇧 English» chiqadi. Birinchi kirishda lug'atdagi so'zlar
  soni darajalar bo'yicha va maqsad (B2) ko'rsatiladi, keyin daraja testi.
  Bu tanishtiruv matnini foydalanuvchi o'zi yozib bergan ("18 tagacha savol"
  bilan) — so'ramasdan qayta tahrirlamang.
- Darajadan keyin «🇬🇧 English» — menyu: «Darajangiz: B1» va klaviaturada
  «📚 Vocabulary» (bugungi 3 ta so'z, so'ng vaqti kelgan so'zlarni
  takrorlash), «🎯 Darajani aniqlash». So'zlar English bosilganda emas, faqat
  Vocabulary'da chiqadi (foydalanuvchi talabi). Test natijasidan keyin ham
  so'zlar avtomatik chiqmaydi.
- Qayta test **haftada bir marta**: `users.en_tested` + 7 kun
  (`english.next_test_date`). Sana test **boshlanganda** yoziladi —
  boshlab tashlab ketilgan test ham imkonni sarflaydi. Yopiq paytda tugma
  klaviaturada yo'q, menyuda «Keyingi test: sana»; eski klaviaturadan
  bosilsa — qachon ochilishi aytiladi. Birinchi test (daraja yo'q) har doim ochiq.
- Daraja testi: B1 dan, har darajada **har doim 6 ta savol** (erta to'xtash
  yo'q — avval 2 xato bilan daraja hal qilinardi, foydalanuvchi "6 savol
  darajani aniqlay olmaydi" degan), 5/6 — o'tdi. O'tsa yuqoriga, o'tmasa
  pastga. Yuqoriga yo'l har doim 12 savol (B2 dan o'tsa — C1; C1 ni so'rash
  natijani o'zgartirmas edi), pastga — 12 yoki 18 (A1 ham tekshiriladi,
  A2/A1 ni ajratish uchun; foydalanuvchi 18 ni qoldirishni tanlagan).
  **Test davomida to'g'ri/xato ko'rsatilmaydi**
  — oxirida bitta natija: «Darajangiz: B1» (IELTS balli yo'q), har daraja
  bo'yicha hisob va xato javoblar ro'yxati. Kunlik takrorlashda esa har
  javobdan keyin ✅/❌ chiqadi (o'rganish uchun). Testda topilgan so'zlar
  `known` — o'rgatilmaydi.
- Har kuni 3 ta yangi so'z: `EN_HOUR:EN_MINUTE` (05:00) da avtomatik,
  Vocabulary tugmasida ham. Bir kunda o'sha 3 ta (`en_words.added`), tanlov deterministik — push va
  tugma bir vaqtda kelsa ham takrorlanmaydi. So'zlar daraja ichida har
  foydalanuvchiga o'z tartibida (faylda A2+ alifbo bo'yicha turibdi).
- **🎮 O'yin** (English menyusida, Vocabulary yonida): 10 savol, test kabi —
  oraliqda to'g'ri/xato yo'q, oxirida hisob va topilmaganlar. So'zlar
  hovuzi: darajadan **pastdagi hamma** so'zlar (A2 bo'lsa — butun A1) va
  `en_words` dagilar (berilgan, testda topilgan); hali berilmagan joriy
  daraja so'zlari yo'q. Har foydalanuvchiga barqaror aylana
  (`english.game_key` — hash; `users.en_game` — oxirgi javob berilgan so'z
  kaliti, har javobda yoziladi): hamma so'z bir martadan chiqmaguncha
  takror yo'q, tashlab ketilgan o'yin davomidan. Topilmagan so'z darhol
  `db.en_relearn` — box 0, ertaga takror, `known = 0`. Foydalanuvchi
  maqsadi: "A2 gacha bilmagan so'zlarini qaytadan yodlatish".
- **Gap tuzish** (Groq, `grammar.py`): Vocabulary'da so'zlardan keyin
  (takrorlash bo'lsa — u tugagach) «✍️ gap tuzib ko'ring» taklifi va
  `EnglishSentence.waiting` rejimi — erkin matn Groq'ga boradi: ✅ yoki
  to'g'ri varianti + qisqa izoh (foydalanuvchi tilida). Handler fallback'dan
  oldin, barcha tugma/buyruqlardan keyin turadi. Model `GROQ_MODEL`
  (standart `qwen/qwen3.8-27b` — sinovda o'zbekcha izohlari `gpt-oss-120b`
  nikidan aniqroq). Kalit faqat serverdagi `.env` da (600); bo'sh bo'lsa
  funksiya o'chiq. Kuniga 30 tekshiruv, gap 300 belgigacha. Ertalabki
  yuborishda taklif yo'q.
- Takrorlash — Leitner: 1, 3, 7, 21 kun; 4 ta ketma-ket to'g'ri — yodlandi
  (`due = NULL`), xato — boshidan. Bir o'tirishda 10 tagacha.
- Savol variantlari orasida **umumiy ma'no bo'lmasligi shart** (sinonimlar:
  very/really → «juda»), aks holda ikkita to'g'ri javob chiqadi —
  `english.make_question` buni tekshiradi.
- `words.json` dagi `id` barqaror — progress unga bog'langan. Mavjud id'ni
  o'zgartirmang/qayta ishlatmang; yangi so'z — yangi id (qo'shimchalar
  10001 dan). Yordamchi so'zlar (the, a, he…) o'rgatilmaydi, faylda yo'q.
  Tarjimalar model tomonidan yozilgan; xato topilsa shu faylda tuzatiladi.
- Uzbek tarjimada apostrof faqat ASCII `'` (o', g', tutuq belgisi).

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
