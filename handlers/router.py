"""
Trading Journal - Router: kelgan xabar va callback'larni tegishli handlerga yo'naltiradi.
"""
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes

from config import (
    BOT_NAME, VERSION, OWNER_ID, DEFAULT_TAG, PAIRS, LANGS,
    BTN_HOME, BTN_STATS, BTN_MY_CHANNELS, BTN_REGISTER, BTN_OWNER_REGISTER,
    BTN_SETTINGS, BTN_CONTACT, BTN_LEADS, BTN_BACK, BTN_WEEK, BTN_MONTH,
    BTN_PAIR, BTN_UNREGISTER, BTN_YES_DELETE, BTN_ALL_CHANNELS, BTN_RATING,
    BTN_AI, BTN_AI_ASK, BTN_AI_ANALYZE_SIGNALS,
)
from database import (
    get_dm_user, save_dm_user, list_dm_users, get_channel, get_all_channels,
    set_channel_tag, remove_channel, is_subscribed, subscribe, unsubscribe,
)
from utils.n8n import n8n_send
from utils.ai import ask_ai_analyst
from utils.reports import build_week_report, build_monthly_report, build_pair_stats
from handlers.state import (
    pending_register, pending_contact, onboarding, reply_menu_states, channel_health,
)
from handlers.onboarding import handle_onboarding_message, send_start
from handlers.admin import (
    handle_admin_reply, handle_forward_for_register, handle_tag_for_register,
    cmd_register, cmd_tag_in_channel, cmd_tag_in_dm, cmd_all_channels_stats,
    cmd_admin_rating, handle_admin_stats_pick, toggle_admin_push_handler,
)
from handlers.user import (
    handle_contact_message, cmd_stats, cmd_report_in_dm, start_contact_flow,
    on_channel_stats_callback,
)
from handlers.signals import (
    cmd_del, handle_signal_text, handle_channel_post, handle_result_reply,
    is_post_message,
)
from bot_core import (
    log, notify, send_report, schedule_delete, is_protected_tag_blocked,
)
from bot_ui import (
    CATALOG_BUTTONS, AI_ASK_PROMPT, catalog_rows, channel_help_text, full_info_text,
    show_reply_menu, send_reply_text, show_home_for, show_help_reply_menu,
    show_ai_reply_menu, _ai_send_answer, ai_analyze_signals, show_my_channels,
    show_stats_flow, show_stats_reply_menu, show_channel_reply_menu,
)


async def on_m_action(ctx, q, action, parts):
    """Eski (inline) "m:" callback'lari — faqat eski xabarlar uchun qoldirilgan.
    Yangi tugmalar ReplyKeyboard orqali handle_catalog_action() ga keladi."""
    user = q.from_user
    chat_id = q.message.chat_id

    is_owner = bool(OWNER_ID and user.id == OWNER_ID)
    home = parts[0] if (parts and parts[0] in ("mainhome", "adminhome")) else ("adminhome" if is_owner else "mainhome")

    if action == "lang":
        choices = {label: code for code, label in LANGS.items()}
        await show_reply_menu(ctx, chat_id, "Tilni tanlang / Выберите язык / Choose language",
                              [[label] for label in choices],
                              {"screen": "lang", "choices": choices})
        return

    if action == "back":
        await show_home_for(ctx, chat_id, user, home)
        return

    if action == "info":
        await show_reply_menu(ctx, chat_id, full_info_text(), [BTN_BACK],
                              {"screen": "info", "home": home}, parse_mode="Markdown")
        return

    if action == "register":
        pending_register[user.id] = {"stage": "await_forward", "home": home}
        await show_reply_menu(
            ctx, chat_id,
            "Botni o'z kanalingizga ADMIN qilib qo'shing, so'ng kanaldan istalgan "
            "postni menga forward qiling.",
            [BTN_BACK], {"screen": "register", "home": home},
        )
        return

    if action == "mysubs":
        await show_my_channels(ctx, chat_id, user, home)
        return

    if action == "chandetail":
        ch = get_channel(int(parts[0]))
        if ch:
            await show_channel_reply_menu(ctx, chat_id, user, ch, parts[1])
        return

    if action in ("chanweek", "chanmonth"):
        ch = get_channel(int(parts[0]))
        if ch:
            if action == "chanweek":
                body = build_week_report(ch["channel_id"], ch["title"])
            else:
                body = build_monthly_report(ch["channel_id"], ch["title"], [])
            await show_channel_reply_menu(ctx, chat_id, user, ch, parts[1], text=body)
        return

    if action == "chanpair":
        await show_reply_menu(ctx, chat_id, "Qaysi juftlik?", [PAIRS, [BTN_BACK]],
                              {"screen": "pair", "channel_id": int(parts[0]),
                               "home": parts[1], "origin": "channel"})
        return

    if action == "chanpairval":
        channel_id, phome, pair = int(parts[0]), parts[1], parts[2]
        ch = get_channel(channel_id)
        if ch:
            await show_channel_reply_menu(ctx, chat_id, user, ch, phome,
                                          text=build_pair_stats(channel_id, ch["title"], pair))
        return

    if action == "chantoggle":
        channel_id, phome = int(parts[0]), parts[1]
        if is_subscribed(user.id, channel_id):
            unsubscribe(user.id, channel_id)
        else:
            subscribe(user.id, channel_id)
        ch = get_channel(channel_id)
        if ch:
            await show_channel_reply_menu(ctx, chat_id, user, ch, phome)
        return

    if action == "settings":
        await show_help_reply_menu(ctx, chat_id, home)
        return

    if action == "helptopic":
        key = parts[0] if parts else ""
        phome = parts[1] if len(parts) > 1 else home
        await show_help_reply_menu(ctx, chat_id, phome, key)
        return

    if action == "contact":
        await start_contact_flow(ctx, chat_id, user)
        return

    if action == "leads":
        if not is_owner:
            return
        leads = list_dm_users(limit=15)
        if leads:
            body = "\n".join(["👥 So'nggi kontaktlar:", ""] +
                             [f"{r['name'] or '—'} | {r['contact'] or '—'}" for r in leads])
        else:
            body = "👥 So'nggi kontaktlar:\n\nHali hech kim yo'q."
        await send_reply_text(ctx, chat_id, body)
        return


async def handle_catalog_action(ctx, msg):
    """Shaxsiy chatdagi barcha ReplyKeyboard navigatsiyasi."""
    user = msg.from_user
    text = msg.text.strip()
    is_owner = bool(OWNER_ID and user.id == OWNER_ID)
    home = "adminhome" if is_owner else "mainhome"

    if text in CATALOG_BUTTONS:
        # Katalog tugmasi bosildi — tugallanmagan onboarding/registratsiya
        # bosqichlari bekor qilinadi, foydalanuvchi adashib qolmaydi.
        onboarding.pop(user.id, None)
        pending_register.pop(user.id, None)
        pending_contact.pop(user.id, None)

    if text == BTN_HOME:
        await show_home_for(ctx, msg.chat_id, user, home)
        return True
    if text == BTN_STATS:
        await show_stats_flow(ctx, msg.chat_id, user, home)
        return True
    if text == BTN_ALL_CHANNELS and is_owner:
        await cmd_all_channels_stats(ctx, msg)
        return True
    if text == BTN_RATING and is_owner:
        await cmd_admin_rating(ctx, msg)
        return True
    if text == BTN_MY_CHANNELS and not is_owner:

        await show_my_channels(ctx, msg.chat_id, user, home)
        return True
    if text in (BTN_REGISTER, BTN_OWNER_REGISTER):
        pending_register[user.id] = {"stage": "await_forward", "home": home}
        await show_reply_menu(
            ctx, msg.chat_id,
            "Botni o'z kanalingizga ADMIN qilib qo'shing, so'ng kanaldan istalgan postni menga forward qiling.",
            [BTN_BACK], {"screen": "register", "home": home},
        )
        return True
    if text == BTN_SETTINGS:
        await show_help_reply_menu(ctx, msg.chat_id, home)
        return True
    if text == BTN_CONTACT and not is_owner:
        await start_contact_flow(ctx, msg.chat_id, user)
        return True
    if text == BTN_LEADS and is_owner:
        leads = list_dm_users(limit=15)
        if leads:
            body = "\n".join(["👥 So'nggi kontaktlar:", ""] +
                             [f"{r['name'] or '—'} | {r['contact'] or '—'}" for r in leads])
        else:
            body = "👥 So'nggi kontaktlar:\n\nHali hech kim yo'q."
        await send_reply_text(ctx, msg.chat_id, body)
        return True
    if text == BTN_AI:
        return False

    state = reply_menu_states.get(msg.chat_id, {})
    screen = state.get("screen")
    choices = state.get("choices", {})
    shome = state.get("home", home)

    if screen == "ai":
        if text == BTN_AI_ASK:
            await show_reply_menu(
                ctx, msg.chat_id, AI_ASK_PROMPT, [BTN_BACK],
                {"screen": "ai_question", "home": shome},
            )
            return True
        if text == BTN_AI_ANALYZE_SIGNALS:
            await ai_analyze_signals(ctx, msg.chat_id, user, is_owner)
            return True
    if screen == "ai_question":
        await _ai_send_answer(ctx, msg.chat_id, ask_ai_analyst(text))
        await show_ai_reply_menu(ctx, msg.chat_id, shome)
        return True

    if screen == "lang" and text in choices:
        lang = choices[text]
        save_dm_user(user.id, lang=lang)
        onboarding[user.id] = {"stage": "await_name"}
        reply_menu_states[msg.chat_id] = {"screen": "await_name", "rows": []}
        await ctx.bot.send_message(msg.chat_id, "Ismingizni kiriting:",
                                   reply_markup=ReplyKeyboardRemove())
        return True
    if text == BTN_BACK:
        # Ortga — asosiy menyuga qaytish; tugallanmagan oqimlar bekor bo'ladi.
        pending_register.pop(user.id, None)
        pending_contact.pop(user.id, None)
        onboarding.pop(user.id, None)
        if screen == "admin_chan_detail" and is_owner:
            await cmd_all_channels_stats(ctx, msg)
            return True
        if screen == "pair":
            channel = get_channel(state.get("channel_id"))
            if channel:
                if state.get("origin") == "channel":
                    await show_channel_reply_menu(ctx, msg.chat_id, user, channel, shome)
                else:
                    await show_stats_reply_menu(ctx, msg.chat_id, channel, shome)
            return True
        if screen in ("ai", "ai_question"):
            await show_home_for(ctx, msg.chat_id, user, shome)
            return True
        await show_home_for(ctx, msg.chat_id, user, home)
        return True
    if screen in ("stats_channel", "channel_pick") and text in choices:
        ch = get_channel(choices[text])
        if ch:
            if screen == "stats_channel":
                await show_stats_reply_menu(ctx, msg.chat_id, ch, shome)
            else:
                await show_channel_reply_menu(ctx, msg.chat_id, user, ch, shome)
        return True
    if screen == "stats_channel_pair" and text in choices:
        ch = get_channel(choices[text])
        if ch:
            await show_stats_reply_menu(
                ctx, msg.chat_id, ch, shome,
                text=build_pair_stats(ch["channel_id"], ch["title"], state.get("pair")),
            )
        return True
    if screen == "report_channel" and text in choices:
        ch = get_channel(choices[text])
        if ch:
            args = state.get("args") or []
            if state.get("kind") == "week":
                body = build_week_report(ch["channel_id"], ch["title"])
            else:
                body = build_monthly_report(ch["channel_id"], ch["title"], args)
            await send_reply_text(ctx, msg.chat_id, body)
        return True
    if screen == "tag_channel" and text in choices:
        channel_id = choices[text]
        new_tag = state.get("new_tag")
        if new_tag:
            if is_protected_tag_blocked(new_tag, user.id):
                return True
            set_channel_tag(channel_id, new_tag)
            await send_reply_text(ctx, msg.chat_id, f'Yangilandi: endi "{new_tag}" deb yoziladi.')
        else:
            ch = get_channel(channel_id)
            current = (ch["tag"] or DEFAULT_TAG) if ch else DEFAULT_TAG
            await send_reply_text(ctx, msg.chat_id, f'Joriy so\'z: "{current}"')
        return True
    if screen == "contact_channel" and text in choices:
        ch = get_channel(choices[text])
        pending_contact[user.id] = {
            "stage": "await_message",
            "channel_id": ch["channel_id"] if ch else None,
            "channel_title": ch["title"] if ch else None,
        }
        await show_reply_menu(
            ctx, msg.chat_id, "Xabaringizni yozing, men uni adminga yetkazaman.", [BTN_BACK],
            {"screen": "contact_message", "home": shome},
        )
        return True
    if screen == "stats":
        channel = get_channel(state.get("channel_id"))
        if not channel:
            return True
        if text == BTN_WEEK:
            await send_reply_text(ctx, msg.chat_id,
                                  build_week_report(channel["channel_id"], channel["title"]))
            return True
        if text == BTN_MONTH:
            await send_reply_text(ctx, msg.chat_id,
                                  build_monthly_report(channel["channel_id"], channel["title"], []))
            return True
        if text == BTN_PAIR:
            await show_reply_menu(ctx, msg.chat_id, "Qaysi juftlik?", [PAIRS, [BTN_BACK]],
                                  {"screen": "pair", "channel_id": channel["channel_id"], "home": shome, "origin": "stats"})
            return True
    if screen == "pair" and text in PAIRS:
        channel = get_channel(state.get("channel_id"))
        if channel:
            await send_reply_text(ctx, msg.chat_id,
                                  build_pair_stats(channel["channel_id"], channel["title"], text))
        return True
    if screen == "channel":
        channel = get_channel(state.get("channel_id"))
        if not channel:
            return True
        if text == BTN_WEEK:
            await send_reply_text(ctx, msg.chat_id,
                                  build_week_report(channel["channel_id"], channel["title"]))
            return True
        if text == BTN_MONTH:
            await send_reply_text(ctx, msg.chat_id,
                                  build_monthly_report(channel["channel_id"], channel["title"], []))
            return True
        if text == BTN_PAIR:
            await show_reply_menu(ctx, msg.chat_id, "Qaysi juftlik?", [PAIRS, [BTN_BACK]],
                                  {"screen": "pair", "channel_id": channel["channel_id"], "home": shome, "origin": "channel"})
            return True
        if text.startswith("🔔") or text.startswith("🔕"):
            if is_subscribed(user.id, channel["channel_id"]):
                unsubscribe(user.id, channel["channel_id"])
            else:
                subscribe(user.id, channel["channel_id"])
            await show_channel_reply_menu(ctx, msg.chat_id, user, channel, shome)
            return True
        if text == BTN_UNREGISTER:
            if channel["owner_id"] == user.id:
                await show_reply_menu(
                    ctx, msg.chat_id,
                    f'«{channel["title"]}» ro\'yxatdan chiqarilsinmi?\n\n'
                    "Bot bu kanalga endi xizmat qilmaydi, push va hisobotlar "
                    "to'xtaydi (kanaldagi signallar tarixi bazada qoladi).",
                    [[BTN_YES_DELETE], [BTN_BACK]],
                    {"screen": "unregister", "channel_id": channel["channel_id"], "home": shome},
                )
            return True
    if screen == "unregister" and text == BTN_YES_DELETE:
        ch = get_channel(state.get("channel_id"))
        if ch and ch["owner_id"] == user.id:
            remove_channel(ch["channel_id"])
            channel_health.pop(ch["channel_id"], None)
            await show_reply_menu(
                ctx, msg.chat_id,
                f'🗑 «{ch["title"]}» ro\'yxatdan chiqarildi. Qayta ulash uchun '
                f'«🔗 Kanalimni ulash» tugmasini bosing.',
                catalog_rows(msg.chat_id), {"screen": "home", "home": home},
            )
        else:
            await show_home_for(ctx, msg.chat_id, user, home)
        return True
    if screen == "help" and text in choices:
        await show_help_reply_menu(ctx, msg.chat_id, shome, choices[text])
        return True

    # Admin barcha kanallar statistikasi va boshqaruvi
    if is_owner:
        if screen == "admin_all_stats" and text in choices:
            await handle_admin_stats_pick(ctx, msg, choices[text])
            return True

        # Stateless fallback: Agar xotirada screen yo'qolgan bo'lsa ham
        # kanal nomi orqali darhol mos kanal ochiladi
        all_channels = get_all_channels()
        for i, ch in enumerate(all_channels, start=1):
            title = ch["title"] or str(ch["channel_id"])
            cid_str = str(ch["channel_id"])
            possible_labels = {title, f"{i}. {title}", f"{i}. {title} [{cid_str}]"}
            if text in possible_labels or (cid_str in text and text.endswith("]")):
                await handle_admin_stats_pick(ctx, msg, ch["channel_id"])
                return True

    if (screen == "admin_chan_detail" or is_owner) and (text.startswith("🔔") or text.startswith("🔕")):
        chan_id = state.get("channel_id")
        if chan_id:
            await toggle_admin_push_handler(ctx, msg, chan_id)
            return True

    if screen == "admin_rating" and ("Winrate" in text or "Sof foyda" in text):
        sort_by = "winrate" if "Winrate" in text else "pips"
        await cmd_admin_rating(ctx, msg, sort_by=sort_by)
        return True
    return False


async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        await _on_message(update, ctx)
    except Exception as e:
        log.exception("Xabar qayta ishlanmadi")
        await n8n_send("bot_error", {"where": "message", "error": type(e).__name__,
                                     "message": str(e)[:300]})


async def _on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return

    # --- onboarding: kontakt (telefon) qabul qilish ---
    if await handle_onboarding_message(ctx, update):
        return

    raw_text = msg.text or msg.caption or ""
    is_forward = bool(msg.forward_origin or getattr(msg, "forward_from_chat", None))
    if not raw_text and not is_forward:
        return

    is_private = msg.chat.type == "private"
    channel = None if is_private else get_channel(msg.chat_id)
    is_registered_channel = channel is not None
    text = raw_text.strip()
    low = text.lower()

    if not is_private and not is_registered_channel:
        if low.startswith("/"):
            await notify(
                ctx, msg.chat_id,
                "Bu kanal hali botga ulanmagan. Botga shaxsiy yozib /register bering.",
            )
            try:
                await ctx.bot.delete_message(msg.chat_id, msg.message_id)
            except Exception:
                pass
        return

    if is_private and not low.startswith("/"):
        if await handle_catalog_action(ctx, msg):
            return

        if await handle_admin_reply(ctx, msg):
            return
        if msg.forward_origin or getattr(msg, "forward_from_chat", None):
            if await handle_forward_for_register(ctx, msg):
                return
        if await handle_tag_for_register(ctx, msg):
            return
        if await handle_contact_message(ctx, msg):
            return
        # Holat xotiradan yo'qolgan bo'lsa (bot qayta ishga tushgan) — pastdagi
        # katalog tugmalari ishlashda davom etishi uchun menyuni tiklaymiz.
        if reply_menu_states.get(msg.chat_id) is None:
            if get_dm_user(msg.from_user.id) is None and not (
                OWNER_ID and msg.from_user.id == OWNER_ID
            ):
                await send_start(ctx, msg.chat_id, msg.from_user)
            else:
                home = "adminhome" if (OWNER_ID and msg.from_user.id == OWNER_ID) else "mainhome"
                await show_home_for(ctx, msg.chat_id, msg.from_user, home)

    if low.startswith("/"):
        parts = text.split()
        cmd = parts[0].split("@")[0].lower()
        args = parts[1:]

        if cmd == "/start" and is_private:
            await send_start(ctx, msg.chat_id, msg.from_user)
        elif cmd == "/register" and is_private:
            await cmd_register(ctx, msg)
        elif cmd == "/help":
            if is_registered_channel:
                await send_report(ctx, msg.chat_id, channel_help_text(), True)
            else:
                home = "adminhome" if (OWNER_ID and msg.from_user.id == OWNER_ID) else "mainhome"
                await show_help_reply_menu(ctx, msg.chat_id, home)
        elif cmd == "/version":
            await notify(ctx, msg.chat_id, f"{BOT_NAME} v{VERSION}")
        elif cmd == "/ai":
            if is_private:
                ai_home = "adminhome" if (OWNER_ID and msg.from_user.id == OWNER_ID) else "mainhome"
                question = " ".join(args).strip()
                if question:
                    await _ai_send_answer(ctx, msg.chat_id, ask_ai_analyst(question))
                await show_ai_reply_menu(ctx, msg.chat_id, ai_home)
            else:
                await notify(ctx, msg.chat_id, "🧠 AI Tahlilchi shaxsiy chatda ishlaydi.")
        elif cmd == "/stats":
            await cmd_stats(ctx, msg, is_registered_channel, channel, args)
        elif cmd == "/week":
            if is_registered_channel:
                await send_report(ctx, msg.chat_id, build_week_report(channel["channel_id"], channel["title"]), True)
            elif is_private:
                await cmd_report_in_dm(ctx, msg, "week", args)
        elif cmd == "/monthly":
            if is_registered_channel:
                await send_report(ctx, msg.chat_id, build_monthly_report(channel["channel_id"], channel["title"], args), True)
            elif is_private:
                await cmd_report_in_dm(ctx, msg, "monthly", args)
        elif cmd == "/tag":
            if is_registered_channel:
                await cmd_tag_in_channel(ctx, msg, channel, args)
            elif is_private:
                await cmd_tag_in_dm(ctx, msg, args)
        elif cmd == "/del" and is_registered_channel:
            await cmd_del(ctx, msg)

        if is_registered_channel:
            schedule_delete(ctx, msg.chat_id, msg.message_id)
    elif is_registered_channel and low.startswith("#signal"):
        await handle_signal_text(ctx, msg, channel)
    elif is_registered_channel and is_post_message(text):
        await handle_channel_post(ctx, msg, channel)
    elif is_registered_channel and msg.reply_to_message:
        await handle_result_reply(msg)


async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        await _on_callback(update, ctx)
    except Exception as e:
        log.exception("Tugma qayta ishlanmadi")
        await n8n_send("bot_error", {"where": "callback", "error": type(e).__name__,
                                     "message": str(e)[:300]})


async def _on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not (q.data or "").startswith("cst:"):
        await q.answer()  # "cst:" tugmalarini handlerning o'zi javoblaydi (admin bo'lmasa ogohlantirish)
    user = q.from_user
    data = q.data
    if not data:
        return

    if data.startswith("m:"):
        parts = data.split(":")[1:]
        action, rest = parts[0], parts[1:]
        await on_m_action(ctx, q, action, rest)
        return

    if data.startswith("cst:"):
        await on_channel_stats_callback(ctx, q, data.split(":", 1)[1])
        return

    if data.startswith("pairsel:"):
        pair = data.split(":")[1]
        channel = get_channel(q.message.chat_id)
        if not channel:
            return
        try:
            member = await ctx.bot.get_chat_member(q.message.chat_id, user.id)
            if member.status not in ("administrator", "creator"):
                await q.answer("Faqat kanal admini tanlay oladi.", show_alert=True)
                return
        except Exception:
            return
        try:
            await q.message.edit_text(f"{q.message.text_html}\n{pair}", parse_mode="HTML", reply_markup=None)
        except Exception as e:
            log.warning("Juftlikni yozib bo'lmadi: %s", e)
        return

    # ---- eski (v0.05/0.06) callback prefikslari ----
    if data == "contact":
        await start_contact_flow(ctx, q.message.chat_id, user)
        return

    if data.startswith("ctch:"):
        channel_id = int(data.split(":")[1])
        ch = get_channel(channel_id)
        pending_contact[user.id] = {
            "stage": "await_message", "channel_id": channel_id,
            "channel_title": ch["title"] if ch else None,
        }
        home = "adminhome" if (OWNER_ID and user.id == OWNER_ID) else "mainhome"
        await show_reply_menu(ctx, q.message.chat_id,
                              "Xabaringizni yozing, men uni adminga yetkazaman.", [BTN_BACK],
                              {"screen": "contact_message", "home": home})
        return

    if data.startswith("rpch:"):
        channel_id = int(data.split(":")[1])
        state = pending_contact.pop(user.id, None)
        kind = "week"
        args = []
        if state and state.get("stage", "").startswith("report_pick_channel"):
            kind = state["stage"].split(":")[1]
            args = state.get("args", [])
        ch = get_channel(channel_id)
        if ch:
            home = "adminhome" if (OWNER_ID and user.id == OWNER_ID) else "mainhome"
            if kind == "week":
                body = build_week_report(ch["channel_id"], ch["title"])
            else:
                body = build_monthly_report(ch["channel_id"], ch["title"], args)
            await show_channel_reply_menu(ctx, q.message.chat_id, user, ch, home, text=body)
        return

    if data.startswith("tagch:"):
        channel_id = int(data.split(":")[1])
        state = pending_contact.pop(user.id, None)
        ch = get_channel(channel_id)
        if not ch:
            return
        new_tag = state.get("new_tag") if state else None
        if new_tag:
            if is_protected_tag_blocked(new_tag, user.id):
                return
            set_channel_tag(channel_id, new_tag)
            await send_reply_text(ctx, q.message.chat_id, f'Yangilandi: endi "{new_tag}" deb yoziladi.')
        else:
            await send_reply_text(ctx, q.message.chat_id,
                                  f'Joriy so\'z: "{ch["tag"] or DEFAULT_TAG}"')
        return
