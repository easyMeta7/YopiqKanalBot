# Trading Journal bot

Telegram signal bot (ko'p kanalli, ko'p juftlikli).

## Muhit o'zgaruvchilari
- `BOT_TOKEN` - BotFather bergan token (kodda yoki GitHub'da saqlanmaydi)
- `OWNER_ID` - admin Telegram ID
- `DB_PATH` - baza fayli yo'li (Railway'da `/data/signals.db`, lokalda bo'sh qoldirsa `signals.db`)
- `N8N_WEBHOOK_URL` - n8n webhook manzili (bo'sh bo'lsa n8n integratsiyasi butunlay o'chiq)
- `N8N_SECRET` - maxfiy kalit; har bir so'rovda `X-Bot-Secret` sarlavhasida yuboriladi
- `FREELLMAPI_URL` - FreeLLMAPI router manzili (standart: `http://localhost:3001/v1`)
- `FREELLMAPI_KEY` - unified API kalit (`freellmapi-...`); bo'sh bo'lsa AI Tahlilchi butunlay o'chiq
- `AI_MODEL` - model yoki strategiya (standart `auto`; `auto:fast`, `auto:coding`, `fusion`)
- `AI_TIMEOUT` - AI javobini kutish vaqti, sekund (standart 35)
- `AI_MAX_TOKENS` - javob uzunligi chegarasi (standart 1000)
- `AI_TEMPERATURE` - javobning "ijodkorligi" (standart 0.7)

## n8n integratsiya (v0.16)
Bot bir tomonlama ishlaydi: faqat **bot -> n8n** yo'nalishida hodisa yuboradi.
Har bir so'rov tanasi: `{event, bot, version, sent_at, data}` (+ zaxirada `file`).

| `event` | Qachon yuboriladi |
|---|---|
| `new_lead` | Onboarding tugagach (ism, Telegram ID, username, telefon, til) |
| `contact_message` | Foydalanuvchi "Admin bilan bog'lanish" xabarini yuborganda |
| `channel_registered` | Kanal botga ulanganda (kanal id, nom, egasi, so'z) |
| `channel_removed` | Bot kanaldan chiqarilganda (sabab: `left`/`kicked`) |
| `bot_error` | Handler'da kutilmagan xato bo'lganda |
| `heartbeat` | Har 5 daqiqada (kanal/user/signal soni, baza hajmi, ishga tushgan vaqt) |
| `daily_backup` | Har kuni 03:00 (Toshkent) da `signals_YYYY-MM-DD.db` base64 sifatida |

Sozlamalar: `HEARTBEAT_MINUTES = 5`, `BACKUP_HOUR = 3` (kod boshidagi konfiguratsiya).
n8n'ga yuborish "best effort": xato bo'lsa bot ishlashda davom etadi, manzil
(maxfiy kalit bilan) loglarga yozilmaydi.

## AI Tahlilchi (v0.17)

Shaxsiy chatdagi **🤖 AI Tahlilchi** bo'limi [FreeLLMAPI](https://github.com/tashfeenahmed/freellmapi)
routeri orqali ishlaydi: 30+ bepul LLM provayderi (Google, Groq, Mistral, Cloudflare,
OpenRouter ...) bitta OpenAI-mos `/v1` manzil ortida, avtomatik failover bilan.

| Amal | Tavsif |
|---|---|
| 💬 Savol berish | Bozor, juftlik yoki risk-menejment bo'yicha savolingizga AI javobi (o'zbek tilida) |
| 📊 Signallar tahlili | Oxirgi 10 signal bo'yicha xulosa: qaysi juftlik/yonalishda natija yaxshi, keyingi qadam tavsiyasi |
| `/ai <savol>` | Bir martalik savol (faqat shaxsiy chatda) |

### AI'ni yoqish (5 daqiqa)

1. FreeLLMAPI'ni ishga tushiring (desktop ilova, Docker yoki manbadan: `npm run dev`).
   Standart manzil: `http://localhost:3001`, API: `http://localhost:3001/v1`.
2. Boshqaruv panelida (`http://localhost:3001`, dev rejimida `http://localhost:5173`)
   **Keys** sahifasida provayder API kalitlarini qo'shing (bepul kalitlar:
   Google AI Studio, Groq, Mistral, Cloudflare va h.k.).
3. O'sha sahifadagi **unified kalitni** (`freellmapi-...`) nusxalab, muhit
   o'zgaruvchisiga qo'ying:

   ```powershell
   $env:FREELLMAPI_URL = "http://localhost:3001/v1"
   $env:FREELLMAPI_KEY = "freellmapi-..."
   $env:AI_MODEL       = "auto"
   ```

   Railway'da shu nomlar bilan Variables bo'limiga qo'shiladi.

### Xulq-atvor

- Kalit berilmasa: bo'lim holat satrida "FREELLMAPI_KEY berilmagan" deb ko'rsatiladi
  va AI so'rovlari yuborilmaydi (botning qolgan qismi normal ishlaydi).
- Kalit noto'g'ri / limit tugagan / router o'chiq: javob o'rniga sabab yoziladi
  (`HTTP 401`, `HTTP 429`, "aloqa yo'q").
- Javob 3800 belgidan uzun bo'lsa bo'lib yuboriladi; `AI_TIMEOUT` ichida javob
  kelmasa "vaqt tugadi" xabari chiqadi.

## Ishga tushirish
    pip install -r requirements.txt
    python trading_journal_bot.py

## Hisobotlar

Savdo kuni: **02:00 dan keyingi kun 02:00 gacha (GMT+5)**; signal yuborilgan vaqti (`created_at`) bo'yicha kunga yoziladi.

| Hisobot | Qanday chaqiriladi | Nima ko'rsatadi |
|---|---|---|
| Kunlik | har kuni **02:10** da kanalga o'zi (ovozsiz); signal bo'lmasa yuborilmaydi | tugagan savdo kuni |
| Haftalik | `/week` yoki "Haftalik" tugmasi; yakshanba 10:00 da avto | joriy hafta, dushanbadan yakshanbagacha |
| Oylik | `/monthly` (`/monthly avgust`) yoki "Oylik" tugmasi | kalendar oy, haftalar bo'yicha qatorlar bilan |
| Juftlik | `/stats XAU` | oxirgi 30 kun, juftlik bo'yicha |

## Loyiha tuzilmasi

```
trading_journal_bot.py   # ishga tushirish (main), joblar, xato ushlagich
bot_core.py              # logger, kanal holati keshi, vaqtinchalik xabarlar
bot_ui.py                # ReplyKeyboard menyulari, yordam matnlari, AI bo'limi
config.py                # sozlamalar va BTN_* tugma matnlari
database.py              # SQLite qatlami
handlers/                # router, onboarding, user, admin, signals, state
utils/                   # ai, n8n, reports, signals
```
