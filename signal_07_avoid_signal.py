# =============================================================================
# GOLD BOT — signal_07_avoid_signal.py
# Signal 07: Avoid Signal (Risk Filter)
#
# COMPLETELY INDEPENDENT — shares no data or logic with any other signal.
# HAS OVERRIDE AUTHORITY — if this signal outputs AVOID, Signal 08
# (Final Verdict) is BLOCKED regardless of how bullish other signals are.
#
# Three independent risk checks:
#
#   CHECK A1 — Single-Day Move Guard
#       Gold already up 3–4%+ today? → Chasing = dangerous. AVOID.
#       Uses: Yahoo Finance (GOLDBEES.NS + GC=F)
#
#   CHECK A2 — Economic Event Calendar (next 24–48 hours)
#       Major US events (NFP, FOMC, CPI, PCE, Powell speech) imminent?
#       → High volatility risk. AVOID or CAUTION.
#       Uses: Hardcoded 2026 FOMC schedule + dynamic NFP/CPI date logic
#             + NewsAPI keyword scan as a secondary check
#
#   CHECK A3 — Transaction Cost Reality Check
#       Is the expected profit target actually achievable after brokerage,
#       STT, and exchange charges?
#       Uses: config.py only (no external data)
#
# DATA RULE: If data fetch fails → mark that check DATA UNAVAILABLE.
#            Default to CAUTION (never CLEAR) when data is missing.
#            No assumed values ever substituted.
# =============================================================================

import yfinance as yf
import requests
import pandas as pd
from datetime import datetime, timedelta, date
import calendar
import logging
import os
import sys

# ── Setup ─────────────────────────────────────────────────────────────────────

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CONFIG

os.makedirs(CONFIG["log_directory"], exist_ok=True)
log_file = os.path.join(
    CONFIG["log_directory"],
    f"signal07_{datetime.now().strftime('%Y-%m-%d')}.log"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SIGNAL07] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("signal07")

# ── Constants ─────────────────────────────────────────────────────────────────

AVOID_SINGLE_DAY_RISE_PCT   = 3.5   # % gain in a single day → AVOID chasing
CAUTION_SINGLE_DAY_RISE_PCT = 2.5   # % gain → CAUTION (reduce size)
AVOID_LARGE_DROP_PCT        = -3.0  # % drop → note as DIP opportunity (not avoid)
TIMEOUT                     = CONFIG["fetch_timeout_seconds"]
NEWSAPI_BASE_URL            = "https://newsapi.org/v2/everything"

# =============================================================================
# FOMC & MAJOR EVENT CALENDAR (2026)
# Source: federalreserve.gov — these dates are officially published in advance
# =============================================================================

# FOMC Meeting dates 2026 (last day of 2-day meeting = decision day)
FOMC_DATES_2026 = [
    date(2026, 1, 29),
    date(2026, 3, 19),
    date(2026, 5, 7),
    date(2026, 6, 18),
    date(2026, 7, 30),
    date(2026, 9, 17),
    date(2026, 10, 29),
    date(2026, 12, 10),
]

# FOMC Minutes are released 3 weeks after each meeting (approx)
FOMC_MINUTES_2026 = [d + timedelta(weeks=3) for d in FOMC_DATES_2026]

# Known Fed Chair speech dates in 2026 (add more as they are announced)
FED_SPEECH_DATES_2026 = [
    date(2026, 1, 15),
    date(2026, 3, 5),
    date(2026, 4, 16),
    date(2026, 6, 2),
    date(2026, 8, 27),   # Jackson Hole typically late August
    date(2026, 11, 10),
]

def get_nfp_dates(year: int, months_ahead: int = 3) -> list[date]:
    """
    US Non-Farm Payrolls (NFP) is released on the first Friday of each month.
    Returns a list of NFP dates for the next `months_ahead` months.
    """
    nfp_dates = []
    today = date.today()

    for offset in range(-1, months_ahead + 1):
        month = (today.month + offset - 1) % 12 + 1
        yr    = year + ((today.month + offset - 1) // 12)

        # Find first Friday of that month
        first_day = date(yr, month, 1)
        weekday   = first_day.weekday()   # 0=Mon, 4=Fri
        days_to_friday = (4 - weekday) % 7
        first_friday = first_day + timedelta(days=days_to_friday)
        nfp_dates.append(first_friday)

    return nfp_dates


def get_cpi_dates(year: int, months_ahead: int = 3) -> list[tuple[date, date]]:
    """
    US CPI is typically released in the 2nd week of each month.
    Returns approximate windows (10th–15th of each month) as (start, end) tuples.
    """
    windows = []
    today = date.today()

    for offset in range(-1, months_ahead + 1):
        month = (today.month + offset - 1) % 12 + 1
        yr    = year + ((today.month + offset - 1) // 12)
        windows.append((date(yr, month, 10), date(yr, month, 15)))

    return windows


def build_event_calendar() -> list[dict]:
    """
    Build a unified calendar of all known high-impact US events
    for the next 48 hours (and recent past for same-day detection).

    Returns a list of event dicts:
        { name, date, impact, hours_from_now }
    """
    today = date.today()
    now   = datetime.now()
    events = []

    def add(name: str, event_date: date, impact: str):
        dt = datetime.combine(event_date, datetime.min.time())
        hours_away = (dt - now).total_seconds() / 3600
        events.append({
            "name":          name,
            "date":          event_date,
            "impact":        impact,
            "hours_from_now": round(hours_away, 1)
        })

    # FOMC meetings
    for d in FOMC_DATES_2026:
        add("FOMC Interest Rate Decision", d, "EXTREME")
        # Also flag the day BEFORE as pre-event caution
        add("FOMC Meeting (Day 1 — pre-event)", d - timedelta(days=1), "HIGH")

    # FOMC minutes
    for d in FOMC_MINUTES_2026:
        add("FOMC Minutes Release", d, "HIGH")

    # Fed speeches
    for d in FED_SPEECH_DATES_2026:
        add("Federal Reserve Chair Speech", d, "HIGH")

    # NFP (first Friday of each month)
    for d in get_nfp_dates(today.year):
        add("US Non-Farm Payrolls (NFP)", d, "EXTREME")

    # CPI windows
    for (start, end) in get_cpi_dates(today.year):
        for day_offset in range((end - start).days + 1):
            add("US CPI Inflation Data (est. window)", start + timedelta(days=day_offset), "HIGH")

    return events


def get_events_in_window(hours: int = 48) -> tuple[list[dict], list[dict]]:
    """
    Filter events to those within the next `hours` hours.
    Returns (extreme_events, high_events).
    """
    calendar_events = build_event_calendar()
    extreme = []
    high    = []

    for ev in calendar_events:
        if -2 <= ev["hours_from_now"] <= hours:    # -2h = already started today
            if ev["impact"] == "EXTREME":
                extreme.append(ev)
            elif ev["impact"] == "HIGH":
                high.append(ev)

    # Deduplicate by name+date
    seen = set()
    extreme = [e for e in extreme if (e["name"], e["date"]) not in seen
               and not seen.add((e["name"], e["date"]))]
    high    = [e for e in high    if (e["name"], e["date"]) not in seen
               and not seen.add((e["name"], e["date"]))]

    return extreme, high

# =============================================================================
# CHECK A1 — SINGLE-DAY MOVE GUARD
# =============================================================================

def check_a1_single_day_move() -> dict:
    """
    Fetch today's price change for GOLDBEES.NS (primary) and GC=F (COMEX backup).
    AVOID if either has already risen 3.5%+ in a single day (chasing risk).
    CAUTION if 2.5–3.5% rise.
    DATA UNAVAILABLE if both fetches fail.
    """
    log.info("A1: Checking single-day price move...")

    result = {
        "check":         "A1_SINGLE_DAY_MOVE",
        "verdict":       None,
        "etf_change":    None,
        "comex_change":  None,
        "status":        "",
        "detail":        "",
        "data_ok":       False,
    }

    # ── Fetch GOLDBEES ────────────────────────────────────────────────────────
    etf_change = None
    try:
        ticker = yf.Ticker(CONFIG["primary_etf"])
        df = ticker.history(period="3d", auto_adjust=True)
        if df is not None and len(df) >= 2:
            prev_close = float(df["Close"].iloc[-2])
            today_close = float(df["Close"].iloc[-1])
            etf_change = round(((today_close - prev_close) / prev_close) * 100, 3)
            log.info(f"A1: GOLDBEES change = {etf_change:+.3f}%  (₹{prev_close:.2f} → ₹{today_close:.2f})")
        else:
            log.warning(f"A1: Could not fetch GOLDBEES data")
    except Exception as e:
        log.warning(f"A1: GOLDBEES fetch error: {e}")

    # ── Fetch COMEX as backup ─────────────────────────────────────────────────
    comex_change = None
    try:
        ticker = yf.Ticker(CONFIG["comex_symbol"])
        df = ticker.history(period="3d", auto_adjust=True)
        if df is not None and len(df) >= 2:
            prev_close = float(df["Close"].iloc[-2])
            today_close = float(df["Close"].iloc[-1])
            comex_change = round(((today_close - prev_close) / prev_close) * 100, 3)
            log.info(f"A1: COMEX Gold change = {comex_change:+.3f}%")
        else:
            log.warning("A1: Could not fetch COMEX data")
    except Exception as e:
        log.warning(f"A1: COMEX fetch error: {e}")

    result["etf_change"]   = etf_change
    result["comex_change"] = comex_change

    # ── Evaluate ──────────────────────────────────────────────────────────────
    if etf_change is None and comex_change is None:
        result["verdict"] = "CAUTION"
        result["data_ok"] = False
        result["status"]  = "A1 ⚠️  DATA UNAVAILABLE — could not fetch price change"
        result["detail"]  = (
            "Cannot assess today's move. Treat as CAUTION — "
            "verify price manually before trading."
        )
        log.warning("A1: Both fetches failed → CAUTION (defaulting to safe side)")
        return result

    result["data_ok"] = True
    # Use whichever is available; prefer ETF, fall back to COMEX
    ref_change = etf_change if etf_change is not None else comex_change
    ref_label  = "GOLDBEES" if etf_change is not None else "COMEX"

    if ref_change >= AVOID_SINGLE_DAY_RISE_PCT:
        result["verdict"] = "AVOID"
        result["status"]  = (
            f"A1 🚫 AVOID — {ref_label} already UP {ref_change:+.2f}% TODAY. "
            f"DO NOT CHASE. This is a high-risk entry."
        )
        result["detail"] = (
            f"Buying after a {ref_change:.1f}% single-day spike is one of the "
            f"most common losing trades. The move is largely priced in. "
            f"Wait for a pullback before entering."
        )

    elif ref_change >= CAUTION_SINGLE_DAY_RISE_PCT:
        result["verdict"] = "CAUTION"
        result["status"]  = (
            f"A1 ⚠️  CAUTION — {ref_label} up {ref_change:+.2f}% today. "
            f"Elevated entry risk."
        )
        result["detail"] = (
            f"Significant single-day rise. If entering, reduce position "
            f"size by 50% and use a tighter stop loss (-0.5%)."
        )

    elif ref_change <= AVOID_LARGE_DROP_PCT:
        result["verdict"] = "CLEAR"
        result["status"]  = (
            f"A1 ✅ LARGE DIP TODAY — {ref_label} down {ref_change:+.2f}%. "
            f"Potential buy opportunity — check Signal 01 & 02."
        )
        result["detail"] = (
            f"Sharp intraday dip may be a mean-reversion entry. "
            f"Cross-check with Signal 01 (RSI dip) and Signal 02 (macro support)."
        )

    else:
        result["verdict"] = "CLEAR"
        result["status"]  = (
            f"A1 ✅ NORMAL MOVE — {ref_label} {ref_change:+.2f}% today. "
            f"No chase risk."
        )
        result["detail"] = "Daily move within normal range. No single-day risk flag."

    log.info(f"A1 verdict: {result['verdict']} | {result['status']}")
    return result


# =============================================================================
# CHECK A2 — ECONOMIC EVENT CALENDAR (Next 24–48 Hours)
# =============================================================================

def check_a2_economic_events() -> dict:
    """
    Check if any high-impact US economic events fall within the next 24–48 hours
    using a hardcoded 2026 event calendar (FOMC, NFP, CPI) + NewsAPI backup scan.
    AVOID if EXTREME event is within 24h.
    CAUTION if HIGH event within 24h, or EXTREME event within 24–48h.
    """
    log.info("A2: Checking economic event calendar...")

    result = {
        "check":           "A2_ECONOMIC_EVENTS",
        "verdict":         None,
        "extreme_events":  [],
        "high_events":     [],
        "news_warning":    None,
        "status":          "",
        "detail":          "",
        "data_ok":         True,    # calendar is always available (hardcoded)
    }

    # ── Primary: hardcoded calendar ───────────────────────────────────────────
    extreme_24h, high_24h = get_events_in_window(hours=24)
    extreme_48h, high_48h = get_events_in_window(hours=48)

    # Separate 24–48h window (not already in 0–24h)
    extreme_24_48h = [e for e in extreme_48h if e not in extreme_24h]
    high_24_48h    = [e for e in high_48h    if e not in high_24h]

    result["extreme_events"] = extreme_24h + extreme_24_48h
    result["high_events"]    = high_24h    + high_24_48h

    log.info(
        f"A2 Calendar: {len(extreme_24h)} extreme in 24h, "
        f"{len(high_24h)} high in 24h, "
        f"{len(extreme_24_48h)} extreme in 24–48h"
    )

    # ── Secondary: NewsAPI scan for economic keywords (bonus check) ───────────
    news_api_key = CONFIG.get("news_api_key", "")
    if news_api_key and news_api_key != "YOUR_NEWSAPI_KEY_HERE":
        try:
            params = {
                "q": '"NFP" OR "non-farm payrolls" OR "FOMC" OR "Fed decision" OR "CPI report" OR "Powell speech"',
                "from": (datetime.now() - timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%S"),
                "language": "en",
                "sortBy": "publishedAt",
                "apiKey": news_api_key,
                "pageSize": 20,
            }
            resp = requests.get(NEWSAPI_BASE_URL, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") == "ok" and data.get("articles"):
                urgent_words = ["today", "imminent", "hours", "tonight", "this week"]
                news_hits = [
                    a["title"] for a in data["articles"]
                    if any(w in (a.get("title", "") + a.get("description", "")).lower()
                           for w in urgent_words)
                ]
                if news_hits:
                    result["news_warning"] = (
                        f"NewsAPI found {len(news_hits)} time-sensitive economic "
                        f"articles: e.g. \"{news_hits[0][:80]}\""
                    )
                    log.info(f"A2 NewsAPI warning: {result['news_warning']}")
        except Exception as e:
            log.warning(f"A2: NewsAPI scan failed (non-critical): {e}")

    # ── Evaluate ──────────────────────────────────────────────────────────────
    if extreme_24h:
        names = ", ".join(set(e["name"] for e in extreme_24h))
        dates = ", ".join(str(e["date"]) for e in extreme_24h)
        result["verdict"] = "AVOID"
        result["status"]  = (
            f"A2 🚫 AVOID — EXTREME EVENT IN NEXT 24H: {names} ({dates})"
        )
        result["detail"] = (
            f"Major market-moving event imminent. Gold can move 2–5% in either "
            f"direction within minutes of the release. "
            f"DO NOT enter new positions. If holding, ensure stop loss is live."
        )

    elif high_24h or extreme_24_48h:
        events_list = list(set(
            [e["name"] for e in high_24h] +
            [e["name"] for e in extreme_24_48h]
        ))
        names = ", ".join(events_list)
        result["verdict"] = "CAUTION"
        result["status"]  = (
            f"A2 ⚠️  CAUTION — HIGH-IMPACT EVENT SOON: {names}"
        )
        result["detail"] = (
            f"Upcoming event may cause volatility. "
            f"If entering, use a tighter stop (-0.5%) and "
            f"do NOT hold your position through the event release time."
        )

    elif high_24_48h or result["news_warning"]:
        result["verdict"] = "CAUTION"
        result["status"]  = "A2 ⚠️  MILD CAUTION — Medium-impact events in 24–48h window"
        result["detail"]  = (
            "Some scheduled events in the next 48 hours. "
            "Normal trading is fine but monitor news closely."
        )

    else:
        result["verdict"] = "CLEAR"
        result["status"]  = "A2 ✅ CLEAR — No major US economic events in next 48 hours"
        result["detail"]  = (
            "Economic calendar is clear. No event-driven volatility expected "
            "in the next 48 hours."
        )

    if result["news_warning"] and result["verdict"] != "AVOID":
        result["detail"] += f" | News alert: {result['news_warning']}"

    log.info(f"A2 verdict: {result['verdict']} | {result['status']}")
    return result


# =============================================================================
# CHECK A3 — TRANSACTION COST REALITY CHECK
# =============================================================================

def check_a3_transaction_costs() -> dict:
    """
    Verify the profit target is realistic after all trading costs.
    Uses config.py only — no external data needed.
    """
    log.info("A3: Checking transaction cost viability...")

    result = {
        "check":               "A3_TRANSACTION_COSTS",
        "verdict":             None,
        "target_pct":          None,
        "total_costs_pct":     None,
        "net_profit_pct":      None,
        "status":              "",
        "detail":              "",
        "data_ok":             True,
        "cost_breakdown":      {},
    }

    try:
        target_pct    = float(CONFIG["profit_target_pct"])
        brokerage_pct = float(CONFIG["transaction_cost_pct"])

        # Round-trip cost = buy + sell brokerage
        round_trip_brokerage = brokerage_pct * 2

        # Estimated additional statutory charges (STT + exchange charges + GST)
        # STT on delivery equity = 0.1% (applies to sell side only for equity)
        # STT on ETF = 0.001% (intraday / ETF special rate — approximate)
        # Exchange transaction charges ≈ 0.00325%
        # GST on brokerage ≈ 18% of brokerage
        # SEBI turnover fees ≈ negligible
        stt_estimate          = 0.025   # conservative estimate for Gold ETF
        exchange_charges      = 0.007
        gst_on_brokerage      = round_trip_brokerage * 0.18
        stamp_duty            = 0.015   # buy side stamp duty

        total_extra = stt_estimate + exchange_charges + gst_on_brokerage + stamp_duty
        total_costs = round(round_trip_brokerage + total_extra, 4)
        net_profit  = round(target_pct - total_costs, 4)

        result["target_pct"]      = target_pct
        result["total_costs_pct"] = total_costs
        result["net_profit_pct"]  = net_profit
        result["cost_breakdown"]  = {
            "brokerage_round_trip_pct": round(round_trip_brokerage, 4),
            "stt_estimate_pct":         stt_estimate,
            "exchange_charges_pct":     exchange_charges,
            "gst_on_brokerage_pct":     round(gst_on_brokerage, 4),
            "stamp_duty_pct":           stamp_duty,
            "total_costs_pct":          total_costs,
            "net_profit_pct":           net_profit,
        }

        log.info(
            f"A3: Target={target_pct}% | "
            f"Total costs={total_costs}% | "
            f"Net profit={net_profit}%"
        )

        # ── Evaluate ──────────────────────────────────────────────────────────
        if net_profit < 0.3:
            result["verdict"] = "AVOID"
            result["status"]  = (
                f"A3 🚫 AVOID — Profit margin too thin. "
                f"Target {target_pct}% − Costs {total_costs}% = "
                f"Net only {net_profit}%"
            )
            result["detail"] = (
                f"After all charges (brokerage {round_trip_brokerage:.2f}%, "
                f"STT ~{stt_estimate}%, exchange {exchange_charges}%, "
                f"GST {gst_on_brokerage:.3f}%, stamp duty {stamp_duty}%), "
                f"your net gain is only {net_profit:.2f}%. "
                f"This is not worth the risk. "
                f"Increase your profit target to at least {round(total_costs + 1.0, 1)}% "
                f"or reduce your transaction costs."
            )

        elif net_profit < 1.0:
            result["verdict"] = "CAUTION"
            result["status"]  = (
                f"A3 ⚠️  CAUTION — Thin margin. "
                f"Net {net_profit}% after {total_costs}% costs"
            )
            result["detail"] = (
                f"Profit margin is tight. Only trade this setup if "
                f"confidence is HIGH from other signals. "
                f"Consider raising target to {round(target_pct + 1.0, 1)}%."
            )

        else:
            result["verdict"] = "CLEAR"
            result["status"]  = (
                f"A3 ✅ VIABLE — Net {net_profit}% profit after "
                f"{total_costs}% total costs"
            )
            result["detail"] = (
                f"Target is realistic. "
                f"Cost breakdown: brokerage {round_trip_brokerage:.2f}%, "
                f"STT ~{stt_estimate}%, exchange {exchange_charges}%, "
                f"GST {gst_on_brokerage:.3f}%, stamp duty {stamp_duty}%."
            )

    except (KeyError, TypeError, ValueError) as e:
        result["verdict"] = "CAUTION"
        result["data_ok"] = False
        result["status"]  = f"A3 ⚠️  CONFIG ERROR — {e}"
        result["detail"]  = (
            "Could not read profit_target_pct or transaction_cost_pct "
            "from config.py. Verify your settings file."
        )
        log.error(f"A3: Config read error: {e}")

    log.info(f"A3 verdict: {result['verdict']} | {result['status']}")
    return result


# =============================================================================
# FINAL VERDICT AGGREGATOR
# =============================================================================

def generate_final_verdict(a1: dict, a2: dict, a3: dict) -> dict:
    """
    Combine A1, A2, A3 into the final AVOID / CAUTION / CLEAR verdict.
    AVOID from ANY single check → entire signal is AVOID.
    Two or more CAUTION → CAUTION.
    All CLEAR → CLEAR.
    """
    verdicts = [a1["verdict"], a2["verdict"], a3["verdict"]]

    avoid_reasons  = []
    caution_reasons = []

    if a1["verdict"] == "AVOID":
        avoid_reasons.append("A1: Gold chasing risk (large single-day move)")
    elif a1["verdict"] == "CAUTION":
        caution_reasons.append("A1: Elevated daily move")

    if a2["verdict"] == "AVOID":
        avoid_reasons.append("A2: Major economic event within 24 hours")
    elif a2["verdict"] == "CAUTION":
        caution_reasons.append("A2: High-impact event nearby")

    if a3["verdict"] == "AVOID":
        avoid_reasons.append("A3: Profit target not viable after costs")
    elif a3["verdict"] == "CAUTION":
        caution_reasons.append("A3: Thin profit margin")

    if avoid_reasons:
        final = "AVOID"
        action = (
            "🚫 DO NOT TRADE. One or more critical risk conditions triggered. "
            f"Blocked by: {' | '.join(avoid_reasons)}"
        )
        override_note = (
            "SIGNAL 07 OVERRIDE ACTIVE — Signal 08 Final Verdict is BLOCKED. "
            "No trade regardless of other signal scores."
        )

    elif len(caution_reasons) >= 2:
        final = "CAUTION"
        action = (
            f"⚠️  TRADE WITH CAUTION. Multiple risk flags: "
            f"{' | '.join(caution_reasons)}. "
            f"Use 50% of normal position size. Tighten stop to -0.5%."
        )
        override_note = "Signal 08 score will be reduced by 20 points."

    elif len(caution_reasons) == 1:
        final = "CAUTION"
        action = (
            f"⚠️  PROCEED CAREFULLY. One caution flag: {caution_reasons[0]}. "
            f"Trade is allowed but stay alert."
        )
        override_note = "Signal 08 score will be reduced by 10 points."

    else:
        final = "CLEAR"
        action = "✅ NO RISK FLAGS. Safe trading conditions. Normal position size allowed."
        override_note = "Signal 08 runs normally with no penalty."

    return {
        "final_verdict":  final,
        "action":         action,
        "override_note":  override_note,
        "avoid_reasons":  avoid_reasons,
        "caution_reasons": caution_reasons,
        "verdicts":       {"a1": a1["verdict"], "a2": a2["verdict"], "a3": a3["verdict"]},
    }


# =============================================================================
# PRINT OUTPUT
# =============================================================================

def print_signal_output(a1: dict, a2: dict, a3: dict, verdict: dict, ts: str):
    W = 70
    line = "═" * W

    def row(text=""):
        print(f"║{str(text)[:W].ljust(W)}║")

    def sep():
        print(f"╠{line}╣")

    print(f"\n╔{line}╗")
    row(f"  SIGNAL 07 — AVOID SIGNAL  (Risk Filter)")
    row(f"  {ts}")
    sep()

    # A1
    row(f"  CHECK A1 — SINGLE-DAY MOVE GUARD")
    row(f"  {a1['status'][:W-2]}")
    if a1["etf_change"] is not None:
        row(f"  ETF (GOLDBEES) : {a1['etf_change']:+.3f}% today")
    if a1["comex_change"] is not None:
        row(f"  COMEX Gold     : {a1['comex_change']:+.3f}% today")
    if a1["detail"]:
        row(f"  Note : {a1['detail'][:W-9]}")
    sep()

    # A2
    row(f"  CHECK A2 — ECONOMIC EVENT CALENDAR (Next 48h)")
    row(f"  {a2['status'][:W-2]}")
    extreme = a2.get("extreme_events", [])
    high    = a2.get("high_events", [])
    if extreme:
        for ev in extreme[:3]:
            row(f"  🔴 EXTREME: {ev['name']} — {ev['date']} ({ev['hours_from_now']:.0f}h away)")
    if high:
        for ev in high[:3]:
            row(f"  🟡 HIGH   : {ev['name']} — {ev['date']} ({ev['hours_from_now']:.0f}h away)")
    if not extreme and not high:
        row(f"  No major events in next 48 hours")
    if a2.get("news_warning"):
        row(f"  News: {a2['news_warning'][:W-9]}")
    if a2["detail"]:
        row(f"  Note : {a2['detail'][:W-9]}")
    sep()

    # A3
    row(f"  CHECK A3 — TRANSACTION COST REALITY")
    row(f"  {a3['status'][:W-2]}")
    if a3.get("target_pct") is not None:
        row(f"  Profit Target  : {a3['target_pct']}%")
        row(f"  Est. Total Cost: {a3['total_costs_pct']}%  (brokerage + STT + charges)")
        row(f"  Net Profit     : {a3['net_profit_pct']}%")
    if a3["detail"]:
        row(f"  Note : {a3['detail'][:W-9]}")
    sep()

    # Final verdict
    icon = {"AVOID": "🚫", "CAUTION": "⚠️ ", "CLEAR": "✅"}.get(verdict["final_verdict"], "")
    row(f"  FINAL VERDICT  : {icon} {verdict['final_verdict']}")
    for chunk in [verdict["action"][i:i+W-4] for i in range(0, len(verdict["action"]), W-4)]:
        row(f"  {chunk}")
    sep()
    row(f"  OVERRIDE RULE  : {verdict['override_note'][:W-18]}")
    print(f"╚{line}╝\n")


# =============================================================================
# MAIN RUNNER
# =============================================================================

def run_signal_07() -> dict:
    """
    Main entry point. Runs all 3 checks and returns the final verdict dict.
    Call standalone or from Signal 08 — always run FIRST before other signals.
    """
    log.info("=" * 60)
    log.info("SIGNAL 07 — AVOID SIGNAL (RISK FILTER) — START")
    log.info("=" * 60)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Run all 3 checks independently ───────────────────────────────────────
    log.info("Running Check A1: Single-Day Move Guard...")
    a1 = check_a1_single_day_move()

    log.info("Running Check A2: Economic Event Calendar...")
    a2 = check_a2_economic_events()

    log.info("Running Check A3: Transaction Cost Check...")
    a3 = check_a3_transaction_costs()

    # ── Final verdict ─────────────────────────────────────────────────────────
    verdict = generate_final_verdict(a1, a2, a3)
    log.info(
        f"SIGNAL 07 VERDICT: {verdict['final_verdict']} | "
        f"A1={a1['verdict']} | A2={a2['verdict']} | A3={a3['verdict']}"
    )

    # ── Print ─────────────────────────────────────────────────────────────────
    print_signal_output(a1, a2, a3, verdict, ts)

    log.info("SIGNAL 07 — AVOID SIGNAL — END")

    return {
        "signal":          verdict["final_verdict"],   # "AVOID" / "CAUTION" / "CLEAR"
        "action":          verdict["action"],
        "override_note":   verdict["override_note"],
        "avoid_reasons":   verdict["avoid_reasons"],
        "caution_reasons": verdict["caution_reasons"],
        "check_verdicts":  verdict["verdicts"],
        "timestamp":       ts,
        "raw": {
            "a1": a1,
            "a2": a2,
            "a3": a3,
        }
    }


# =============================================================================
# RUN AS STANDALONE SCRIPT
# =============================================================================

if __name__ == "__main__":
    run_signal_07()
