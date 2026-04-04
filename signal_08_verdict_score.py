# =============================================================================
# GOLD BOT — signal_08_verdict_score.py
# Signal 08: Final Verdict Score  (Composite Aggregator)
#
# This is the ONLY signal that calls other signals.
# Signals 01–07 remain 100% independent of each other.
#
# Execution order (hardcoded):
#   1. Signal 07 (Avoid / Risk Gate)   ← runs FIRST. AVOID = full stop.
#   2. Signal 01 (Buy the Dip)
#   3. Signal 02 (Macro Trigger)
#   4. Signal 04 (Bollinger Bands)
#   5. Signal 03 (Seasonality)         ← stub if not yet built
#   6. Signal 05 (2026 Outlook)        ← stub if not yet built
#   7. Signal 06 (Weekly Routine)      ← stub if not yet built
#   8. This file — combine & score.
#
# SCORING (max 80 pts — Signal 07 is a penalty gate, not a scorer):
#   Signal 02  Macro Trigger   →  25 pts  (most reliable)
#   Signal 01  Buy the Dip     →  15 pts
#   Signal 04  Bollinger Bands →  15 pts
#   Signal 06  Weekly Routine  →  10 pts
#   Signal 05  2026 Outlook    →  10 pts
#   Signal 03  Seasonality     →   5 pts
#
# Signal 07 Penalties:
#   AVOID   →  full block (score irrelevant)
#   CAUTION →  -20 pts
#   DATA UNAVAILABLE → -10 pts (precautionary)
#
# Verdict thresholds (after penalty):
#   >= 60  STRONG BUY
#   >= 45  BUY
#   >= 30  WATCH
#   >= 15  WAIT
#   <  15  DO NOT TRADE
# =============================================================================

import os
import sys
import logging
from datetime import datetime
from typing import Optional

# ── Setup ─────────────────────────────────────────────────────────────────────

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CONFIG

os.makedirs(CONFIG["log_directory"], exist_ok=True)
log_file = os.path.join(
    CONFIG["log_directory"],
    f"signal08_{datetime.now().strftime('%Y-%m-%d')}.log"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SIGNAL08] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("signal08")

# ── Telegram alerts (optional — graceful if not configured) ───────────────────
try:
    from telegram_alerts import send_verdict_alert as _tg_send
    _telegram_available = True
except ImportError:
    _telegram_available = False
    log.debug("telegram_alerts.py not found — Telegram alerts disabled")


# =============================================================================
# SIGNAL IMPORTERS  (safe — each wrapped in try/except)
# =============================================================================

def _load_signal_01():
    try:
        from signal_01_buy_the_dip import run_signal_01
        return run_signal_01
    except ImportError as e:
        log.error(f"Cannot import Signal 01: {e}")
        return None

def _load_signal_02():
    try:
        from signal_02_macro_trigger import run_signal_02
        return run_signal_02
    except ImportError as e:
        log.error(f"Cannot import Signal 02: {e}")
        return None

def _load_signal_03():
    try:
        from signal_03_seasonality import run_signal_03
        return run_signal_03
    except ImportError as e:
        log.error(f"Cannot import Signal 03: {e}")
        return None

def _load_signal_09():
    try:
        from signal_09_volume import run_signal_09
        return run_signal_09
    except ImportError as e:
        log.error(f"Cannot import Signal 09: {e}")
        return None

def _load_signal_10():
    try:
        from signal_10_mcx_spread import run_signal_10
        return run_signal_10
    except ImportError as e:
        log.error(f"Cannot import Signal 10: {e}")
        return None

def _load_signal_05():
    try:
        from signal_05_2026_outlook import run_signal_05
        return run_signal_05
    except ImportError as e:
        log.error(f"Cannot import Signal 05: {e}")
        return None

def _load_signal_04():
    try:
        from signal_04_bollinger_bands import run_signal_04
        return run_signal_04
    except ImportError as e:
        log.error(f"Cannot import Signal 04: {e}")
        return None

def _load_signal_06():
    try:
        from signal_06_weekly_routine import run_signal_06
        return run_signal_06
    except ImportError as e:
        log.error(f"Cannot import Signal 06: {e}")
        return None

def _load_signal_07():
    try:
        from signal_07_avoid_signal import run_signal_07
        return run_signal_07
    except ImportError as e:
        log.error(f"Cannot import Signal 07: {e}")
        return None

# ── All real signals now loaded (03, 05, 06 fully built) ──────────────────────
# Stubs below remain as FALLBACK only if the real files are missing.

def _stub_signal_03():
    """
    Signal 03 — Seasonality Play.
    Returns a live seasonality result based on the current month.
    Replace with real import once signal_03_seasonality.py is built.
    """
    from datetime import date
    month = date.today().month

    # Seasonal mapping (month → score, label)
    seasonal_map = {
        1:  (0,   "POST_HOLIDAY_LULL",       "NEUTRAL"),
        2:  (2,   "PRE_WEDDING_EARLY",        "WATCH"),
        3:  (4,   "WEDDING_SEASON",           "ACCUMULATE"),
        4:  (5,   "AKSHAYA_TRITIYA_BUILDUP",  "STRONG ACCUMULATE"),
        5:  (4,   "AKSHAYA_TRITIYA_PEAK",     "HOLD / SELL"),
        6:  (1,   "SUMMER_LULL",              "NEUTRAL"),
        7:  (5,   "MONSOON_LULL",             "ACCUMULATE"),
        8:  (5,   "MONSOON_LULL",             "ACCUMULATE"),
        9:  (3,   "PRE_NAVRATRI",             "WATCH"),
        10: (4,   "NAVRATRI_DUSSEHRA",        "HOLD"),
        11: (5,   "DHANTERAS_DIWALI",         "HOLD / SELL"),
        12: (3,   "WEDDING_SEASON_END",       "HOLD"),
    }
    score, phase, action = seasonal_map.get(month, (0, "UNKNOWN", "NEUTRAL"))
    return {
        "signal":     action,
        "confidence": "LOW" if score <= 2 else "MEDIUM",
        "score":      score,   # raw 0–5 used by scorer below
        "phase":      phase,
        "source":     "stub",
    }

def _stub_signal_05():
    """
    Signal 05 — 2026 Gold Outlook.
    Stub returns DATA UNAVAILABLE until signal_05_2026_outlook.py is built.
    """
    return {
        "signal":     "DATA UNAVAILABLE",
        "confidence": "NONE",
        "source":     "stub",
    }

def _stub_signal_06():
    """
    Signal 06 — Weekly Routine Checker.
    Stub checks if today is Mon–Thu and returns a basic timing verdict.
    Replace with real import once signal_06_weekly_routine.py is built.
    """
    from datetime import date
    dow = date.today().weekday()   # 0=Mon … 6=Sun
    if dow >= 4:   # Fri / Sat / Sun
        return {
            "signal":     "NON-TRADING DAY",
            "confidence": "NONE",
            "source":     "stub",
        }
    # Mon–Thu: return ENTRY ZONE as a stub pass-through
    return {
        "signal":     "ENTRY ZONE",
        "confidence": "MEDIUM",
        "source":     "stub",
    }


# =============================================================================
# PER-SIGNAL SCORERS
# =============================================================================

def score_signal_01(result: dict) -> tuple[float, float, str]:
    """Returns (points_earned, max_points, note)."""
    MAX = 15.0
    sig = result.get("signal", "DATA UNAVAILABLE")
    conf = result.get("confidence", "NONE")
    sc = result.get("score", 0)   # raw 0–4 from S01

    if "DATA UNAVAILABLE" in sig or "CALC" in sig:
        return 0, MAX, "S01 ⬛ DATA UNAVAILABLE — 0/15 pts"

    if sig == "BUY" and conf == "HIGH":
        pts = 15
        note = f"S01 ✅ BUY (HIGH, score={sc:.1f}/4) — {pts}/15 pts"
    elif sig == "BUY" and conf == "MEDIUM":
        pts = 10
        note = f"S01 ✅ BUY (MEDIUM, score={sc:.1f}/4) — {pts}/15 pts"
    elif sig == "WATCH":
        pts = 5
        note = f"S01 ⚠️  WATCH (score={sc:.1f}/4) — {pts}/15 pts"
    else:
        pts = 0
        note = f"S01 ❌ {sig} (score={sc:.1f}/4) — 0/15 pts"

    return float(pts), MAX, note


def score_signal_02(result: dict) -> tuple[float, float, str]:
    """Returns (points_earned, max_points, note)."""
    MAX = 25.0
    sig  = result.get("signal", "DATA UNAVAILABLE")
    conf = result.get("confidence", "NONE")
    bull = result.get("factors_bullish", 0)
    avail = result.get("factors_available", 0)

    if "DATA UNAVAILABLE" in sig or "INSUFFICIENT" in sig:
        return 0, MAX, "S02 ⬛ DATA UNAVAILABLE — 0/25 pts"

    if sig == "STRONG BUY" and bull >= 4:
        pts = 25
    elif sig == "STRONG BUY":
        pts = 22
    elif sig == "BUY" and conf == "MEDIUM":
        pts = 16
    elif sig == "WATCH":
        pts = 5
    else:
        pts = 0

    note = f"S02 {'✅' if pts > 0 else '❌'} {sig} ({bull}/{avail} factors bullish) — {pts}/25 pts"
    return float(pts), MAX, note


def score_signal_03(result: dict) -> tuple[float, float, str]:
    """Returns (points_earned, max_points, note)."""
    MAX = 5.0
    sig   = result.get("signal", "NEUTRAL")
    phase = result.get("phase", "UNKNOWN")
    raw   = result.get("score", 0)   # stub provides 0–5

    if "DATA UNAVAILABLE" in sig:
        return 0, MAX, "S03 ⬛ DATA UNAVAILABLE — 0/5 pts"

    # Map raw stub score (0–5) directly to points (0–5)
    pts = min(float(raw), MAX)

    if pts >= 4:
        note = f"S03 ✅ SEASONAL BUY — {phase} — {pts:.0f}/5 pts"
    elif pts >= 2:
        note = f"S03 ⚠️  SEASONAL NEUTRAL — {phase} — {pts:.0f}/5 pts"
    else:
        note = f"S03 ❌ SEASONAL SELL/LULL — {phase} — {pts:.0f}/5 pts"

    return pts, MAX, note


def score_signal_04(result: dict) -> tuple[float, float, str]:
    """Returns (points_earned, max_points, note)."""
    MAX = 15.0
    sig  = result.get("signal", "DATA UNAVAILABLE")
    conf = result.get("confidence", "NONE")
    zone = result.get("zone", "MID_BAND")

    if "DATA UNAVAILABLE" in sig:
        return 0, MAX, "S04 ⬛ DATA UNAVAILABLE — 0/15 pts"

    if sig == "SELL / TAKE PROFIT":
        return 0, MAX, f"S04 📤 SELL SIGNAL (at upper band) — 0/15 pts | EXIT if holding"

    if sig == "APPROACHING TARGET":
        return 0, MAX, f"S04 📤 NEAR UPPER BAND — 0/15 pts | Tighten stop"

    if sig == "WAIT — SQUEEZE ACTIVE":
        return 0, MAX, f"S04 ⚡ SQUEEZE ACTIVE — 0/15 pts | Wait for breakout direction"

    if sig == "STRONG BUY" and conf == "HIGH":
        pts = 15
    elif sig == "STRONG BUY" and conf == "MEDIUM":
        pts = 12
    elif sig == "BUY" and conf in ("HIGH", "MEDIUM"):
        pts = 10
    elif sig == "WATCH":
        pts = 4
    else:
        pts = 0

    note = f"S04 {'✅' if pts > 0 else '❌'} {sig} ({zone}) — {pts}/15 pts"
    return float(pts), MAX, note


def score_signal_05(result: dict) -> tuple[float, float, str]:
    """Returns (points_earned, max_points, note)."""
    MAX = 10.0
    sig = result.get("signal", "DATA UNAVAILABLE")

    if "DATA UNAVAILABLE" in sig or "INSUFFICIENT" in sig:
        return 0, MAX, "S05 ⬛ DATA UNAVAILABLE (stub) — 0/10 pts"

    map_ = {
        "STRONGLY BULLISH": 10,
        "BULLISH":           7,
        "NEUTRAL":           4,
        "MILDLY BEARISH":    0,
        "BEARISH":           0,
    }
    pts = float(map_.get(sig, 0))
    note = f"S05 {'✅' if pts >= 7 else ('⚠️ ' if pts >= 4 else '❌')} 2026 OUTLOOK: {sig} — {pts:.0f}/10 pts"
    return pts, MAX, note


def score_signal_09(result: dict) -> tuple[float, float, str]:
    """Returns (points_earned, max_points, note). Signal 09 — Volume Confirmation."""
    MAX = 10.0
    sig  = result.get("signal", "DATA UNAVAILABLE")
    sc   = result.get("score",  0)

    if "DATA UNAVAILABLE" in sig:
        return 0, MAX, "S09 ⬛ DATA UNAVAILABLE — 0/10 pts"

    if "STRONG VOLUME BUY" in sig:
        pts  = 10
        note = f"S09 ✅✅ STRONG VOLUME BUY (score={sc}/10) — {pts}/10 pts"
    elif "VOLUME BUY" in sig:
        pts  = 7
        note = f"S09 ✅ VOLUME BUY (score={sc}/10) — {pts}/10 pts"
    elif "WATCH" in sig:
        pts  = 3
        note = f"S09 ⚠️  VOLUME WATCH (score={sc}/10) — {pts}/10 pts"
    else:
        pts  = 0
        note = f"S09 ❌ VOLUME CAUTION (score={sc}/10) — 0/10 pts"

    return float(pts), MAX, note


def score_signal_10(result: dict) -> tuple[float, float, str]:
    """Returns (points_earned, max_points, note). Signal 10 — MCX-COMEX Spread."""
    MAX = 5.0
    sig = result.get("signal", "DATA UNAVAILABLE")
    sc  = result.get("score",  0)

    if "DATA UNAVAILABLE" in sig:
        return 0, MAX, "S10 ⬛ DATA UNAVAILABLE — 0/5 pts"

    if "DISCOUNT" in sig:
        pts  = 5
        note = f"S10 ✅✅ MCX DISCOUNT — strong entry value — {pts}/5 pts"
    elif "FAIR VALUE" in sig:
        pts  = 5
        note = f"S10 ✅ MCX FAIR VALUE — good entry — {pts}/5 pts"
    elif "MILD PREMIUM" in sig or "WATCH" in sig:
        pts  = 2
        note = f"S10 ⚠️  MCX MILD PREMIUM — reduce size — {pts}/5 pts"
    else:
        pts  = 0
        note = f"S10 ❌ MCX OVERPRICED — avoid entry — 0/5 pts"

    return float(pts), MAX, note


def score_signal_06(result: dict) -> tuple[float, float, str]:
    """Returns (points_earned, max_points, note)."""
    MAX = 10.0
    sig = result.get("signal", "DATA UNAVAILABLE")

    if sig == "NON-TRADING DAY":
        return 0, MAX, "S06 🚫 NON-TRADING DAY (Fri/Sat/Sun) — 0/10 pts | No new entries"
    if "DATA UNAVAILABLE" in sig:
        return 0, MAX, "S06 ⬛ DATA UNAVAILABLE — 0/10 pts"

    map_ = {
        "ENTRY ZONE":     10,
        "WAIT":            5,
        "HIGH RISK WEEK":  0,
        "CAUTION WEEK":    2,
    }
    pts = float(map_.get(sig, 0))
    note = f"S06 {'✅' if pts >= 7 else ('⚠️ ' if pts >= 3 else '❌')} WEEKLY: {sig} — {pts:.0f}/10 pts"
    return pts, MAX, note


# =============================================================================
# SIGNAL 07 PENALTY CALCULATOR
# =============================================================================

def calculate_s07_penalty(result: dict) -> tuple[float, str, bool]:
    """
    Returns (penalty_points, note, is_blocked).
    is_blocked=True means AVOID was triggered → entire verdict is blocked.
    """
    sig = result.get("signal", "DATA UNAVAILABLE")

    if sig == "AVOID":
        reasons = " | ".join(result.get("avoid_reasons", ["Unknown reason"]))
        return 0, f"S07 🚫 AVOID — TRADE BLOCKED ({reasons})", True

    if sig == "CAUTION":
        reasons = " | ".join(result.get("caution_reasons", []))
        return 20.0, f"S07 ⚠️  CAUTION — penalty -20 pts ({reasons})", False

    if "DATA UNAVAILABLE" in sig or result.get("signal") is None:
        return 10.0, "S07 ⬛ DATA UNAVAILABLE — precautionary -10 pts penalty", False

    return 0.0, "S07 ✅ CLEAR — no penalty", False


# =============================================================================
# VERDICT CALCULATOR
# =============================================================================

def calculate_verdict(final_score: float, is_nontrading: bool) -> tuple[str, str, str]:
    """
    Convert numeric score to signal, confidence, action text.
    Returns (signal, confidence, action).
    """
    if is_nontrading:
        return (
            "NON-TRADING DAY",
            "NONE",
            "Friday / weekend — do NOT enter new positions. "
            "Hold existing positions with stop loss active.",
        )

    if final_score >= 60:
        return (
            "STRONG BUY 🟢",
            "VERY HIGH",
            "All major signals aligned. Enter full planned position. "
            "Set limit sell at +3% and stop at -1% immediately after entry.",
        )
    elif final_score >= 45:
        return (
            "BUY 🟢",
            "HIGH",
            "Good signal alignment. Enter with 75–100% of planned size. "
            "Target +3%, stop -1%.",
        )
    elif final_score >= 30:
        return (
            "WATCH 🟡",
            "MEDIUM",
            "Partial signal alignment. Enter 50% of planned size only. "
            "Wait for one more confirmation before adding.",
        )
    elif final_score >= 15:
        return (
            "WAIT 🟡",
            "LOW",
            "Insufficient signal alignment. Do not enter today. "
            "Re-run tomorrow or after a macro development.",
        )
    else:
        return (
            "DO NOT TRADE 🔴",
            "NONE",
            "No meaningful signal alignment. Stay in cash. "
            "Wait for conditions to improve.",
        )


# =============================================================================
# SCORE BAR RENDERER
# =============================================================================

def render_score_bar(score: float, max_score: float = 80.0, width: int = 40) -> str:
    """Render a simple ASCII progress bar for the score."""
    pct = min(score / max_score, 1.0)
    filled = int(pct * width)
    empty  = width - filled
    bar = "█" * filled + "░" * empty
    return f"[{bar}] {score:.1f}/{max_score:.0f}"


# =============================================================================
# PRINT OUTPUT
# =============================================================================

def print_verdict_output(
    scores: list[tuple[float, float, str]],
    s07_penalty: float,
    s07_note: str,
    raw_score: float,
    final_score: float,
    signal: str,
    confidence: str,
    action: str,
    ts: str,
    entry_price: Optional[float],
    target_price: Optional[float],
    stop_price: Optional[float],
    sell_alert: Optional[str],
    **kwargs,
):
    W = 70
    line = "═" * W

    def row(text=""):
        print(f"║{str(text)[:W].ljust(W)}║")

    def sep():
        print(f"╠{line}╣")

    print(f"\n╔{line}╗")
    row(f"  SIGNAL 08 — GOLD BOT FINAL VERDICT")
    row(f"  {ts}")
    sep()
    row(f"  SIGNAL SCORES")
    row()
    for (pts, mx, note) in scores:
        row(f"  {note}")
    row()
    row(f"  {s07_note}")
    sep()
    row(f"  Raw Score (before penalty) : {raw_score:.1f} / 80.0")
    row(f"  S07 Penalty                : -{s07_penalty:.1f} pts")
    row(f"  FINAL SCORE                : {final_score:.1f} / 80.0")
    row(f"  {render_score_bar(final_score)}")
    sep()
    row(f"  VERDICT    : {signal}")
    row(f"  CONFIDENCE : {confidence}")
    # wrap action
    for chunk in [action[i:i+W-4] for i in range(0, len(action), W-4)]:
        row(f"  {chunk}")

    if sell_alert:
        sep()
        row(f"  ⚡ EXIT ALERT: {sell_alert[:W-18]}")

    if entry_price and "BUY" in signal:
        sep()
        row(f"  ── TRADE PARAMETERS ────────────────────────────────────")
        row(f"  ETF          : {CONFIG['primary_etf']}")
        row(f"  Entry Price  : ₹{entry_price}")
        row(f"  Target (+{CONFIG['profit_target_pct']}%) : ₹{target_price}")
        row(f"  Stop  (-{CONFIG['stop_loss_pct']}%)  : ₹{stop_price}")
        row(f"  Hold Period  : 1–5 trading days (exit by Thursday if Mon entry)")

    # Trailing stop section (only if holding a position)
    ts_result = kwargs.get("trailing_stop_result", {})
    if ts_result and ts_result.get("active"):
        sep()
        row(f"  ── TRAILING STOP MANAGER ───────────────────────────────")
        row(f"  {ts_result.get('emoji','')} {ts_result.get('phase','')}")
        row(f"  Entry        : ₹{ts_result.get('entry_price')}")
        row(f"  Current      : ₹{ts_result.get('current_price')}")
        row(f"  Gain         : {ts_result.get('gain_pct',0):+.2f}%")
        row(f"  Trail Stop   : ₹{ts_result.get('stop_price')}")
        for chunk in [ts_result['action'][i:i+W-4] for i in range(0, len(ts_result['action']), W-4)]:
            row(f"  → {chunk}")

    sep()
    row(f"  SCORE GUIDE: >=60 STRONG BUY | >=45 BUY | >=30 WATCH | >=15 WAIT | <15 NO TRADE")
    print(f"╚{line}╝\n")


# =============================================================================
# TRAILING STOP CALCULATOR
# Activates only when you are holding a position (CONFIG["holding_entry_price"])
# Logic:
#   Phase 1 — below +1.5% gain  : use fixed stop at -1% from entry (protect capital)
#   Phase 2 — +1.5% to +2.5%   : move stop to breakeven (entry price) — risk-free
#   Phase 3 — above +2.5%       : trail stop at 50% of peak gain (lock in profit)
#   Phase 4 — above target      : trail stop at 75% of peak gain (maximise exit)
# =============================================================================

def calculate_trailing_stop(current_price: Optional[float]) -> dict:
    """
    Calculates trailing stop recommendation based on holding position.
    Reads CONFIG["holding_entry_price"] (0 or missing = not holding).
    Returns dict with action, stop_price, gain_pct, phase.
    """
    holding_price = float(CONFIG.get("holding_entry_price", 0) or 0)

    if holding_price <= 0:
        return {
            "active":   False,
            "message":  "No position held. Set CONFIG['holding_entry_price'] when you buy.",
            "phase":    "NOT_HOLDING",
        }

    if not current_price or current_price <= 0:
        return {
            "active":   True,
            "message":  "Holding detected but current price unavailable — check stop manually.",
            "phase":    "PRICE_UNAVAILABLE",
            "entry":    holding_price,
        }

    gain_pct    = ((current_price - holding_price) / holding_price) * 100
    profit_target = CONFIG.get("profit_target_pct", 3.0)
    stop_loss_pct = CONFIG.get("stop_loss_pct",     1.0)

    # Phase 1: loss or tiny gain — fixed stop at -stop_loss_pct%
    if gain_pct < 1.5:
        phase     = "PHASE 1 — PROTECT CAPITAL"
        stop      = round(holding_price * (1 - stop_loss_pct / 100), 2)
        action    = f"Hold. Fixed stop at ₹{stop} (-{stop_loss_pct}% from entry). No adjustment yet."
        emoji     = "🔵"

    # Phase 2: +1.5% to +2.5% — move stop to breakeven
    elif gain_pct < 2.5:
        phase     = "PHASE 2 — BREAKEVEN STOP"
        stop      = round(holding_price * 1.001, 2)    # tiny buffer above entry
        action    = f"Move stop to ₹{stop} (breakeven + 0.1%). Trade is now RISK-FREE."
        emoji     = "🟡"

    # Phase 3: +2.5% to target — trail at 50% of peak gain
    elif gain_pct < profit_target:
        trail_pct = gain_pct * 0.50
        stop      = round(current_price * (1 - trail_pct / 100), 2)
        phase     = "PHASE 3 — TRAIL 50% OF GAIN"
        action    = (f"Trail stop to ₹{stop} (50% of {gain_pct:.1f}% gain locked). "
                     f"Let winner run toward ₹{round(holding_price*(1+profit_target/100),2)} target.")
        emoji     = "🟢"

    # Phase 4: above target — trail tightly at 75% of peak gain
    else:
        trail_pct = gain_pct * 0.75
        stop      = round(current_price * (1 - trail_pct / 100), 2)
        phase     = "PHASE 4 — TIGHT TRAIL (TARGET HIT)"
        action    = (f"TARGET REACHED! Trail stop to ₹{stop} (75% of {gain_pct:.1f}% gain locked). "
                     f"Consider full exit or partial profit booking.")
        emoji     = "🏆"

    log.info(f"Trailing Stop: {phase} | Gain={gain_pct:+.2f}% | Stop=₹{stop}")

    return {
        "active":        True,
        "phase":         phase,
        "emoji":         emoji,
        "entry_price":   holding_price,
        "current_price": current_price,
        "gain_pct":      round(gain_pct, 2),
        "stop_price":    stop,
        "action":        action,
    }


# =============================================================================
# MAIN RUNNER
# =============================================================================

def run_signal_08() -> dict:
    """
    Main entry point for the Gold Bot Final Verdict.
    Runs all signals in order, scores them, and produces the composite verdict.
    """
    log.info("=" * 60)
    log.info("SIGNAL 08 — FINAL VERDICT — START")
    log.info("=" * 60)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── STEP 1: Signal 07 — Risk gate (runs FIRST) ────────────────────────────
    log.info("Running Signal 07 (Avoid / Risk Gate)...")
    run_s07 = _load_signal_07()
    if run_s07:
        r07 = run_s07()
    else:
        log.warning("Signal 07 not importable — treating as DATA UNAVAILABLE")
        r07 = {"signal": "DATA UNAVAILABLE"}

    s07_penalty, s07_note, is_blocked = calculate_s07_penalty(r07)

    if is_blocked:
        # Hard stop — don't even run other signals
        log.warning("SIGNAL 07 AVOID TRIGGERED — TRADE BLOCKED")
        print(f"\n{'🚫'*35}")
        print(f"  SIGNAL 08: TRADE BLOCKED BY SIGNAL 07 (AVOID)")
        print(f"  {r07.get('action', 'Risk condition triggered.')}")
        print(f"{'🚫'*35}\n")
        blocked_result = {
            "signal":        "DO NOT TRADE — BLOCKED",
            "confidence":    "NONE",
            "final_score":   0,
            "blocked_by":    "SIGNAL_07_AVOID",
            "reason":        r07.get("avoid_reasons", []),
            "avoid_reasons": r07.get("avoid_reasons", []),
            "action":        r07.get("action", "Risk condition triggered. Do not trade."),
            "timestamp":     ts,
            "signal_scores": {},
        }
        # ── Telegram: send AVOID alert ─────────────────────────────────────
        if _telegram_available:
            _tg_send(blocked_result)
        return blocked_result

    # ── STEP 2: Run all scoring signals ───────────────────────────────────────
    log.info("Running Signal 01 (Buy the Dip)...")
    run_s01 = _load_signal_01()
    r01 = run_s01() if run_s01 else {"signal": "DATA UNAVAILABLE", "confidence": "NONE", "score": 0}

    log.info("Running Signal 02 (Macro Trigger)...")
    run_s02 = _load_signal_02()
    r02 = run_s02() if run_s02 else {"signal": "DATA UNAVAILABLE", "confidence": "NONE"}

    log.info("Running Signal 04 (Bollinger Bands)...")
    run_s04 = _load_signal_04()
    r04 = run_s04() if run_s04 else {"signal": "DATA UNAVAILABLE", "confidence": "NONE"}

    log.info("Running Signal 03 (Seasonality)...")
    run_s03 = _load_signal_03()
    r03 = run_s03() if run_s03 else _stub_signal_03()

    log.info("Running Signal 05 (2026 Outlook)...")
    run_s05 = _load_signal_05()
    r05 = run_s05() if run_s05 else _stub_signal_05()

    log.info("Running Signal 06 (Weekly Routine)...")
    run_s06 = _load_signal_06()
    r06 = run_s06() if run_s06 else _stub_signal_06()

    log.info("Running Signal 09 (Volume Confirmation)...")
    run_s09 = _load_signal_09()
    r09 = run_s09() if run_s09 else {"signal": "DATA UNAVAILABLE", "confidence": "NONE", "score": 0}

    log.info("Running Signal 10 (MCX-COMEX Spread)...")
    run_s10 = _load_signal_10()
    r10 = run_s10() if run_s10 else {"signal": "DATA UNAVAILABLE", "confidence": "NONE", "score": 0}

    # ── STEP 3: Score each signal ─────────────────────────────────────────────
    s01_pts, s01_max, s01_note = score_signal_01(r01)
    s02_pts, s02_max, s02_note = score_signal_02(r02)
    s03_pts, s03_max, s03_note = score_signal_03(r03)
    s04_pts, s04_max, s04_note = score_signal_04(r04)
    s05_pts, s05_max, s05_note = score_signal_05(r05)
    s06_pts, s06_max, s06_note = score_signal_06(r06)
    s09_pts, s09_max, s09_note = score_signal_09(r09)
    s10_pts, s10_max, s10_note = score_signal_10(r10)

    scores = [
        (s01_pts, s01_max, s01_note),
        (s02_pts, s02_max, s02_note),
        (s03_pts, s03_max, s03_note),
        (s04_pts, s04_max, s04_note),
        (s05_pts, s05_max, s05_note),
        (s06_pts, s06_max, s06_note),
        (s09_pts, s09_max, s09_note),
        (s10_pts, s10_max, s10_note),
    ]

    log.info(
        f"Scores: S01={s01_pts} S02={s02_pts} S03={s03_pts} "
        f"S04={s04_pts} S05={s05_pts} S06={s06_pts} "
        f"S09={s09_pts} S10={s10_pts}"
    )

    # ── STEP 4: Calculate final score ─────────────────────────────────────────
    raw_score   = s01_pts + s02_pts + s03_pts + s04_pts + s05_pts + s06_pts + s09_pts + s10_pts
    final_score = max(0.0, raw_score - s07_penalty)

    log.info(
        f"Raw={raw_score:.1f} | S07 penalty={s07_penalty:.1f} | Final={final_score:.1f}"
    )

    # ── STEP 5: Non-trading day cap ───────────────────────────────────────────
    is_nontrading = "NON-TRADING" in r06.get("signal", "")
    if is_nontrading:
        final_score = min(final_score, 20.0)
        log.info("Non-trading day: score capped at 20")

    # ── STEP 6: Verdict ───────────────────────────────────────────────────────
    signal, confidence, action = calculate_verdict(final_score, is_nontrading)

    # ── STEP 7: Sell alert (if Bollinger says exit) ───────────────────────────
    sell_alert = None
    s04_sig = r04.get("signal", "")
    if s04_sig in ("SELL / TAKE PROFIT", "APPROACHING TARGET"):
        sell_alert = (
            f"Signal 04 Bollinger Bands says {s04_sig}. "
            f"If you are holding a position, consider exiting now."
        )

    # ── STEP 8: Entry levels (from whichever signal has a live price) ─────────
    entry_price  = None
    target_price = None
    stop_price   = None

    if "BUY" in signal:
        # Try S01 first, then S04
        for r in [r01, r04]:
            if r.get("current_price"):
                p = float(r["current_price"])
                entry_price  = round(p, 2)
                target_price = round(p * (1 + CONFIG["profit_target_pct"] / 100), 2)
                stop_price   = round(p * (1 - CONFIG["stop_loss_pct"]   / 100), 2)
                break

    # ── STEP 8b: Trailing Stop Calculator ────────────────────────────────────
    # If you are ALREADY holding a position, pass your entry price via config
    # CONFIG["holding_entry_price"] = <your buy price>  (set 0 or omit if not holding)
    trailing_stop_result = calculate_trailing_stop(entry_price)


    # ── STEP 9: Print ─────────────────────────────────────────────────────────
    print_verdict_output(
        scores, s07_penalty, s07_note,
        raw_score, final_score,
        signal, confidence, action,
        ts, entry_price, target_price, stop_price,
        sell_alert,
        trailing_stop_result=trailing_stop_result,
    )

    log.info(f"FINAL VERDICT: {signal} | Score: {final_score:.1f}/80 | Confidence: {confidence}")
    log.info("SIGNAL 08 — FINAL VERDICT — END")

    result = {
        "signal":               signal,
        "confidence":           confidence,
        "final_score":          final_score,
        "raw_score":            raw_score,
        "s07_penalty":          s07_penalty,
        "action":               action,
        "sell_alert":           sell_alert,
        "entry_price":          entry_price,
        "target_price":         target_price,
        "stop_price":           stop_price,
        "trailing_stop":        trailing_stop_result,
        "timestamp":            ts,
        "signal_scores": {
            "s01": {"pts": s01_pts, "max": s01_max},
            "s02": {"pts": s02_pts, "max": s02_max},
            "s03": {"pts": s03_pts, "max": s03_max},
            "s04": {"pts": s04_pts, "max": s04_max},
            "s05": {"pts": s05_pts, "max": s05_max},
            "s06": {"pts": s06_pts, "max": s06_max},
            "s09": {"pts": s09_pts, "max": s09_max},
            "s10": {"pts": s10_pts, "max": s10_max},
            "s07_penalty": s07_penalty,
        },
    }

    # ── STEP 10: Telegram alert ───────────────────────────────────────────────
    if _telegram_available:
        ok = _tg_send(result)
        log.info(f"Telegram alert dispatched: {ok}")

    return result


# =============================================================================
# RUN AS STANDALONE
# =============================================================================

if __name__ == "__main__":
    run_signal_08()
