"""
Trading Journal - Signal Calculation Utils
"""
import re
from config import PIP

NUM = r"(\d+(?:\.\d+)?)"

def pips(side, entry, price):
    diff = (price - entry) if side == "buy" else (entry - price)
    return round(diff / PIP)

def signal_looks_complete(text):
    t = text.lower()
    return bool(
        re.search(r"\b(buy|sell)\b", t)
        and re.search(NUM + r"\s*[-–—]\s*" + NUM, t)
        and re.search(r"\bstop\b", t)
        and re.search(r"\btp1\b", t)
    )

def detect_pair(text):
    m = re.search(r"\b(xau|btc|nas100)\b", text.lower())
    return m.group(1).upper() if m else "XAU"

def parse_signal(text):
    t = text.lower()
    m = re.search(r"\b(buy|sell)\b", t)
    if not m:
        raise ValueError("Buy yoki Sell topilmadi")
    side = m.group(1)

    r = re.search(NUM + r"\s*[-–—]\s*" + NUM, t)
    if not r:
        raise ValueError("Entry oralig'i topilmadi (masalan 4332-4328)")
    a, b = float(r.group(1)), float(r.group(2))
    entry = max(a, b) if side == "buy" else min(a, b)

    s = re.search(r"stop\s*[:\-]?\s*" + NUM, t)
    if not s:
        raise ValueError("Stop topilmadi")
    stop = float(s.group(1))

    tps = {}
    for n, val in re.findall(r"tp\s*([123])\s*[:\-]?\s*" + NUM, t):
        tps[f"tp{n}"] = float(val)
    if "tp1" not in tps:
        raise ValueError("TP1 topilmadi")

    if side == "buy":
        ok = stop < entry < tps["tp1"]
    else:
        ok = tps["tp1"] < entry < stop
    if not ok:
        raise ValueError("Stop/TP entry ga nisbatan noto'g'ri tomonda")

    return dict(side=side, entry=entry, stop=stop,
                tp1=tps.get("tp1"), tp2=tps.get("tp2"), tp3=tps.get("tp3"))

def fmt_pips(p):
    return f"{p:+d} pips"
