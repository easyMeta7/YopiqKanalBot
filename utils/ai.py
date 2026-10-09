"""
Trading Journal - FreeLLMAPI AI Integration Layer
"""
import logging
import time
import httpx
from config import (
    FREELLMAPI_URL, FREELLMAPI_KEY, AI_MODEL,
    AI_TIMEOUT, AI_MAX_TOKENS, AI_TEMPERATURE,
)

log = logging.getLogger("bot")

STATUS_TTL = 30  # soniya: AI menyusi har ochilganda routerga so'rov yubormaslik uchun
_status_cache = (0.0, "")


def ai_enabled():
    """Unified kalit berilganmi? (kalitsiz router 401 qaytaradi)"""
    return bool(FREELLMAPI_KEY)


async def ai_status(timeout: int = 8) -> str:
    """Router va unified kalit holatini qisqa qatorda qaytaradi (menyu sarlavhasi uchun)."""
    global _status_cache
    if not ai_enabled():
        return "⚠️ FREELLMAPI_KEY berilmagan — AI Tahlilchi o'chiq"
    cached_at, cached = _status_cache
    if cached and time.monotonic() - cached_at < STATUS_TTL:
        return cached
    result = await _fetch_status(timeout)
    _status_cache = (time.monotonic(), result)
    return result


async def _fetch_status(timeout: int) -> str:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                f"{FREELLMAPI_URL}/models",
                headers={"Authorization": f"Bearer {FREELLMAPI_KEY}"},
            )
        if resp.status_code == 200:
            models = resp.json().get("data") or []
            return f"✅ Router ishlayapti ({len(models)} ta model)"
        if resp.status_code in (401, 403):
            return "⚠️ Unified kalit qabul qilinmadi (HTTP 401)"
        return f"⚠️ Router javobi: HTTP {resp.status_code}"
    except Exception:
        return f"⚠️ Router bilan aloqa yo'q ({FREELLMAPI_URL})"


SYSTEM_PROMPT = (
    "Siz 'Trading Journal' trading platformasining professional AI tahlilchisisiz. "
    "Siz moliya bozorlari (ayniqsa Oltin / XAUUSD, Bitcoin / BTC, NAS100), texnik tahlil, "
    "Smart Money Concepts (SMC), Price Action va risk-menejment bo'yicha kuchli mutaxassissiz. "
    "Foydalanuvchilarga o'zbek tilida aniq, tushunarli, foydali va lo'nda javob bering. "
    "Har doim risk menejmenti (depozitning 1-2% dan ko'pini xavfga qo'ymaslik) muhimligini eslatib turing."
)

async def ask_freellm(messages: list, model: str = None, timeout: int = None) -> str:
    """FreeLLMAPI orqali OpenAI-mos endpointga so'rov yuborish."""
    url = f"{FREELLMAPI_URL}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if FREELLMAPI_KEY:
        headers["Authorization"] = f"Bearer {FREELLMAPI_KEY}"

    payload = {
        "model": model or AI_MODEL or "auto",
        "messages": messages,
        "temperature": AI_TEMPERATURE,
        "max_tokens": AI_MAX_TOKENS,
    }
    timeout = timeout or AI_TIMEOUT

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)

        if resp.status_code == 200:
            data = resp.json()
            choices = data.get("choices", [])
            if choices and "message" in choices[0]:
                return (choices[0]["message"].get("content", "") or "").strip() \
                    or "⚠️ AI dan bo'sh javob qaytdi."
            return "⚠️ AI dan bo'sh javob qaytdi."
        elif resp.status_code == 401 or resp.status_code == 403:
            log.warning("FreeLLMAPI kalit xatosi: %s", resp.status_code)
            return "⚠️ FreeLLMAPI kalitida xatolik bor. Sozlamalarni tekshiring."
        elif resp.status_code == 429:
            return "⏳ AI ga so'rovlar limiti to'ldi. Birozdan so'ng qayta urinib ko'ring."
        else:
            log.warning("FreeLLMAPI xato kodi: %s -> %s", resp.status_code, resp.text[:200])
            return f"⚠️ AI xizmatida xatolik yuz berdi (HTTP {resp.status_code})."
    except httpx.ConnectError:
        log.warning("FreeLLMAPI serveriga ulanib bo'lmadi: %s", url)
        return (
            "⚠️ FreeLLMAPI serveri bilan aloqa yo'q.\n\n"
            "Server ishga tushirilganligini va FREELLMAPI_URL to'g'ri sozlanganligini tekshiring."
        )
    except httpx.TimeoutException:
        return "⏳ AI javob berish vaqti tugadi. Qayta urinib ko'ring."
    except Exception as e:
        log.exception("FreeLLMAPI so'rovida kutilmagan xatolik: %s", e)
        return f"⚠️ Xatolik yuz berdi: {type(e).__name__}"

async def ask_ai_analyst(user_query: str) -> str:
    """Foydalanuvchi savoliga javob olish."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_query},
    ]
    return await ask_freellm(messages)

async def analyze_recent_signals(signals: list) -> str:
    """Oxirgi signallar bo'yicha AI tahlili va xulosasi."""
    if not signals:
        return "Tahlil qilish uchun signallar topilmadi."

    summary_lines = []
    for s in signals[:10]:
        status = s['status'] or 'open'
        res = f"{status.upper()} ({s['result_pips']} pips)" if status != 'open' else "OCHIQ"
        summary_lines.append(
            f"• {s['pair'] or 'XAU'} {(s['side'] or '').upper()} | Entry: {s['entry']} | "
            f"TP1: {s['tp1']} | Stop: {s['stop']} | Holat: {res}"
        )

    prompt = (
        "Quyida trading botimizdagi so'nggi signallar berilgan:\n\n"
        + "\n".join(summary_lines) +
        "\n\nIltimos, ushbu signallarni tahlil qilib, quyidagilarni o'z ichiga olgan qisqa va lo'nda tahliliy xulosa ber:\n"
        "1. Qaysi juftlik va yo'nalishlarda ko'proq foyda olingan?\n"
        "2. Bozorning joriy holati va treyderlarga bugungi asosiy maslahat/tavsiya."
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    return await ask_freellm(messages)
