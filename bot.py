"""
Yopiq kanal uchun obuna boshqaruv boti.
Python + aiogram 3 + SQLite. Railway'ga deploy qilinadi.

>>> AI YORDAMCHILAR UCHUN (Claude, ChatGPT, Gemini, Codex, Cursor, Freebuff...) <<<
  1. Bu faylga tegishdan OLDIN AI_LOG.md ni to'liq o'qing (loyiha holati, qarorlar,
     ochiq masalalar, oxirgi ishlar shu yerda).
  2. Kodni o'zgartirsangiz, ish tugagach AI_LOG.md dagi "O'zgarishlar jurnali"
     TEPASIGA yangi yozuv qo'shing. Foydalanuvchi eslatmasa ham. Bu majburiy.
  3. Yangi buyruq/o'zgaruvchi/qaror bo'lsa AI_LOG.md "Joriy holat" ni ham yangilang.
  4. Token, karta raqami va boshqa sirlarni logga yozmang.

Asosiy funksiyalar:
  - To'lov: chek skrinshoti -> admin tasdiqlashi -> bir martalik invite link
  - Takroriy chek ogohlantirishi (bir xil rasm qayta kelsa adminga ⚠️)
  - Muddat tugashidan 3 kun va 1 kun oldin eslatma
  - Muddat tugaganda kanaldan chiqarish (xato bo'lsa keyingi aylanishda qayta uriniladi)
  - Chiqarib bo'lmasa yoki backup xato bersa, adminlarga ogohlantirish (bir muammo uchun bir marta)
  - Admin: /users, /add, /addmin, /kick, /link + klaviatura tugmalari
  - /add <id> <kun>   - muddatni uzaytiradi
  - /add <id> <sana>  - tugash sanasini aniq qo'yadi (31-12-2026), eski a'zolar uchun
  - /addmin <id> <daqiqa> - test rejimi (eski muddatni ALMASHTIRADI)
  - /kick <id>, /link <id>
  - 📢 Broadcast  - barcha faol obunachilarga xabar
  - 📂 Auto-Backup - har 6 soatda baza nusxasi BACKUP_CHANNEL_ID kanaliga
"""

import asyncio
import html
import logging
import os
import sqlite3
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    FSInputFile,
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
CARD_OWNER = os.getenv("CARD_OWNER", "Karta egasi")
CARDS = [
    ("💳 Visa", os.getenv("CARD_VISA", "")),
    ("💳 Humo", os.getenv("CARD_HUMO", "")),
    ("💳 Uzcard", os.getenv("CARD_UZCARD", "")),
]
if not any(num for _, num in CARDS) and os.getenv("CARD_NUMBER"):
    CARDS = [("💳 Karta", os.getenv("CARD_NUMBER", ""))]

CHECK_INTERVAL_SEC = int(os.getenv("CHECK_INTERVAL_SEC", "600"))
DB_PATH = os.getenv("DB_PATH", "bot.db")
ADMIN_CONTACT_USERNAME = os.getenv("ADMIN_CONTACT_USERNAME", "").lstrip("@")
BACKUP_CHANNEL_ID = int(os.getenv("BACKUP_CHANNEL_ID", "0"))

_db_dir = os.path.dirname(DB_PATH)
if _db_dir:
    os.makedirs(_db_dir, exist_ok=True)

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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS receipts (
                rid        TEXT PRIMARY KEY,
                status     TEXT,
                admin_id   INTEGER,
                admin_name TEXT,
                decided_at TEXT
            )
            """
        )
        for col in ("admin_name TEXT", "photo_uid TEXT"):
            try:
                conn.execute(f"ALTER TABLE receipts ADD COLUMN {col}")
            except sqlite3.OperationalError:
                pass
        conn.execute("CREATE INDEX IF NOT EXISTS idx_receipts_photo ON receipts(photo_uid)")
        conn.commit()

def register_receipt(rid: str, photo_uid: str) -> None:
    """Chekni 'pending' sifatida ro'yxatga oladi."""
    with db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO receipts (rid, status, photo_uid) VALUES (?, 'pending', ?)",
            (rid, photo_uid),
        )

def claim_receipt(rid: str, status: str, admin_id: int, admin_name: str) -> sqlite3.Row | None:
    """Chekni atomik egallaydi: faqat birinchi bosgan admin o'tadi (None qaytadi).
    Keyingilarga mavjud yozuv qaytadi."""
    now = now_tashkent().replace(microsecond=0).isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "UPDATE receipts SET status=?, admin_id=?, admin_name=?, decided_at=? "
            "WHERE rid=? AND status='pending'",
            (status, admin_id, admin_name, now, rid),
        )
        conn.commit()
        if cur.rowcount == 1:
            return None
        row = conn.execute("SELECT * FROM receipts WHERE rid = ?", (rid,)).fetchone()
        if row is None:  # ro'yxatga olinmagan chek – to'g'ridan-to'g'ri egallaymiz
            conn.execute(
                "INSERT INTO receipts (rid, status, admin_id, admin_name, decided_at) VALUES (?,?,?,?,?)",
                (rid, status, admin_id, admin_name, now),
            )
            conn.commit()
            return None
        return row
    finally:
        conn.close()

def find_duplicate_receipt(photo_uid: str, exclude_rid: str) -> sqlite3.Row | None:
    """Xuddi shu rasm (file_unique_id) avval kelganmi? Tahrirlanmagan bir xil
    rasm har doim bir xil file_unique_id beradi."""
    if not photo_uid:
        return None
    with db() as conn:
        return conn.execute(
            "SELECT * FROM receipts WHERE photo_uid = ? AND rid != ? "
            "ORDER BY (status='approved') DESC, decided_at DESC LIMIT 1",
            (photo_uid, exclude_rid),
        ).fetchone()

def get_sub(user_id: int) -> sqlite3.Row | None:
    with db() as conn:
        return conn.execute("SELECT * FROM subs WHERE user_id = ?", (user_id,)).fetchone()

def upsert_sub(user_id: int, username: str | None, start_at: datetime, end_at: datetime, replace: bool = False) -> None:
    with db() as conn:
        row = conn.execute("SELECT * FROM subs WHERE user_id = ?", (user_id,)).fetchone()
        duration = end_at - start_at
        if row is None:
            conn.execute(
                "INSERT INTO subs (user_id, username, start_at, end_at) VALUES (?,?,?,?)",
                (user_id, username or "", start_at.isoformat(), end_at.isoformat()),
            )
        elif replace:
            conn.execute(
                "UPDATE subs SET username=?, start_at=?, end_at=?, reminded3=0, reminded1=0, expired_msg=0 WHERE user_id=?",
                (username or row["username"], start_at.isoformat(), end_at.isoformat(), user_id),
            )
        else:
            old_end = datetime.fromisoformat(row["end_at"])
            base = max(now_tashkent().replace(microsecond=0), old_end)
            conn.execute(
                "UPDATE subs SET username=?, end_at=?, reminded3=0, reminded1=0, expired_msg=0 WHERE user_id=?",
                (username or row["username"], (base + duration).isoformat(), user_id),
            )
        conn.commit()

def all_subs() -> list[sqlite3.Row]:
    with db() as conn:
        return conn.execute("SELECT * FROM subs ORDER BY end_at DESC").fetchall()

def subs_to_check() -> list[sqlite3.Row]:
    """Tekshiruv uchun: tugash xabari hali yuborilmaganlar (faollar va endi tugaganlar)."""
    with db() as conn:
        return conn.execute("SELECT * FROM subs WHERE expired_msg = 0").fetchall()

def count_subs() -> int:
    with db() as conn:
        return conn.execute("SELECT COUNT(*) FROM subs").fetchone()[0]

# ---------------------------------------------------------------------------
# Yordamchilar
# ---------------------------------------------------------------------------

def now_tashkent() -> datetime:
    return datetime.now(timezone(timedelta(hours=5)))

def parse_end_date(text: str) -> datetime | None:
    """Tugash sanasini o'qiydi: 31-12-2026, 31.12.2026, 31/12/2026 yoki 2026-12-31.
    Shu kun 23:59 (Toshkent) qaytariladi. Noto'g'ri bo'lsa None."""
    t = (text or "").strip()
    for sep in ("-", ".", "/"):
        if sep in t:
            parts = t.split(sep)
            break
    else:
        return None
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return None
    try:
        if len(parts[0]) == 4:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        elif len(parts[2]) == 4:
            d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
        else:
            return None
        return datetime(y, m, d, 23, 59, tzinfo=timezone(timedelta(hours=5)))
    except ValueError:
        return None

async def add_by_days_or_date(uid: int, arg: str, msg: Message) -> bool:
    """arg – kun soni (uzaytiradi) yoki tugash sanasi (aniq muddat qo'yadi).
    Muvaffaqiyatli bo'lsa True, noto'g'ri kiritilsa False (xabar yuboriladi)."""
    arg = (arg or "").strip()
    start = now_tashkent().replace(microsecond=0)
    if arg.isdigit():
        days = int(arg)
        if days <= 0:
            await msg.answer("Kun soni 0 dan katta bo'lishi kerak.")
            return False
        await grant_and_send(uid, start, start + timedelta(days=days), replace=False, msg=msg)
        return True
    end = parse_end_date(arg)
    if end is None:
        await msg.answer("❌ Tushunmadim. Kun sonini (masalan: 30) yoki tugash sanasini (masalan: 31-12-2026) yozing.")
        return False
    if end <= start:
        await msg.answer(f"❌ Sana o'tib ketgan ({fmt_dt(end.isoformat())}). Kelajakdagi sanani yozing.")
        return False
    await grant_and_send(uid, start, end, replace=True, msg=msg)
    return True

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def notify_admins(text: str, except_id: int | None = None) -> None:
    """Barcha adminlarga xabar (except_id – o'tkazib yuboriladigan admin, masalan tugmani bosgan)."""
    for admin_id in ADMIN_IDS:
        if admin_id == except_id:
            continue
        try:
            await bot.send_message(admin_id, text)
        except Exception as e:
            log.warning("Adminga (%s) xabar yuborilmadi: %s", admin_id, e)

async def in_channel(user_id: int) -> bool | None:
    """True/False – aniq javob. None – tekshirib bo'lmadi (tarmoq/API xatosi)."""
    try:
        m = await bot.get_chat_member(CHANNEL_ID, user_id)
    except TelegramBadRequest as e:
        if "user not found" in str(e).lower() or "participant" in str(e).lower():
            return False
        log.warning("in_channel(%s) BadRequest: %s", user_id, e)
        return None
    except Exception as e:
        log.warning("in_channel(%s) xato: %s", user_id, e)
        return None
    if m.status in ("member", "administrator", "creator"):
        return True
    if m.status == "restricted":
        return bool(getattr(m, "is_member", False))
    return False

async def make_invite_link(user_id: int) -> str:
    link = await bot.create_chat_invite_link(
        chat_id=CHANNEL_ID,
        name=f"user_{user_id}",
        member_limit=1,
        expire_date=now_tashkent() + timedelta(hours=24),
        creates_join_request=False,
    )
    return link.invite_link

async def remove_from_channel(user_id: int) -> None:
    await bot.ban_chat_member(CHANNEL_ID, user_id)
    await bot.unban_chat_member(CHANNEL_ID, user_id)

def fmt_dt(iso: str) -> str:
    dt = datetime.fromisoformat(iso)
    return dt.strftime("%d.%m.%Y %H:%M")

def plans_kb(with_contact: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"{p['name']} – {p['price']:,} so'm".replace(",", " "), callback_data=f"plan:{pid}")]
        for pid, p in PLANS.items()
    ]
    if with_contact and ADMIN_CONTACT_USERNAME:
        rows.append([InlineKeyboardButton(text="📞 Admin bilan bog'lanish", url=f"https://t.me/{ADMIN_CONTACT_USERNAME}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ---------------------------------------------------------------------------
# Holatlar (FSM)
# ---------------------------------------------------------------------------

class Pay(StatesGroup):
    waiting_photo = State()

class Feedback(StatesGroup):
    text = State()

class AddDlg(StatesGroup):
    user_id = State()
    days = State()

class TestDlg(StatesGroup):
    user_id = State()
    minutes = State()

class KickDlg(StatesGroup):
    user_id = State()

class LinkDlg(StatesGroup):
    user_id = State()

class BroadcastDlg(StatesGroup):
    text = State()

def cards_text() -> str:
    lines = []
    for name, number in CARDS:
        if number:
            lines.append(f"{name}: <code>{number}</code>")
    if not lines:
        lines.append(f"Karta: <code>{os.getenv('CARD_NUMBER', '')}</code>")
    lines.append(f"Karta egasi: {CARD_OWNER}")
    return "\n".join(lines)

def status_text(user_id: int) -> str:
    sub = get_sub(user_id)
    if not sub or datetime.fromisoformat(sub["end_at"]) <= now_tashkent():
        return "❌ Faol obunangiz yo'q. /start orqali tarif tanlang."
    left = datetime.fromisoformat(sub["end_at"]) - now_tashkent()
    return (
        f"✅ Faol obuna.\n"
        f"Muddat: <b>{fmt_dt(sub['end_at'])}</b>\n"
        f"Qoldi: ~{left.days} kun"
    )

def main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Obunachilar ro'yxati"),
             KeyboardButton(text="🛠 Buyruqlar")],
        ],
        resize_keyboard=True,
    )

def commands_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Qo'shish"),
             KeyboardButton(text="🧪 Test obuna")],
            [KeyboardButton(text="❌ Chiqarish"),
             KeyboardButton(text="🔗 Link")],
            [KeyboardButton(text="📢 Broadcast")],
            [KeyboardButton(text="🔙 Orqaga")],
        ],
        resize_keyboard=True,
    )

# ---------------------------------------------------------------------------
# Foydalanuvchi buyruqlari
# ---------------------------------------------------------------------------

@router.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext) -> None:
    await state.clear()
    if is_admin(msg.from_user.id):
        await msg.answer(
            "👋 Assalomu alaykum, admin!\n\n"
            "Pastdagi tugmalar orqali obunachilarni boshqaring.",
            reply_markup=main_kb(),
        )
        await msg.answer(
            "Bu bot orqali yopiq kanalga obuna bo'lasiz.\n"
            "Quyidagi tarifni tanlang:",
            reply_markup=plans_kb(),
        )
        return

    await msg.answer(
        "👋 Assalomu alaykum!\n\n"
        "Bu bot orqali yopiq kanalga obuna bo'lasiz.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await msg.answer(
        "Quyidagi tarifni tanlang:",
        reply_markup=plans_kb(with_contact=True),
    )

@router.message(F.text == "🔙 Orqaga")
async def kb_back(msg: Message, state: FSMContext) -> None:
    if not is_admin(msg.from_user.id):
        return
    await state.clear()
    await msg.answer("Asosiy menyu ⬅️", reply_markup=main_kb())

@router.message(F.text == "👥 Obunachilar ro'yxati")
async def kb_users(msg: Message) -> None:
    if not is_admin(msg.from_user.id):
        return
    await send_subs_list(msg)

@router.message(F.text == "🛠 Buyruqlar")
async def kb_help(msg: Message) -> None:
    if not is_admin(msg.from_user.id):
        return
    await msg.answer(
        "🛠 <b>Admin tugmalari</b>\n"
        "\n"
        "➕ <b>Qo'shish</b>\n"
        "Obuna qo'shadi yoki uzaytiradi. Eski a'zolarni ham shu orqali kiritasiz.\n"
        "ID yuborasiz, keyin quyidagilardan birini yozasiz:\n"
        "• kun soni, masalan <code>30</code> – hozirgi muddatga qo'shadi\n"
        "• tugash sanasi, masalan <code>31-12-2026</code> – muddatni aynan shu kunga qo'yadi\n"
        "\n"
        "🧪 <b>Test obuna</b>\n"
        "Bot ishlashini sinash uchun juda qisqa obuna beradi.\n"
        "ID yuborasiz, keyin daqiqa sonini yozasiz, masalan <code>2</code>.\n"
        "Eski muddat almashtiriladi, uzaytirilmaydi.\n"
        "\n"
        "❌ <b>Chiqarish</b>\n"
        "Foydalanuvchini kanaldan chiqaradi va obunasini yopadi. Faqat ID yuborasiz.\n"
        "\n"
        "🔗 <b>Link</b>\n"
        "Kanalga kirish uchun yangi bir martalik link yuboradi (24 soat amal qiladi). Faqat ID yuborasiz.\n"
        "\n"
        "📢 <b>Broadcast</b>\n"
        "Barcha faol obunachilarga xabar yuboradi (matn yoki rasm). Oxirida nechta odamga yetgani va yetmagani yoziladi.\n"
        "\n"
        "🔙 <b>Orqaga</b>\n"
        "Asosiy menyuga qaytaradi. Dialog paytida bossangiz, dialog bekor bo'ladi.",
        reply_markup=commands_kb(),
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
        f"💳 <b>{PLANS[pid]['name']}</b> – {price} so'm\n\n"
        f"{cards_text()}\n\n"
        f"To'lovdan keyin chek skrinshotini shu yerga yuboring."
    )
    await cb.answer()

@router.message(Pay.waiting_photo, F.photo)
async def got_receipt(msg: Message, state: FSMContext) -> None:
    data = await state.get_data()
    pid = data.get("plan", 1)
    await state.clear()
    price = f"{PLANS[pid]['price']:,}".replace(",", " ")
    rid = uuid.uuid4().hex[:16]
    photo_uid = msg.photo[-1].file_unique_id or ""
    register_receipt(rid, photo_uid)
    dup = find_duplicate_receipt(photo_uid, exclude_rid=rid)
    dup_info = ""
    if dup is not None:
        if dup["status"] == "pending":
            dup_info = "⚠️ <b>TAKRORLANISH!</b> Bu surat avval ham yuborilgan, hali hal qilinmagan.\n\n"
        else:
            when = f", {fmt_dt(dup['decided_at'])}" if dup["decided_at"] else ""
            dup_info = (
                f"⚠️ <b>TAKRORLANISH!</b> Bu surat avval ham kelgan – "
                f"{_decision_word(dup['status']).lower()} ({html.escape(dup['admin_name'] or 'admin')}{when}).\n\n"
            )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(
                chat_id=admin_id,
                photo=msg.photo[-1].file_id,
                caption=(
                    dup_info
                    + f"🧾 Yangi chek!\n"
                    f"Foydalanuvchi: {msg.from_user.id} (@{msg.from_user.username or '-'})\n"
                    f"Tarif: {PLANS[pid]['name']} – {price} so'm"
                ),
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve:{rid}:{msg.from_user.id}:{pid}"),
                            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject:{rid}:{msg.from_user.id}"),
                        ]
                    ]
                ),
            )
        except Exception as e:
            log.error("Admin %s ga yuborishda xato: %s", admin_id, e)
    await msg.answer("📦 Chek adminga yuborildi. Tasdiqlangandan so'ng invite link keladi.")

@router.message(Pay.waiting_photo)
async def not_photo(msg: Message) -> None:
    await msg.answer("Iltimos, chek skrinshotini (rasm) yuboring.")

# ---------------------------------------------------------------------------
# Tasdiqlash / rad etish
# ---------------------------------------------------------------------------

def _admin_name(user) -> str:
    if user.username:
        return f"@{user.username}"
    return f"{user.full_name} (ID: {user.id})"

def _decision_word(status: str) -> str:
    return "Tasdiqlandi" if status == "approved" else "Rad etildi"

def _decision_emoji(status: str) -> str:
    return "✅" if status == "approved" else "❌"

async def _finalize_receipt(cb: CallbackQuery, emoji: str, word: str, by_name: str | None = None) -> None:
    who = by_name or _admin_name(cb.from_user)
    try:
        await cb.message.edit_caption(caption=f"{emoji} {word} – {html.escape(who)}")
    except Exception:
        pass
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

async def _claim(cb: CallbackQuery, rid: str, status: str) -> bool:
    """Chekni shu admin nomiga egallaydi. Boshqa admin allaqachon hal qilgan bo'lsa,
    ogohlantiradi, chek ostidagi yozuvni yangilaydi va False qaytaradi."""
    existing = claim_receipt(rid, status, cb.from_user.id, _admin_name(cb.from_user))
    if existing is None:
        return True
    await cb.answer(
        f"⚠️ Bu chek allaqachon {_decision_word(existing['status']).lower()} – {existing['admin_name'] or 'boshqa admin'}",
        show_alert=True,
    )
    await _finalize_receipt(cb, _decision_emoji(existing['status']), _decision_word(existing['status']), by_name=existing['admin_name'])
    return False

@router.callback_query(F.data.startswith("approve:"))
async def cb_approve(cb: CallbackQuery) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("Ruxsat yo'q", show_alert=True)
        return
    _, rid, uid_s, pid_s = cb.data.split(":")
    uid, pid = int(uid_s), int(pid_s)
    plan = PLANS[pid]
    if not await _claim(cb, rid, "approved"):
        return
    start = now_tashkent().replace(microsecond=0)
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
            await bot.send_message(uid, f"✅ To'lov tasdiqlandi! Siz kanaldasiz, obunangiz {fmt_dt(end_iso)} gacha uzaytirildi.")
        else:
            link = await make_invite_link(uid)
            await bot.send_message(uid, f"✅ To'lov tasdiqlandi!\n\nKanalga kirish linki (24 soat, 1 martalik):\n{link}\n\nMuddat: {fmt_dt(end_iso)}")
    except Exception as e:
        await cb.message.answer(f"❌ {uid} ga xabar yuborib bo'lmadi (botni /start bosgan bo'lishi kerak): {html.escape(str(e))}")
    await cb.answer("✅ Tasdiqlandi")
    await _finalize_receipt(cb, "✅", "Tasdiqlandi")
    await notify_admins(
        f"✅ Chek tasdiqlandi – {html.escape(_admin_name(cb.from_user))}\nFoydalanuvchi: {uid} ({plan['name']})",
        except_id=cb.from_user.id,
    )

@router.callback_query(F.data.startswith("reject:"))
async def cb_reject(cb: CallbackQuery) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("Ruxsat yo'q", show_alert=True)
        return
    _, rid, uid_s = cb.data.split(":")
    uid = int(uid_s)
    if not await _claim(cb, rid, "rejected"):
        return
    try:
        await bot.send_message(uid, "❌ To'lov rad etildi. Savol bo'lsa, adminga yozing yoki qaytadan urinib ko'ring.")
    except Exception:
        pass
    await cb.answer("❌ Rad etildi")
    await _finalize_receipt(cb, "❌", "Rad etildi")

# ---------------------------------------------------------------------------
# Muddat tugagandagi tugmalar
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "resub")
async def cb_resub(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.message.answer("Qaysi tarifni tanlaysiz?", reply_markup=plans_kb(with_contact=True))
    await cb.answer()

@router.callback_query(F.data == "feedback")
async def cb_feedback(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Feedback.text)
    await cb.message.answer("💭 Kanal haqida fikringizni yozing. Xabaringiz adminga yetkaziladi.")
    await cb.answer()

@router.message(Feedback.text)
async def got_feedback(msg: Message, state: FSMContext) -> None:
    if not msg.text:
        await msg.answer("Iltimos, fikringizni matn ko'rinishida yozing.")
        return
    await state.clear()
    await notify_admins(f"💭 Fikr bildirish – {msg.from_user.id} (@{msg.from_user.username or '-'}):\n\n{html.escape(msg.text)}")
    await msg.answer("Rahmat! Fikringiz adminga yuborildi.")

# ---------------------------------------------------------------------------
# Admin buyruqlari
# ---------------------------------------------------------------------------

async def grant_and_send(uid: int, start: datetime, end: datetime, replace: bool, msg: Message) -> None:
    was_in = await in_channel(uid)
    upsert_sub(uid, None, start, end, replace=replace)
    end_iso = get_sub(uid)["end_at"]
    if was_in:
        await msg.answer(f"✅ {uid} allaqachon kanalda. Muddat: {fmt_dt(end_iso)}")
        return
    try:
        link = await make_invite_link(uid)
        await bot.send_message(uid, f"✅ Sizga obuna berildi.\nLink (24 soat, 1 martalik): {link}\nMuddat: {fmt_dt(end_iso)}")
        await msg.answer(f"✅ {uid} ga link yuborildi. Muddat: {fmt_dt(end_iso)}")
    except Exception as e:
        await msg.answer(f"❌ {uid} ga link yuborilmadi (botni /start bosgan bo'lishi kerak): {html.escape(str(e))}\nMuddat bazaga yozildi: {fmt_dt(end_iso)}")

@router.message(Command("add"))
async def cmd_add(msg: Message) -> None:
    if not is_admin(msg.from_user.id):
        return
    parts = (msg.text or "").split()
    if len(parts) != 3 or not parts[1].isdigit():
        await msg.answer("Foydalanish:\n/add &lt;user_id&gt; &lt;kun&gt;  – muddatni uzaytiradi\n/add &lt;user_id&gt; &lt;sana&gt;  – tugash sanasini aniq qo'yadi (31-12-2026)")
        return
    await add_by_days_or_date(int(parts[1]), parts[2], msg)

@router.message(Command("addmin"))
async def cmd_addmin(msg: Message) -> None:
    if not is_admin(msg.from_user.id):
        return
    parts = (msg.text or "").split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await msg.answer("Foydalanish: /addmin <user_id> <daqiqa>")
        return
    uid, minutes = int(parts[1]), int(parts[2])
    start = now_tashkent().replace(microsecond=0)
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
        s = get_sub(uid)
        if s:
            await bot.send_message(uid, f"🔗 Invite link (24 soat):\n{link}")
            await msg.answer(f"✅ {uid} ga link yuborildi.")
        else:
            await msg.answer(f"❌ {uid} obunachi emas.")
    except Exception as e:
        await msg.answer(f"Xato: {html.escape(str(e))}")

@router.message(Command("users"))
async def cmd_users(msg: Message) -> None:
    if not is_admin(msg.from_user.id):
        return
    await send_subs_list(msg)

# ---------------------------------------------------------------------------
# Klaviatura dialoglari (2-daraja tugmalar)
# ---------------------------------------------------------------------------

def _need_admin(msg: Message) -> bool:
    return is_admin(msg.from_user.id)

async def _ask_uid(msg: Message, state: FSMContext, new_state: State, prompt: str) -> None:
    await state.set_state(new_state)
    await msg.answer(prompt, reply_markup=commands_kb())

async def _read_uid(msg: Message) -> int | None:
    """Dialogda yuborilgan ID ni o'qiydi. Raqam bo'lmasa, qayta so'raydi va None qaytaradi."""
    text = (msg.text or "").strip()
    if not text.isdigit():
        await msg.answer("ID raqam bo'lishi kerak. Masalan: 123456789")
        return None
    return int(text)

@router.message(F.text == "➕ Qo'shish")
async def kb_add(msg: Message, state: FSMContext) -> None:
    if not _need_admin(msg):
        return
    await _ask_uid(msg, state, AddDlg.user_id, "👥 Foydalanuvchi ID raqamini yuboring:")

@router.message(AddDlg.user_id)
async def kb_add_uid(msg: Message, state: FSMContext) -> None:
    uid = await _read_uid(msg)
    if uid is None:
        return
    await state.update_data(user_id=uid)
    await state.set_state(AddDlg.days)
    await msg.answer(
        "📅 Necha kun qo'shilsin yoki obuna qachon tugasin?\n\n"
        "• Kun soni: <code>30</code> – hozirgi muddatga qo'shadi\n"
        "• Sana: <code>31-12-2026</code> – tugash sanasini aniq qo'yadi (eski a'zolar uchun)"
    )

@router.message(AddDlg.days)
async def kb_add_days(msg: Message, state: FSMContext) -> None:
    data = await state.get_data()
    uid = data["user_id"]
    ok = await add_by_days_or_date(uid, msg.text or "", msg)
    if ok:
        await state.clear()

@router.message(F.text == "🧪 Test obuna")
async def kb_test(msg: Message, state: FSMContext) -> None:
    if not _need_admin(msg):
        return
    await _ask_uid(msg, state, TestDlg.user_id, "👥 Foydalanuvchi ID raqamini yuboring:")

@router.message(TestDlg.user_id)
async def kb_test_uid(msg: Message, state: FSMContext) -> None:
    uid = await _read_uid(msg)
    if uid is None:
        return
    await state.update_data(user_id=uid)
    await state.set_state(TestDlg.minutes)
    await msg.answer("⏱ Necha daqiqa? (masalan: 2)\nEski muddat almashtiriladi, uzaytirilmaydi.")

@router.message(TestDlg.minutes)
async def kb_test_minutes(msg: Message, state: FSMContext) -> None:
    text = (msg.text or "").strip()
    if not text.isdigit() or int(text) <= 0:
        await msg.answer("Daqiqa sonini kiriting. Masalan: 2")
        return
    data = await state.get_data()
    uid = data["user_id"]
    minutes = int(text)
    await state.clear()
    start = now_tashkent().replace(microsecond=0)
    end = start + timedelta(minutes=minutes)
    await grant_and_send(uid, start, end, replace=True, msg=msg)

@router.message(F.text == "❌ Chiqarish")
async def kb_kick(msg: Message, state: FSMContext) -> None:
    if not _need_admin(msg):
        return
    await _ask_uid(msg, state, KickDlg.user_id, "👥 Chiqariladigan foydalanuvchi ID raqamini yuboring:")

@router.message(KickDlg.user_id)
async def kb_kick_uid(msg: Message, state: FSMContext) -> None:
    uid = await _read_uid(msg)
    if uid is None:
        return
    await state.clear()
    await kick_user(uid, msg)

@router.message(F.text == "🔗 Link")
async def kb_link(msg: Message, state: FSMContext) -> None:
    if not _need_admin(msg):
        return
    await _ask_uid(msg, state, LinkDlg.user_id, "👥 Link yuboriladigan foydalanuvchi ID raqamini yuboring:")

@router.message(LinkDlg.user_id)
async def kb_link_uid(msg: Message, state: FSMContext) -> None:
    uid = await _read_uid(msg)
    if uid is None:
        return
    await state.clear()
    try:
        link = await make_invite_link(uid)
        await bot.send_message(uid, f"🔗 Invite link (24 soat):\n{link}")
        await msg.answer(f"✅ {uid} ga link yuborildi.")
    except Exception as e:
        await msg.answer(f"Xato: {html.escape(str(e))}")

@router.message(F.text == "📢 Broadcast")
async def kb_broadcast(msg: Message, state: FSMContext) -> None:
    if not _need_admin(msg):
        return
    await state.set_state(BroadcastDlg.text)
    await msg.answer("📢 Barcha faol obunachilarga yubormoqchi bo'lgan xabaringizni yozing (matn yoki rasm):", reply_markup=commands_kb())

@router.message(BroadcastDlg.text)
async def got_broadcast_text(msg: Message, state: FSMContext) -> None:
    await state.clear()
    subs = all_subs()
    ok = failed = 0
    now = now_tashkent()
    for s in subs:
        if datetime.fromisoformat(s['end_at']) > now:
            if await _copy_with_retry(msg, s['user_id']):
                ok += 1
            else:
                failed += 1
            await asyncio.sleep(0.05)
    text = f"✅ Xabar {ok} ta faol obunachiga yetdi."
    if failed:
        text += f"\n❌ {failed} tasiga yetmadi (botni bloklagan yoki o'chirgan)."
    await msg.answer(text)

async def _copy_with_retry(msg: Message, uid: int, attempts: int = 3) -> bool:
    """Telegram "kut" (RetryAfter) desa, aytilgan vaqtcha kutib qayta uriniladi."""
    for _ in range(attempts):
        try:
            await msg.copy_to(uid)
            return True
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
        except Exception as e:
            log.info("Broadcast %s ga yetmadi: %s", uid, e)
            return False
    return False

# ---------------------------------------------------------------------------
# Admin yordamchi funksiyalari
# ---------------------------------------------------------------------------

async def kick_user(uid: int, msg: Message) -> None:
    try:
        await remove_from_channel(uid)
        with db() as conn:
            conn.execute(
                "UPDATE subs SET end_at=?, expired_msg=1 WHERE user_id=?",
                (now_tashkent().replace(microsecond=0).isoformat(), uid),
            )
            conn.commit()
        await msg.answer(f"❌ {uid} kanaldan chiqarildi va muddati yopildi.")
    except Exception as e:
        await msg.answer(f"Xato: {html.escape(str(e))}")

def subs_list_text() -> str:
    """Faqat FAOL obunachilar (muddati tugaganlar ko'rsatilmaydi)."""
    now = now_tashkent()
    rows = [r for r in all_subs() if datetime.fromisoformat(r["end_at"]) > now]
    if not rows:
        return "Faol obunachilar yo'q."
    lines = [f"👥 Faol obunachilar ({len(rows)}):", ""]
    for r in rows:
        uname = f"@{r['username']}" if r['username'] else "-"
        lines.append(f"✅ ID: <code>{r['user_id']}</code> {uname} – muddat: {fmt_dt(r['end_at'])}")
    return "\n".join(lines)

def split_text(text: str, limit: int = 3900) -> list[str]:
    """Telegram xabar chegarasi (4096) dan oshmasligi uchun qatorlar bo'yicha bo'ladi."""
    chunks, cur = [], ""
    for line in text.split("\n"):
        if cur and len(cur) + len(line) + 1 > limit:
            chunks.append(cur)
            cur = line
        else:
            cur = f"{cur}\n{line}" if cur else line
    if cur:
        chunks.append(cur)
    return chunks

async def send_subs_list(msg: Message) -> None:
    for chunk in split_text(subs_list_text()):
        await msg.answer(chunk, disable_web_page_preview=True)

# ---------------------------------------------------------------------------
# Muddatni tekshirish tsikli
# ---------------------------------------------------------------------------

async def _set_flag(field: str, uid: int) -> None:
    with db() as conn:
        conn.execute(f"UPDATE subs SET {field}=1 WHERE user_id=?", (uid,))
        conn.commit()

# ---------------------------------------------------------------------------
# Adminlarga ogohlantirish (bir xil muammo uchun bir marta)
# ---------------------------------------------------------------------------

_kick_alerted: set[int] = set()        # chiqarib bo'lmagan va adminga aytilgan foydalanuvchilar
_kick_fail_count: dict[int, int] = {}  # a'zolikni tekshirib bo'lmagan ketma-ket urinishlar
_backup_alerted = False                # backup xatosi haqida adminga aytilganmi
KICK_UNKNOWN_ALERT_AFTER = 3           # tekshirib bo'lmasa, shuncha urinishdan keyin ogohlantiramiz

def _who(r) -> str:
    uname = f" @{r['username']}" if r["username"] else ""
    return f"<code>{r['user_id']}</code>{uname}"

async def alert_kick_problem(r, reason: str) -> None:
    uid = r["user_id"]
    if uid in _kick_alerted:
        return
    _kick_alerted.add(uid)
    low = reason.lower()
    hint = (
        "Bu odam kanal egasi yoki admini bo'lishi mumkin: Telegram botga ularni chiqarishga ruxsat bermaydi."
        if ("owner" in low or "administrator" in low or "can't remove" in low or "cannot remove" in low)
        else "Bot kanalda admin ekanini va \"Ban users\" huquqi borligini tekshiring."
    )
    await notify_admins(
        "⚠️ <b>Muddati tugagan foydalanuvchini kanaldan chiqarib bo'lmadi</b>\n"
        "\n"
        f"Foydalanuvchi: {_who(r)}\n"
        f"Tugagan: {fmt_dt(r['end_at'])}\n"
        f"Sabab: {html.escape(reason[:200])}\n"
        "\n"
        f"{hint}\n"
        "Bot har tekshiruvda qayta urinadi. Qo'lda chiqarish: ❌ Chiqarish tugmasi."
    )

async def resolve_kick_problem(r) -> None:
    uid = r["user_id"]
    _kick_fail_count.pop(uid, None)
    if uid in _kick_alerted:
        _kick_alerted.discard(uid)
        await notify_admins(f"✅ {_who(r)} kanaldan chiqarildi (avvalgi muammo hal bo'ldi).")

async def check_subscriptions() -> None:
    now = now_tashkent()
    for r in subs_to_check():
        end = datetime.fromisoformat(r["end_at"])
        uid = r["user_id"]
        if end > now:
            left_days = (end - now).total_seconds() / 86400
            # 1 kundan kam qolgan bo'lsa faqat 1 kunlik eslatma: 3 kunlik ham yuborilgan deb belgilanadi
            if left_days <= 1 and not r["reminded1"]:
                try:
                    await bot.send_message(
                        uid,
                        "🚨 <b>Obuna tugashiga 1 kundan kam qoldi</b>\n"
                        "\n"
                        f"Tugash vaqti: <b>{fmt_dt(r['end_at'])}</b>\n"
                        "\n"
                        "Kanaldan chiqib ketmaslik uchun hoziroq uzaytiring: /start",
                    )
                except Exception:
                    pass
                await _set_flag("reminded1", uid)
                await _set_flag("reminded3", uid)
            elif left_days <= 3 and not r["reminded3"]:
                try:
                    await bot.send_message(
                        uid,
                        "⚠️ <b>Obuna tugashiga 3 kundan kam qoldi</b>\n"
                        "\n"
                        f"Tugash vaqti: <b>{fmt_dt(r['end_at'])}</b>\n"
                        "\n"
                        "Uzilishsiz davom etishi uchun muddat tugashidan oldin obunani uzaytiring: /start",
                    )
                except Exception:
                    pass
                await _set_flag("reminded3", uid)
            continue
        if r["expired_msg"]:
            continue
        # Avval kanaldan chiqaramiz. Tekshirib bo'lmasa yoki chiqarish xato bersa,
        # belgi qo'ymaymiz – keyingi aylanishda qayta uriniladi.
        status = await in_channel(uid)
        if status is None:
            n = _kick_fail_count.get(uid, 0) + 1
            _kick_fail_count[uid] = n
            log.warning("Muddati tugagan %s: a'zolikni tekshirib bo'lmadi (%s-urinish), keyin qayta uriniladi", uid, n)
            if n >= KICK_UNKNOWN_ALERT_AFTER:
                await alert_kick_problem(r, "Telegram a'zolikni tekshirishga javob bermayapti")
            continue
        if status:
            try:
                await remove_from_channel(uid)
            except Exception as e:
                log.error("Chiqarishda xato %s: %s (keyin qayta uriniladi)", uid, e)
                await alert_kick_problem(r, str(e))
                continue
        await resolve_kick_problem(r)
        try:
            await bot.send_message(uid, "🔔 Obuna muddatingiz tugadi.\n\nQaytadan obuna bo'lasizmi yoki kanal haqida qandaydir fikringiz bormi?", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Qayta obuna bo'lish", callback_data="resub")], [InlineKeyboardButton(text="💭 Fikr bildirish", callback_data="feedback")]]))
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

def _make_backup_copy() -> str:
    """Ishlayotgan bazadan xavfsiz nusxa (sqlite backup API) – vaqtinchalik faylga."""
    tmp = tempfile.NamedTemporaryFile(prefix="bot_backup_", suffix=".db", delete=False)
    tmp.close()
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(tmp.name)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return tmp.name

async def run_backup_once() -> None:
    """Bitta backup. Xato bo'lsa adminga bir marta xabar beradi, tiklansa yana bir marta."""
    global _backup_alerted
    if not BACKUP_CHANNEL_ID:
        log.warning("BACKUP_CHANNEL_ID topilmadi, backup yuborilmadi.")
        return
    try:
        path = await asyncio.to_thread(_make_backup_copy)
        try:
            await bot.send_document(
                chat_id=BACKUP_CHANNEL_ID,
                document=FSInputFile(path, filename="bot.db"),
                caption=f"📂 Avtomatik Backup\nSana: {now_tashkent().strftime('%d.%m.%Y %H:%M')}",
            )
            log.info("Backup yuborildi")
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
    except Exception as e:
        log.error("Backup yuborishda xato: %s", e)
        if not _backup_alerted:
            _backup_alerted = True
            await notify_admins(
                "⚠️ <b>Backup yuborilmadi</b>\n"
                "\n"
                f"Sabab: {html.escape(str(e)[:200])}\n"
                "\n"
                "Bot backup kanalida admin ekanini va BACKUP_CHANNEL_ID to'g'riligini tekshiring. "
                "Bot 6 soatdan keyin qayta urinadi."
            )
        return
    if _backup_alerted:
        _backup_alerted = False
        await notify_admins("✅ Backup yana ishlayapti.")

async def backup_loop() -> None:
    while True:
        await run_backup_once()
        await asyncio.sleep(6 * 3600)

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
        raise SystemExit("BOT_TOKEN topilmadi – .env faylini to'ldiring.")
    if not CHANNEL_ID or not ADMIN_IDS:
        raise SystemExit("CHANNEL_ID va ADMIN_IDS ni .env da kiriting.")
    init_db()
    log.info("DB: %s – obunachilar soni: %s", os.path.abspath(DB_PATH), count_subs())
    if not ADMIN_CONTACT_USERNAME:
        log.warning("ADMIN_CONTACT_USERNAME kiritilmagan – 'Admin bilan bog'lanish' tugmasi ko'rinmaydi.")
    await on_startup()
    # Havolani saqlaymiz: aks holda Python fon vazifasini o'chirib yuborishi mumkin
    tasks = [asyncio.create_task(checker_loop()), asyncio.create_task(backup_loop())]
    for t in tasks:
        t.add_done_callback(_log_task_end)
    log.info("Bot ishga tushdi (tekshiruv har %s soniyada, backup har 6 soatda)", CHECK_INTERVAL_SEC)
    try:
        await dp.start_polling(bot)
    finally:
        for t in tasks:
            t.cancel()

def _log_task_end(task: asyncio.Task) -> None:
    """Fon tsikli to'xtab qolsa (bo'lmasligi kerak), logda ko'rinsin."""
    if task.cancelled():
        return
    log.error("Fon vazifasi to'xtadi: %s, xato: %r", task.get_coro().__name__, task.exception())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot to'xtatildi.")