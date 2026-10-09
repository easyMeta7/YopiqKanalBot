"""
Trading Journal - Core helpers

Handlerlarga BOG'LIQ BO'LMAGAN umumiy funksiyalar: logger, kanal holati keshi,
vaqtinchalik xabarlar va foydalanuvchi kanallarini topish.
(Aylanma import bo'lmasligi uchun handlers/* shu moduldan import qiladi.)
"""
import logging
from datetime import datetime

from telegram.error import BadRequest, Forbidden
from telegram.ext import ContextTypes

from config import (
    TZ, OWNER_ID, NOTICE_SECONDS, REPORT_SECONDS, PROTECTED_TAG, CHANNEL_CHECK_TTL,
)
from database import remove_channel, get_all_channels, get_channels_of
from handlers.state import channel_health

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # tokenli URL loglarga tushmasin
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger("bot")


# ------------------------------ kanal holati ------------------------------
async def channel_is_alive(ctx, channel_id):
    """Kanal mavjudmi va bot unda adminmi? (natija CHANNEL_CHECK_TTL keshlanadi)."""
    now_ts = datetime.now(TZ).timestamp()
    cached = channel_health.get(channel_id)
    if cached and now_ts - cached[0] < CHANNEL_CHECK_TTL:
        return cached[1]
    try:
        me = await ctx.bot.get_chat_member(channel_id, ctx.bot.id)
        alive = me.status in ("administrator", "creator")
    except (Forbidden, BadRequest):
        alive = False           # bot chiqarilgan yoki kanal o'chirilgan
    except Exception as e:
        log.info("Kanal holatini tekshirib bo'lmadi (%s): %s", channel_id, e)
        channel_health[channel_id] = (now_ts, True)   # tarmoq xatosi — o'chirmaymiz
        return True
    channel_health[channel_id] = (now_ts, alive)
    return alive


async def prune_dead_channels(ctx, channels, chat_id=None):
    """O'chirilgan / botdan chiqarilgan kanallarni ro'yxatdan olib tashlaydi."""
    alive, removed = [], []
    for ch in channels:
        if await channel_is_alive(ctx, ch["channel_id"]):
            alive.append(ch)
            continue
        remove_channel(ch["channel_id"])
        channel_health.pop(ch["channel_id"], None)
        removed.append(ch["title"] or str(ch["channel_id"]))
    if removed and chat_id:
        await ctx.bot.send_message(
            chat_id,
            "⚠️ Bu kanal(lar) endi mavjud emas yoki bot chiqarilgan, "
            "ro'yxatdan olib tashlandi: " + ", ".join(removed),
        )
    return alive


def is_protected_tag_blocked(new_tag, actor_user_id):
    return new_tag.strip().lower() == PROTECTED_TAG and actor_user_id != OWNER_ID


# ======================= Vaqtinchalik xabarlar =======================
async def _delete_later(ctx: ContextTypes.DEFAULT_TYPE):
    chat_id, message_id = ctx.job.data
    try:
        await ctx.bot.delete_message(chat_id, message_id)
    except Exception:
        pass


def schedule_delete(ctx, chat_id, message_id, seconds=NOTICE_SECONDS):
    jq = getattr(ctx, "job_queue", None)
    if not jq:
        return
    jq.run_once(_delete_later, seconds, data=(chat_id, message_id),
                name=f"del:{chat_id}:{message_id}")


def reschedule_delete(ctx, chat_id, message_id, seconds):
    """Xabarni o'chirish vaqtini yangidan boshlaydi (tugma bosilganda xabar yo'qolib qolmasin)."""
    jq = getattr(ctx, "job_queue", None)
    if not jq:
        return
    for job in jq.get_jobs_by_name(f"del:{chat_id}:{message_id}"):
        job.schedule_removal()
    schedule_delete(ctx, chat_id, message_id, seconds)


async def notify(ctx, chat_id, text, seconds=NOTICE_SECONDS):
    sent = await ctx.bot.send_message(chat_id, text)
    schedule_delete(ctx, sent.chat_id, sent.message_id, seconds)


async def send_report(ctx, chat_id, text, is_channel, reply_markup=None):
    sent = await ctx.bot.send_message(chat_id, text, reply_markup=reply_markup)
    if is_channel:
        schedule_delete(ctx, sent.chat_id, sent.message_id, REPORT_SECONDS)
    return sent


# --------------------- foydalanuvchi uchun kanallar ---------------------
async def find_subscriber_channels(ctx, user_id):
    """Foydalanuvchi uchun mavjud kanallar (takrorlanmas, o'liklar tozangan).

    Tartib:
    1) ADMIN (OWNER_ID) kanallari — obunachi hali hech qanday kanal
       qo'shmagan bo'lsa ham uning statistikasi ko'rinadi.
    2) Foydalanuvchining o'zi ulagan kanallari.
    3) A'zo bo'lgan kanallar.
    Bitta kanal bo'lsa — darhol statistika; bir nechta bo'lsa —
    qaysi kanaldan olishi so'raladi.
    """
    ordered, seen = [], set()

    def add(ch):
        if ch and ch["channel_id"] not in seen:
            seen.add(ch["channel_id"])
            ordered.append(ch)

    alive = await prune_dead_channels(ctx, get_all_channels(), chat_id=user_id)
    by_id = {ch["channel_id"]: ch for ch in alive}

    if OWNER_ID:                           # 1) admin kanallari (obunachiga ham)
        for ch in get_channels_of(OWNER_ID):
            add(by_id.get(ch["channel_id"]))
    for ch in get_channels_of(user_id):    # 2) o'z kanallari
        add(by_id.get(ch["channel_id"]))
    for ch in alive:                       # 3) a'zo bo'lgan kanallar
        if ch["channel_id"] in seen:
            continue
        try:
            member = await ctx.bot.get_chat_member(ch["channel_id"], user_id)
            if member.status not in ("left", "kicked"):
                add(ch)
        except Exception:
            continue
    return ordered
