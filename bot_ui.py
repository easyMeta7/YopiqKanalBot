"""
Trading Journal - UI helpers (ReplyKeyboard menyulari, yordam matnlari, AI bo'limi)

Handlerlarga BOG'LIQ BO'LMAGAN menyu/ekran funksiyalari. bot_core ga tayanadi.
"""
from telegram import ReplyKeyboardMarkup

from config import (
    BOT_NAME, VERSION, OWNER_ID,
    BTN_HOME, BTN_STATS, BTN_MY_CHANNELS, BTN_REGISTER, BTN_OWNER_REGISTER,
    BTN_SETTINGS, BTN_CONTACT, BTN_LEADS, BTN_BACK, BTN_WEEK, BTN_MONTH,
    BTN_PAIR, BTN_UNREGISTER, BTN_YES_DELETE, BTN_ALL_CHANNELS, BTN_RATING,
    BTN_AI, BTN_AI_ASK, BTN_AI_ANALYZE_SIGNALS,
)
from database import get_recent_signals, is_subscribed
from handlers.state import reply_menu_states
from utils.ai import ai_status, analyze_recent_signals
from bot_core import find_subscriber_channels


# ------------------------------ matnlar ------------------------------
HELP_TOPICS = {
    "signal": (
        "📥 Signal yuborish\n\n"
        "Kanalga yakka \"#Signal\" deb yuboring. Bot XAU/BTC/NAS100 tugmalarini "
        "chiqaradi — birini tanlang. Shu postning o'zini tahrirlab davom ettiring:\n\n"
        "Buy (yoki Sell)\n4332-4328\nStop 4325\nTP1 4340\nTP2 4350\nTP3 4370\n\n"
        "Qoidalar:\n"
        "• Yo'nalish: Buy yoki Sell\n"
        "• Narx oralig'i (yuqori-past). Buy da yuqori raqam entry, Sell da past "
        "raqam entry bo'ladi\n"
        "• Stop — zararni to'xtatish narxi\n"
        "• TP1 majburiy, TP2 va TP3 ixtiyoriy\n"
        "• Stop/TP entry ga nisbatan noto'g'ri tomonda bo'lsa, bot ogohlantiradi "
        "va signalni saqlamaydi\n"
        "• Qabul qilingan signal postning oxiriga tag qo'shiladi va shu kanalga "
        "obuna bo'lganlarga shaxsiy yuboriladi"
    ),
    "result": (
        "✅ Natija belgilash (TP/Stop)\n\n"
        "Signal postiga reply qilib: TP1, TP2, TP3 yoki Stop deb yozing.\n\n"
        "• Bot reply xabaringizning o'ziga natijani qo'shib qo'yadi\n"
        "• Yakuniy natija — faqat eng yuqori TP (qo'shilmaydi)\n"
        "• TP1 dan keyin narx Stopga qaytsa ham, natija TP1 bo'lib qoladi\n"
        "• Signal Stop bilan yopilgandan keyin unga TP yozib bo'lmaydi"
    ),
    "reports": (
        "📊 Hisobotlar\n\n"
        "/week — joriy hafta (dushanbadan yakshanbagacha)\n"
        "/monthly — joriy oy (1-sanadan oxirgi sanagacha), har hafta alohida qator bilan\n"
        "/monthly avgust — avgust oyi\n"
        "/stats — Haftalik / Oylik / Juftlik bo'yicha submenyu\n"
        "/stats XAU — shu juftlikning oxirgi 30-31 kunlik statistikasi "
        "(TP1/TP2/TP3/Stop soni, winrate, sof pips)\n\n"
        "Kunlik natija har kuni 02:10 da (GMT+5) kanalga o'zi yuboriladi. "
        "Savdo kuni — 02:00 dan keyingi kun 02:00 gacha; haftalik va oylik hisobotlar ham shu chegarada.\n\n"
        "Kanalda hisobot bir necha soniyadan keyin o'zi o'chib, kanalni toza "
        "tutadi. Shaxsiy chatda doim saqlanadi."
    ),
    "tag": (
        "🏷 Tag sozlash\n\n"
        "Signal qabul qilinganda, bot postning oxiriga qisqa so'z (\"tag\") "
        "qo'shadi — bu sizning shaxsiy uslubingiz.\n\n"
        "/tag — joriy tag so'zini ko'rsatadi\n"
        "/tag Locked in — tagni \"Locked in\" ga o'zgartiradi\n\n"
        "Kanalda yozsangiz — o'sha kanalning tagi o'zgaradi. Shaxsiy chatda "
        "yozsangiz — bir nechta kanalingiz bo'lsa, bot qaysi kanal ekanini "
        "so'raydi."
    ),
    "del": (
        "🗑 Signal va postlarni o'chirish\n\n"
        "Signal yoki postga reply qilib /del deb yozing.\n\n"
        "• Bot postni kanaldan butunlay o'chiradi\n"
        "• Obunachilarga borgan push nusxalarini ham o'chiradi\n"
        "• Signal bo'lsa bazadan o'chiradi — hisobotlarda ko'rinmaydi\n"
        "• Faqat reply orqali ishlaydi\n"
        "• Har doim /del ishlating"
    ),
    "posts": (
        "📝 Post / Fikr / Tahlil ulashish\n\n"
        "Kanalda signal emas, oddiy xabar, bozor tahlili yoki grafik rasmlarini ham "
        "obunachilarga yuborishingiz mumkin.\n\n"
        "Buning uchun post yoki rasm izohi (caption) quyidagi heshteglar bilan boshlanishi kerak:\n"
        "• #post\n"
        "• #idea\n"
        "• #fikr\n"
        "• #yangilik (yoki #news)\n\n"
        "Bot post oxiriga kanal imzosini (tag) qo'shadi va uni barcha obunachilarga push qiladi. "
        "Bu postlar savdo statistikangizga ta'sir qilmaydi.\n"
        "Postni o'chirish uchun unga reply qilib /del yozing."
    ),
    "register": (
        "🔗 Kanalni ulash\n\n"
        "1. Botni kanalingizga ADMIN qilib qo'shing\n"
        "2. Botga shaxsiy yozib /register bering (yoki menyudan \"Kanalimni "
        "ulash\" ni bosing)\n"
        "3. Kanalingizdan istalgan postni botga forward qiling\n"
        "4. Bot sizni o'sha kanalda admin ekaningizni tekshiradi\n"
        "5. \"Qabul qilindi\" so'zingizni kiriting (standart uchun /skip)\n\n"
        "Shundan keyin o'sha kanalda hammasi ishlaydi."
    ),
    "contact": (
        "📩 Admin bilan bog'lanish\n\n"
        "Taklif, savol yoki muammo bo'lsa, shu bo'lim orqali murojaat "
        "qoldirishingiz mumkin.\n\n"
        "• Bir nechta kanalingiz bo'lsa, bot qaysi kanal haqida ekanini so'raydi\n"
        "• Keyingi yozgan xabaringiz to'g'ridan-to'g'ri adminga yetadi\n"
        "• Admin sizga botdan javob qaytarishi mumkin"
    ),
    "ai": (
        "🤖 AI Tahlilchi\n\n"
        "Bo'lim o'zingizda ishlaydigan FreeLLMAPI routeri (bepul LLM proksisi) "
        "orqali ishlaydi.\n\n"
        "• 💬 Savol berish — bozor, juftlik yoki risk-menejment bo'yicha savolingizni "
        "yozing; AI o'zbek tilida javob beradi\n"
        "• 📊 Signallar tahlili — kanalingizdagi oxirgi 10 signal bo'yicha xulosa "
        "(qaysi juftlikda natija yaxshi, keyingi qadam uchun tavsiya)\n"
        "• /ai <savol> — bir martalik savol (faqat shaxsiy chatda)\n\n"
        "AI javoblari investitsiya maslahati emas — qarorlar uchun javobgarlik "
        "sizda."
    ),
}


HELP_TOPIC_LIST = [
    ("📥 Signal yuborish", "signal"),
    ("📝 Post / Fikr ulashish", "posts"),
    ("✅ Natija belgilash", "result"),
    ("📊 Hisobotlar", "reports"),
    ("🤖 AI Tahlilchi", "ai"),
    ("🏷 Tag sozlash", "tag"),
    ("🗑 Signalni o'chirish", "del"),
    ("🔗 Kanalni ulash", "register"),
    ("📩 Murojaat haqida", "contact"),
]


def channel_help_text():
    return (
        f"{BOT_NAME} — buyruqlar (kanal)\n\n"
        "#Signal ... — yangi signal (juftlik tugmalari orqali)\n"
        "#Post / #Idea / #Fikr ... — yangilik, fikr yoki grafik rasmi (obunachilarga push)\n"
        "TP1 / TP2 / TP3 / Stop — signal postiga reply\n"
        "/del — post/signalga reply qilib uni o'chirish\n"
        "/week, /monthly, /stats — hisobotlar\n"
        "/tag <matn> — qabul qilindi so'zini o'zgartirish\n"
        "/version — bot versiyasi"
    )


def full_info_text():
    return (
        f"*{BOT_NAME}*\nv{VERSION}\n\n"
        "Bu bot kanaldagi trading signallarini kuzatadi: TP/Stop natijalarini "
        "belgilaydi, haftalik/oylik/juftlik bo'yicha statistika beradi va "
        "yangi signallarni obuna bo'lganlarga avtomatik yuboradi."
    )


AI_ASK_PROMPT = (
    "💬 Savolingizni yozing — AI tahlilchi javob beradi.\n\n"
    "Masalan: «XAU uchun bugungi asosiy darajalar qanday?», "
    "«NAS100 savdosida risk qanday bo'lishi kerak?»"
)


# ------------------------------ tugmalar ------------------------------
def catalog_rows(chat_id):
    """Asosiy menyu qatorlari (bo'limlar). Bo'lim ichida bu takrorlanmaydi."""
    if OWNER_ID and chat_id == OWNER_ID:
        return [
            [BTN_STATS, BTN_OWNER_REGISTER],
            [BTN_LEADS, BTN_SETTINGS],
            [BTN_ALL_CHANNELS, BTN_RATING],
        ]
    return [
        [BTN_MY_CHANNELS, BTN_STATS],
        [BTN_REGISTER, BTN_SETTINGS],
        [BTN_CONTACT],
    ]


CATALOG_BUTTONS = {
    BTN_HOME, BTN_STATS, BTN_MY_CHANNELS, BTN_REGISTER,
    BTN_OWNER_REGISTER, BTN_SETTINGS, BTN_CONTACT, BTN_LEADS,
    BTN_ALL_CHANNELS, BTN_RATING, BTN_AI,
}


def norm_rows(rows):
    """Qatorlarni bir xil ko'rinishga keltiradi (matn ham, ro'yxat ham bo'ladi)."""
    result = []
    for row in (rows or []):
        result.append([row] if isinstance(row, str) else list(row))
    return result


def reply_keyboard(rows, chat_id):
    """Bo'lim tugmalari; bo'sh bo'lsa — asosiy menyu katalogi."""
    result = norm_rows(rows) or catalog_rows(chat_id)
    return ReplyKeyboardMarkup(result, resize_keyboard=True, one_time_keyboard=False)


def channel_choices(channels):
    """ReplyKeyboard uchun kanal tanlash tugmalari (nomlar takrorlanmaydi,
    boshqa tugmalar bilan to'qnashmaydi)."""
    reserved = CATALOG_BUTTONS | {
        BTN_WEEK, BTN_MONTH, BTN_PAIR, BTN_BACK, BTN_UNREGISTER, BTN_YES_DELETE,
    }
    labels, choices, used = [], {}, set()
    for i, ch in enumerate(channels, start=1):
        title = ch["title"] or str(ch["channel_id"])
        label = title
        if label in used or label in reserved:
            label = f"{i}. {title}"
        while label in used:
            label = f"{i}. {title} [{ch['channel_id']}]"
        used.add(label)
        labels.append(label)
        choices[label] = ch["channel_id"]
    return labels, choices


# ------------------------------ menyular ------------------------------
async def show_reply_menu(ctx, chat_id, text, rows, state, parse_mode=None):
    """ReplyKeyboard menyusini chiqaradi; mazmunli eski xabarlar o'chirilmaydi."""
    rows = norm_rows(rows)
    new_state = dict(state or {})
    new_state["rows"] = rows
    reply_menu_states[chat_id] = new_state
    await ctx.bot.send_message(chat_id, text, reply_markup=reply_keyboard(rows, chat_id),
                               parse_mode=parse_mode)


async def send_reply_text(ctx, chat_id, text, rows=None, state=None, parse_mode=None):
    """Hisobot/matn chatning o'zida saqlanadi; pastdagi tugmalar joyida qoladi."""
    cur = dict(reply_menu_states.get(chat_id) or {})
    if state is not None:
        cur.update(state)
    if rows is not None:
        cur["rows"] = norm_rows(rows)
    if cur:
        reply_menu_states[chat_id] = cur
    return await ctx.bot.send_message(
        chat_id, text, reply_markup=reply_keyboard(cur.get("rows", []), chat_id),
        parse_mode=parse_mode,
    )


async def show_home_for(ctx, chat_id, user, home):
    if home == "adminhome":
        await show_admin_home(ctx, chat_id, user)
    else:
        await show_main_home(ctx, chat_id, user)


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


async def show_help_reply_menu(ctx, chat_id, home, key=None):
    choices = {title: k for title, k in HELP_TOPIC_LIST}
    topics = list(choices)
    rows = [topics[i:i + 2] for i in range(0, len(topics), 2)]
    rows.append([BTN_BACK])
    text = HELP_TOPICS.get(key) if key else None
    await show_reply_menu(
        ctx, chat_id, text or "⚙️ Sozlamalar / Yordam — mavzuni tanlang",
        rows, {"screen": "help", "choices": choices, "home": home},
    )


async def show_ai_reply_menu(ctx, chat_id, home, text=None):
    """AI bo'limi: router holati + ikkita amal."""
    body = text or (
        f"🤖 AI Tahlilchi\n\n{await ai_status()}\n\n"
        "• 💬 Savol berish — savolingizga AI javob beradi\n"
        "• 📊 Signallar tahlili — oxirgi signallar bo'yicha xulosa"
    )
    await show_reply_menu(
        ctx, chat_id, body, [[BTN_AI_ASK, BTN_AI_ANALYZE_SIGNALS], [BTN_BACK]],
        {"screen": "ai", "home": home},
    )


async def _ai_send_answer(ctx, chat_id, answer_coro):
    """Javob kutilayotganda '⏳' ko'rsatib, keyin shu xabarni tahrirlab yuboradi."""
    placeholder = await ctx.bot.send_message(chat_id, "⏳ AI javob tayyorlayapti...")
    answer = (await answer_coro) or "⚠️ AI dan bo'sh javob qaytdi."
    limit = 3800  # Telegram chegarasi (4096) uchun zaxira bilan
    chunks = [answer[i:i + limit] for i in range(0, len(answer), limit)]
    try:
        await placeholder.edit_text(chunks[0])
    except Exception:
        await ctx.bot.send_message(chat_id, chunks[0])
    for extra in chunks[1:]:
        await ctx.bot.send_message(chat_id, extra)


async def collect_ai_signals(ctx, user, is_owner, limit=10):
    """AI tahlili uchun signallar: OWNER uchun barchasi, aks holda o'z kanallari."""
    if is_owner:
        return get_recent_signals(limit=limit)
    rows = []
    for ch in await find_subscriber_channels(ctx, user.id):
        rows.extend(get_recent_signals(limit=limit, channel_id=ch["channel_id"]))
    rows.sort(key=lambda r: r["created_at"] or "", reverse=True)
    return rows[:limit]


async def ai_analyze_signals(ctx, chat_id, user, is_owner):
    """Oxirgi signallar bo'yicha AI xulosasi."""
    rows = await collect_ai_signals(ctx, user, is_owner)
    if not rows:
        await send_reply_text(
            ctx, chat_id,
            "📊 Tahlil uchun signal topilmadi.\n\n"
            "Kanal ulangandan keyin (yoki signallar yozila boshlagach) shu yerda "
            "ular bo'yicha xulosa chiqadi.",
        )
        return
    await _ai_send_answer(ctx, chat_id, analyze_recent_signals(rows))


async def show_my_channels(ctx, chat_id, user, home):
    channels = await find_subscriber_channels(ctx, user.id)
    if not channels:
        await show_reply_menu(ctx, chat_id, "Siz hozircha ro'yxatdan o'tgan kanalga a'zo emassiz.",
                              [BTN_BACK], {"screen": "channel_pick", "choices": {}, "home": home})
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
                              [BTN_BACK], {"screen": "stats_channel", "choices": {}, "home": home})
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
