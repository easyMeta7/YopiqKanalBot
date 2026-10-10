"""Vaqtinchalik: karta va admin-nomi logikasini tekshiradi."""
import os

os.environ.setdefault("BOT_TOKEN", "123456:TEST")
os.environ.setdefault("CHANNEL_ID", "-100123")
os.environ.setdefault("ADMIN_IDS", "123456789")
os.environ["CARD_VISA"] = "8600 1111 1111 1111"
os.environ["CARD_HUMO"] = "9860 2222 2222 2222"
os.environ["CARD_UZCARD"] = "8600 3333 3333 3333"
os.environ["CARD_OWNER"] = "Muso Karimov"
os.environ["DB_PATH"] = "test_cards.db"

import bot

# 1. 3 ta karta
assert len(bot.CARDS) == 3, "karta soni 3 bo'lishi kerak"
names = [n for n, _ in bot.CARDS]
assert "Visa" in names[0] and "Humo" in names[1] and "Uzcard" in names[2]
print("1. 3 karta OK:", names)

# 2. cards_text
text = bot.cards_text()
assert "8600 1111" in text and "9860 2222" in text and "8600 3333" in text
assert "Muso Karimov" in text
print("2. cards_text OK:")
print(text)

# 3. admin nomi
class FakeUser:
    def __init__(self, username, full_name, uid):
        self.username = username
        self.full_name = full_name
        self.id = uid

assert bot._admin_name(FakeUser("muso", "Muso Karimov", 1)) == "@muso"
assert bot._admin_name(FakeUser(None, "Muso Karimov", 42)) == "Muso Karimov (ID: 42)"
print("3. _admin_name OK")

if os.path.exists("test_cards.db"):
    os.remove("test_cards.db")
print()
print("HAMMA TEST O'TDI ✅")
