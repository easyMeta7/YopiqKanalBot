"""Test: DB papkasini avtomatik yaratish + obunachi klaviaturasi."""
import os
import shutil
import tempfile

test_dir = os.path.join(tempfile.gettempdir(), "musofx_dbtest")
if os.path.exists(test_dir):
    shutil.rmtree(test_dir)

os.environ.setdefault("BOT_TOKEN", "123456:TEST")
os.environ.setdefault("CHANNEL_ID", "-100123")
os.environ.setdefault("ADMIN_IDS", "111")
os.environ["DB_PATH"] = os.path.join(test_dir, "sub", "bot.db")
os.environ["ADMIN_CONTACT_USERNAME"] = "@musokamronbek"

import bot

# 1. DB papkasi avtomatik yaratilganmi (import paytida)
assert os.path.isdir(os.path.join(test_dir, "sub")), "DB papkasi yaratilmagan"
print("1. DB papkasi avtomatik yaratildi OK")

# 2. init_db ishlaydi
bot.DB_PATH = os.environ["DB_PATH"]
bot.init_db()
assert os.path.exists(bot.DB_PATH), "bot.db yaratilmagan"
print("2. init_db OK")

# 3. user_kb — ADMIN_CONTACT_USERNAME bor
kb = bot.user_kb()
assert kb is not None, "user_kb None bo'lmasligi kerak"
btn = kb.keyboard[0][0]
assert btn.text == "💬 Admin bilan bog'lanish"
assert btn.url == "https://t.me/musokamronbek", f"noto'g'ri url: {btn.url}"
print(f"3. user_kb OK: text={btn.text!r}, url={btn.url}")

# 4. @ belgisi avtomatik olib tashlanadi
assert bot.ADMIN_CONTACT_USERNAME == "musokamronbek", "lstrip ishlamagan"
print("4. @ lstriplashi OK")

# 5. Username bo'sh bo'lsa -> None (tugma ko'rinmaydi)
bot.ADMIN_CONTACT_USERNAME = ""
assert bot.user_kb() is None, "bo'sh username'da None bo'lishi kerak"
print("5. Bo'sh username -> None OK")

# Eslatma: lstrip faqat .env o'qilganda ishlaydi (test 4 da tekshirilgan);
# to'g'ridan-to'g'ri o'zgartirishda qayta ishga tushirilmaydi — bu normal.

shutil.rmtree(test_dir, ignore_errors=True)
print()
print("HAMMA TEST O'TDI ✅")