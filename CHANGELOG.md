# CHANGELOG — Trading Journal bot

Bu fayl **hozirgi holatni** va commit tarixidagi chalkashlikni tushuntiradi.

---

## ✅ Hozirgi holat

| | |
|---|---|
| **Versiya** | **v0.17** |
| **AI Tahlilchi** | **Yoqilgan** (`utils/ai.py`; `FREELLMAPI_KEY` berilsa ishlaydi) |
| **n8n integratsiya** | **Yoqilgan** (`n8n_send`, `heartbeat_job`, `backup_job`) |
| **`requirements.txt`** | `python-telegram-bot[job-queue]`, **`httpx`**, `tzdata` |
| **GitHub** | `main` = `origin/main` (sinxron) |

Tekshirish:
```bash
git show origin/main:config.py | grep '^VERSION'
# VERSION = "0.17"
```

---

## 📜 Versiyalar

### v0.17 — Refaktoring (versiya raqami o'zgarmadi, xatti-harakat bir xil)
- **Nom**: "By Uskanboev" → **Trading Journal**; asosiy fayl `trading_journal_bot.py`
- **Aylanma importlar yo'qotildi**: umumiy funksiyalar `bot_core.py` (logger, kanal holati,
  vaqtinchalik xabarlar) va `bot_ui.py` (menyular, tugmalar, AI bo'limi) ga ko'chirildi;
  xabar/callback yo'naltirish `handlers/router.py` ga o'tdi. `handlers/*` endi asosiy fayldan import qilmaydi
- Asosiy fayl 1508 → ~220 qator (faqat ishga tushirish, joblar, xato ushlagich)
- Takrorlangan kod olib tashlandi: `send_start`, `is_post_message`, `is_protected_tag_blocked`, `BTN_*`
- Ishlatilmagan (o'lik) kod olib tashlandi: eski inline `show()`, `send_plain()`, menyu-taymer mexanizmi,
  `get_ui_message/save_ui_message`, ishlatilmagan importlar
- `database.db()`: ulanish endi har doim yopiladi (commit / xatoda rollback)
- Yangi indekslar: `signals(chat_id, created_at)`, `subscriptions(channel_id)`, `channels(owner_id)`
- `heartbeat_job`: kanallar soni bitta `COUNT(*)` bilan (hamma qatorni o'qimaydi)
- `ai_status()`: natija 30 soniya keshlanadi (AI menyusi har ochilganda routerga so'rov ketmaydi)
- **Tuzatildi** (avvaldan bor xato): kanaldagi `/stats` tugmalari `url="cst:..."` bilan yuborilardi
  (Telegram rad etadi) va `on_channel_stats_callback` funksiyasi yo'q edi. Endi tugmalar `callback_data`
  bilan, hisobot xabarning o'zida almashadi, faqat kanal admini bosa oladi, o'chirish taymeri har bosishda
  45 soniyadan qayta boshlanadi (`handlers/user.py`, `bot_core.reschedule_delete`)
- **Hisobotlar qayta ishlandi** (oldingi haftalar ustma-ust tushib, signallarni ikki marta sanash xatosi bartaraf etildi):
  - Savdo kuni: **02:00 dan keyingi kun 02:00 gacha (GMT+5)**; kunlik, haftalik va oylik hisobotlar shu chegarada,
    signal yuborilgan vaqt (`created_at`) bo'yicha (`config.TRADING_DAY_START_HOUR`, `utils/reports.py`)
  - **Oylik**: kalendar oy (1-sanadan oxirgi sanagacha) bitta oraliq; haftalar dushanba-yakshanba, oy chegarasida
    kesilgan (6 hafta ham bo'lishi mumkin), har signal faqat bitta haftada
  - **Haftalik**: joriy hafta (dushanba-yakshanba); `/week 2`, `/week 2 iyul` kabi raqamli chaqiruv olib tashlandi
  - **Kunlik**: har kuni **02:10 da** (`daily_job`) kanallarga tugagan savdo kunining natijasi avtomatik, ovozsiz
    yuboriladi; signal bo'lmagan kanalga yuborilmaydi
  - `/stats XAU` (juftlik, oxirgi 30 kun) o'zgarishsiz qoldi

### v0.17 — AI Tahlilchi (hozirgi)
- **🤖 AI Tahlilchi** bo'limi shaxsiy chat menyusiga qo'shildi:
  💬 Savol berish (bozor/signallar bo'yicha savol-javob) va
  📊 Signallar tahlili (oxirgi 10 signal bo'yicha AI xulosasi)
- **`/ai <savol>`** — bir martalik savol (faqat shaxsiy chatda)
- **`utils/ai.py`** ulandi: `ai_enabled()`, `ai_status()` (router holati menyu
  sarlavhasida), `ask_ai_analyst()`, `analyze_recent_signals()`; xato sabablari
  o'zbek tilida qaytariladi (kalit / limit / aloqa yo'q)
- **Standart manzil tuzatildi**: `FREELLMAPI_URL` = `http://localhost:3001/v1`
  (avval `:3000` edi — ishlamaydigan port)
- Yangi o'zgaruvchilar: `FREELLMAPI_URL`, `FREELLMAPI_KEY`, `AI_MODEL`,
  `AI_TIMEOUT`, `AI_MAX_TOKENS`, `AI_TEMPERATURE`
- `config.py` dagi `VERSION` endi `0.17` (tekshirish buyrug'i ham yangilandi)
- Kanalda `/ai` chaqirilsa — "AI Tahlilchi shaxsiy chatda ishlaydi" deb javob beradi

### v0.16 — n8n integratsiya
- **`n8n_send()`** — botdan n8n'ga hodisa yuborish (best effort, xato botni to'xtatmaydi)
- **7 ta hodisa**: `new_lead`, `contact_message`, `channel_registered`, `channel_removed`,
  `bot_error`, `heartbeat`, `daily_backup`
- **`heartbeat_job`** — har 5 daqiqada "tirikman" signali (`N8N_WEBHOOK_URL`)
- **`backup_job`** — har kuni 03:00 (Toshkent) da `signals.db` ni base64 qilib n8n'ga zaxira
- **`on_error`** — kutilmagan xatolarni `bot_error` sifatida yuboradi
- Yangi o'zgaruvchilar: `N8N_WEBHOOK_URL`, `N8N_SECRET`
- `httpx` `requirements.txt` ga qo'shildi

### v0.15 — Railway test bot
- `DB_PATH` o'zgaruvchisi (Railway: `/data/signals.db`)
- `.gitignore`, `requirements.txt`, `README.md`
- Token logga tushmasligi uchun `httpx`/`httpcore` log darajasi `WARNING` qilindi

---

## ⚠️ Commit tarixidagi chalkashlikni tushuntirish

Tarixda **ikkita bir-birini bekor qiluvchi commit** bor. Bu normal va **kodga ta'sir qilmaydi**:

| # | Commit | Nima bo'ldi |
|---|---|---|
| 1 | `4c15ae3` — *v0.16: n8n webhook...* | n8n kodi **qo'shildi** ✅ |
| 2 | `45e3d2a` — *requirements: httpx...* | `httpx` **qo'shildi** ✅ |
| 3 | `31cc0ac` — *v0.15 holatiga qaytarildi...* | n8n kodi **olib tashlandi** ❌ |
| 4 | `673021b` — ***Revert** "v0.15 holatiga qaytarildi..."* | 3-renchi commitning **olib tashlashi bekor qilindi** → n8n **qaytdi** ✅ |

> **4-renchi commit nomi chalkashtiradi.** Git `Revert "..."` yozadi — bu inglizchada
> **"bekor qilaman"** demak. Ya'ni nomi *"v0.15 holatiga qaytarildi"* bo'lgan
> **olib tashlash amali o'zini bekor qildi** = holat **v0.16** ga qaytdi.
>
> **Commit nomini emas, commitning ichidagi o'zgarishni tekshiring:**
> ```bash
> git diff 31cc0ac 673021b   # natija: n8n kodi QAYTGANINI ko'rsatadi
> ```

### Nega `trading_journal_bot.py` yonida `Revert...` ko'rinadi?

GitHub'dagi **"oxirgi kim o'zgartirdi"** ustuni faylning versiyasini emas,
**oxirgi tahrir commitini** ko'rsatadi. `Revert` — bu shu faylning **oxirgi**
tahriri, u v0.16 ni tiklagan.

`README.md`, `.gitignore`, `cmd.exe` kabi fayllar esa v0.16 ga tegilmagan,
shuning uchun ular eski commit nomini ko'rsatadi — bu ham to'g'ri.

---

## 🚀 Deploy

Railway `main` shoxiga push tushganda **avtomatik deploy** qiladi.
Tekshirish: Railway → Deployments → Logs da

```
Trading Journal v0.16 ishga tushdi
n8n integratsiya yoqildi (heartbeat: 5 daq, zaxira: 03:00)
```
