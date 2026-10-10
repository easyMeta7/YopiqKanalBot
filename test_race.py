"""Race-condition testi: ikkala admin bir chekni 'bosganda'.

claim_receipt DB qulfi: faqat BIRINCHI chaqiruv None qaytaradi (qulf egallandi),
ikkinchisi mavjud yozuv oladi (rad etiladi).
"""
import os
import threading

os.environ.setdefault("BOT_TOKEN", "123456:TEST")
os.environ.setdefault("CHANNEL_ID", "-100123")
os.environ.setdefault("ADMIN_IDS", "111,222")
os.environ["DB_PATH"] = "test_race.db"

if os.path.exists("test_race.db"):
    os.remove("test_race.db")

import bot

bot.DB_PATH = "test_race.db"
bot.init_db()

# 1. Birinchi chaqiruv qulfi egallaydi
r1 = bot.claim_receipt("rid001", "approved", 111, "@admin_a")
assert r1 is None, "birinchi claim None qaytarishi kerak"
print("1. Birinchi claim OK (None)")

# 2. Ikkinchi chaqiruv — allaqachon egallangan
r2 = bot.claim_receipt("rid001", "approved", 222, "@admin_b")
assert r2 is not None, "ikkinchi claim rad etilishi kerak"
assert r2["admin_id"] == 111, "haqiqiy qaror qabul qilgan admin 111 bo'lishi kerak"
assert r2["admin_name"] == "@admin_a"
print("2. Ikkinchi claim OK (admin_a egallagan)")

# 3. Turli holat: approve bosgan, keyin reject bosgan -> ham rad etiladi
r3 = bot.claim_receipt("rid001", "rejected", 222, "@admin_b")
assert r3 is not None and r3["status"] == "approved", "status o'zgarmasligi kerak"
print("3. Approve->reject OK (status approved bo'lib qoldi)")

# 4. Turli cheklar mustaqil (boshqa rid bog'lanmaydi)
r4 = bot.claim_receipt("rid002", "rejected", 222, "@admin_b")
assert r4 is None, "boshqa rid mustaqil bo'lishi kerak"
print("4. Mustaqil rid OK")

# 5. Haqiqiy parallel yugurish: 20 ta thread bitta rid'ga urinadi
results = []
lock = threading.Lock()

def try_claim(i):
    row = bot.claim_receipt("rid_parallel", "approved", 1000 + i, f"@admin_{i}")
    with lock:
        results.append(row)

threads = [threading.Thread(target=try_claim, args=(i,)) for i in range(20)]
for t in threads:
    t.start()
for t in threads:
    t.join()

winners = [r for r in results if r is None]
assert len(winners) == 1, f"faqat 1 ta g'olib bo'lishi kerak, {len(winners)} ta chiqdi"
print(f"5. Parallel 20 thread OK — faqat 1 ta g'olib (atomik qulf ishladi)")

# 6. callback_data formati uzunligi (Telegram limiti 64 bayt)
cd = f"approve:{'a' * 16}:{1234567890123}:{3}"
assert len(cd.encode()) <= 64, "callback_data 64 baytdan oshmasligi kerak"
print(f"6. callback_data uzunligi OK ({len(cd.encode())} bayt <= 64)")

os.remove("test_race.db")
print()
print("HAMMA RACE TEST O'TDI ✅")