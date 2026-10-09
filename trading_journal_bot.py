"""
Trading Journal v0.17 - Ko'p kanalli, ko'p juftlikli Telegram signal bot

O'rnatish:
    pip install "python-telegram-bot[job-queue]" tzdata

Ishga tushirish:
    set BOT_TOKEN=tokeningiz
    set OWNER_ID=123456789
    python trading_journal_bot.py

===============================================================================
YANGI (v0.07) OQIM

1) SIGNAL YUBORISH (kanalda, ikki bosqichli):
   - Admin kanalga yakka "#Signal" deb yozadi.
   - Bot shu postga [XAU] [BTC] [NAS100] tugmalarini biriktiradi (faqat shu
     kanal admini bosa oladi).
   - Tugma bosilgach, bot postni tahrirlab pastiga juftlik nomini qo'shadi.
   - Admin O'SHA POSTNI tahrirlab davom ettiradi: Buy/Sell, narx oralig'i,
     Stop, TP1(-3). Post to'liq va to'g'ri bo'lgach, bot uni signal sifatida
     qabul qilib, oxiriga tagni qo'shadi va shu kanalga obuna bo'lganlarga
     nusxasini shaxsiy yuboradi (push).
   - Juftlik yozilmagan eski/oddiy signallar XAU deb hisoblanadi.

2) /start — onboarding va katalog menyusi:
   - Yangi foydalanuvchi: til tanlash -> ism -> telefon (kontakt) -> bosh menyu.
     Tayyor foydalanuvchi va OWNER_ID uchun esa darhol bosh menyu chiqadi.
   - Bot hech qanday kanal ro'yxatini bermaydi — foydalanuvchi ro'yxatdan
     o'tgan qaysi kanal(lar)ga a'zoligini o'zi aniqlaydi (bir nechta bo'lsa,
     faqat o'shalar orasidan pastdagi tugmalar bilan tanlanadi).

3) STATISTIKA:
   /stats — Haftalik / Oylik / Juftlik bo'yicha submenyu
   /stats XAU — shu juftlik bo'yicha oxirgi 30-31 kunlik aylanma statistika
   (TP1/TP2/TP3/Stop soni, jami, winrate, sof pips)

4) NAVIGATSIYA (shaxsiy chat): barcha tugmalar PASTDAGI ReplyKeyboard'da.
   - Asosiy menyu (katalog): 📊 Kanallarim, 📈 Statistika, 🔗 Kanalimni ulash,
     ⚙️ Sozlamalar, 📩 Admin bilan bog'lanish (OWNER_ID uchun boshqacha).
   - Har bir bo'lim o'z tugmalarini va "⬅️ Ortga" ni ko'rsatadi — ortga
     bosilganda asosiy menyuga qaytiladi (bo'lim tugmalari ostida asosiy
     menyu takrorlanmaydi).
   - Statistika/hisobot MATNI chatning o'zida saqlanadi (o'chirilmaydi).
   - Statistika/Kanallarim ro'yxati: admin kanali + o'zingiz ulagan kanallar
     + a'zo bo'lgan kanallar. Bitta kanal bo'lsa — darhol statistika ochiladi,
     bir nechta bo'lsa — qaysi kanaldan olishingiz so'raladi.
   - O'chirilgan yoki botdan chiqarilgan kanallar ro'yxatdan avtomatik
     olib tashlanadi (qo'lda: kanal sahifasidagi "🗑 Kanalni o'chirish").
   - Faqat kanal postlaridagi juftlik tanlash tugmalari inline bo'lib qoladi.

Eslatma: DM dagi register/contact/menyu holatlari xotirada saqlanadi. Bot
qayta ishga tushsa ham pastdagi katalog tugmalari ishlashda davom etadi —
holat yo'qolgan bo'lsa bot 🏠 Bosh menyuni qayta chiqaradi.
===============================================================================
YANGI (v0.16) — n8n INTEGRATSIYA (bir tomonlama, bot -> n8n)

Bot n8n webhook'iga hodisalarni yuboradi. Manzil va maxfiy kalit faqat muhit
o'zgaruvchilarida turadi:

    N8N_WEBHOOK_URL   - n8n webhook manzili (bo'sh bo'lsa integratsiya o'chiq)
    N8N_SECRET        - maxfiy kalit, "X-Bot-Secret" sarlavhasida yuboriladi

Hodisa turlari ("event" maydoni):
  1) new_lead           - onboarding tugagach (ism, Telegram ID, username, telefon)
  2) contact_message    - foydalanuvchi admin bilan bog'lanish xabari yuborganda
  3) channel_registered - kanal botga ulanganda (id, nom, egasi, so'z)
  4) channel_removed    - bot kanaldan chiqarilganda
  5) bot_error          - handler'da kutilmagan xato bo'lganda
  6) heartbeat          - har 5 daqiqada "tirikman" signali (kanal/user/signal soni)
  7) daily_backup       - har kuni 03:00 (Toshkent) da baza (base64) n8n'ga yuboriladi

Xato yoki tarmoq uzilishi bo'lsa bot ishlashda davom etadi — n8n hodisalari
"best effort" tarzda yuboriladi va hech qachon asosiy oqimni to'xtatmaydi.
===============================================================================
YANGI (v0.17) — AI TAHLILCHI (FreeLLMAPI)

Shaxsiy chatdagi "🤖 AI Tahlilchi" bo'limi FreeLLMAPI routeri orqali ishlaydi.

    FREELLMAPI_URL   - router manzili (standart: http://localhost:3001/v1)
    FREELLMAPI_KEY   - unified API kalit ("freellmapi-..."); bo'sh bo'lsa AI o'chiq
    AI_MODEL         - model yoki strategiya (standart "auto"; "auto:fast",
                       "auto:coding", "fusion" va h.k.)

  1) 💬 Savol berish      - bozor/signallar bo'yicha erkin savol, javobi AI'dan
  2) 📊 Signallar tahlili - oxirgi 10 signal bo'yicha AI xulosasi (o'z kanallari
                            doirasida; OWNER_ID uchun barcha kanallar)
  3) /ai <savol>          - bir martalik savol (faqat shaxsiy chatda)

Kalit noto'g'ri, limit tugagan yoki router o'chiq bo'lsa javob o'rniga o'zbek
tilida aniq sabab qaytariladi; AI ishlamasa ham botning qolgan qismi ishlaydi.
===============================================================================
"""

from datetime import time, timedelta

from telegram import Update, BotCommand
from telegram.ext import (
    Application, ContextTypes, MessageHandler, CallbackQueryHandler,
    ChatMemberHandler, filters,
)

from config import (
    BOT_NAME, VERSION, TOKEN, TZ, DAILY_REPORT_HOUR, DAILY_REPORT_MINUTE,
    HEARTBEAT_MINUTES, BACKUP_HOUR, FREELLMAPI_URL, AI_MODEL,
)
from database import init_db, get_channel, get_all_channels, remove_channel
from utils.n8n import n8n_enabled, n8n_send, heartbeat_job, backup_job
from utils.ai import ai_enabled
from utils.reports import build_week_report, build_daily_report, trading_date
from handlers.state import channel_health
from handlers.router import on_message, on_callback
from bot_core import log, prune_dead_channels


async def on_bot_membership_changed(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Bot kanaldan chiqarilsa (yoki o'chirilsa) — kanal ro'yxatdan olib tashlanadi."""
    upd = update.my_chat_member
    if not upd or upd.chat.type != "channel":
        return
    if upd.new_chat_member.status not in ("left", "kicked"):
        return
    ch = get_channel(upd.chat.id)
    if not ch:
        return
    remove_channel(ch["channel_id"])
    channel_health.pop(ch["channel_id"], None)
    log.info("Kanal ro'yxatdan chiqarildi (bot kanaldan chiqdi): %s", ch["title"])
    await n8n_send("channel_removed", {
        "channel_id": ch["channel_id"],
        "title": ch["title"],
        "owner_id": ch["owner_id"],
        "reason": upd.new_chat_member.status,
    })
    if ch["owner_id"]:
        try:
            await ctx.bot.send_message(
                ch["owner_id"],
                f'⚠️ «{ch["title"]}» kanalidan meni chiqarib yuborishdi — kanal '
                f"ro'yxatdan o'chirildi, push va hisobotlar to'xtadi.\n\n"
                f"Qayta ishlatish uchun /register bering.",
            )
        except Exception as e:
            log.info("Kanal egasiga xabar yuborilmadi: %s", e)


async def weekly_job(ctx: ContextTypes.DEFAULT_TYPE):
    for ch in await prune_dead_channels(ctx, get_all_channels()):
        try:
            text = build_week_report(ch["channel_id"], ch["title"])
            await ctx.bot.send_message(ch["channel_id"], text)
        except Exception as e:
            log.warning("Avtomatik hisobot yuborilmadi (%s): %s", ch["title"], e)


async def daily_job(ctx: ContextTypes.DEFAULT_TYPE):
    """Har kuni 02:10 da: hozirgina tugagan savdo kunining (02:00-02:00) natijasini kanallarga
    ovozsiz yuboradi. Signal bo'lmagan kanalga hech narsa yuborilmaydi."""
    day = trading_date() - timedelta(days=1)
    for ch in await prune_dead_channels(ctx, get_all_channels()):
        text = build_daily_report(ch["channel_id"], ch["title"], day)
        if not text:
            continue
        try:
            await ctx.bot.send_message(ch["channel_id"], text, disable_notification=True)
        except Exception as e:
            log.warning("Kunlik hisobot yuborilmadi (%s): %s", ch["title"], e)


async def on_error(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    """PTB'ning umumiy xato ushlagichi (handler ichida ushlanmagan xatolar)."""
    err = ctx.error
    log.exception("Kutilmagan xato: %s", err)
    await n8n_send("bot_error", {
        "where": "handler",
        "error": type(err).__name__ if err else "Unknown",
        "message": str(err)[:300] if err else "",
    })


# ============================== ishga tushirish ==============================
async def _post_init(app):
    try:
        await app.bot.set_my_commands([
            BotCommand("start", "Botni boshlash / bosh menyu"),
            BotCommand("register", "Kanalingizni botga ulash"),
            BotCommand("stats", "Statistika (haftalik/oylik/juftlik)"),
            BotCommand("week", "Joriy hafta hisoboti"),
            BotCommand("monthly", "Oylik hisobot"),
            BotCommand("tag", "Qabul qilindi so'zini o'zgartirish"),
            BotCommand("del", "Signal yoki postni o'chirish (postga reply)"),
            BotCommand("help", "Yordam / buyruqlar ro'yxati"),
            BotCommand("version", "Bot versiyasi"),
            BotCommand("ai", "AI Tahlilchi — savol berish"),
        ])
    except Exception as e:
        log.warning("Buyruqlar katalogi o'rnatilmadi: %s", e)
    if n8n_enabled():
        log.info("n8n integratsiya yoqildi (heartbeat: %s daq, zaxira: %02d:00)",
                 HEARTBEAT_MINUTES, BACKUP_HOUR)
    else:
        log.info("n8n integratsiya o'chiq (N8N_WEBHOOK_URL berilmagan)")
    if ai_enabled():
        log.info("AI Tahlilchi yoqildi (%s, model: %s)", FREELLMAPI_URL, AI_MODEL)
    else:
        log.info("AI Tahlilchi o'chiq (FREELLMAPI_KEY berilmagan)")


def main():
    if not TOKEN:
        raise SystemExit("BOT_TOKEN berilmagan")
    init_db()
    app = Application.builder().token(TOKEN).post_init(_post_init).build()
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.CONTACT | filters.PHOTO | filters.CAPTION) & (
            filters.UpdateType.MESSAGE
            | filters.UpdateType.CHANNEL_POST
            | filters.UpdateType.EDITED_CHANNEL_POST
        ),
        on_message,
    ))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(ChatMemberHandler(on_bot_membership_changed,
                                      ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_error_handler(on_error)
    app.job_queue.run_daily(weekly_job, time=time(10, 0, tzinfo=TZ), days=(6,))
    app.job_queue.run_daily(daily_job, time=time(DAILY_REPORT_HOUR, DAILY_REPORT_MINUTE, tzinfo=TZ))
    if n8n_enabled():
        # heartbeat: birinchi signal 15 sekunddan keyin, keyin har 5 daqiqada
        app.job_queue.run_repeating(heartbeat_job, interval=HEARTBEAT_MINUTES * 60, first=15)
        # kunlik zaxira: har kuni 03:00 (Toshkent)
        app.job_queue.run_daily(backup_job, time=time(BACKUP_HOUR, 0, tzinfo=TZ))
    log.info("%s v%s ishga tushdi", BOT_NAME, VERSION)
    app.run_polling()


if __name__ == "__main__":
    main()
