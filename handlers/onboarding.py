"""
Trading Journal - Onboarding Handlers
"""
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import ContextTypes
from config import LANGS, BTN_SEND_CONTACT, OWNER_ID
from database import save_dm_user, get_dm_user
from handlers.state import onboarding
from utils.n8n import n8n_send

from bot_ui import show_reply_menu, show_main_home, show_admin_home

async def send_start(ctx: ContextTypes.DEFAULT_TYPE, chat_id: int, user):
    if OWNER_ID and user.id == OWNER_ID:
        await show_admin_home(ctx, chat_id, user)
        return

    existing = get_dm_user(user.id)
    if existing and existing["contact"]:
        await show_main_home(ctx, chat_id, user)
        return

    onboarding[user.id] = {"stage": "lang"}
    choices = {label: code for code, label in LANGS.items()}
    await show_reply_menu(
        ctx, chat_id, "Tilni tanlang / Выберите язык / Choose language",
        [[label] for label in choices],
        {"screen": "lang", "choices": choices},
    )

async def handle_onboarding_message(ctx: ContextTypes.DEFAULT_TYPE, update: Update):
    msg = update.effective_message
    user = msg.from_user
    if not user:
        return False
    text = msg.text.strip() if msg.text else ""

    # 1. Contact sharing stage
    if msg.contact and user and onboarding.get(user.id, {}).get("stage") == "await_contact":
        phone = msg.contact.phone_number
        name = onboarding[user.id].get("name")
        save_dm_user(user.id, name=name, contact=phone)
        onboarding.pop(user.id, None)

        saved = get_dm_user(user.id)
        if not (OWNER_ID and user.id == OWNER_ID):
            await n8n_send("new_lead", {
                "user_id": user.id,
                "username": user.username,
                "name": name,
                "phone": phone,
                "lang": saved["lang"] if saved else None,
            })

        if OWNER_ID:
            who = f"@{user.username}" if user.username else user.full_name
            try:
                await ctx.bot.send_message(
                    OWNER_ID,
                    f"👤 Yangi kontakt\nIsm: {name}\nTelegram: {who} (id {user.id})\nTelefon: {phone}",
                )
            except Exception:
                pass

        await ctx.bot.send_message(msg.chat_id, "Rahmat!", reply_markup=ReplyKeyboardRemove())
        await show_main_home(ctx, msg.chat_id, user)
        return True

    # 2. Name input stage
    if onboarding.get(user.id, {}).get("stage") == "await_name":
        onboarding[user.id] = {"stage": "await_contact", "name": text}
        kb = ReplyKeyboardMarkup(
            [[KeyboardButton(BTN_SEND_CONTACT, request_contact=True)]],
            resize_keyboard=True, one_time_keyboard=True,
        )
        await ctx.bot.send_message(
            msg.chat_id,
            "Rahmat! Endi pastdagi tugma orqali kontaktingizni yuboring.",
            reply_markup=kb,
        )
        return True

    return False
