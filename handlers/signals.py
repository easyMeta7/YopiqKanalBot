"""
Trading Journal - Signal Handlers
"""
import re
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import Forbidden, BadRequest
from config import DEFAULT_TAG, PAIRS, TZ, OWNER_ID
from database import get_push_recipients, db, is_admin_push_enabled
from utils.signals import signal_looks_complete, parse_signal, detect_pair, fmt_pips, pips
from bot_core import notify, log

async def offer_pair_buttons(ctx, msg, channel):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(p, callback_data=f"pairsel:{p}") for p in PAIRS]])
    try:
        await ctx.bot.edit_message_reply_markup(msg.chat_id, msg.message_id, reply_markup=kb)
    except Exception as e:
        log.warning("Juftlik tugmalarini biriktirib bo'lmadi: %s", e)

async def push_to_subscribers(ctx, channel_id, message_id):
    # 1. Obunachilarga yuborish
    for user_id in get_push_recipients(channel_id):
        try:
            sent = await ctx.bot.copy_message(chat_id=user_id, from_chat_id=channel_id, message_id=message_id)
            with db() as con:
                con.execute(
                    "INSERT OR REPLACE INTO pushes (channel_id, message_id, user_id, pushed_message_id) "
                    "VALUES (?,?,?,?)",
                    (channel_id, message_id, user_id, sent.message_id),
                )
        except Exception as e:
            log.info("Push yuborilmadi (user %s): %s", user_id, e)

    # 2. Admin uchun push-monitoring tekshiruvi
    if OWNER_ID and is_admin_push_enabled(channel_id):
        try:
            await ctx.bot.copy_message(chat_id=OWNER_ID, from_chat_id=channel_id, message_id=message_id)
        except Exception as e:
            log.info("Admin push yuborilmadi: %s", e)

POST_TAG_PREFIXES = ("#post", "#idea", "#fikr", "#yangilik", "#news")
POST_TAG_PATTERN = re.compile(
    r"^(" + "|".join(re.escape(p) for p in POST_TAG_PREFIXES) + r")(?:\b|\s|[^\w]|$)",
    re.IGNORECASE,
)

def is_post_message(text: str) -> bool:
    if not text:
        return False
    return bool(POST_TAG_PATTERN.search(text.strip()))

async def handle_signal_text(ctx, msg, channel):
    text = msg.text or msg.caption or ""
    t = text.strip()
    low = t.lower()

    if low == "#signal":
        await offer_pair_buttons(ctx, msg, channel)
        return
    if not low.startswith("#signal"):
        return
    if not signal_looks_complete(t):
        return

    try:
        s = parse_signal(t)
    except ValueError as e:
        await notify(ctx, msg.chat_id, f"⚠️ Signalni o'qib bo'lmadi: {e}", seconds=15)
        return

    pair = detect_pair(t)
    with db() as con:
        existing = con.execute(
            "SELECT * FROM signals WHERE chat_id=? AND message_id=?",
            (msg.chat_id, msg.message_id),
        ).fetchone()
        if existing:
            con.execute(
                "UPDATE signals SET pair=?, side=?, entry=?, stop=?, tp1=?, tp2=?, tp3=? WHERE id=?",
                (pair, s["side"], s["entry"], s["stop"], s["tp1"], s["tp2"], s["tp3"], existing["id"]),
            )
            return
        con.execute(
            """INSERT INTO signals
               (chat_id, message_id, pair, side, entry, stop, tp1, tp2, tp3, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (msg.chat_id, msg.message_id, pair, s["side"], s["entry"], s["stop"],
             s["tp1"], s["tp2"], s["tp3"], datetime.now(TZ).isoformat()),
        )

    tag = channel["tag"] or DEFAULT_TAG
    try:
        if getattr(msg, "caption", None) is not None:
            await msg.edit_caption(f"{msg.caption_html}\n\n{tag}.", parse_mode="HTML", reply_markup=None)
        else:
            await msg.edit_text(f"{msg.text_html}\n\n{tag}.", parse_mode="HTML", reply_markup=None)
    except Exception as e:
        log.warning("Postni tahrirlab bo'lmadi: %s", e)
        await notify(
            ctx, msg.chat_id,
            "⚠️ Postni tahrirlab bo'lmadi: botga 'Boshqalarning xabarlarini "
            "tahrirlash' ruxsatini bering.",
            seconds=15,
        )

    await push_to_subscribers(ctx, msg.chat_id, msg.message_id)

async def handle_channel_post(ctx, msg, channel):
    with db() as con:
        existing = con.execute(
            "SELECT 1 FROM channel_posts WHERE channel_id=? AND message_id=?",
            (msg.chat_id, msg.message_id),
        ).fetchone()
        if existing:
            return
        con.execute(
            "INSERT INTO channel_posts (channel_id, message_id, created_at) VALUES (?,?,?)",
            (msg.chat_id, msg.message_id, datetime.now(TZ).isoformat()),
        )

    tag = channel["tag"] or DEFAULT_TAG
    tag_str = f"{tag}."
    text_content = msg.caption or msg.text or ""

    if tag_str not in text_content:
        is_caption = getattr(msg, "caption", None) is not None
        raw_html = msg.caption_html if is_caption else getattr(msg, "text_html", "")
        try:
            new_html = f"{raw_html}\n\n{tag_str}" if raw_html else tag_str
            if is_caption:
                await msg.edit_caption(new_html, parse_mode="HTML", reply_markup=None)
            else:
                await msg.edit_text(new_html, parse_mode="HTML", reply_markup=None)
        except Exception as e:
            log.warning("Postga tag qo'shib bo'lmadi: %s", e)

    await push_to_subscribers(ctx, msg.chat_id, msg.message_id)

async def handle_result_reply(msg):
    raw = msg.text or msg.caption or ""
    word = raw.strip().lower()
    if word not in ("tp1", "tp2", "tp3", "stop"):
        return
    target = msg.reply_to_message
    with db() as con:
        r = con.execute(
            "SELECT * FROM signals WHERE chat_id=? AND message_id=?",
            (msg.chat_id, target.message_id),
        ).fetchone()
        if not r:
            return
        sid, side, entry = r["id"], r["side"], r["entry"]
        cur = r["status"]

        if word == "stop":
            if cur != "open":
                await msg.reply_text(f"Bu signal allaqachon {cur.upper()} bilan yopilgan, o'zgarmadi.")
                return
            p = pips(side, entry, r["stop"])
        else:
            price = r[word]
            if price is None:
                await msg.reply_text(f"Bu signalda {word.upper()} belgilanmagan.")
                return
            if cur == "stop":
                await msg.reply_text("Bu signal Stop bilan yopilgan, o'zgarmadi.")
                return
            if cur in {"tp1", "tp2", "tp3"} and {"tp1": 1, "tp2": 2, "tp3": 3}[word] <= {"tp1": 1, "tp2": 2, "tp3": 3}[cur]:
                await msg.reply_text(f"Bu signalda natija allaqachon {cur.upper()} (yuqoriroq yoki teng).")
                return
            p = pips(side, entry, price)

        con.execute(
            "UPDATE signals SET status=?, result_pips=?, result_at=? WHERE id=?",
            (word, p, datetime.now(TZ).isoformat(), sid),
        )
    icon = "🛑" if word == "stop" else "✅"
    result_line = f"{icon} {fmt_pips(p)}"
    try:
        if getattr(msg, "caption", None) is not None:
            await msg.edit_caption(f"{msg.caption_html}\n\n{result_line}", parse_mode="HTML")
        else:
            await msg.edit_text(f"{msg.text_html}\n\n{result_line}", parse_mode="HTML")
    except Exception as e:
        log.warning("Natija xabarini tahrirlab bo'lmadi: %s", e)
        await msg.reply_text(result_line)

async def cmd_del(ctx, msg):
    if not msg.reply_to_message:
        await notify(ctx, msg.chat_id, "Signal yoki postga reply qilib /del deb yozing.")
        return
    target_id = msg.reply_to_message.message_id
    with db() as con:
        row = con.execute(
            "SELECT * FROM signals WHERE chat_id=? AND message_id=?",
            (msg.chat_id, target_id),
        ).fetchone()
        ch_post = con.execute(
            "SELECT * FROM channel_posts WHERE channel_id=? AND message_id=?",
            (msg.chat_id, target_id),
        ).fetchone()
        pushes = con.execute(
            "SELECT * FROM pushes WHERE channel_id=? AND message_id=?",
            (msg.chat_id, target_id),
        ).fetchall()
        if row:
            con.execute("DELETE FROM signals WHERE id=?", (row["id"],))
        if ch_post:
            con.execute(
                "DELETE FROM channel_posts WHERE channel_id=? AND message_id=?",
                (msg.chat_id, target_id),
            )
        if pushes:
            con.execute(
                "DELETE FROM pushes WHERE channel_id=? AND message_id=?",
                (msg.chat_id, target_id),
            )

    if not row and not ch_post and not pushes:
        await notify(ctx, msg.chat_id, "Bu post signal yoki xabar sifatida topilmadi.")
        return
    try:
        await ctx.bot.delete_message(msg.chat_id, target_id)
        deleted_successfully = True
    except Forbidden:
        await notify(ctx, msg.chat_id, "❌ Botga xabarlarni o'chirish ruxsati berilmagan.")
        deleted_successfully = False
    except BadRequest as e:
        await notify(ctx, msg.chat_id, f"❌ Xabar topilmadi yoki juda eski: {e}")
        deleted_successfully = False
    except Exception as e:
        log.info("Postni o'chirib bo'lmadi: %s", e)
        await notify(ctx, msg.chat_id, "❌ Kutilmagan xatolik yuz berdi.")
        deleted_successfully = False

    # Obunachilarga ketgan push-nusxalarni o'chirish
    if pushes:
        log.info("O'chirilayotgan push-nusxalar soni: %d", len(pushes))
        for p in pushes:
            try:
                await ctx.bot.delete_message(p["user_id"], p["pushed_message_id"])
            except Forbidden:
                log.info("Push o'chirilmadi (user %s): bot bloklangan", p["user_id"])
            except BadRequest:
                log.info("Push o'chirilmadi (user %s): xabar topilmadi", p["user_id"])
            except Exception as e:
                log.info("Push o'chirishda kutilmagan xato (user %s): %s", p["user_id"], e)

    if deleted_successfully:
        if row:
            await notify(ctx, msg.chat_id, "🗑 Signal o'chirildi va hisobotdan chiqarildi.")
        else:
            await notify(ctx, msg.chat_id, "🗑 Post o'chirildi va obunachilardan tozalandi.")
