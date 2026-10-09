"""
Trading Journal - Admin Handlers
"""
from telegram.ext import ContextTypes
from config import OWNER_ID, DEFAULT_TAG, BTN_BACK
from database import (
    register_channel, set_channel_tag, remove_channel,
    get_channel, get_channels_of, get_contact_mapping, get_all_channels,
    get_channel_stats, get_channels_rating, is_admin_push_enabled,
    toggle_admin_push
)
from handlers.state import pending_register, channel_health
from utils.n8n import n8n_send

from bot_core import notify, log, prune_dead_channels, is_protected_tag_blocked
from bot_ui import show_reply_menu, show_home_for, send_reply_text, channel_choices


async def cmd_register(ctx: ContextTypes.DEFAULT_TYPE, msg):
    home = "adminhome" if (OWNER_ID and msg.from_user.id == OWNER_ID) else "mainhome"
    pending_register[msg.from_user.id] = {"stage": "await_forward", "home": home}
    await show_reply_menu(
        ctx, msg.chat_id,
        "Kanalingizni ulash uchun: botni o'sha kanalga ADMIN qilib qo'shing, "
        "so'ng kanaldan istalgan postni menga forward qiling.",
        [[BTN_BACK]], {"screen": "register", "home": home},
    )

async def handle_forward_for_register(ctx: ContextTypes.DEFAULT_TYPE, msg):
    state = pending_register.get(msg.from_user.id)
    if not state or state.get("stage") != "await_forward":
        return False
    home = state.get("home", "mainhome")

    origin_chat = None
    fo = getattr(msg, "forward_origin", None)
    if fo is not None and getattr(fo, "chat", None) is not None:
        origin_chat = fo.chat
    elif getattr(msg, "forward_from_chat", None) is not None:
        origin_chat = msg.forward_from_chat

    if origin_chat is None or origin_chat.type != "channel":
        await show_reply_menu(
            ctx, msg.chat_id,
            "Bu kanal posti emasga o'xshaydi. Kanaldan bevosita forward qiling.",
            [[BTN_BACK]], {"screen": "register", "home": home},
        )
        return True

    try:
        member = await ctx.bot.get_chat_member(origin_chat.id, msg.from_user.id)
        is_admin = member.status in ("administrator", "creator")
    except Exception:
        is_admin = False

    if not is_admin:
        await show_reply_menu(
            ctx, msg.chat_id,
            "Sizni bu kanalda admin sifatida topa olmadim. Avval o'zingizni "
            "shu kanalga admin qilib qo'shing, keyin qayta urinib ko'ring.",
            [[BTN_BACK]], {"screen": "register", "home": home},
        )
        pending_register.pop(msg.from_user.id, None)
        return True

    try:
        me = await ctx.bot.get_chat_member(origin_chat.id, ctx.bot.id)
        bot_ok = me.status in ("administrator", "creator")
    except Exception:
        bot_ok = False
    if not bot_ok:
        await show_reply_menu(
            ctx, msg.chat_id,
            "Men hali bu kanalga admin qilib qo'shilmaganman. Avval shuni qiling.",
            [[BTN_BACK]], {"screen": "register", "home": home},
        )
        pending_register.pop(msg.from_user.id, None)
        return True

    pending_register[msg.from_user.id] = {
        "stage": "await_tag",
        "channel_id": origin_chat.id,
        "title": origin_chat.title or str(origin_chat.id),
        "home": home,
    }
    await show_reply_menu(
        ctx, msg.chat_id,
        f'"{origin_chat.title}" topildi ✅\n\n'
        f'Endi shu kanal uchun "qabul qilindi" so\'zini yozing '
        f'(standart uchun /skip yozing).',
        [[BTN_BACK]], {"screen": "register", "home": home},
    )
    return True

async def handle_tag_for_register(ctx: ContextTypes.DEFAULT_TYPE, msg):
    state = pending_register.get(msg.from_user.id)
    if not state or state.get("stage") != "await_tag":
        return False

    text = msg.text.strip()
    low = text.lower()
    cmd = low.split()[0].split("@")[0] if low.startswith("/") else ""
    if cmd and cmd != "/skip":
        return False
    if cmd == "/skip":
        tag = DEFAULT_TAG
    else:
        if is_protected_tag_blocked(text, msg.from_user.id):
            return True
        tag = text

    register_channel(state["channel_id"], msg.from_user.id, state["title"], tag)
    await n8n_send("channel_registered", {
        "channel_id": state["channel_id"],
        "title": state["title"],
        "owner_id": msg.from_user.id,
        "tag": tag,
    })
    home = state.get("home", "mainhome")
    pending_register.pop(msg.from_user.id, None)
    await ctx.bot.send_message(
        msg.chat_id,
        f'✅ "{state["title"]}" ro\'yxatdan o\'tdi. Endi shu kanalda #Signal '
        f'postlarini yuborishingiz mumkin.',
    )
    await show_home_for(ctx, msg.chat_id, msg.from_user, home)
    return True

async def cmd_tag_in_channel(ctx: ContextTypes.DEFAULT_TYPE, msg, channel, args):
    if not args:
        await notify(ctx, msg.chat_id, f'Joriy so\'z: "{channel["tag"] or DEFAULT_TAG}"')
        return
    new_tag = " ".join(args)
    actor_id = msg.from_user.id if msg.from_user else 0
    if is_protected_tag_blocked(new_tag, actor_id):
        return
    set_channel_tag(channel["channel_id"], new_tag)
    await notify(ctx, msg.chat_id, f'Yangilandi: endi "{new_tag}" deb yoziladi.')

async def cmd_tag_in_dm(ctx: ContextTypes.DEFAULT_TYPE, msg, args):
    channels = await prune_dead_channels(ctx, get_channels_of(msg.from_user.id), chat_id=msg.chat_id)
    if not channels:
        await ctx.bot.send_message(msg.chat_id, "Sizda ro'yxatdan o'tgan kanal yo'q. Avval /register bering.")
        return
    if len(channels) == 1:
        ch = channels[0]
        if not args:
            await ctx.bot.send_message(msg.chat_id, f'Joriy so\'z: "{ch["tag"] or DEFAULT_TAG}"')
            return
        new_tag = " ".join(args)
        if is_protected_tag_blocked(new_tag, msg.from_user.id):
            return
        set_channel_tag(ch["channel_id"], new_tag)
        await ctx.bot.send_message(msg.chat_id, f'Yangilandi: endi "{new_tag}" deb yoziladi.')
        return
    home = "adminhome" if (OWNER_ID and msg.from_user.id == OWNER_ID) else "mainhome"
    labels, choices = channel_choices(channels)
    await show_reply_menu(
        ctx, msg.chat_id, "Qaysi kanal uchun?", [[label] for label in labels] + [[BTN_BACK]],
        {
            "screen": "tag_channel",
            "choices": choices,
            "new_tag": " ".join(args) if args else None,
            "home": home,
        },
    )

async def handle_admin_reply(ctx: ContextTypes.DEFAULT_TYPE, msg):
    if not (OWNER_ID and msg.chat_id == OWNER_ID and msg.reply_to_message):
        return False
    mapping = get_contact_mapping(msg.reply_to_message.message_id)
    if not mapping:
        return False
    try:
        await ctx.bot.send_message(mapping["user_chat_id"], f"✉️ Admin javobi:\n\n{msg.text}")
        await msg.reply_text("✅ Yuborildi.")
    except Exception as e:
        log.warning("Admin javobini yuborib bo'lmadi: %s", e)
        await msg.reply_text("⚠️ Yuborib bo'lmadi, foydalanuvchi botni bloklagan bo'lishi mumkin.")
    return True

async def on_bot_membership_changed(update, ctx: ContextTypes.DEFAULT_TYPE):
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
        except Exception:
            pass

# ================= Admin Stats & Rating =================

async def cmd_all_channels_stats(ctx, msg):
    if not (OWNER_ID and msg.from_user.id == OWNER_ID):
        return

    channels = get_all_channels()
    if not channels:
        await send_reply_text(ctx, msg.chat_id, "Hozircha ro'yxatdan o'tgan kanallar yo'q.")
        return

    # Kanal tanlash menyusi
    log.info("Admin barcha kanallar statistikasi so'raldi. Kanallar soni: %d", len(channels))
    labels, choices = channel_choices(channels)
    await show_reply_menu(
        ctx, msg.chat_id,
        "Barcha kanallar ro'yxati. Statistika va push sozlamalari uchun kanalni tanlang:",
        [[label] for label in labels] + [[BTN_BACK]],
        {"screen": "admin_all_stats", "choices": choices, "home": "adminhome"}
    )

import html

async def handle_admin_stats_pick(ctx, msg, channel_id):
    log.info("Kanal tanlandi. channel_id: %s", channel_id)
    ch = get_channel(channel_id)
    if not ch:
        log.warning("Kanal topilmadi: %s", channel_id)
        await notify(ctx, msg.chat_id, "Kanal topilmadi.")
        return

    stats = get_channel_stats(channel_id)
    push_enabled = is_admin_push_enabled(channel_id)
    push_btn = "🔔 Push yoqish" if not push_enabled else "🔕 Push o'chirish"

    title = html.escape(str(ch['title'] or ch['channel_id']))
    tag = html.escape(str(ch['tag'] or DEFAULT_TAG))
    owner_str = html.escape(str(ch['owner_id'] or '—'))

    text = (
        f"📊 <b>{title}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID: <code>{ch['channel_id']}</code>\n"
        f"👤 Egasi: <code>{owner_str}</code>\n"
        f"🏷 Tag: <b>{tag}</b>\n\n"
        f"📈 <b>Statistika:</b>\n"
        f"• Jami signallar: {stats['total']}\n"
        f"• G'alabalar: {stats['wins']}\n"
        f"• Mag'lubiyatlar: {stats['losses']}\n"
        f"• Sof foyda: {stats['total_pips']} pips\n"
        f"• Obunachilar: {stats['subs']}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )

    rows = [[push_btn], [BTN_BACK]]
    try:
        await show_reply_menu(
            ctx, msg.chat_id, text, rows,
            {"screen": "admin_chan_detail", "channel_id": channel_id, "home": "adminhome"},
            parse_mode="HTML"
        )
    except Exception as e:
        log.warning("HTML formatda kanal tafsilotini yuborib bo'lmadi: %s", e)
        clean_text = (
            f"📊 {ch['title']}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🆔 ID: {ch['channel_id']}\n"
            f"👤 Egasi: {ch['owner_id']}\n"
            f"🏷 Tag: {ch['tag'] or DEFAULT_TAG}\n\n"
            f"📈 Statistika:\n"
            f"• Jami signallar: {stats['total']}\n"
            f"• G'alabalar: {stats['wins']}\n"
            f"• Mag'lubiyatlar: {stats['losses']}\n"
            f"• Sof foyda: {stats['total_pips']} pips\n"
            f"• Obunachilar: {stats['subs']}\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        await show_reply_menu(
            ctx, msg.chat_id, clean_text, rows,
            {"screen": "admin_chan_detail", "channel_id": channel_id, "home": "adminhome"}
        )

async def toggle_admin_push_handler(ctx, msg, channel_id):
    current = is_admin_push_enabled(channel_id)
    toggle_admin_push(channel_id, not current)

    await handle_admin_stats_pick(ctx, msg, channel_id)
    status = "yoqildi" if not current else "o'chirildi"
    await notify(ctx, msg.chat_id, f"Kanal push-bildirishnomalari {status} ✅")

async def cmd_admin_rating(ctx, msg, sort_by="pips"):
    if not (OWNER_ID and msg.from_user.id == OWNER_ID):
        return

    rating = get_channels_rating(sort_by)
    if not rating:
        await send_reply_text(ctx, msg.chat_id, "Reyting uchun yetarli ma'lumot yo'q.")
        return

    title = "🏆 Reyting (Sof foyda bo'yicha)" if sort_by == "pips" else "🏆 Reyting (Winrate bo'yicha)"
    lines = [title, "━━━━━━━━━━━━━━━━━━"]

    for i, row in enumerate(rating, 1):
        # row: channel_id, title, total_pips, winrate
        lines.append(f"{i}. {row['title']} — {row['total_pips']} pips | {row['winrate']:.1f}%")

    rows = [[ "🔄 Winrate bo'yicha", "🔄 Sof foyda bo'yicha"], [BTN_BACK]]

    # Tugmalarni dinamik qilish uchun callback orqali emas, balki matn orqali handle qilamiz (ReplyKeyboard)
    # Bu yerda biz oddiyroq yondashuvni tanlaymiz:
    await send_reply_text(
        ctx, msg.chat_id, "\n".join(lines),
        rows, {"screen": "admin_rating", "home": "adminhome"}
    )
