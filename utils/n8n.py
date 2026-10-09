"""
Trading Journal - n8n Integration Utils
"""
import asyncio
import base64
import os
import tempfile
import logging
import httpx
import sqlite3
from datetime import datetime
from config import (
    BOT_NAME, VERSION, N8N_WEBHOOK_URL, N8N_SECRET,
    N8N_TIMEOUT, TZ, DB
)
from database import db

log = logging.getLogger("bot")
BOT_START_TIME = datetime.now(TZ).isoformat()

def n8n_enabled():
    """Webhook manzili berilganmi?"""
    return bool(N8N_WEBHOOK_URL)

async def n8n_send(event, data=None, *, file_path=None):
    """n8n webhook'iga bitta hodisa yuboradi (best effort)."""
    if not n8n_enabled():
        return False

    payload = {
        "event": event,
        "bot": BOT_NAME,
        "version": VERSION,
        "sent_at": datetime.now(TZ).isoformat(),
        "data": data or {},
    }
    if file_path and os.path.exists(file_path):
        try:
            with open(file_path, "rb") as fh:
                payload["file"] = {
                    "name": os.path.basename(file_path),
                    "size": os.path.getsize(file_path),
                    "base64": base64.b64encode(fh.read()).decode("ascii"),
                }
        except Exception as e:
            log.warning("Zaxira faylini o'qib bo'lmadi: %s", e)

    headers = {"Content-Type": "application/json"}
    if N8N_SECRET:
        headers["X-Bot-Secret"] = N8N_SECRET

    try:
        async with httpx.AsyncClient(timeout=N8N_TIMEOUT) as client:
            resp = await client.post(N8N_WEBHOOK_URL, json=payload, headers=headers)
        if resp.status_code >= 400:
            log.warning("n8n javobi %s (%s)", resp.status_code, event)
            return False
        return True
    except Exception as e:
        log.warning("n8n'ga yuborilmadi (%s): %s", event, type(e).__name__)
        return False

def _copy_db_to(path):
    """SQLite'ning backup API'si orqali izchil nusxa oladi."""
    src = sqlite3.connect(DB)
    try:
        dst = sqlite3.connect(path)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

async def heartbeat_job(ctx):
    """Har HEARTBEAT_MINUTES da n8n'ga 'tirikman' signali yuboradi."""
    with db() as con:
        users = con.execute("SELECT COUNT(*) AS n FROM dm_users").fetchone()["n"]
        signals = con.execute("SELECT COUNT(*) AS n FROM signals").fetchone()["n"]
        channels = con.execute("SELECT COUNT(*) AS n FROM channels").fetchone()["n"]

    await n8n_send("heartbeat", {
        "channels": channels,
        "users": users,
        "signals": signals,
        "db_size": os.path.getsize(DB) if os.path.exists(DB) else 0,
        "started_at": BOT_START_TIME,
    })

async def backup_job(ctx):
    """Har kuni BACKUP_HOUR:00 da bazani n8n'ga zaxira qilib yuboradi."""
    if not n8n_enabled():
        return
    name = f"signals_{datetime.now(TZ).strftime('%Y-%m-%d')}.db"
    tmp_path = os.path.join(tempfile.gettempdir(), name)
    try:
        await asyncio.to_thread(_copy_db_to, tmp_path)
        ok = await n8n_send("daily_backup", {"db_path": DB, "file_name": name},
                            file_path=tmp_path)
        if ok:
            log.info("Kunlik zaxira n8n'ga yuborildi: %s", name)
    except Exception as e:
        log.warning("Kunlik zaxira yuborilmadi: %s", e)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
