"""Tuzatishlar testi: takroriy chek, in_channel, muddat tugaganda qayta urinish, backup."""
import asyncio, os, sqlite3
from datetime import timedelta
from types import SimpleNamespace

os.environ.setdefault("BOT_TOKEN", "123456:TEST")
os.environ.setdefault("CHANNEL_ID", "-100123")
os.environ.setdefault("ADMIN_IDS", "111,222")
os.environ["DB_PATH"] = "test_fixes.db"
for f in ("test_fixes.db",):
    if os.path.exists(f):
        os.remove(f)

import bot
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.methods import GetChatMember

bot.init_db()

# 1. Takroriy chek
bot.register_receipt("r1", "UNIQ1")
assert bot.find_duplicate_receipt("UNIQ1", "r1") is None
assert bot.claim_receipt("r1", "approved", 111, "@a") is None
bot.register_receipt("r2", "UNIQ1")
d = bot.find_duplicate_receipt("UNIQ1", "r2")
assert d is not None and d["status"] == "approved" and d["admin_name"] == "@a"
assert bot.find_duplicate_receipt("BOSHQA", "r2") is None
assert bot.claim_receipt("r2", "approved", 222, "@b") is None
assert bot.claim_receipt("r2", "rejected", 111, "@a")["status"] == "approved"
print("1. takroriy chek + race OK")

# 2. in_channel
async def fake_gcm(kind):
    async def f(chat, uid):
        if kind == "member": return SimpleNamespace(status="member")
        if kind == "left": return SimpleNamespace(status="left")
        if kind == "kicked": return SimpleNamespace(status="kicked")
        if kind == "net": raise TelegramNetworkError(GetChatMember(chat_id=1, user_id=1), "timeout")
        if kind == "nf": raise TelegramBadRequest(GetChatMember(chat_id=1, user_id=1), "Bad Request: user not found")
        if kind == "other": raise TelegramBadRequest(GetChatMember(chat_id=1, user_id=1), "Bad Request: chat not found")
    return f

async def t_in_channel():
    for kind, exp in [("member", True), ("left", False), ("kicked", False), ("net", None), ("nf", False), ("other", None)]:
        bot.bot.get_chat_member = await fake_gcm(kind)
        got = await bot.in_channel(5)
        assert got is exp, (kind, got)
asyncio.run(t_in_channel())
print("2. in_channel OK")

# 3. Muddat tugaganda: xato bo'lsa qayta uriniladi
calls = {"removed": [], "msgs": [], "status": None, "remove_fail": False}
async def fake_in(uid): return calls["status"]
async def fake_remove(uid):
    if calls["remove_fail"]: raise RuntimeError("boom")
    calls["removed"].append(uid)
async def fake_send(uid, *a, **k):
    if uid == 900:  # adminlarga ketgan ogohlantirishlar bu yerda hisoblanmaydi
        calls["msgs"].append(uid)
bot.in_channel = fake_in
bot.remove_from_channel = fake_remove
bot.bot.send_message = fake_send

now = bot.now_tashkent().replace(microsecond=0)
bot.upsert_sub(900, "x", now - timedelta(days=40), now - timedelta(days=1), replace=True)
def flag(): return bot.get_sub(900)["expired_msg"]

calls["status"] = None                       # tekshirib bo'lmadi
asyncio.run(bot.check_subscriptions())
assert flag() == 0 and not calls["msgs"], "tekshirib bo'lmasa belgi qo'yilmasin"

calls["status"] = True; calls["remove_fail"] = True   # chiqarish xato
asyncio.run(bot.check_subscriptions())
assert flag() == 0 and not calls["msgs"], "chiqarish xato bo'lsa belgi qo'yilmasin"

calls["remove_fail"] = False                 # endi hammasi yaxshi
asyncio.run(bot.check_subscriptions())
assert flag() == 1 and calls["removed"] == [900] and calls["msgs"] == [900]
asyncio.run(bot.check_subscriptions())       # takror yuborilmasin
assert calls["msgs"] == [900]
print("3. muddat tugashi qayta urinish OK")

# 4. Backup nusxasi
p = bot._make_backup_copy()
c = sqlite3.connect(p)
assert c.execute("SELECT COUNT(*) FROM subs").fetchone()[0] == 1
c.close(); os.remove(p)
from aiogram.types import FSInputFile
sent = {}
async def fake_doc(chat_id, document, caption=None): sent["doc"] = document; raise asyncio.CancelledError
bot.bot.send_document = fake_doc
bot.BACKUP_CHANNEL_ID = -100999
try:
    asyncio.run(bot.backup_loop())
except BaseException:
    pass
assert isinstance(sent["doc"], FSInputFile)
print("4. backup FSInputFile OK")
print("\nHAMMA TEST O'TDI ✅")

# 5. Qo'shish: kun yoki sana
from datetime import datetime, timezone
assert bot.parse_end_date("31-12-2026").day == 31
assert bot.parse_end_date("31.12.2026").month == 12
assert bot.parse_end_date("31/12/2026").year == 2026
assert bot.parse_end_date("2026-12-31").day == 31
assert bot.parse_end_date("31-13-2026") is None and bot.parse_end_date("abc") is None and bot.parse_end_date("30") is None
answers = []
class M:
    async def answer(self, t, **k): answers.append(t)
async def fake_in2(uid): return True
bot.in_channel = fake_in2
async def t_add():
    # sana
    ok = await bot.add_by_days_or_date(700, "31-12-2030", M()); assert ok
    assert bot.get_sub(700)["end_at"].startswith("2030-12-31T23:59")
    # kun: mavjud muddatga qo'shiladi
    ok = await bot.add_by_days_or_date(700, "30", M()); assert ok
    assert bot.get_sub(700)["end_at"].startswith("2031-01-30T23:59")
    # noto'g'ri / o'tgan sana / 0 kun -> False, baza o'zgarmaydi
    before = bot.get_sub(700)["end_at"]
    for bad in ("hello", "01-01-2020", "0"):
        assert await bot.add_by_days_or_date(700, bad, M()) is False
    assert bot.get_sub(700)["end_at"] == before
asyncio.run(t_add())
print("5. Qo'shish (kun/sana) OK")
print("\nHAMMA TEST O'TDI ✅ (5)")

# 6. Obunachilar ro'yxati: faqat faol
bot.upsert_sub(801, "faol1", now, now + timedelta(days=10), replace=True)
bot.upsert_sub(802, "tugagan", now - timedelta(days=30), now - timedelta(days=1), replace=True)
txt = bot.subs_list_text()
assert "801" in txt and "802" not in txt and "tugagan" not in txt and "❌" not in txt
assert "Faol obunachilar (" in txt
# bo'sh holat
with bot.db() as c:
    c.execute("UPDATE subs SET end_at=?", ((now - timedelta(days=1)).isoformat(),))
assert bot.subs_list_text() == "Faol obunachilar yo'q."
# uzun ro'yxat bo'linadi
long_text = "\n".join(f"✅ ID: {i} @user{i} – muddat: 01.01.2030 23:59" for i in range(300))
parts = bot.split_text(long_text)
assert len(parts) > 1 and all(len(p) <= 4096 for p in parts) and "\n".join(parts) == long_text
print("6. Faol obunachilar ro'yxati OK")
print("\nHAMMA TEST O'TDI ✅ (6)")

# 7. Yordam matni va eslatma xabarlari
import re
helps = []
class AdminMsg:
    from_user = SimpleNamespace(id=1)
    async def answer(self, t, **k): helps.append(t)
asyncio.run(bot.kb_help(AdminMsg()))
h = helps[0]
assert "Matn buyruqlari" not in h
for name in ("Qo'shish", "Test obuna", "Chiqarish", "Link", "Broadcast", "Orqaga"):
    assert f"<b>{name}</b>" in h, name
assert h.count("<b>") == h.count("</b>") and h.count("<code>") == h.count("</code>")
assert len(h) < 4096 and "\n\n" in h

# eslatmalar: 2 daqiqa qolgan obuna -> ikkala eslatma ham, chiroyli formatda
sent7 = []
async def fake_send7(uid, text, **k): sent7.append((uid, text))
bot.bot.send_message = fake_send7
async def fake_in7(uid): return True
bot.in_channel = fake_in7
now7 = bot.now_tashkent().replace(microsecond=0)
bot.upsert_sub(950, "rem", now7, now7 + timedelta(minutes=2), replace=True)
asyncio.run(bot.check_subscriptions())
texts = [t for u, t in sent7 if u == 950]
assert len(texts) == 2, texts
assert "3 kundan kam" in texts[0] and "1 kundan kam" in texts[1]
for t in texts:
    assert "Tugash vaqti: <b>" in t and "/start" in t and "\n\n" in t
asyncio.run(bot.check_subscriptions())   # qayta yuborilmasin
assert len([1 for u, t in sent7 if u == 950]) == 2
print("7. Yordam matni va eslatmalar OK")

# 8. Adminga ogohlantirish: chiqarib bo'lmasa va backup xato bersa
msgs8 = []
async def fake_send8(uid, text, **k): msgs8.append((uid, text))
bot.bot.send_message = fake_send8
state8 = {"in": True, "fail": "Bad Request: can't remove chat owner"}
async def fake_in8(uid): return state8["in"]
async def fake_remove8(uid):
    if state8["fail"]: raise RuntimeError(state8["fail"])
bot.in_channel = fake_in8
bot.remove_from_channel = fake_remove8
now8 = bot.now_tashkent().replace(microsecond=0)
bot.upsert_sub(960, "ownerx", now8 - timedelta(days=5), now8 - timedelta(days=1), replace=True)
admins = list(bot.ADMIN_IDS)

asyncio.run(bot.check_subscriptions())
alerts = [(u, t) for u, t in msgs8 if "chiqarib bo'lmadi" in t]
assert sorted(u for u, _ in alerts) == sorted(admins), alerts
assert "960" in alerts[0][1] and "@ownerx" in alerts[0][1] and "kanal egasi" in alerts[0][1]
assert bot.get_sub(960)["expired_msg"] == 0
asyncio.run(bot.check_subscriptions())   # ikkinchi urinish: qayta ogohlantirmasin
assert len([1 for u, t in msgs8 if "chiqarib bo'lmadi" in t]) == len(admins)

state8["fail"] = None                    # muammo hal bo'ldi
asyncio.run(bot.check_subscriptions())
assert len([1 for u, t in msgs8 if "avvalgi muammo hal bo'ldi" in t]) == len(admins)
assert bot.get_sub(960)["expired_msg"] == 1
assert any(u == 960 and "tugadi" in t for u, t in msgs8)

# tekshirib bo'lmasa: 3-urinishdan keyin ogohlantiradi
async def fake_in_none(uid): return None
bot.in_channel = fake_in_none
msgs8.clear()
bot.upsert_sub(961, "net", now8 - timedelta(days=5), now8 - timedelta(days=1), replace=True)
for _ in range(2):
    asyncio.run(bot.check_subscriptions())
assert not [1 for u, t in msgs8 if "chiqarib bo'lmadi" in t], "2 urinishda hali ogohlantirmasin"
asyncio.run(bot.check_subscriptions())
assert len([1 for u, t in msgs8 if "chiqarib bo'lmadi" in t]) == len(admins)

# Backup xatosi: bir marta xabar, tiklansa yana bir marta
msgs8.clear()
bot.BACKUP_CHANNEL_ID = -100777
async def doc_fail(chat_id, document, caption=None): raise RuntimeError("chat not found <b>")
bot.bot.send_document = doc_fail
asyncio.run(bot.run_backup_once()); asyncio.run(bot.run_backup_once())
b = [(u, t) for u, t in msgs8 if "Backup yuborilmadi" in t]
assert len(b) == len(admins) and "&lt;b&gt;" in b[0][1]   # HTML escape qilingan
async def doc_ok(chat_id, document, caption=None): return None
bot.bot.send_document = doc_ok
asyncio.run(bot.run_backup_once())
assert len([1 for u, t in msgs8 if "Backup yana ishlayapti" in t]) == len(admins)
print("8. Adminga ogohlantirishlar OK")
print("\nHAMMA TEST O'TDI ✅ (8)")

