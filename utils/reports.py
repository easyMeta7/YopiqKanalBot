"""
Trading Journal - Report Generation Utils
"""
from datetime import datetime, date, time, timedelta
from config import TZ, MONTH_NAMES_UZ, MONTHS, TRADING_DAY_START_HOUR
from database import db

def month_bounds(year, month):
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    end = end - timedelta(days=1)
    return start, end

def trading_date(dt=None):
    """Savdo kuni sanasi: bozor kuni 02:00 dan keyingi kun 02:00 gacha (GMT+5).
    Masalan 11.10 soat 01:30 -> 10.10 kuniga tegishli."""
    dt = (dt or datetime.now(TZ)).astimezone(TZ)
    return (dt - timedelta(hours=TRADING_DAY_START_HOUR)).date()

def day_window(start_d, end_d):
    """[start_d 02:00, end_d dan keyingi kun 02:00) — end_d savdo kuni ham kiradi."""
    start = datetime.combine(start_d, time(TRADING_DAY_START_HOUR), tzinfo=TZ)
    end = datetime.combine(end_d + timedelta(days=1), time(TRADING_DAY_START_HOUR), tzinfo=TZ)
    return start, end

def week_bounds(day):
    """Berilgan kun tegishli dushanba-yakshanba haftasi."""
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)

def month_weeks(year, month):
    """Oy ichidagi dushanba-yakshanba haftalari (oy chegarasida kesilgan, bir-biriga o'tmaydi)."""
    month_start, month_end = month_bounds(year, month)
    weeks, cur = [], month_start
    while cur <= month_end:
        end = min(week_bounds(cur)[1], month_end)
        weeks.append((cur, end))
        cur = end + timedelta(days=1)
    return weeks

def parse_month_arg(args, default_year, default_month):
    for a in args:
        key = a.lower()
        if key in MONTHS:
            return default_year, MONTHS[key]
    return default_year, default_month

def rows_between(channel_id, start_d, end_d, pair=None):
    start_dt = datetime.combine(start_d, time.min, tzinfo=TZ)
    end_dt = datetime.combine(end_d, time.max, tzinfo=TZ)
    q = "SELECT * FROM signals WHERE chat_id=? AND created_at >= ? AND created_at <= ?"
    params = [channel_id, start_dt.isoformat(), end_dt.isoformat()]
    if pair:
        q += " AND pair=?"
        params.append(pair)
    q += " ORDER BY created_at"
    with db() as con:
        return con.execute(q, params).fetchall()

def rows_in_days(channel_id, start_d, end_d, pair=None):
    """Savdo kunlari bo'yicha (02:00 dan 02:00 gacha) signallar; end_d ham kiradi."""
    start, end = day_window(start_d, end_d)
    q = "SELECT * FROM signals WHERE chat_id=? AND created_at >= ? AND created_at < ?"
    params = [channel_id, start.isoformat(), end.isoformat()]
    if pair:
        q += " AND pair=?"
        params.append(pair)
    q += " ORDER BY created_at"
    with db() as con:
        return con.execute(q, params).fetchall()

def summarize(rows):
    closed = [r for r in rows if r["status"] != "open"]
    wins = [r for r in closed if r["status"] != "stop"]
    losses = [r for r in closed if r["status"] == "stop"]
    total = sum(r["result_pips"] for r in closed)
    winrate = round(len(wins) / len(closed) * 100) if closed else 0
    return closed, wins, losses, total, winrate

def render_rows_by_day(rows, day_headers=True):
    from utils.signals import fmt_pips # Import inside to avoid circular
    lines = []
    last_day = None
    n = 0
    for r in rows:
        d = trading_date(datetime.fromisoformat(r["created_at"]))
        if day_headers and d != last_day:
            if lines:
                lines.append("")
            lines.append(f"{d:%d.%m.%Y}")
            last_day = d
        n += 1
        res = "ochiq" if r["status"] == "open" else f"{r['status'].upper()} ({fmt_pips(r['result_pips'])})"
        lines.append(f"#{n} {r['pair']} {r['side'].capitalize()} {r['entry']:g} → {res}")
    return lines

def render_summary(rows):
    from utils.signals import fmt_pips
    closed, wins, losses, total, winrate = summarize(rows)
    return [
        "",
        f"Jami signal: {len(rows)} | Yopilgan: {len(closed)}",
        f"TP: {len(wins)} | Stop: {len(losses)}",
        f"Winrate: {winrate}%",
        f"Sof natija: {fmt_pips(total)}",
    ]

def build_week_report(channel_id, title):
    """Joriy hafta: dushanbadan yakshanbagacha (savdo kuni 02:00 chegarasi bilan)."""
    start_d, end_d = week_bounds(trading_date())
    rows = rows_in_days(channel_id, start_d, end_d)
    lines = [f"📊 {title} — hafta ({start_d:%d.%m} - {end_d:%d.%m})", ""]
    body = render_rows_by_day(rows)
    lines += body if body else ["Bu hafta signal bo'lmadi."]
    if rows:
        lines += render_summary(rows)
    return "\n".join(lines)

def build_monthly_report(channel_id, title, args):
    """Kalendar oy: 1-sanadan oxirgi sanagacha. Haftalar qatori yig'indini aynan bo'lib ko'rsatadi."""
    from utils.signals import fmt_pips # Import inside to avoid circular
    today = trading_date()
    year, month = parse_month_arg(args, today.year, today.month)
    month_start, month_end = month_bounds(year, month)
    rows = rows_in_days(channel_id, month_start, month_end)
    weeks = month_weeks(year, month)
    by_week = [[] for _ in weeks]
    for r in rows:
        d = trading_date(datetime.fromisoformat(r["created_at"]))
        for i, (week_start, week_end) in enumerate(weeks):
            if week_start <= d <= week_end:
                by_week[i].append(r)
                break
    lines = [f"📊 {title} — {MONTH_NAMES_UZ[month]} {year} ({month_start:%d.%m} - {month_end:%d.%m})", ""]
    for wn, ((week_start, week_end), week_rows) in enumerate(zip(weeks, by_week), start=1):
        span = f"{wn}-hafta ({week_start:%d.%m}-{week_end:%d.%m})"
        if not week_rows:
            lines.append(f"{span}: signal yo'q")
            continue
        closed, wins, losses, total, _ = summarize(week_rows)
        lines.append(f"{span}: {len(week_rows)} signal | TP {len(wins)}, Stop {len(losses)} | {fmt_pips(total)}")
    if rows:
        lines += render_summary(rows)
    else:
        lines.append("")
        lines.append("Bu oy signal bo'lmadi.")
    return "\n".join(lines)

def build_daily_report(channel_id, title, day):
    """Bitta savdo kuni (day 02:00 -> keyingi kun 02:00) natijasi. Signal bo'lmasa None qaytaradi."""
    rows = rows_in_days(channel_id, day, day)
    if not rows:
        return None
    start, end = day_window(day, day)
    lines = [
        f"📅 {title} — kunlik natija",
        f"{start:%d.%m.%Y %H:%M} → {end:%d.%m.%Y %H:%M}",
        "",
    ]
    lines += render_rows_by_day(rows, day_headers=False)
    lines += render_summary(rows)
    return "\n".join(lines)

def build_pair_stats(channel_id, title, pair):
    from utils.signals import fmt_pips
    end_d = datetime.now(TZ).date()
    start_d = end_d - timedelta(days=30)
    rows = rows_between(channel_id, start_d, end_d, pair=pair)
    tp_counts = {"tp1": 0, "tp2": 0, "tp3": 0, "stop": 0}
    for r in rows:
        if r["status"] in tp_counts:
            tp_counts[r["status"]] += 1
    closed, wins, losses, total, winrate = summarize(rows)
    lines = [
        f"📈 {pair} statistikasi — {title}",
        f"Davr: {start_d:%d.%m.%Y} - {end_d:%d.%m.%Y}",
        "",
        f"TP1: {tp_counts['tp1']} | TP2: {tp_counts['tp2']} | TP3: {tp_counts['tp3']} | Stop: {tp_counts['stop']}",
        f"Jami signal: {len(rows)} | Yopilgan: {len(closed)}",
        f"Winrate: {winrate}%",
        f"Sof natija: {fmt_pips(total)}",
    ]
    return "\n".join(lines)
