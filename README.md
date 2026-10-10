# YopiqKanal Obuna Boti

Telegram yopiq kanali uchun obuna boshqaruv boti. Python + aiogram 3 + SQLite.

> AI yordamchi ishlatayotgan bo'lsangiz: loyiha holati va oxirgi ishlar `AI_LOG.md` da, AI qoidasi `AGENTS.md` da.

## Funksiyalar

- To'lov: chek skrinshoti, admin tasdiqlashi, bir martalik invite link (24 soat)
- Bir xil chek rasmi qayta kelsa, adminga ⚠️ TAKRORLANISH ogohlantirishi
- Muddat tugashidan 3 kun va 1 kun oldin eslatma
- Muddat tugaganda kanaldan chiqarish + "Qayta obuna / Fikr bildirish" tugmalari
- Admin: obunachilar ro'yxati, qo'shish/uzaytirish, test obuna, chiqarish, link, broadcast
- Har 6 soatda baza nusxasi backup kanaliga yuboriladi

## Buyruqlar

| Buyruq | Kim uchun | Tavsif |
|---|---|---|
| `/start` | hamma | Boshlash / tarif tanlash |
| `/obuna` | hamma | Obuna holati |
| `/users` | admin | Faol obunachilar ro'yxati |
| `/add <id> <kun>` | admin | Muddatni uzaytirish |
| `/add <id> <sana>` | admin | Tugash sanasini aniq qo'yish (`31-12-2026`), eski a'zolar uchun |
| `/kick <id>` | admin | Kanaldan chiqarish |
| `/link <id>` | admin | Invite linkni qayta yuborish |

Obunachi `/start` bosgach pastda "📋 Obuna holati" va "💳 Tariflar" tugmalari chiqadi.

Admin klaviaturasida shular tugma sifatida ham bor, qo'shimcha: 🧪 Test obuna (N daqiqalik obuna, muddatni
almashtiradi) va 📢 Broadcast (barcha faol obunachilarga xabar).

## Mahalliy ishga tushirish

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # to'ldiring
python bot.py
```

## Railway'ga deploy

1. Repo'ni GitHub'ga push qiling
2. [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
3. **Variables** bo'limida kiriting (`.env` dagidek):
   - `BOT_TOKEN`: @BotFather tokeni
   - `CHANNEL_ID`: `-100...` ko'rinishida
   - `ADMIN_IDS`: admin Telegram ID lari (vergul bilan)
   - `CARD_VISA`, `CARD_HUMO`, `CARD_UZCARD`, `CARD_OWNER`
   - `ADMIN_CONTACT_USERNAME`: "Admin bilan bog'lanish" tugmasi uchun (`@` siz)
   - `CHECK_INTERVAL_SEC`: `600`
   - `DB_PATH`: `/data/bot.db`
   - `BACKUP_CHANNEL_ID`: backup yuboriladigan kanal ID (bot u yerda admin bo'lsin)
4. ⚠️ **Volume** (obunachilar bazasi saqlanishi uchun, shart):
   - Settings → **Volumes** → *New Volume* → mount path: **`/data`**
   - `DB_PATH=/data/bot.db` bilan birgalikda ishlaydi
   - Tekshirish: Logs'da `DB: /data/bot.db – obunachilar soni: N` chiqishi kerak.
     `bot.db` chiqsa, Volume ulanmagan
5. Botni kanalga **admin** qiling: *Invite users via link* + *Ban users*

## Testlar

```powershell
python test_fixes.py
python test_race.py
python test_cards.py
```
