"""
Trading Journal - Database layer
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from config import DB, TZ, OWNER_ID

@contextmanager
def db():
    """SQLite ulanishi: muvaffaqiyatda commit, xatoda rollback, DOIM yopiladi.

    (Oldin `with sqlite3.connect()` faqat commit qilardi, ulanishni yopmasdi.)
    """
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    try:
        with con:
            yield con
    finally:
        con.close()

def init_db():
    with db() as con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER, message_id INTEGER,
                pair TEXT DEFAULT 'XAU',
                side TEXT, entry REAL, stop REAL,
                tp1 REAL, tp2 REAL, tp3 REAL,
                status TEXT DEFAULT 'open',
                result_pips INTEGER,
                created_at TEXT, result_at TEXT,
                UNIQUE(chat_id, message_id)
            )"""
        )
        cols = [r["name"] for r in con.execute("PRAGMA table_info(signals)")]
        if "pair" not in cols:
            con.execute("ALTER TABLE signals ADD COLUMN pair TEXT DEFAULT 'XAU'")

        con.execute(
            """CREATE TABLE IF NOT EXISTS channels (
                channel_id INTEGER PRIMARY KEY,
                owner_id INTEGER,
                title TEXT,
                tag TEXT
            )"""
        )
        con.execute(
            """CREATE TABLE IF NOT EXISTS contact_messages (
                admin_message_id INTEGER PRIMARY KEY,
                user_chat_id INTEGER,
                user_label TEXT
            )"""
        )
        con.execute(
            """CREATE TABLE IF NOT EXISTS subscriptions (
                user_id INTEGER, channel_id INTEGER,
                PRIMARY KEY (user_id, channel_id)
            )"""
        )
        con.execute(
            """CREATE TABLE IF NOT EXISTS pushes (
                channel_id INTEGER, message_id INTEGER,
                user_id INTEGER, pushed_message_id INTEGER,
                PRIMARY KEY (channel_id, message_id, user_id)
            )"""
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_signals_chat_created ON signals(chat_id, created_at)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_channel ON subscriptions(channel_id)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_channels_owner ON channels(owner_id)")

        con.execute(
            """CREATE TABLE IF NOT EXISTS dm_users (
                user_id INTEGER PRIMARY KEY,
                name TEXT, contact TEXT, lang TEXT, created_at TEXT
            )"""
        )
        con.execute(
            """CREATE TABLE IF NOT EXISTS ui_messages (
                chat_id INTEGER PRIMARY KEY,
                message_id INTEGER NOT NULL
            )"""
        )
        con.execute(
            """CREATE TABLE IF NOT EXISTS channel_posts (
                channel_id INTEGER, message_id INTEGER,
                created_at TEXT,
                PRIMARY KEY (channel_id, message_id)
            )"""
        )
        con.execute(
            """CREATE TABLE IF NOT EXISTS admin_pushes (
                channel_id INTEGER PRIMARY KEY,
                enabled INTEGER DEFAULT 0
            )"""
        )

def get_dm_user(user_id):
    with db() as con:
        return con.execute("SELECT * FROM dm_users WHERE user_id=?", (user_id,)).fetchone()

def save_dm_user(user_id, name=None, contact=None, lang=None):
    with db() as con:
        existing = con.execute("SELECT * FROM dm_users WHERE user_id=?", (user_id,)).fetchone()
        if existing:
            con.execute(
                "UPDATE dm_users SET name=COALESCE(?,name), contact=COALESCE(?,contact), "
                "lang=COALESCE(?,lang) WHERE user_id=?",
                (name, contact, lang, user_id),
            )
        else:
            con.execute(
                "INSERT INTO dm_users (user_id, name, contact, lang, created_at) VALUES (?,?,?,?,?)",
                (user_id, name, contact, lang, datetime.now(TZ).isoformat()),
            )

def list_dm_users(limit=20):
    with db() as con:
        return con.execute(
            "SELECT * FROM dm_users ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()

def get_channel(channel_id):
    with db() as con:
        return con.execute("SELECT * FROM channels WHERE channel_id=?", (channel_id,)).fetchone()

def get_all_channels():
    with db() as con:
        return con.execute("SELECT * FROM channels ORDER BY title").fetchall()

def get_channels_of(owner_id):
    with db() as con:
        return con.execute(
            "SELECT * FROM channels WHERE owner_id=? ORDER BY title", (owner_id,)
        ).fetchall()

def get_channel_stats(channel_id):
    with db() as con:
        stats = con.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN result_pips > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result_pips < 0 THEN 1 ELSE 0 END) as losses,
                SUM(result_pips) as total_pips
            FROM signals
            WHERE chat_id = ? AND status != 'open'
        """, (channel_id,)).fetchone()

        subs = con.execute("SELECT COUNT(*) as count FROM subscriptions WHERE channel_id=?", (channel_id,)).fetchone()

        return {
            "total": stats["total"] or 0,
            "wins": stats["wins"] or 0,
            "losses": stats["losses"] or 0,
            "total_pips": stats["total_pips"] or 0,
            "subs": subs["count"] or 0
        }

def get_channels_rating(sort_by="pips"):
    with db() as con:
        query = """
            SELECT c.channel_id, c.title,
                   SUM(s.result_pips) as total_pips,
                   (CAST(SUM(CASE WHEN s.result_pips > 0 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(s.id)) * 100 as winrate
            FROM channels c
            JOIN signals s ON c.channel_id = s.chat_id
            WHERE s.status != 'open'
            GROUP BY c.channel_id
        """
        if sort_by == "winrate":
            query += " ORDER BY winrate DESC"
        else:
            query += " ORDER BY total_pips DESC"

        return con.execute(query).fetchall()

def get_recent_channels(limit=5):
    with db() as con:
        return con.execute("SELECT * FROM channels ORDER BY channel_id DESC LIMIT ?", (limit,)).fetchall()

def get_recent_signals(limit=10, channel_id=None):
    with db() as con:
        if channel_id:
            return con.execute(
                "SELECT * FROM signals WHERE chat_id=? ORDER BY created_at DESC LIMIT ?",
                (channel_id, limit),
            ).fetchall()
        return con.execute(
            "SELECT * FROM signals ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()

def is_admin_push_enabled(channel_id):
    with db() as con:
        row = con.execute("SELECT enabled FROM admin_pushes WHERE channel_id=?", (channel_id,)).fetchone()
        return row["enabled"] == 1 if row else False

def toggle_admin_push(channel_id, enable):
    with db() as con:
        con.execute(
            "INSERT INTO admin_pushes (channel_id, enabled) VALUES (?,?) "
            "ON CONFLICT(channel_id) DO UPDATE SET enabled=excluded.enabled",
            (channel_id, 1 if enable else 0),
        )

def register_channel(channel_id, owner_id, title, tag):
    with db() as con:
        con.execute(
            "INSERT INTO channels (channel_id, owner_id, title, tag) VALUES (?,?,?,?) "
            "ON CONFLICT(channel_id) DO UPDATE SET owner_id=excluded.owner_id, "
            "title=excluded.title, tag=excluded.tag",
            (channel_id, owner_id, title, tag),
        )

def set_channel_tag(channel_id, tag):
    with db() as con:
        con.execute("UPDATE channels SET tag=? WHERE channel_id=?", (tag, channel_id))

def remove_channel(channel_id):
    with db() as con:
        con.execute("DELETE FROM channels WHERE channel_id=?", (channel_id,))
        con.execute("DELETE FROM subscriptions WHERE channel_id=?", (channel_id,))
        con.execute("DELETE FROM pushes WHERE channel_id=?", (channel_id,))

def save_contact_mapping(admin_message_id, user_chat_id, user_label):
    with db() as con:
        con.execute(
            "INSERT OR REPLACE INTO contact_messages (admin_message_id, user_chat_id, user_label) "
            "VALUES (?,?,?)",
            (admin_message_id, user_chat_id, user_label),
        )

def get_contact_mapping(admin_message_id):
    with db() as con:
        return con.execute(
            "SELECT * FROM contact_messages WHERE admin_message_id=?", (admin_message_id,)
        ).fetchone()

def is_subscribed(user_id, channel_id):
    with db() as con:
        return con.execute(
            "SELECT 1 FROM subscriptions WHERE user_id=? AND channel_id=?", (user_id, channel_id)
        ).fetchone() is not None

def subscribe(user_id, channel_id):
    with db() as con:
        con.execute(
            "INSERT OR IGNORE INTO subscriptions (user_id, channel_id) VALUES (?,?)",
            (user_id, channel_id),
        )

def unsubscribe(user_id, channel_id):
    with db() as con:
        con.execute(
            "DELETE FROM subscriptions WHERE user_id=? AND channel_id=?", (user_id, channel_id)
        )

def get_subscribers(channel_id):
    with db() as con:
        return [r["user_id"] for r in con.execute(
            "SELECT user_id FROM subscriptions WHERE channel_id=?", (channel_id,)
        ).fetchall()]

def get_push_recipients(channel_id):
    """Obunachilar. Kanal egasiga push yuborilmaydi.
    Agar bu OWNER_ID ning bayroq kanali bo'lsa, barcha bot foydalanuvchilariga reklama sifatida yuboriladi."""
    ch = get_channel(channel_id)
    recipients = set(get_subscribers(channel_id))
    if ch and OWNER_ID and ch["owner_id"] == OWNER_ID:
        with db() as con:
            recipients |= {
                r["user_id"] for r in con.execute("SELECT DISTINCT user_id FROM subscriptions").fetchall()
            }
    if ch and ch["owner_id"]:
        recipients.discard(ch["owner_id"])
    return [i for i in recipients if i]
