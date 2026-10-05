"""Vaqtinchalik test: DB mantiqini tekshiradi."""
import os

os.environ.setdefault("BOT_TOKEN", "123456:TEST")
os.environ.setdefault("CHANNEL_ID", "-100123")
os.environ.setdefault("ADMIN_IDS", "123456789")
os.environ["DB_PATH"] = "test_bot.db"

if os.path.exists("test_bot.db"):
    os.remove("test_bot.db")

import bot
from datetime import timedelta

bot.DB_PATH = "test_bot.db"
bot.init_db()

# 1. Yangi obuna
start = bot.now_utc().replace(microsecond=0)
end = start + timedelta(days=30)
bot.upsert_sub(111, "testuser", start, end)
sub = bot.get_sub(111)
assert sub is not None, "obuna yaratilmadi"
print("1. Yangi obuna OK:", sub["end_at"])

# 2. Uzaytirish (replace=False) — muddat uzayishi kerak
bot.upsert_sub(111, "testuser", start, end, replace=False)
sub2 = bot.get_sub(111)
assert sub2["end_at"] > sub["end_at"], "uzaytirish ishlamadi!"
print("2. Uzaytirish OK:", sub["end_at"], "->", sub2["end_at"])

# 3. Almashtirish (replace=True) — 2 daqiqa qo'yish
end_min = bot.now_utc().replace(microsecond=0) + timedelta(minutes=2)
bot.upsert_sub(111, None, bot.now_utc().replace(microsecond=0), end_min, replace=True)
sub3 = bot.get_sub(111)
assert sub3["end_at"] < sub2["end_at"], "almashtirish ishlamadi!"
print("3. Almashtirish OK:", sub3["end_at"])

# 4. Ro'yxat matni
text = bot.subs_list_text()
assert "111" in text and "testuser" in text, "ro'yxat noto'g'ri"
print("4. Ro'yxat OK:")
print(text)

# 5. is_admin
assert bot.is_admin(123456789) is True
assert bot.is_admin(999) is False
print("5. is_admin OK")

os.remove("test_bot.db")
print("\nHAMMA TEST O'TDI ✅")
