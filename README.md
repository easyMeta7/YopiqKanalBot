# YopiqKanal Obuna Boti

Telegram yopiq kanali uchun obuna boshqaruv boti. Python + aiogram 3 + SQLite.

## Funktsiyalar

- To'lov (Variant B): chek skrinshoti → admin tasdiqlashi → bir martalik invite link
- Muddat tugashidan 3 kun va 1 kun oldin eslatma
- Muddat tugaganda kanaldan chiqarish + "Qayta obuna / Fikr bildirish" tugmalari
- Admin buyruqlari: obunachilar ro'yxati (ID + muddat), ID bo'yicha chiqarish

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
   - `CARD_NUMBER`, `CARD_OWNER` — karta ma'lumotlari
   - `CHECK_INTERVAL_SEC` — `600`
   - `DB_PATH` — `/data/bot.db`
4. **Volumes** → *New Volume* → mount point: `/data`
   (aks holda har deploy'da `bot.db` yo'qoladi!)
5. Bot kanalga **admin** qiling: ruxsatlar *Invite users via link* + *Ban users*

Loyihaning eski versioni bilan aralashtirmaslik uchun Railway'da **aloqida yangi project** yarating — "Deploy from GitHub repo" repositoriya tanlashda yangi repo bo'ladi.

## Test

```powershell
python test_logic.py
```
