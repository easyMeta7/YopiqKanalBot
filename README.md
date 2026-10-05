# YopiqKanal Obuna Boti

Telegram yopiq kanali uchun obuna boshqaruv boti. Python + aiogram 3 + SQLite.

## Funktsiyalar

- To'lov (Variant B): chek skrinshoti → admin tasdiqlashi → bir martalik invite link
- Muddat tugashidan 3 kun va 1 kun oldin eslatma
- Muddat tugaganda kanaldan chiqarish + "Qayta obuna / Fikr bildirish" tugmalari
- Admin buyruqlari: obunachilar ro'yxati (ID + muddat), ID bo'yicha chiqarish
- Obunachilarda "💬 Admin bilan bog'lanish" tugmasi (shaxsiy chatga URL)

## Buyruqlar

| Buyruq | Kim uchun | Tavsif |
|---|---|---|
| `/start` | hamma | Boshlash / tarif tanlash |
| `/obuna` | hamma | Obuna holati |
| `/users` | admin | Obunachilar ro'yxati |
| `/add <id> <kun>` | admin | Obuna qo'shish/uzaytirish |
| `/addmin <id> <daqiqa>` | admin | Test rejimi (muddatni almashtiradi) |
| `/kick <id>` | admin | Kanaldan chiqarish |
| `/link <id>` | admin | Invite linkni qayta yuborish |

## Mahalliy ishga tushirish

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # to'ldiring
python bot.py
```

## Railway'ga deploy (yangi project)

1. Bu repo'ni GitHub'ga push qiling
2. [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo** → bu repo'ni tanlang
3. **Variables** bo'limida kiriting (`.env` dagidek):
   - `BOT_TOKEN` — @BotFather tokeni
   - `CHANNEL_ID` — `-100...` ko'rinishida
   - `ADMIN_IDS` — sizning Telegram ID ingiz
   - `CARD_VISA`, `CARD_HUMO`, `CARD_UZCARD` — 3 ta karta raqami
   - `CARD_OWNER` — karta egasi
   - `CHECK_INTERVAL_SEC` — `600`
   - `DB_PATH` — `/data/bot.db`
   - `ADMIN_CONTACT_USERNAME` — obunachilarga chiqadigan
     "💬 Admin bilan bog'lanish" tugmasi (username, `@` sizsiz)
4. ⚠️ **ENG MUHIM QADAM — Volume (obunachilar saqlanishi uchun):**
   - Settings → **Volumes** → *New Volume* → mount path: **`/data`**
   - `DB_PATH=/data/bot.db` bilan **birgalikda** ishlaydi — ikkisi ham shart
   - Aks holda har deploy'da `bot.db` (obunachilar bazasi) yo'qoladi
   - Tekshirish: Logs'da `DB: /data/bot.db — obunachilar soni: N`
     chiqishi kerak. `bot.db` da chiqsa (papka ichida) — Volume ulanmagan
   - Railway'da Volume **Starter+ plan**da mavjud
5. Bot kanalga **admin** qiling: ruxsatlar *Invite users via link* + *Ban users*

Loyihaning eski versioni bilan aralashtirmaslik uchun Railway'da **aloqida yangi project** yarating — "Deploy from GitHub repo" repositoriya tanlashda yangi repo bo'ladi.

## Test

```powershell
python test_logic.py
```
