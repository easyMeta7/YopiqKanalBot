# AI_LOG: loyiha holati va ishlar jurnali

> Qoida: har bir AI (qaysi vosita bo'lishidan qat'iy nazar) ishni boshlashdan oldin buni o'qiydi,
> ish tugagach "O'zgarishlar jurnali" tepasiga yozuv qo'shadi. Batafsil: AGENTS.md.
> Oxirgi yangilanish: 2026-10-10 (Claude)

## Loyiha qisqacha
Telegram yopiq kanal uchun pullik obuna boti. Foydalanuvchi tarif tanlaydi, karta raqamlariga pul o'tkazadi,
chek skrinshotini yuboradi. Admin tasdiqlaydi, bot bir martalik invite link beradi. Muddat tugashidan oldin
eslatadi, tugaganda kanaldan chiqaradi. Stack: Python, aiogram 3, SQLite. Deploy: Railway (Volume `/data`).
GitHub (public): https://github.com/easyMeta7/YopiqKanalBot (2026-10-08 gacha nomi `MusoFX` edi), branch `main`.
Railway shu `main` dan deploy qilinadi. `beta-1.1` shoxida so'nggi tuzatishlar `main` ga qo'shilishidan oldin turadi.

## Fayllar
| Fayl | Vazifasi |
|---|---|
| `bot.py` | Butun bot (bitta fayl): DB, handlerlar, tekshiruv va backup tsikllari |
| `requirements.txt` | `aiogram>=3.13,<4`, `python-dotenv` |
| `railway.json` | Nixpacks, `python bot.py`, xatoda qayta ishga tushirish |
| `.env.example` | Kerakli o'zgaruvchilar namunasi (haqiqiy `.env` gitga tushmaydi) |
| `test_fixes.py` | Takroriy chek, in_channel, muddat tugash qayta urinishi, backup, Qo'shish (kun/sana) |
| `test_race.py` | Ikki admin bir chekni bosganda faqat birinchisi o'tishi |
| `test_cards.py` | Karta matni formati |
| `README.md` | Foydalanuvchi uchun ishga tushirish va deploy yo'riqnomasi |

## Joriy holat (2026-10-08)
- Tariflar: 1 oy = 30 kun = 100 000 so'm; 3 oy = 90 kun = 270 000 so'm (`PLANS`).
- Vaqt zonasi: Toshkent (UTC+5), `now_tashkent()`. Hamma sana shu zonada saqlanadi.
- Env: `BOT_TOKEN`, `CHANNEL_ID`, `ADMIN_IDS` (vergul bilan), `CARD_VISA`, `CARD_HUMO`, `CARD_UZCARD`, `CARD_OWNER`,
  `ADMIN_CONTACT_USERNAME`, `CHECK_INTERVAL_SEC` (600), `DB_PATH` (Railway: `/data/bot.db`), `BACKUP_CHANNEL_ID`.
- DB jadvallari: `subs` (user_id, username, start_at, end_at, reminded3, reminded1, expired_msg),
  `receipts` (rid, status pending/approved/rejected, admin_id, admin_name, decided_at, photo_uid).
- Obunachilar ro'yxati (`/users` va tugma) faqat faol (muddati tugamagan) obunachilarni ko'rsatadi.
- Foydalanuvchi buyruqlari: `/start`, `/obuna`. Admin: `/users`, `/add`, `/addmin`, `/kick`, `/link` va klaviatura
  tugmalari (Obunachilar ro'yxati, Buyruqlar > Qo'shish, Test obuna, Chiqarish, Link, Broadcast, Orqaga).
- `/add <id> <kun>` uzaytiradi; `/add <id> <sana>` (31-12-2026) tugash sanasini aniq qo'yadi (23:59 Toshkent).
- Chek tasdiqlashda atomik qulf: `register_receipt` (pending) -> `claim_receipt` (faqat birinchi admin o'tadi).
- Takroriy chek: `file_unique_id` bo'yicha solishtiriladi, adminga ⚠️ chiqadi. Avtomatik rad etilmaydi.
- Muddat tugaganda: `in_channel()` True/False/None qaytaradi. None yoki chiqarish xatosida `expired_msg` belgisi
  qo'yilmaydi va keyingi aylanishda qayta uriniladi.
- Adminga ogohlantirish: kanaldan chiqarib bo'lmasa va backup xato bersa (bir muammo uchun bir marta, hal bo'lsa xabar).
- Backup: har 6 soatda sqlite backup API bilan nusxa olinib `BACKUP_CHANNEL_ID` kanaliga fayl sifatida yuboriladi
  (bot ishga tushganda ham birinchi marta yuboradi).
- Railway: loyiha `eloquent-curiosity`, servis `YopiqKanalBot`, Volume `musofx-volume` (`/data`, 500 MB).
  Tekshiruv tsikli (`CHECK_INTERVAL_SEC`, default 600 s) muvaffaqiyatli ishlaganda log yozmaydi, faqat xatoda yozadi.
- FSM holati `MemoryStorage` da: bot qayta ishga tushsa, tugallanmagan dialoglar yo'qoladi (normal).

## Qabul qilingan qarorlar
- `/import` buyrug'i KERAK EMAS (foydalanuvchi qarori, 2026-10-08). Eski a'zolar "➕ Qo'shish" orqali kiritiladi,
  tugash sanasini yozish bilan.
- Takroriy chek faqat ogohlantirish, qaror admin qo'lida.
- Barcha xabarlar HTML (`DefaultBotProperties(parse_mode=HTML)`) bo'lib qoladi (foydalanuvchi qarori, 2026-10-10):
  karta raqami va ID `<code>` bilan bir bosishda nusxalanadi. QOIDA: foydalanuvchi, Telegram yoki xatodan kelgan
  har qanday matn (ism, fikr, `{e}`, ...) HTML xabarga faqat `html.escape(...)` bilan qo'yiladi. `cb.answer`
  (oyna) HTML emas, u yerda escape qilinmaydi. Username (`@...`) xavfsiz (faqat harf, raqam, `_`).
- Bitta fayl (`bot.py`) saqlanadi, loyiha kichik, bo'lib tashlash shart emas.
- Eski `test_logic.py` va `test_userkb.py` o'chirildi: ular boshqa (1345 qatorli) versiyaga yozilgan edi va hozirgi
  kodga mos kelmasdi.

## Ochiq masalalar / noaniq joylar
- Railway'da ishlayotgan versiya: GitHub `main` (commit 195796f, 2026-10-08, "Add files via upload") = 873 qatorli
  `bot.py` (foydalanuvchi tasdiqladi). Git tarixidagi 7a9372b (1345 qator: `/import`, `RETENTION_DAYS` 90 kunlik
  tarix tozalash, UTC vaqt) alohida shoxda yozilgan, keyin "Revert"/"Back" bilan qaytarilgan; hozirgi kodda
  ular yo'q. Tarix tozalash (retention) haqida qaror YO'Q: kerak bo'lsa foydalanuvchi bilan kelishib qo'shing,
  eski kod `git show 7a9372b:bot.py` da.
- Repo public: `.env`, token va haqiqiy karta raqami hech qachon commit qilinmagan (2026-10-08 tekshirildi).
  Tarixda faqat namunaviy raqamlar, admin kontakt username (`ADMIN_CONTACT_USERNAME` namunasi) va test uchun
  ism bor. Yangi commitga sir yozmang.
- "🛠 Buyruqlar" yordam matnida Broadcast haqida qisqa yozilgan (matn yoki rasm yuborilishi aytilmagan).
- Takroriy chek faqat bir xil rasm uchun ishlaydi; qayta saqlangan/kesilgan rasm boshqa deb hisoblanadi.
- `/start` bosmagan eski a'zolarga eslatma va tugash xabarlari yetmaydi (kanaldan chiqarish baribir ishlaydi).

## Yozuv formati
```
### YYYY-MM-DD, <AI nomi/vosita>
- Nima o'zgardi (1-3 qator)
- Nega
- Fayllar: ...
- Sinov: <qaysi testlar o'tdi / sinalmagan>
- Keyingi AI uchun eslatma: (agar bo'lsa)
```

## O'zgarishlar jurnali (yangisi tepada)

### 2026-10-10, Claude Code (desktop): `cleanup-v1` shoxi (xatolar + tozalash, birma-bir)
- Reja (foydalanuvchi bilan kelishilgan): 1) feedback, 2) HTML escape, 3) fon vazifalari, 4) broadcast RetryAfter,
  5) eslatmalar (1 kundan kam qolsa faqat 🚨), 6) SQL filtrlari, 7) takroriy kodni birlashtirish. Har qadam alohida
  commit; `main` ga push faqat foydalanuvchi aytganda. Bitta fayl (`bot.py`) saqlanadi.
- 1-qadam: `got_feedback` fikr matnini `html.escape` qiladi (avval `<`/`&` bo'lsa Telegram rad etib, fikr adminga
  yetmasdi, foydalanuvchiga esa "yuborildi" deyilardi). Matnsiz xabarda (rasm, stiker) matn so'raydi, holat saqlanadi.
  Test: test_fixes.py 9-bo'lim.
- 2-qadam: admin ismi (`_admin_name`, full_name) va xato matnlari (`{e}`) HTML xabarlarga `html.escape` bilan
  qo'yiladi: chek ostidagi yozuv, boshqa adminlarga xabar, takroriy chek ogohlantirishi, 5 ta "Xato"/"yuborilmadi"
  xabari. Bazada ism asl holida qoladi (`cb.answer` oynasi HTML emas, u yerda escape qilinmaydi).
  Test: test_fixes.py 10-bo'lim.
- 3-qadam: `main()` fon vazifalarini (`checker_loop`, `backup_loop`) ro'yxatda saqlaydi (avval havola yo'q edi,
  GC o'chirib yuborishi mumkin edi), to'xtasa `_log_task_end` logga xato yozadi, bot to'xtaganda bekor qilinadi.
  Test: test_fixes.py 11-bo'lim (`_log_task_end`). `main()` ning o'zi haqiqiy token bilan ishga tushirib sinalmagan.
- 4-qadam: Broadcast `_copy_with_retry`: Telegram RetryAfter bersa aytilgan vaqt kutib qayta urinadi (3 marta).
  Hisobot: "✅ N ta yetdi" + yetmaganlar bo'lsa "❌ M tasiga yetmadi" (foydalanuvchi qarori: ID ro'yxatisiz).
  Ochiq masaladan olib tashlandi. Test: test_fixes.py 12-bo'lim.
- Sinov: test_fixes.py, test_race.py, test_cards.py o'tdi.

### 2026-10-10, Claude Code (desktop)
- Git holati: PR #2 ("Trading Journal v0.17" refactor, boshqa loyiha kodi) `main` ga qo'shilgan, keyin foydalanuvchi
  revert qilgan (ce0e830). Hozirgi kod f3491ff bilan aynan bir xil (`git diff f3491ff HEAD` bo'sh).
- test_fixes.py 7-bo'lim tuzatildi: admin ID `1` o'rniga `bot.ADMIN_IDS[0]` (test `ADMIN_IDS=111,222` qo'yadi,
  shuning uchun `kb_help` javob bermay `IndexError` berardi). Bot kodiga tegilmadi.
- Windows'da testlar `PYTHONIOENCODING=utf-8` bilan ishga tushirilishi kerak (aks holda emoji print xatosi).
- Fayllar: test_fixes.py, AI_LOG.md
- Sinov: test_fixes.py, test_race.py, test_cards.py o'tdi.

### 2026-10-09, Claude (claude.ai chat)
- Adminlarga ogohlantirish qo'shildi (`notify_admins`, `alert_kick_problem`, `resolve_kick_problem`):
  - Muddati tugagan foydalanuvchini kanaldan chiqarib bo'lmasa, barcha `ADMIN_IDS` ga sabab va maslahat bilan xabar
    ketadi (kanal egasi/admini bo'lsa, shu haqida ham yoziladi). Bir foydalanuvchi uchun bir marta; bot qayta urinadi.
  - A'zolikni tekshirib bo'lmasa (tarmoq/API), 3 ketma-ket urinishdan keyin ogohlantiradi (`KICK_UNKNOWN_ALERT_AFTER`).
  - Muammo hal bo'lsa "✅ chiqarildi" xabari boradi.
  - Backup xatosi: adminga bir marta xabar, tiklansa yana bir marta ("✅ Backup yana ishlayapti").
    `backup_loop` ichidagi ish `run_backup_once()` ga ajratildi.
- Nega: foydalanuvchi talabi (chiqarish xato bersa admin bilishi kerak). Avval faqat logga yozilardi.
- Ogohlantirish holati xotirada (`_kick_alerted`, `_backup_alerted`): bot qayta ishga tushsa, muammo davom etayotgan
  bo'lsa, bir marta yana xabar beradi (normal).
- Fayllar: bot.py, test_fixes.py (8-bo'lim; 3-bo'lim faqat 900 ID xabarlarini sanaydi)
- Sinov: test_fixes.py, test_race.py, test_cards.py o'tdi. Hali `main` ga push qilinmagan.
- Keyingi rejalar (foydalanuvchi hozircha KERAK EMAS dedi): eski obunachilarni ommaviy kiritish (ro'yxat yoki
  "Men eski a'zoman" tugmasi) va Railway pullik rejasi. Boshqa g'oyalar: statistika, kunlik xulosa, /find.

### 2026-10-08, Claude (claude.ai chat)
- Admin yordam matni ("🛠 Buyruqlar") qayta yozildi: har tugma alohida blok, sarlavha qalin, misollar `<code>` ichida.
  "Matn buyruqlari ham ishlaydi" qatori OLIB TASHLANDI (foydalanuvchi qarori, qaytarmang). Buyruqlarning o'zi
  (`/users`, `/add`, `/addmin`, `/kick`, `/link`, `/obuna`) ishlayveradi.
- 3 kun va 1 kun eslatmalari qayta yozildi: sarlavha, "Tugash vaqti: ...", uzaytirish uchun `/start`.
  Muddat tugagan xabar (resub/feedback tugmalari bilan) o'zgarmadi.
- Fayllar: bot.py (`kb_help`, `check_subscriptions`), test_fixes.py (7-bo'lim)
- Sinov: test_fixes.py, test_race.py, test_cards.py o'tdi. Hali `main` ga push qilinmagan.

### 2026-10-08, Claude (claude.ai chat)
- Railway loglari tahlil qilindi (kod xato emas): 2 daqiqalik test obunada 3 va 1 kunlik eslatmalar kelmadi, chunki
  `CHECK_INTERVAL_SEC=600` va tekshiruv obuna faol paytda ishlamadi. Obuna tugagach tekshiruv faqat chiqarish
  va "tugadi" xabarini bajaradi (to'g'ri ishladi, 08:05 da). Eslatmalarni sinash uchun vaqtincha
  `CHECK_INTERVAL_SEC=30` qo'ying, keyin `600` ga qaytaring. Obuna kunlar bilan o'lchanadigan haqiqiy ishda muammo yo'q.
- Tugagan obunachiga `expired_msg=1` qo'yiladi: keyingi tekshiruvlarda qayta xabar yuborilmaydi va Telegram'ga
  murojaat bo'lmaydi.

### 2026-10-08, Claude (claude.ai chat)
- GitHub repo nomi `MusoFX` dan `YopiqKanalBot` ga o'zgartirildi (eski havola yo'naltiriladi). Faqat hujjat
  (shu fayl) yangilandi, kodga tegilmadi.
- Eslatma: nom o'zgargandan keyin Railway avto-deploy to'xtab qolishi mumkin. Tekshirish: servis > Settings >
  Source da repo topilganini ko'ring, kichik commit push qilib build boshlanishini kuzating. Kerak bo'lsa reponi
  uzib qayta ulang. Servisni o'chirmang (obunachilar bazasi Volume'da, `/data`).
- Lokal papkada: `git remote set-url origin https://github.com/easyMeta7/YopiqKanalBot.git`
- Fayllar: AI_LOG.md

### 2026-10-08, Claude (claude.ai chat)
- "👥 Obunachilar ro'yxati" va `/users` endi faqat FAOL obunachilarni ko'rsatadi (muddati tugaganlar chiqmaydi,
  ular bazada saqlanadi). Ro'yxat Telegram chegarasi (4096) dan oshsa, bir necha xabarga bo'linadi.
- Fayllar: bot.py (`subs_list_text`, `split_text`, `send_subs_list`), test_fixes.py (6-bo'lim)
- Sinov: test_fixes.py, test_race.py, test_cards.py o'tdi. Hali `main` ga push qilinmagan.

### 2026-10-08, Claude (claude.ai chat)
- Papka tozalandi: `.freebuff/`, eskirgan `test_logic.py` va `test_userkb.py` olib tashlandi; `.gitignore` ga
  `.freebuff/` qo'shildi; README yangilandi; `.env.example` ga `BACKUP_CHANNEL_ID` qo'shildi.
- AI'lar uchun jurnal tizimi kiritildi: `AI_LOG.md`, `AGENTS.md` (+ `CLAUDE.md`, `GEMINI.md` ishora fayllari),
  `bot.py` boshida AI qoidasi.
- Fayllar: AI_LOG.md, AGENTS.md, CLAUDE.md, GEMINI.md, bot.py (faqat docstring), README.md, .gitignore, .env.example
- GitHub `main` tekshirildi: u foydalanuvchining 873 qatorli versiyasi, Railway'da shu ishlayapti. Bu tuzatishlar
  (backup, chiqarish, takroriy chek, Qo'shish) hali `main` ga yuborilmagan va Railway'da ishlamaydi, to'g'ri
  deploy uchun commit/push kerak.
- Sinov: `test_fixes.py`, `test_race.py`, `test_cards.py` o'tdi.

### 2026-10-08, Claude (claude.ai chat)
- "➕ Qo'shish" va `/add`: kun soni yoki tugash sanasi qabul qiladi (`parse_end_date`, `add_by_days_or_date`).
  Noto'g'ri kiritilsa xato aytadi, dialog bekor bo'lmaydi. Sana o'tib ketgan bo'lsa rad etiladi.
- Nega: `/import` o'rniga eski a'zolarni shu tugma bilan kiritish.
- Fayllar: bot.py, test_fixes.py
- Sinov: test_fixes.py (5-bo'lim) o'tdi.

### 2026-10-08, Claude (claude.ai chat)
- Backup tuzatildi: `FSInputFile` + sqlite backup API (avval fayl yo'li matn sifatida berilib, backup ishlamas edi).
- Muddati tugaganlarni chiqarish tuzatildi: `in_channel()` endi True/False/None; xatoda `expired_msg` qo'yilmaydi,
  qayta uriniladi (avval tarmoq xatosida odam kanalda abadiy qolib ketishi mumkin edi).
- Takroriy chek himoyasi qaytarildi (pending ro'yxat, `file_unique_id`, adminga ⚠️).
- `claim_receipt` ro'yxatga olinmagan rid uchun ham ishlaydi (to'g'ridan-to'g'ri egallaydi).
- Fayllar: bot.py, test_fixes.py (yangi)
- Sinov: test_fixes.py, test_race.py o'tdi.

### 2026-10-07, noma'lum AI (git commit 7a9372b, keyin Revert/Back)
- Commit xabari: `/import`, chek takrori, 6 soatlik backup, 90 kunlik retention. Keyin foydalanuvchi qaytargan
  (4b5a4fe) va 2026-10-08 da 873 qatorli versiyani yuklagan (195796f). Batafsil: "Ochiq masalalar".

### 2026-10-05, noma'lum AI (git commitlar c723d16 ... 6d1a4d2)
- Bot yaratildi: to'lov tasdiqlash, invite link, muddat boshqaruvi, ikki darajali admin klaviatura, ko'p adminli
  tasdiqlash va race-condition qulfi, 3 ta karta (Visa/Humo/Uzcard), "Admin bilan bog'lanish" tugmasi,
  Railway Volume yo'riqnomasi.
