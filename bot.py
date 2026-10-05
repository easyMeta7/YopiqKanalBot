"""
Yopiq kanal uchun obuna boshqaruv boti.
Python + aiogram 3 + SQLite.

Asosiy funksiyalar:
  - To'lov (Variant B): chek skrinshoti -> admin tasdiqlashi -> bir martalik invite link
  - Muddat tugashidan 3 kun va 1 kun oldin eslatma
  - Muddat tugaganda kanaldan chiqarish + "Qayta obuna / Fikr bildirish" tugmalari
  - Admin buyruqlari: /users, /add, /addmin, /kick, /link + klaviatura tugmalari
  - /add <id> <kun>      - obuna qo'shish/uzaytirish
  - /addmin <id> <daqiqa> - test rejimi (eski muddatni ALMASHTIRADI)
  - /kick <id>           - foydalanuvchini kanaldan chiqarish
  - /link <id>           - invite linkni qayta yuborish
"""

import asyncio
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
ADMIN_IDS = [
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x
]
CARD_NUMBER = os.getenv("CARD_NUMBER", "8600 0000 0000 0000")
CARD_OWNER = os.getenv("CARD_OWNER", "Karta egasi")
CHECK_INTERVAL_SEC = int(os.getenv("CHECK_INTERVAL_SEC", "600"))
DB_PATH = os.getenv("DB_PATH", "bot.db")

# Tariflar - narxlarni o'zingizga moslang
PLANS = {
    1: {"name": "1 oy", "days": 30, "price": 100_000},
    3: {"name": "3 oy", "days": 90, "price": 270_000},
}

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

@contextmanager
def db() -> sqlite3.Connection:
    """Connection ochadi, commit qiladi va YOPADI (sizib ketishga qarshi)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS subs (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                start_at    TEXT,
                end_at      TEXT,
                reminded3   INTEGER DEFAULT 0,
                reminded1   INTEGER DEFAULT 0,
                expired_msg INTEGER DEFAULT 0
            )
            """
        )
        conn.commit()


def get_sub(user_id: int) -> sqlite3.Row | None:
    with db() as conn:
        return conn.execute(
            "SELECT * FROM subs WHERE user_id = ?", (user_id,)
        ).fetchone()


def upsert_sub(
    user_id: int,
    username: str | None,
    start_at: datetime,
    end_at: datetime,
    replace: bool = False,
) -> None:
    """Obuna qo'shadi/uzaytiradi.

    replace=False: muddat eskisiga qo'shib uzaytiradi (agar eskisi tugagan
    bo'lsa hozirdan boshlaydi).
    replace=True: eski muddatni almashtiradi (test rejimi uchun).
    """
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM subs WHERE user_id = ?", (user_id,)
        ).fetchone()
        duration = end_at - start_at
        if row is None:
            conn.execute(
                "INSERT INTO subs (user_id, username, start_at, end_at) "
                "VALUES (?,?,?,?)",
                (user_id, username or "", start_at.isoformat(), end_at.isoformat()),
            )
        elif replace:
            conn.execute(
                "UPDATE subs SET username=?, start_at=?, end_at=?, reminded3=0, "
                "reminded1=0, expired_msg=0 WHERE user_id=?",
                (
                    username or row["username"],
                    start_at.isoformat(),
                    end_at.isoformat(),
                    user_id,
                ),
            )
        else:
            old_end = datetime.fromisoformat(row["end_at"])
            base = max(now_utc(), old_end)
            conn.execute(
                "UPDATE subs SET username=?, end_at=?, reminded3=0, "
                "reminded1=0, expired_msg=0 WHERE user_id=?",
                (
                    username or row["username"],
                    (base + duration).isoformat(),
                    user_id,
                ),
            )
        conn.commit()


def all_subs() -> list[sqlite3.Row]:
    with db() as conn:
        return conn.execute(
            "SELECT * FROM subs ORDER BY end_at DESC"
        ).fetchall()


# ---------------------------------------------------------------------------
# Yordamchilar
# ---------------------------------------------------------------------------

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def in_channel(user_id: int) -> bool:
    try:
        m = await bot.get_chat_member(CHANNEL_ID, user_id)
        return m.status in ("member", "administrator", "creator")
    except Exception:
        return False


async def make_invite_link(user_id: int) -> str:
    """Bir martalik invite link (member_limit=1, 24 soat amal qiladi)."""
    link = await bot.create_chat_invite_link(
        chat_id=CHANNEL_ID,
        name=f"user_{user_id}",
        member_limit=1,
        expire_date=now_utc() + timedelta(hours=24),
        creates_join_request=False,
    )
    return link.invite_link


async def remove_from_channel(user_id: int) -> None:
    """Kanaldan chiqaradi (ban -> unban, shunda keyin qayta qo'shila oladi)."""
    await bot.ban_chat_member(CHANNEL_ID, user_id)
    await bot.unban_chat_member(CHANNEL_ID, user_id)


def fmt_dt(iso: str) -> str:
    dt = datetime.fromisoformat(iso)
    return dt.astimezone().strftime("%d.%m.%Y %H:%M")


def plans_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{p['name']} — {p['price']:,} so'm".replace(",", " "),
                    callback_data=f"plan:{pid}",
                )
            ]
            for pid, p in PLANS.items()
        ]
    )


# ---------------------------------------------------------------------------
# Holatlar (FSM)
# ---------------------------------------------------------------------------

class Pay(StatesGroup):
    waiting_photo = State()


class Feedback(StatesGroup):
    text = State()


def status_text(user_id: int) -> str:
    """Obuna holati matni (/obuna buyrug'i uchun)."""
    sub = get_sub(user_id)
    if not sub or datetime.fromisoformat(sub["end_at"]) <= now_utc():
        return "⏳ Faol obunangiz yo'q. /start orqali tarif tanlang."
    left = datetime.fromisoformat(sub["end_at"]) - now_utc()
    return (
        f"✅ Faol obuna.\n"
        f"Muddat: <b>{fmt_dt(sub['end_at'])}</b>\n"
        f"Qoldi: ~{left.days} kun"
    )


def admin_kb() -> ReplyKeyboardMarkup:
    """Admin uchun klaviatura ostidagi doimiy tugmalar."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Obunachilar ro'yxati"),
             KeyboardButton(text="ℹ️ Buyruqlar")],
        ],
        resize_keyboard=True,
    )


# ---------------------------------------------------------------------------
# Foydalanuvchi buyruqlari
# ---------------------------------------------------------------------------

@router.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext) -> None:
    await state.clear()
    # Admin uchun klaviatura ostiga tugmalar chiqadi
    if is_admin(msg.from_user.id):
        await msg.answer(
            "👋 Assalomu alaykum, admin!\n\n"
            "Pastdagi tugmalar orqali obunachilarni boshqaring.",
            reply_markup=admin_kb(),
        )
    await msg.answer(
        "Bu bot orqali yopiq kanalga obuna bo'lasiz.\n"
        "Quyidagi tarifni tanlang:",
        reply_markup=plans_kb(),
    )


# --- Klaviatura ostidagi admin tugmalari ---

@router.message(F.text == "👥 Obunachilar ro'yxati")
async def kb_users(msg: Message) -> None:
    if not is_admin(msg.from_user.id):
        return
    await msg.answer(subs_list_text(), disable_web_page_preview=True)


@router.message(F.text == "ℹ️ Buyruqlar")
async def kb_help(msg: Message) -> None:
    if not is_admin(msg.from_user.id):
        return
    await msg.answer(
        "ℹ️ <b>Admin buyruqlari:</b>\n\n"
        "/users — obunachilar ro'yxati (ID + muddat)\n"
        "/add &lt;id&gt; &lt;kun&gt; — obuna qo'shish/uzaytirish\n"
        "/addmin &lt;id&gt; &lt;daqiqa&gt; — test rejimi (muddatni almashtiradi)\n"
        "/kick &lt;id&gt; — kanaldan chiqarish\n"
        "/link &lt;id&gt; — invite linkni qayta yuborish\n"
        "/obuna — obuna holati"
    )


@router.message(Command("obuna"))
async def cmd_obuna(msg: Message) -> None:
    await msg.answer(status_text(msg.from_user.id))


@router.callback_query(F.data.startswith("plan:"))
async def cb_plan(cb: CallbackQuery, state: FSMContext) -> None:
    pid = int(cb.data.split(":")[1])
    if pid not in PLANS:
        await cb.answer()
        return
    await state.set_state(Pay.waiting_photo)
    await state.update_data(plan=pid)
    price = f"{PLANS[pid]['price']:,}".replace(",", " ")
    await cb.message.answer(
        f"💳 <b>{PLANS[pid]['name']}</b> — {price} so'm\n\n"
        f"Karta: <code>{CARD_NUMBER}</code>\n"
        f"Karta egasi: {CARD_OWNER}\n\n"
        f"To'lovdan keyin chek skrinshotini shu yerga yuboring."
    )
    await cb.answer()


@router.message(Pay.waiting_photo, F.photo)
async def got_receipt(msg: Message, state: FSMContext) -> None:
    data = await state.get_data()
    pid = data.get("plan", 1)
    await state.clear()
    price = f"{PLANS[pid]['price']:,}".replace(",", " ")

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(
                chat_id=admin_id,
                photo=msg.photo[-1].file_id,
                caption=(
                    f"🧾 Yangi chek!\n"
                    f"Foydalanuvchi: {msg.from_user.id} "
                    f"(@{msg.from_user.username or '-'})\n"
                    f"Tarif: {PLANS[pid]['name']} — {price} so'm"
                ),
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="✅ Tasdiqlash",
                                callback_data=f"approve:{msg.from_user.id}:{pid}",
                            ),
                            InlineKeyboardButton(
                                text="❌ Rad etish",
                                callback_data=f"reject:{msg.from_user.id}",
                            ),
                        ]
                    ]
                ),
            )
        except Exception as e:
            log.error("Admin %s ga yuborishda xato: %s", admin_id, e)

    await msg.answer(
        "📩 Chek adminga yuborildi. Tasdiqlangandan so'ng invite link keladi."
    )


@router.message(Pay.waiting_photo)
async def not_photo(msg: Message) -> None:
    await msg.answer("Iltimos, chek skrinshotini (rasm) yuboring.")


# ---------------------------------------------------------------------------
# Tasdiqlash / rad etish
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("approve:"))
async def cb_approve(cb: CallbackQuery) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("Ruxsat yo'q", show_alert=True)
        return
    _, uid_s, pid_s = cb.data.split(":")
    uid, pid = int(uid_s), int(pid_s)
    plan = PLANS[pid]

    start = now_utc().replace(microsecond=0)
    end = start + timedelta(days=plan["days"])

    username = None
    try:
        user = await bot.get_chat(uid)
        username = user.username
    except Exception:
        pass

    was_in = await in_channel(uid)
    upsert_sub(uid, username, start, end)
    end_iso = get_sub(uid)["end_at"]

    try:
        if was_in:
            await bot.send_message(
                uid,
                f"✅ To'lov tasdiqlandi! Siz kanaldasiz, obunangiz "
                f"{fmt_dt(end_iso)} gacha uzaytirildi.",
            )
        else:
            link = await make_invite_link(uid)
            await bot.send_message(
                uid,
                f"✅ To'lov tasdiqlandi!\n\n"
                f"Kanalga kirish linki (24 soat, 1 martalik):\n{link}\n\n"
                f"Muddat: {fmt_dt(end_iso)}",
            )
    except Exception as e:
        await cb.message.answer(
            f"⚠️ {uid} ga xabar yuborib bo'lmadi "
            f"(botni /start bosgan bo'lishi kerak): {e}"
        )

    await cb.answer("✅ Tasdiqlandi")
    try:
        await cb.message.edit_caption(
            caption=f"✅ Tasdiqlandi — {uid} ({plan['name']})"
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("reject:"))
async def cb_reject(cb: CallbackQuery) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("Ruxsat yo'q", show_alert=True)
        return
    uid = int(cb.data.split(":")[1])
    try:
        await bot.send_message(
            uid,
            "❌ To'lov rad etildi. Savol bo'lsa, adminga yozing "
            "yoki qaytadan urinib ko'ring.",
        )
    except Exception:
        pass
    await cb.answer("❌ Rad etildi")
    try:
        await cb.message.edit_caption(caption=f"❌ Rad etildi — {uid}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Muddat tugagandagi tugmalar
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "resub")
async def cb_resub(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.message.answer(
        "Qaysi tarifni tanlaysiz?", reply_markup=plans_kb()
    )
    await cb.answer()


@router.callback_query(F.data == "feedback")
async def cb_feedback(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Feedback.text)
    await cb.message.answer(
        "✍️ Kanal haqida fikringizni yozing. Xabaringiz adminga yetkaziladi."
    )
    await cb.answer()


@router.message(Feedback.text)
async def got_feedback(msg: Message, state: FSMContext) -> None:
    await state.clear()
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"💬 Fikr bildirish — {msg.from_user.id} "
                f"(@{msg.from_user.username or '-'}):\n\n{msg.text}",
            )
        except Exception:
            pass
    await msg.answer("Rahmat! Fikringiz adminga yuborildi.")


# ---------------------------------------------------------------------------
# Admin buyruqlari
# ---------------------------------------------------------------------------

async def grant_and_send(uid: int, start: datetime, end: datetime,
                         replace: bool, msg: Message) -> None:
    """Obunani bazaga yozadi va kerak bo'lsa invite link yuboradi."""
    was_in = await in_channel(uid)
    upsert_sub(uid, None, start, end, replace=replace)
    end_iso = get_sub(uid)["end_at"]

    if was_in:
        await msg.answer(
            f"✅ {uid} allaqachon kanalda. Muddat: {fmt_dt(end_iso)}"
        )
        return
    try:
        link = await make_invite_link(uid)
        await bot.send_message(
            uid,
            f"✅ Sizga obuna berildi.\n"
            f"Link (24 soat, 1 martalik): {link}\n"
            f"Muddat: {fmt_dt(end_iso)}",
        )
        await msg.answer(f"✅ {uid} ga link yuborildi. Muddat: {fmt_dt(end_iso)}")
    except Exception as e:
        await msg.answer(
            f"⚠️ {uid} ga link yuborilmadi (botni /start bosgan bo'lishi kerak): "
            f"{e}\nMuddat bazaga yozildi: {fmt_dt(end_iso)}"
        )


@router.message(Command("add"))
async def cmd_add(msg: Message) -> None:
    if not is_admin(msg.from_user.id):
        return
    parts = (msg.text or "").split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await msg.answer("Foydalanish: /add <user_id> <kun>")
        return
    uid, days = int(parts[1]), int(parts[2])
    start = now_utc().replace(microsecond=0)
    end = start + timedelta(days=days)
    await grant_and_send(uid, start, end, replace=False, msg=msg)


@router.message(Command("addmin"))
async def cmd_addmin(msg: Message) -> None:
    """Test rejimi: muddatni daqiqa bilan ALMASHTIRADI (uzaytirmaydi)."""
    if not is_admin(msg.from_user.id):
        return
    parts = (msg.text or "").split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await msg.answer("Foydalanish: /addmin <user_id> <daqiqa>")
        return
    uid, minutes = int(parts[1]), int(parts[2])
    start = now_utc().replace(microsecond=0)
    end = start + timedelta(minutes=minutes)
    await grant_and_send(uid, start, end, replace=True, msg=msg)


@router.message(Command("kick"))
async def cmd_kick(msg: Message) -> None:
    if not is_admin(msg.from_user.id):
        return
    parts = (msg.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await msg.answer("Foydalanish: /kick <user_id>")
        return
    await kick_user(int(parts[1]), msg)


@router.message(Command("link"))
async def cmd_link(msg: Message) -> None:
    if not is_admin(msg.from_user.id):
        return
    parts = (msg.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await msg.answer("Foydalanish: /link <user_id>")
        return
    uid = int(parts[1])
    try:
        link = await make_invite_link(uid)
        await bot.send_message(uid, f"🔗 Invite link (24 soat):\n{link}")
        await msg.answer(f"✅ {uid} ga link yuborildi.")
    except Exception as e:
        await msg.answer(f"Xato: {e}")


@router.message(Command("users"))
async def cmd_users(msg: Message) -> None:
    if not is_admin(msg.from_user.id):
        return
    await msg.answer(subs_list_text(), disable_web_page_preview=True)


# ---------------------------------------------------------------------------
# Admin yordamchi funksiyalari
# ---------------------------------------------------------------------------

async def kick_user(uid: int, msg: Message) -> None:
    """Foydalanuvchini kanaldan chiqaradi va muddatini yopadi."""
    try:
        await remove_from_channel(uid)
        with db() as conn:
            conn.execute(
                "UPDATE subs SET end_at=?, expired_msg=1 WHERE user_id=?",
                (now_utc().replace(microsecond=0).isoformat(), uid),
            )
            conn.commit()
        await msg.answer(f"🗑 {uid} kanaldan chiqarildi va muddati yopildi.")
    except Exception as e:
        await msg.answer(f"Xato: {e}")


def subs_list_text() -> str:
    rows = all_subs()
    if not rows:
        return "Obunachilar yo'q."
    now = now_utc()
    lines = [f"👥 Obunachilar ({len(rows)}):", ""]
    for r in rows:
        end = datetime.fromisoformat(r["end_at"])
        status = "🟢" if end > now else "🔴"
        uname = f"@{r['username']}" if r["username"] else "-"
        lines.append(
            f"{status} ID: <code>{r['user_id']}</code> {uname} — "
            f"muddat: {fmt_dt(r['end_at'])}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Muddatni tekshirish tsikli
# ---------------------------------------------------------------------------

async def _set_flag(field: str, uid: int) -> None:
    with db() as conn:
        conn.execute(
            f"UPDATE subs SET {field}=1 WHERE user_id=?", (uid,)
        )
        conn.commit()


async def check_subscriptions() -> None:
    now = now_utc()
    for r in all_subs():
        end = datetime.fromisoformat(r["end_at"])
        uid = r["user_id"]

        if end > now:
            # Eslatmalar: 3 kun va 1 kun oldin
            left_days = (end - now).total_seconds() / 86400
            if left_days <= 3 and not r["reminded3"]:
                try:
                    await bot.send_message(
                        uid,
                        f"⏳ Obunangiz {fmt_dt(r['end_at'])} da tugaydi "
                        f"(3 kundan kam qoldi). Muddat tugashidan oldin "
                        f"uzaysangiz, uzluksiz davom etadi.",
                    )
                except Exception:
                    pass
                await _set_flag("reminded3", uid)
            if left_days <= 1 and not r["reminded1"]:
                try:
                    await bot.send_message(
                        uid,
                        f"🔴 Obunangiz 1 kundan kam qoldi — "
                        f"{fmt_dt(r['end_at'])} da tugaydi.",
                    )
                except Exception:
                    pass
                await _set_flag("reminded1", uid)
            continue

        # Muddat tugadi
        if r["expired_msg"]:
            continue

        # Kanaldan chiqarish
        try:
            if await in_channel(uid):
                await remove_from_channel(uid)
        except Exception as e:
            log.error("Chiqarishda xato %s: %s", uid, e)

        # Xabar + tugmalar
        try:
            await bot.send_message(
                uid,
                "⌛ Obuna muddatingiz tugadi.\n\n"
                "Qaytadan obuna bo'lasizmi yoki kanal haqida "
                "qandaydir fikringiz bormi?",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(
                            text="🔄 Qayta obuna bo'lish",
                            callback_data="resub")],
                        [InlineKeyboardButton(
                            text="💬 Fikr bildirish",
                            callback_data="feedback")],
                    ]
                ),
            )
        except Exception as e:
            log.error("Tugash xabari yuborilmadi %s: %s", uid, e)

        await _set_flag("expired_msg", uid)


async def checker_loop() -> None:
    while True:
        try:
            await check_subscriptions()
        except Exception as e:
            log.error("Tekshiruvda xato: %s", e)
        await asyncio.sleep(CHECK_INTERVAL_SEC)


# ---------------------------------------------------------------------------
# Ishga tushirish
# ---------------------------------------------------------------------------

async def on_startup() -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Boshlash / tarif tanlash"),
            BotCommand(command="obuna", description="Obuna holati"),
            BotCommand(command="users", description="Obunachilar ro'yxati (admin)"),
        ]
    )


async def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN topilmadi — .env faylini to'ldiring.")
    if not CHANNEL_ID or not ADMIN_IDS:
        raise SystemExit("CHANNEL_ID va ADMIN_IDS ni .env da kiriting.")

    init_db()
    await on_startup()
    asyncio.create_task(checker_loop())
    log.info("Bot ishga tushdi (tekshiruv har %s soniyada)", CHECK_INTERVAL_SEC)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot to'xtatildi.")







