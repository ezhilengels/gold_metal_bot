# =============================================================================
# GOLD BOT — signal_06_weekly_routine.py
# Signal 06: Practical Weekly Routine Checker
#
# PURPOSE : Week-level timing signal — is THIS week a good week to trade gold?
# ACTIVE  : MONDAY to THURSDAY ONLY. Friday/Sat/Sun → NON-TRADING DAY.
# INDEPENDENCE: 100% standalone. Shares NO data or logic with any other signal.
#
# DATA SOURCES:
#   W1 — COMEX Gold (GC=F)    via Yahoo Finance
#   W2 — DXY (DX-Y.NYB)       via Yahoo Finance
#   W3 — Economic Calendar     via hardcoded 2026 FOMC + dynamic NFP/CPI windows
#          (ForexFactory/Investing.com have no free API — hardcoded is more reliable)
#
# NO ASSUMPTION RULE: If W1 and W2 both fail → INSUFFICIENT DATA. Never estimate.
# =============================================================================

import os
import sys
import logging
from datetime import date, datetime, timedelta
from typing import Optional

# ── Setup ─────────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CONFIG

os.makedirs(CONFIG["log_directory"], exist_ok=True)
log_file = os.path.join(
    CONFIG["log_directory"],
    f"signal06_{datetime.now().strftime('%Y-%m-%d')}.log"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SIGNAL06] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("signal06")


# =============================================================================
# CONSTANTS — ECONOMIC CALENDAR  (Signal 06 independent copy)
# =============================================================================

# 2026 FOMC meeting dates — both day of announcement (published schedule)
FOMC_DATES_2026 = [
    date(2026, 1, 28),
    date(2026, 3, 18),
    date(2026, 4, 29),
    date(2026, 6, 17),
    date(2026, 7, 29),
    date(2026, 9, 16),
    date(2026, 10, 28),
    date(2026, 12, 16),
]

# CPI is released roughly on the 10th–15th of the month. Treat these as
# medium-risk days. The exact date shifts — the window covers the risk.
CPI_RISK_DAY_START = 10  # day-of-month
CPI_RISK_DAY_END   = 15  # day-of-month (inclusive)

HIGH_RISK_KEYWORDS = [
    "non-farm payrolls", "nfp", "fomc", "fed decision",
    "interest rate decision", "cpi", "inflation rate",
    "gdp", "gross domestic product", "pce price index",
    "fed chair", "powell speech",
]

MEDIUM_RISK_KEYWORDS = [
    "ism manufacturing", "retail sales", "ppi",
    "producer price index", "jobless claims", "fomc minutes",
]


# =============================================================================
# STEP 1 — DAY GATE CHECK
# =============================================================================

def check_day_gate() -> dict:
    """
    Returns dict with is_active (bool) and day info.
    Signal is ONLY active Monday–Thursday (weekday 0–3).
    """
    today   = date.today()
    dow     = today.weekday()   # 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday",
                 "Friday", "Saturday", "Sunday"]
    day_name = day_names[dow]

    # Week range: Monday → Friday of current ISO week
    monday    = today - timedelta(days=dow)
    friday    = monday + timedelta(days=4)
    week_range = f"{monday.strftime('%d %b')} – {friday.strftime('%d %b %Y')}"

    is_active = dow <= 3   # Mon–Thu

    return {
        "today":      today,
        "dow":        dow,
        "day_name":   day_name,
        "is_active":  is_active,
        "week_range": week_range,
        "monday":     monday,
        "friday":     friday,
    }


# =============================================================================
# STEP 2 — COMEX GOLD WEEKLY TREND  (W1)
# =============================================================================

def fetch_comex_trend() -> dict:
    """
    Fetch COMEX Gold (GC=F) for 10 trading days.
    Returns dict with score (0/0.5/1), bias, status, raw data.
    On any failure → DATA UNAVAILABLE.
    """
    try:
        import yfinance as yf
        df = yf.download("GC=F", period="15d", interval="1d",
                         auto_adjust=True, progress=False)

        if df is None or len(df) < 7:
            raise ValueError("Insufficient COMEX data rows")

        if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
            df.columns = df.columns.get_level_values(0)
        closes = df["Close"].dropna()
        if len(closes) < 7:
            raise ValueError("Insufficient COMEX close prices")

        comex_today   = float(closes.iloc[-1])
        comex_5d_ago  = float(closes.iloc[-6])
        comex_1d_ago  = float(closes.iloc[-2])

        change_5d = ((comex_today - comex_5d_ago) / comex_5d_ago) * 100
        change_1d = ((comex_today - comex_1d_ago) / comex_1d_ago) * 100

        log.info(f"COMEX: ${comex_today:.2f} | 5d: {change_5d:+.2f}% | 1d: {change_1d:+.2f}%")

        if change_5d >= 1.0 and change_1d >= 0:
            score = 1.0
            bias  = "BULLISH"
            status = (f"W1 ✅ COMEX GOLD RISING — {change_5d:+.2f}% over 5 days. "
                      f"Gold momentum up.")

        elif change_5d >= 0 and change_1d >= 0:
            score = 0.5
            bias  = "MILDLY BULLISH"
            status = (f"W1 ⚠️ COMEX GOLD FLAT TO MILDLY UP — {change_5d:+.2f}% over 5 days.")

        elif change_5d <= -2.0:
            score = 0.0
            bias  = "BEARISH — POTENTIAL DIP BUY"
            status = (f"W1 📉 COMEX GOLD DOWN {change_5d:+.2f}% over 5 days — "
                      f"watch for dip entry if macro supports.")

        else:
            score = 0.0
            bias  = "BEARISH"
            status = (f"W1 ❌ COMEX GOLD DECLINING — {change_5d:+.2f}% over 5 days. Caution.")

        return {
            "available":    True,
            "score":        score,
            "bias":         bias,
            "status":       status,
            "comex_today":  round(comex_today,  2),
            "change_5d":    round(change_5d,    3),
            "change_1d":    round(change_1d,    3),
        }

    except Exception as e:
        log.warning(f"COMEX fetch failed: {e}")
        return {
            "available": False,
            "score":     0.0,
            "bias":      "UNKNOWN",
            "status":    "W1: DATA UNAVAILABLE — COMEX GOLD FETCH FAILED",
        }


# =============================================================================
# STEP 3 — DXY WEEKLY TREND  (W2)
# =============================================================================

def fetch_dxy_trend() -> dict:
    """
    Fetch DXY (DX-Y.NYB) for 10 trading days.
    Inverse relationship: DXY falling = bullish for gold.
    On any failure → DATA UNAVAILABLE.
    """
    try:
        import yfinance as yf
        df = yf.download("DX-Y.NYB", period="15d", interval="1d",
                         auto_adjust=True, progress=False)

        if df is None or len(df) < 7:
            raise ValueError("Insufficient DXY data rows")

        if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
            df.columns = df.columns.get_level_values(0)
        closes = df["Close"].dropna()
        if len(closes) < 7:
            raise ValueError("Insufficient DXY close prices")

        dxy_today  = float(closes.iloc[-1])
        dxy_5d_ago = float(closes.iloc[-6])
        dxy_1d_ago = float(closes.iloc[-2])

        change_5d = ((dxy_today - dxy_5d_ago) / dxy_5d_ago) * 100
        change_1d = ((dxy_today - dxy_1d_ago) / dxy_1d_ago) * 100

        log.info(f"DXY: {dxy_today:.3f} | 5d: {change_5d:+.2f}% | 1d: {change_1d:+.2f}%")

        if change_5d <= -0.5 and change_1d <= 0:
            score = 1.0
            bias  = "BULLISH FOR GOLD"
            status = (f"W2 ✅ DXY FALLING — {change_5d:+.2f}% over 5 days. Supports gold.")

        elif change_5d <= 0:
            score = 0.5
            bias  = "MILDLY BULLISH"
            status = (f"W2 ⚠️ DXY FLAT TO MILDLY DOWN — {change_5d:+.2f}%. Mild gold support.")

        elif change_5d >= 0.5:
            score = 0.0
            bias  = "BEARISH FOR GOLD"
            status = (f"W2 ❌ DXY RISING — {change_5d:+.2f}% over 5 days. Headwind for gold.")

        else:
            score = 0.0
            bias  = "NEUTRAL"
            status = f"W2 ➡️ DXY FLAT — {change_5d:+.2f}%. No clear directional signal."

        return {
            "available": True,
            "score":     score,
            "bias":      bias,
            "status":    status,
            "dxy_today": round(dxy_today,  3),
            "change_5d": round(change_5d,  3),
            "change_1d": round(change_1d,  3),
        }

    except Exception as e:
        log.warning(f"DXY fetch failed: {e}")
        return {
            "available": False,
            "score":     0.0,
            "bias":      "UNKNOWN",
            "status":    "W2: DATA UNAVAILABLE — DXY FETCH FAILED",
        }


# =============================================================================
# STEP 4 — ECONOMIC CALENDAR  (W3)
# Uses hardcoded 2026 FOMC + dynamic NFP/CPI — no API dependency
# =============================================================================

def _get_nfp_date(year: int, month: int) -> date:
    """Return the first Friday of the given month (NFP release date)."""
    d = date(year, month, 1)
    while d.weekday() != 4:   # 4 = Friday
        d += timedelta(days=1)
    return d


def build_economic_calendar(monday: date, friday: date) -> dict:
    """
    Build a risk calendar for the week (monday → friday).
    Returns dict with risk_level, status, high_risk_events, medium_risk_events.
    """
    high_risk_events   = []
    medium_risk_events = []

    # Check each day in the week
    for offset in range(5):   # Mon=0 … Fri=4
        day = monday + timedelta(days=offset)
        day_name = ["Monday", "Tuesday", "Wednesday",
                    "Thursday", "Friday"][offset]

        # 1. FOMC date?
        if day in FOMC_DATES_2026:
            high_risk_events.append({
                "name":  "FOMC Interest Rate Decision",
                "date":  day,
                "day":   day_name,
                "time":  "02:00 AM IST (next day)",
            })

        # 2. NFP day? (first Friday of month)
        nfp = _get_nfp_date(day.year, day.month)
        if day == nfp:
            high_risk_events.append({
                "name": "Non-Farm Payrolls (NFP)",
                "date": day,
                "day":  day_name,
                "time": "6:00 PM IST",
            })

        # 3. CPI window (10th–15th of month)?
        if CPI_RISK_DAY_START <= day.day <= CPI_RISK_DAY_END:
            medium_risk_events.append({
                "name": "CPI / Inflation Data Window",
                "date": day,
                "day":  day_name,
                "time": "6:00 PM IST (approx)",
            })

    # Deduplicate (same day can't appear twice in the same list)
    seen = set()
    unique_high = []
    for e in high_risk_events:
        key = (e["name"], e["date"])
        if key not in seen:
            seen.add(key)
            unique_high.append(e)
    high_risk_events = unique_high

    # Risk classification
    if len(high_risk_events) >= 2:
        risk_level = "HIGH"
        status = (f"W3 ⚠️ HIGH RISK WEEK — {len(high_risk_events)} major events. "
                  f"Trade with caution.")
    elif len(high_risk_events) == 1:
        risk_level = "MEDIUM"
        e = high_risk_events[0]
        status = (f"W3 ⚠️ MEDIUM RISK — 1 major event "
                  f"({e['name']} on {e['day']}). Avoid holding through it.")
    elif medium_risk_events:
        risk_level = "LOW"
        status = (f"W3 ℹ️ LOW-MEDIUM RISK — {len(medium_risk_events)} medium event(s). "
                  f"Normal trading, stay alert.")
    else:
        risk_level = "LOW"
        status = "W3 ✅ LOW RISK WEEK — no major events. Normal trading conditions."

    log.info(f"Economic calendar: risk={risk_level}, "
             f"high={len(high_risk_events)}, medium={len(medium_risk_events)}")

    return {
        "available":          True,
        "risk_level":         risk_level,
        "status":             status,
        "high_risk_events":   high_risk_events,
        "medium_risk_events": medium_risk_events,
        "calendar_source":    "hardcoded_2026_fomc_nfp_cpi",
    }


# =============================================================================
# STEP 5 — WEEKLY BIAS & DAY PLAN
# =============================================================================

def calculate_weekly_bias(w1: dict, w2: dict, w3: dict) -> tuple[str, str]:
    """
    Returns (weekly_bias, week_signal).
    Bias = BULLISH / NEUTRAL / CAUTION / UNKNOWN.
    """
    # Count available + bullish
    available_factors = []
    bullish_count     = 0

    for w in [w1, w2]:
        if w["available"]:
            available_factors.append(w)
            if w["score"] >= 0.5:
                bullish_count += 1

    risk_level = w3.get("risk_level", "UNKNOWN")

    if len(available_factors) == 0:
        return "UNKNOWN", "DO NOT TRADE — ALL DATA UNAVAILABLE"

    if bullish_count >= 2 or (bullish_count >= 1 and risk_level == "LOW"):
        return "BULLISH", "ENTRY ZONE — This is a good week to look for dip entries"

    if risk_level == "HIGH":
        return "CAUTION", "HIGH RISK WEEK — Reduce position size. No new entries near event days."

    return "NEUTRAL", "WAIT — Not enough bullish signals to enter with confidence"


def build_day_plan(weekly_bias: str, w3: dict, monday: date) -> dict:
    """
    Build Monday–Friday action plan.
    Returns dict keyed by day name.
    """
    high_risk_events = w3.get("high_risk_events", [])
    high_risk_days   = {e["day"] for e in high_risk_events}

    plan = {}
    day_labels = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

    for i, day_name in enumerate(day_labels):
        day_date = monday + timedelta(days=i)

        if day_name == "Friday":
            plan[day_name] = {
                "date":          day_date,
                "action":        "NON-TRADING DAY",
                "instruction":   "Do NOT enter new positions. Hold existing with stop loss active.",
                "entry_allowed": False,
            }
            continue

        # High-risk event on this day?
        if day_name in high_risk_days:
            events_today = [e for e in high_risk_events if e["day"] == day_name]
            event_names  = ", ".join(e["name"] for e in events_today)
            plan[day_name] = {
                "date":          day_date,
                "action":        "⚠️ HIGH RISK EVENT DAY",
                "events":        events_today,
                "instruction":   (f"DO NOT enter new positions today ({event_names}). "
                                  f"If already holding, ensure stop loss is active."),
                "entry_allowed": False,
            }
            continue

        # Day-specific plan based on weekly bias
        if weekly_bias == "BULLISH":
            if day_name in ("Monday", "Tuesday"):
                plan[day_name] = {
                    "date":        day_date,
                    "action":      "PRIMARY ENTRY WINDOW",
                    "instruction": ("Look for a 0.5–1% dip from opening price. "
                                    "Set limit buy at dip. Target +2–3%."),
                    "entry_allowed": True,
                    "stop_loss":   f"-{CONFIG['stop_loss_pct']}% from entry",
                    "hold_until":  "Thursday or target hit",
                }
            elif day_name == "Wednesday":
                plan[day_name] = {
                    "date":        day_date,
                    "action":      "SECONDARY ENTRY OR HOLD",
                    "instruction": ("If no position yet and dip occurs, smaller entry allowed. "
                                    "If holding, maintain stop."),
                    "entry_allowed": True,
                    "note":        "Wednesday entry = shorter hold window (1–2 days only)",
                }
            else:   # Thursday
                plan[day_name] = {
                    "date":        day_date,
                    "action":      "LAST CHANCE / REASSESS",
                    "instruction": ("If target not hit by Thursday EOD, consider exiting flat. "
                                    "Do NOT hold into Friday."),
                    "entry_allowed": False,
                    "note":        "Thursday = reassess day. Exit if target not achieved.",
                }
        else:
            plan[day_name] = {
                "date":          day_date,
                "action":        "WAIT",
                "instruction":   "No trade today. Weekly bias not bullish or high risk present.",
                "entry_allowed": False,
            }

    return plan


# =============================================================================
# TODAY'S ACTION (convenience helper)
# =============================================================================

def get_todays_action(day_plan: dict, day_name: str) -> dict:
    """Return today's specific action from the day plan."""
    return day_plan.get(day_name, {
        "action":      "UNKNOWN",
        "instruction": "Day plan not available.",
    })


# =============================================================================
# PRINT OUTPUT
# =============================================================================

def print_signal_output(
    gate:         dict,
    w1:           dict,
    w2:           dict,
    w3:           dict,
    weekly_bias:  str,
    week_signal:  str,
    day_plan:     dict,
    ts:           str,
):
    W = 66
    line = "═" * W

    def row(text=""):
        print(f"║ {str(text)[:(W-2)].ljust(W-2)} ║")

    def sep():
        print(f"╠{line}╣")

    print(f"\n╔{line}╗")
    row("SIGNAL 06 — WEEKLY ROUTINE CHECKER")
    sep()
    active_label = "YES" if gate["is_active"] else "NO — NON-TRADING DAY"
    row(f"Date/Time  : {ts}")
    row(f"Today      : {gate['day_name']} — Signal Active: {active_label}")
    row(f"Week Of    : {gate['week_range']}")
    sep()
    row(f"W1 COMEX   : {w1['status']}")
    if w1.get("available"):
        row(f"   Raw: COMEX=${w1['comex_today']:.2f} | "
            f"5d: {w1['change_5d']:+.2f}% | 1d: {w1['change_1d']:+.2f}%")
    sep()
    row(f"W2 DXY     : {w2['status']}")
    if w2.get("available"):
        row(f"   Raw: DXY={w2['dxy_today']:.3f} | "
            f"5d: {w2['change_5d']:+.2f}% | 1d: {w2['change_1d']:+.2f}%")
    sep()
    row(f"W3 ECONOMIC: {w3['status']}")
    row(f"   Risk Level : {w3.get('risk_level', 'UNKNOWN')}")
    row(f"   Source     : {w3.get('calendar_source', 'N/A')}")

    # Print key events
    all_events = (w3.get("high_risk_events", []) +
                  w3.get("medium_risk_events", []))
    if all_events:
        row("   Key Events :")
        for e in all_events:
            row(f"     {e['day']}: {e['name']} at {e['time']}")
    else:
        row("   Key Events : None this week")

    sep()
    row(f"WEEKLY BIAS : {weekly_bias}")
    row(f"WEEK SIGNAL : {week_signal}")
    sep()
    row("DAY-BY-DAY PLAN (Mon–Fri):")
    row()

    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    for dname in day_order:
        info = day_plan.get(dname, {})
        action = info.get("action", "—")
        instr  = info.get("instruction", "")
        row(f"  {dname:<10}: {action}")
        if instr:
            # wrap long instructions
            words = instr.split()
            line_buf, lines = [], []
            for w_word in words:
                if len(" ".join(line_buf + [w_word])) > W - 16:
                    lines.append(" ".join(line_buf))
                    line_buf = [w_word]
                else:
                    line_buf.append(w_word)
            if line_buf:
                lines.append(" ".join(line_buf))
            for i, l in enumerate(lines):
                prefix = "              " if i == 0 else "              "
                row(f"{prefix}{l}")
        row()

    # Trade parameters if entry zone
    if "ENTRY ZONE" in week_signal:
        sep()
        row("TRADE PARAMETERS (ENTRY ZONE):")
        row(f"  Entry Style : Limit buy at 0.5–1% dip from open")
        row(f"  Target      : +{CONFIG['profit_target_pct']}% from entry (limit sell order)")
        row(f"  Stop Loss   : -{CONFIG['stop_loss_pct']}% from entry (stop market order)")
        row(f"  Max Hold    : Thursday EOD")

    print(f"╚{line}╝\n")


# =============================================================================
# MAIN RUNNER
# =============================================================================

def run_signal_06() -> dict:
    """
    Main entry point for Signal 06.
    Returns result dict compatible with signal_08_verdict_score.py scorer.
    """
    log.info("=" * 60)
    log.info("SIGNAL 06 — WEEKLY ROUTINE — START")
    log.info("=" * 60)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── STEP 1: Day gate ──────────────────────────────────────────────────────
    gate = check_day_gate()
    log.info(f"Day gate: {gate['day_name']} (dow={gate['dow']}) | active={gate['is_active']}")

    if not gate["is_active"]:
        log.info("Non-trading day — signal inactive")
        result = {
            "signal":      "NON-TRADING DAY",
            "confidence":  "NONE",
            "day_name":    gate["day_name"],
            "week_range":  gate["week_range"],
            "action":      ("Signal 06 inactive on Friday/weekend. "
                            "Do NOT enter new positions. "
                            "Hold existing with stop loss active."),
            "timestamp":   ts,
            "source":      "signal_06",
        }

        # Print compact box for non-trading days
        W = 66
        line = "═" * W
        print(f"\n╔{line}╗")
        print(f"║ {'SIGNAL 06 — WEEKLY ROUTINE CHECKER':<{W-2}} ║")
        print(f"╠{line}╣")
        print(f"║ {'Date/Time  : ' + ts:<{W-2}} ║")
        print(f"║ {'Today      : ' + gate['day_name'] + ' — Signal Active: NO':<{W-2}} ║")
        print(f"║ {'Week Of    : ' + gate['week_range']:<{W-2}} ║")
        print(f"╠{line}╣")
        print(f"║ {'SIGNAL: NON-TRADING DAY':<{W-2}} ║")
        print(f"║ {'ACTION : Do NOT enter new gold positions today.':<{W-2}} ║")
        print(f"║ {'         Hold existing positions with stop loss active.':<{W-2}} ║")
        print(f"╚{line}╝\n")

        return result

    # ── STEP 2: COMEX Gold trend ──────────────────────────────────────────────
    log.info("Fetching COMEX Gold trend (W1)...")
    w1 = fetch_comex_trend()

    # ── STEP 3: DXY trend ────────────────────────────────────────────────────
    log.info("Fetching DXY trend (W2)...")
    w2 = fetch_dxy_trend()

    # ── Insufficient data check ───────────────────────────────────────────────
    if not w1["available"] and not w2["available"]:
        log.warning("Both W1 and W2 failed — INSUFFICIENT DATA")
        result = {
            "signal":     "DATA UNAVAILABLE",
            "confidence": "NONE",
            "action":     "Both COMEX and DXY data unavailable. Do not trade this week.",
            "timestamp":  ts,
            "source":     "signal_06",
        }
        print(f"\n⚠️  SIGNAL 06: INSUFFICIENT DATA — DO NOT TRADE THIS WEEK\n"
              f"   W1: {w1['status']}\n"
              f"   W2: {w2['status']}\n")
        return result

    # ── STEP 4: Economic calendar ─────────────────────────────────────────────
    log.info("Building economic calendar (W3)...")
    w3 = build_economic_calendar(gate["monday"], gate["friday"])

    # ── STEP 5: Weekly bias & day plan ────────────────────────────────────────
    log.info("Calculating weekly bias...")
    weekly_bias, week_signal = calculate_weekly_bias(w1, w2, w3)

    log.info("Building day-by-day plan...")
    day_plan = build_day_plan(weekly_bias, w3, gate["monday"])

    # Today's specific action
    todays_action = get_todays_action(day_plan, gate["day_name"])

    # ── Confidence ────────────────────────────────────────────────────────────
    data_available = sum([w1["available"], w2["available"]])
    if data_available == 2:
        confidence = "HIGH"
    elif data_available == 1:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    # ── Signal label (for Signal 08 scorer) ──────────────────────────────────
    if "ENTRY ZONE" in week_signal:
        signal = "ENTRY ZONE"
    elif "HIGH RISK" in week_signal:
        signal = "HIGH RISK WEEK"
    elif "WAIT" in week_signal:
        signal = "WAIT"
    elif "DO NOT TRADE" in week_signal:
        signal = "DATA UNAVAILABLE"
    else:
        signal = "WAIT"

    # ── Print output ──────────────────────────────────────────────────────────
    print_signal_output(gate, w1, w2, w3, weekly_bias, week_signal, day_plan, ts)

    log.info(f"SIGNAL: {signal} | Bias: {weekly_bias} | Confidence: {confidence}")
    log.info("SIGNAL 06 — WEEKLY ROUTINE — END")

    return {
        "signal":         signal,
        "confidence":     confidence,
        "weekly_bias":    weekly_bias,
        "week_signal":    week_signal,
        "day_name":       gate["day_name"],
        "week_range":     gate["week_range"],
        "todays_action":  todays_action,
        "day_plan":       day_plan,
        "w1":             w1,
        "w2":             w2,
        "w3":             w3,
        "action":         todays_action.get("instruction", week_signal),
        "timestamp":      ts,
        "source":         "signal_06",
    }


# =============================================================================
# STANDALONE LAUNCHER
# =============================================================================

if __name__ == "__main__":
    result = run_signal_06()
    log.info(f"Exit signal: {result.get('signal')}")
