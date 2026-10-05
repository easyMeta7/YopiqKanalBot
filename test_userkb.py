"""Test: obunachi xabarida tariflar + inline aloqa URL tugmasi."""
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

# 3. Obunachi plans_kb: tariflar + aloqa URL tugmasi bitta xabarda
kb = bot.plans_kb(with_contact=True)
rows = kb.inline_keyboard
assert len(rows) == len(bot.PLANS) + 1, "tariflar + aloqa qatori bo'lishi kerak"
last = rows[-1][0]
assert last.text == "💬 Admin bilan bog'lanish"
assert last.url == "https://t.me/musokamronbek", f"noto'g'ri url: {last.url}"
for r in rows[:-1]:
    assert r[0].callback_data.startswith("plan:"), "tarif tugmasi yo'q"
print("3. plans_kb(with_contact=True) OK: tariflar + inline URL tugma")

# 4. @ belgisi avtomatik olib tashlanadi
assert bot.ADMIN_CONTACT_USERNAME == "musokamronbek", "lstrip ishlamagan"
print("4. @ lstriplashi OK")

# 5. Username bo'sh bo'lsa -> aloqa qatori chiqmaydi, tariflar qoladi
bot.ADMIN_CONTACT_USERNAME = ""
kb2 = bot.plans_kb(with_contact=True)
assert len(kb2.inline_keyboard) == len(bot.PLANS), "faqat tariflar bo'lishi kerak"
print("5. Bo'sh username -> faqat tariflar OK")

# 6. Admin ko'rinishi: aloqa tugmasi YO'Q
bot.ADMIN_CONTACT_USERNAME = "musokamronbek"
kb3 = bot.plans_kb()
assert all("Admin" not in (b.text or "") for r in kb3.inline_keyboard for b in r)
print("6. Admin plans_kb da aloqa tugmasi yo'q OK")

shutil.rmtree(test_dir, ignore_errors=True)
print()
print("HAMMA TEST O'TDI ✅")