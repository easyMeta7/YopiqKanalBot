"""
Trading Journal - User Handlers
"""
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from config import OWNER_ID, REPORT_SECONDS, PAIRS, BTN_WEEK, BTN_MONTH, BTN_PAIR, BTN_BACK, BTN_UNREGISTER
from database import (
    get_channel, get_channels_of, is_subscribed, save_contact_mapping
)
from handlers.state import pending_contact
from utils.reports import build_week_report, build_monthly_report, build_pair_stats
from bot_core import prune_dead_channels, schedule_delete, reschedule_delete, find_subscriber_channels, log
from bot_ui import show_reply_menu, channel_choices, catalog_rows
from utils.n8n import n8n_send

def stats_menu_kb():
    """Kanaldagi /stats tugmalari (callback_data bilan; eski kodda xato ravishda url berilgan edi)."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Haftalik", callback_data="cst:week")],
        [InlineKeyboardButton("📅 Oylik", callback_data="cst:month")],
        [InlineKeyboardButton("💱 Juftlik bo'yicha", callback_data="cst:pairpick")],
    ])


async def on_channel_stats_callback(ctx, q, action):
    """Kanaldagi /stats tugmalari ("cst:*"): hisobot xabarning o'zida almashadi.
    Faqat kanal admini bosa oladi; xabar o'chirilish vaqti har bosishda yangilanadi."""
    chat_id = q.message.chat_id
    channel = get_channel(chat_id)
    if not channel:
        await q.answer()
        return
    try:
        member = await ctx.bot.get_chat_member(chat_id, q.from_user.id)
        is_admin = member.status in ("administrator", "creator")
    except Exception:
        await q.answer()
        return
    if not is_admin:
        await q.answer("Faqat kanal admini tanlay oladi.", show_alert=True)
        return
    await q.answer()

    cid, title = channel["channel_id"], channel["title"]
    kb = None
    if action == "week":
        text = build_week_report(cid, title)
    elif action == "month":
        text = build_monthly_report(cid, title, [])
    elif action == "pairpick":
        text = "Qaysi juftlik?"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(p, callback_data=f"cst:pair:{p}") for p in PAIRS],
            [InlineKeyboardButton(BTN_BACK, callback_data="cst:menu")],
        ])
    elif action.startswith("pair:") and action.split(":", 1)[1] in PAIRS:
        text = build_pair_stats(cid, title, action.split(":", 1)[1])
    elif action == "menu":
        text = f"📈 Statistika — {title}"
        kb = stats_menu_kb()
    else:
        return
    try:
        await q.message.edit_text(text, reply_markup=kb)
    except Exception as e:
        log.info("Statistika xabarini tahrirlab bo'lmadi: %s", e)
        return
    reschedule_delete(ctx, chat_id, q.message.message_id, REPORT_SECONDS)


async def cmd_stats(ctx: ContextTypes.DEFAULT_TYPE, msg, is_registered_channel, channel, args):
    pair_arg = None
    if args and args[0].upper() in PAIRS:
        pair_arg = args[0].upper()

    if is_registered_channel:
        if pair_arg:
            await send_report(ctx, msg.chat_id, build_pair_stats(channel["channel_id"], channel["title"], pair_arg), True)
        else:
            kb = stats_menu_kb()
            await send_report(ctx, msg.chat_id, f"📈 Statistika — {channel['title']}", True, reply_markup=kb)
    else:
        await resolve_stats_channel_dm(ctx, msg.chat_id, msg.from_user, pair_arg)

async def resolve_stats_channel_dm(ctx, chat_id, user, pair_arg):
    candidates = await find_subscriber_channels(ctx, user.id)
    if not candidates:
        await ctx.bot.send_message(
            chat_id, "Sizda tegishli kanal topilmadi. /register bering yoki "
            "ro'yxatdan o'tgan kanalga a'zo bo'ling."
        )
        return
    home = "adminhome" if (OWNER_ID and user.id == OWNER_ID) else "mainhome"
    if len(candidates) == 1:
        ch = candidates[0]
        if pair_arg:
            await show_stats_reply_menu(ctx, chat_id, ch, home,
                                        text=build_pair_stats(ch["channel_id"], ch["title"], pair_arg))
        else:
            await show_channel_reply_menu(ctx, chat_id, user, ch, home)
        return
    labels, choices = channel_choices(candidates)
    if pair_arg:
        state = {"screen": "stats_channel_pair", "pair": pair_arg, "choices": choices, "home": home}
    else:
        state = {"screen": "stats_channel", "choices": choices, "home": home}
    await show_reply_menu(ctx, chat_id, "Qaysi kanal uchun?",
                          [[label] for label in labels] + [[BTN_BACK]], state)

async def cmd_report_in_dm(ctx, msg, kind, args):
    await report_in_dm_for(ctx, msg.chat_id, msg.from_user, kind, args)

async def report_in_dm_for(ctx, chat_id, user, kind, args):
    channels = await prune_dead_channels(ctx, get_channels_of(user.id), chat_id=chat_id)
    if not channels:
        await ctx.bot.send_message(chat_id, "Sizda ro'yxatdan o'tgan kanal yo'q. Avval /register bering.")
        return
    if len(channels) == 1:
        await send_report_for_channel_dm(ctx, chat_id, kind, args, channels[0])
        return
    home = "adminhome" if (OWNER_ID and user.id == OWNER_ID) else "mainhome"
    labels, choices = channel_choices(channels)
    await show_reply_menu(
        ctx, chat_id, "Qaysi kanal uchun?", [[label] for label in labels] + [[BTN_BACK]],
        {"screen": "report_channel", "kind": kind, "args": args, "choices": choices, "home": home},
    )

async def send_report_for_channel_dm(ctx, chat_id, kind, args, channel):
    title = channel["title"]
    if kind == "week":
        text = build_week_report(channel["channel_id"], title)
    else:
        text = build_monthly_report(channel["channel_id"], title, args)
    await ctx.bot.send_message(chat_id, text)

async def start_contact_flow(ctx, chat_id, user):
    home = "adminhome" if (OWNER_ID and user.id == OWNER_ID) else "mainhome"
    channels = await prune_dead_channels(ctx, get_channels_of(user.id), chat_id=chat_id)
    if len(channels) <= 1:
        chosen = channels[0]["channel_id"] if channels else None
        chosen_title = channels[0]["title"] if channels else None
        pending_contact[user.id] = {"stage": "await_message", "channel_id": chosen, "channel_title": chosen_title}
        await show_reply_menu(ctx, chat_id, "Xabaringizni yozing, men uni adminga yetkazaman.",
                              [ [BTN_BACK] ], {"screen": "contact_message", "home": home})
        return
    labels, choices = channel_choices(channels)
    await show_reply_menu(
        ctx, chat_id, "Qaysi kanal bo'yicha murojaat qilyapsiz?", [[label] for label in labels] + [[BTN_BACK]],
        {"screen": "contact_channel", "choices": choices, "home": home},
    )

async def handle_contact_message(ctx, msg):
    state = pending_contact.get(msg.from_user.id)
    if not state or state.get("stage") != "await_message":
        return False
    if not OWNER_ID:
        await ctx.bot.send_message(msg.chat_id, "Admin bilan bog'lanish hozircha sozlanmagan.")
        pending_contact.pop(msg.from_user.id, None)
        return True

    u = msg.from_user
    who = f"@{u.username}" if u.username else u.full_name
    ch_line = f"\nKanal: {state['channel_title']}" if state.get("channel_title") else ""
    sent = await ctx.bot.send_message(
        OWNER_ID,
        f"📩 Yangi murojaat\nKimdan: {who} (id {u.id}){ch_line}\n\n{msg.text}",
    )
    save_contact_mapping(sent.message_id, msg.chat_id, who)
    await n8n_send("contact_message", {
        "user_id": u.id,
        "username": u.username,
        "name": u.full_name,
        "channel": state.get("channel_title"),
        "text": msg.text,
    })
    pending_contact.pop(msg.from_user.id, None)
    home = "adminhome" if (OWNER_ID and msg.from_user.id == OWNER_ID) else "mainhome"
    await show_reply_menu(ctx, msg.chat_id, "✅ Xabaringiz yuborildi.", [], {"screen": "home", "home": home})
    return True

async def show_main_home(ctx, chat_id, user):
    await show_reply_menu(
        ctx, chat_id, "Kerakli bo'limni pastdagi menyudan tanlang.",
        catalog_rows(chat_id), {"screen": "home"},
    )

async def show_admin_home(ctx, chat_id, user):
    await show_reply_menu(
        ctx, chat_id, "Kerakli bo'limni pastdagi menyudan tanlang.",
        catalog_rows(chat_id), {"screen": "home"},
    )

async def show_my_channels(ctx, chat_id, user, home):
    channels = await find_subscriber_channels(ctx, user.id)
    if not channels:
        await show_reply_menu(ctx, chat_id, "Siz hozircha ro'yxatdan o'tgan kanalga a'zo emassiz.",
                              [ [BTN_BACK] ], {"screen": "channel_pick", "choices": {}, "home": home})
        return
    if len(channels) == 1:
        await show_channel_reply_menu(ctx, chat_id, user, channels[0], home)
        return
    labels, choices = channel_choices(channels)
    await show_reply_menu(ctx, chat_id, "Qaysi kanal?", [[label] for label in labels] + [[BTN_BACK]],
                          {"screen": "channel_pick", "choices": choices, "home": home})

async def show_stats_flow(ctx, chat_id, user, home):
    channels = await find_subscriber_channels(ctx, user.id)
    if not channels:
        await show_reply_menu(ctx, chat_id, "Sizda tegishli kanal topilmadi.",
                              [ [BTN_BACK] ], {"screen": "stats_channel", "choices": {}, "home": home})
        return
    if len(channels) == 1:
        await show_stats_reply_menu(ctx, chat_id, channels[0], home)
        return
    labels, choices = channel_choices(channels)
    await show_reply_menu(ctx, chat_id, "Qaysi kanal uchun?", [[label] for label in labels] + [[BTN_BACK]],
                          {"screen": "stats_channel", "choices": choices, "home": home})

async def show_stats_reply_menu(ctx, chat_id, channel, home, text=None):
    await show_reply_menu(
        ctx, chat_id, text or f"📈 Statistika — {channel['title']}",
        [[BTN_WEEK, BTN_MONTH], [BTN_PAIR], [BTN_BACK]],
        {"screen": "stats", "channel_id": channel["channel_id"], "home": home},
    )

async def show_channel_reply_menu(ctx, chat_id, user, channel, home, text=None):
    subscribed = is_subscribed(user.id, channel["channel_id"])
    push_label = "🔕 Push o'chirish" if subscribed else "🔔 Push yoqish"
    rows = [[BTN_WEEK, BTN_MONTH], [BTN_PAIR, push_label]]
    if channel["owner_id"] and channel["owner_id"] == user.id:
        rows.append([BTN_UNREGISTER])
    rows.append([BTN_BACK])
    await show_reply_menu(
        ctx, chat_id, text or f"📊 {channel['title']}", rows,
        {"screen": "channel", "channel_id": channel["channel_id"], "home": home},
    )

async def send_report(ctx, chat_id, text, is_channel, reply_markup=None):
    sent = await ctx.bot.send_message(chat_id, text, reply_markup=reply_markup)
    if is_channel:
        schedule_delete(ctx, sent.chat_id, sent.message_id, REPORT_SECONDS)
    return sent
