"""
Trading Journal - Configuration settings
"""
import os
from zoneinfo import ZoneInfo

BOT_NAME = "Trading Journal"
VERSION = "0.17"
TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0")) or None
DB = os.getenv("DB_PATH", "signals.db")  # Railway: /data/signals.db
TZ = ZoneInfo("Asia/Tashkent")  # GMT+5
PIP = 0.1  # oltin: 1 pip = 0.10
NOTICE_SECONDS = 2
REPORT_SECONDS = 45
DEFAULT_TAG = "Qabul qilindi"
PROTECTED_TAG = "easymeta"  # faqat OWNER_ID o'zi uchun ishlatadi
CHANNEL_CHECK_TTL = 120  # kanal tirikmi — shu sekund ichida qayta so'ralmaydi
PAIRS = ["XAU", "BTC", "NAS100"]
LANGS = {"uz": "🇺🇿 O'zbekcha", "ru": "🇷🇺 Русский", "en": "🇬🇧 English"}

# n8n integration
N8N_WEBHOOK_URL = (os.getenv("N8N_WEBHOOK_URL") or "").strip()
N8N_SECRET = (os.getenv("N8N_SECRET") or "").strip()
N8N_TIMEOUT = 10          # sekund
HEARTBEAT_MINUTES = 5     # "tirikman" signali orasidagi vaqt
BACKUP_HOUR = 3           # kunlik zaxira vaqti (Toshkent)

# Savdo kuni: bozor 02:00 dan keyingi kun 02:00 gacha (GMT+5). Kunlik, haftalik va oylik
# hisobotlar shu chegaradan foydalanadi.
TRADING_DAY_START_HOUR = 2
DAILY_REPORT_HOUR, DAILY_REPORT_MINUTE = 2, 10   # kunlik hisobot yuborilish vaqti (Toshkent)

BTN_SEND_CONTACT = "📱 Kontaktni yuborish"
BTN_HOME = "🏠 Bosh menyu"
BTN_STATS = "📈 Statistika"
BTN_MY_CHANNELS = "📊 Kanallarim"
BTN_REGISTER = "🔗 Kanalimni ulash"
BTN_OWNER_REGISTER = "🔗 Yangi kanal ulash"
BTN_SETTINGS = "⚙️ Sozlamalar"
BTN_CONTACT = "📩 Admin bilan bog'lanish"
BTN_LEADS = "👥 Kontaktlar"
BTN_ALL_CHANNELS = "📊 Barcha kanallar"
BTN_RATING = "🏆 Reyting"
BTN_BACK = "⬅️ Ortga"
BTN_WEEK = "📊 Haftalik"
BTN_MONTH = "📅 Oylik"
BTN_PAIR = "💱 Juftlik bo'yicha"
BTN_UNREGISTER = "🗑 Kanalni o'chirish"
BTN_YES_DELETE = "✅ Ha, o'chirish"
BTN_AI = "🤖 AI Tahlilchi"
BTN_AI_ASK = "💬 Savol berish"
BTN_AI_ANALYZE_SIGNALS = "📊 Signallar tahlili"

# FreeLLMAPI / AI integration (AI Tahlilchi)
FREELLMAPI_URL = (os.getenv("FREELLMAPI_URL") or "http://localhost:3001/v1").rstrip("/")
FREELLMAPI_KEY = (os.getenv("FREELLMAPI_KEY") or "").strip()
AI_MODEL = (os.getenv("AI_MODEL") or "auto").strip()   # "auto", "auto:fast", "auto:coding" ...
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT") or "35")      # sekund
AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS") or "1000")
AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE") or "0.7")


MONTHS = {
    "yanvar": 1, "fevral": 2, "mart": 3, "aprel": 4, "may": 5, "iyun": 6,
    "iyul": 7, "avgust": 8, "sentabr": 9, "oktabr": 10, "noyabr": 11, "dekabr": 12,
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}

MONTH_NAMES_UZ = {
    1: "Yanvar", 2: "Fevral", 3: "Mart", 4: "Aprel", 5: "May", 6: "Iyun",
    7: "Iyul", 8: "Avgust", 9: "Sentabr", 10: "Oktabr", 11: "Noyabr", 12: "Dekabr",
}

