# =============================================================================
# GOLD BOT — signal_12_correlation_break.py
# Signal 12: Correlation Break Alert
#
# PURPOSE:
#   Monitors four live correlations between GOLDBEES and global instruments.
#   When correlations break their historical normal range, it signals that
#   something unusual is happening — almost always preceding a large move.
#
# CORRELATIONS MONITORED:
#   C1: GOLDBEES ↔ COMEX Gold   (normal +0.85→+0.99 | break < +0.75)
#   C2: GOLDBEES ↔ DXY          (normal -0.40→-0.80 | break > -0.20)
#   C3: GOLDBEES ↔ USDINR       (normal +0.30→+0.70 | break < +0.10)
#   C4: GOLDBEES ↔ Nifty 50     (normal -0.10→-0.30 | break > +0.40 or < -0.50)
#
# SCORING (max +8 pts, min -5 pts penalty):
#   No breaks           → +5 pts  (all signals reliable, normal regime)
#   1 break — bullish   → +8 pts  (unusual alignment, extra bullish)
#   1 break — bearish   → +0 pts  (caution, reduce confidence)
#   1 break — ambiguous → +3 pts  (flag for review)
#   2+ breaks — bullish → +8 pts  (rare, very high conviction)
#   2+ breaks — bearish → -5 pts  (penalty — overrides bullish signals)
#   2+ breaks — mixed   → +0 pts  (cannot interpret)
#   DATA UNAVAILABLE    → +0 pts  (no score, no penalty)
#
# ALERT TYPES (compound break conditions):
#   A — Crisis Gold:     DXY break positive + Nifty < -0.50
#   B — Arbitrage Win:   COMEX break + GOLDBEES discount vs COMEX fair value
#   C — Liquidity Trap:  Nifty > +0.40 (both gold & stocks up = fake rally)
#   D — Risk-On Dump:    Nifty < -0.50 + gold falling
#   E — Silent Bull:     USDINR break negative + COMEX 5d > +1%
#
# CORRELATION METHOD:
#   • Daily % returns (not raw prices — avoids trend bias)
#   • 20-day rolling Pearson correlation as primary window
#   • 10-day rolling correlation as early-warning window
#   • Minimum 15 return pairs required (out of 20 possible)
#
# DATA RULE:
#   Each instrument fetched independently via yfinance.
#   Failure of any one → that correlation = DATA UNAVAILABLE, score stays at 0.
#   Failure of all → full DATA UNAVAILABLE.
#   No estimated/assumed values ever used.
#
# NON-TRADING DAY:
#   Friday + weekends → correlations computed and displayed, score = 0.
# =============================================================================

import os
import sys
import logging
import numpy as np
import pandas as pd
from datetime import datetime, date
from typing import Optional, Tuple, Dict, Any

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import CONFIG

# ── Logging ───────────────────────────────────────────────────────────────────
os.makedirs(CONFIG["log_directory"], exist_ok=True)
log_file = os.path.join(
    CONFIG["log_directory"],
    f"signal12_{datetime.now().strftime('%Y-%m-%d')}.log"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SIGNAL12] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("signal12")

# ── Constants — from config or defaults ───────────────────────────────────────
LOOKBACK_DAYS    = CONFIG.get("s12_lookback_days",       60)
ROLLING_WIN      = CONFIG.get("s12_rolling_window",      20)
EARLY_WIN        = CONFIG.get("s12_early_warning_window", 10)
MIN_DATA_PAIRS   = 15          # minimum return pairs for reliable correlation
TROY_OZ_GRAMS    = 31.1035

# Break thresholds
COMEX_BREAK      = CONFIG.get("s12_comex_break_threshold", 0.75)
DXY_BREAK        = CONFIG.get("s12_dxy_break_threshold",  -0.20)
USDINR_BREAK     = CONFIG.get("s12_usdinr_break_threshold", 0.10)
NIFTY_POS_BREAK  = CONFIG.get("s12_nifty_positive_break",   0.40)
NIFTY_NEG_BREAK  = CONFIG.get("s12_nifty_negative_break",  -0.50)

# Warning zone: halfway between normal and break
COMEX_WARN       = 0.80     # between normal 0.85 and break 0.75
DXY_WARN         = -0.30    # between normal -0.40 and break -0.20
USDINR_WARN      = 0.20     # between normal 0.30 and break 0.10
NIFTY_POS_WARN   = 0.30     # between normal -0.10 and break +0.40
NIFTY_NEG_WARN   = -0.40    # between normal -0.30 and break -0.50

# Max/penalty pts
S12_MAX_PTS      = CONFIG.get("s12_max_pts",     8)
S12_PENALTY_PTS  = CONFIG.get("s12_penalty_pts", -5)


# =============================================================================
# SECTION 1 — DATA FETCHERS
# Each instrument fetched completely independently.
# =============================================================================

def _fetch(symbol: str, label: str, days: int = LOOKBACK_DAYS) -> Optional[pd.Series]:
    """
    Fetch daily Adj Close for `symbol` over `days` trading days.
    Returns pd.Series indexed by date, or None on any failure.
    Requires at least (MIN_DATA_PAIRS + 2) rows after cleaning.
    """
    try:
        import yfinance as yf
        log.info(f"Fetching {label} ({symbol}) — last {days} days...")
        tkr = yf.Ticker(symbol)
        df  = tkr.history(period=f"{days}d", auto_adjust=True)

        if df is None or df.empty:
            log.error(f"No data returned for {symbol}")
            return None

        close = df["Close"].dropna().sort_index()

        # Normalize timezone
        close.index = pd.to_datetime(close.index).tz_localize(None).normalize()

        if len(close) < MIN_DATA_PAIRS + 2:
            log.error(f"{symbol}: only {len(close)} rows — need ≥{MIN_DATA_PAIRS + 2}")
            return None

        log.info(f"  {label}: {len(close)} rows  {close.index[-1].date()}  last={close.iloc[-1]:.4f}")
        return close

    except Exception as e:
        log.error(f"Fetch failed for {symbol} ({label}): {e}")
        return None


def fetch_goldbees() -> Optional[pd.Series]:
    return _fetch(CONFIG.get("primary_etf",    "GOLDBEES.NS"), "GOLDBEES")

def fetch_comex() -> Optional[pd.Series]:
    return _fetch(CONFIG.get("comex_symbol",   "GC=F"),        "COMEX")

def fetch_dxy() -> Optional[pd.Series]:
    return _fetch(CONFIG.get("dxy_symbol",     "DX-Y.NYB"),    "DXY")

def fetch_usdinr() -> Optional[pd.Series]:
    return _fetch(CONFIG.get("usdinr_symbol",  "USDINR=X"),    "USDINR")

def fetch_nifty() -> Optional[pd.Series]:
    return _fetch("^NSEI", "NIFTY50")


# =============================================================================
# SECTION 2 — RETURN SERIES AND CORRELATION CALCULATOR
# =============================================================================

def _pct_returns(s: pd.Series) -> pd.Series:
    """Convert price series to daily % return series. Drops NaN."""
    return s.pct_change().dropna() * 100


def _align_returns(s1: pd.Series, s2: pd.Series) -> Tuple[np.ndarray, np.ndarray]:
    """
    Align two return series on common trading dates.
    Returns (arr1, arr2) numpy arrays of the same length, or empty arrays if
    fewer than MIN_DATA_PAIRS common dates exist.
    """
    combined = pd.concat([s1, s2], axis=1, join="inner").dropna()
    if len(combined) < MIN_DATA_PAIRS:
        return np.array([]), np.array([])
    return combined.iloc[:, 0].values, combined.iloc[:, 1].values


def _pearson(a: np.ndarray, b: np.ndarray) -> Optional[float]:
    """Pearson correlation. Returns None if arrays too short or zero variance."""
    if len(a) < MIN_DATA_PAIRS:
        return None
    a_std = a.std()
    b_std = b.std()
    if a_std == 0 or b_std == 0:
        return None
    corr = np.corrcoef(a, b)[0, 1]
    # Handle rare NaN from corrcoef
    if np.isnan(corr):
        return None
    return round(float(corr), 3)


def compute_correlation(
    gb_prices: pd.Series,
    other_prices: pd.Series,
    window: int = ROLLING_WIN
) -> Tuple[Optional[float], Optional[float]]:
    """
    Compute (20-day Pearson corr, 10-day Pearson corr) between GOLDBEES and
    another instrument, using the most recent `window` return pairs.

    Returns (corr_20d, corr_10d). Either may be None if data insufficient.
    """
    gb_ret    = _pct_returns(gb_prices)
    other_ret = _pct_returns(other_prices)

    # 20-day
    a20, b20  = _align_returns(gb_ret.iloc[-window:], other_ret.iloc[-window:])
    corr_20d  = _pearson(a20, b20)

    # 10-day early warning
    a10, b10  = _align_returns(gb_ret.iloc[-EARLY_WIN:], other_ret.iloc[-EARLY_WIN:])
    corr_10d  = _pearson(a10, b10)

    return corr_20d, corr_10d


def _recent_chg(prices: pd.Series, days: int = 5) -> Optional[float]:
    """Return % change over last `days` bars, or None if insufficient data."""
    if len(prices) < days + 1:
        return None
    return round((prices.iloc[-1] - prices.iloc[-days-1]) / prices.iloc[-days-1] * 100, 3)


# =============================================================================
# SECTION 3 — CORRELATION STATUS EVALUATOR
# Determines NORMAL / WARNING / BREAK and implication (BULLISH/BEARISH/AMBIGUOUS)
# for each of the four correlation pairs.
# =============================================================================

def _status(corr: Optional[float], pair: str, gb_5d: Optional[float] = None,
            other_5d: Optional[float] = None) -> Dict[str, Any]:
    """
    Evaluate one correlation value and return a status dict:
    {
        "corr":       float | None,
        "status":     "NORMAL" | "WARNING" | "BREAK" | "DATA_UNAVAILABLE",
        "implication":"BULLISH" | "BEARISH" | "AMBIGUOUS" | "NONE",
        "color":      "green" | "yellow" | "red" | "grey",
        "note":       str,
    }
    """
    if corr is None:
        return {"corr": None, "status": "DATA_UNAVAILABLE",
                "implication": "NONE", "color": "grey",
                "note": "DATA UNAVAILABLE — insufficient trading days in common"}

    # ── COMEX ──────────────────────────────────────────────────────────────────
    if pair == "COMEX":
        if corr >= COMEX_WARN:
            return {"corr": corr, "status": "NORMAL", "implication": "NONE",
                    "color": "green",
                    "note": f"GOLDBEES tracking COMEX closely (r={corr:.2f}) — normal"}
        if corr >= COMEX_BREAK:
            return {"corr": corr, "status": "WARNING", "implication": "AMBIGUOUS",
                    "color": "yellow",
                    "note": f"Tracking weakening (r={corr:.2f}) — approaching break threshold"}
        # BREAK
        gb_5d  = gb_5d  or 0
        other_5d = other_5d or 0
        # Is GOLDBEES lagging COMEX (bullish catch-up) or leading down?
        if other_5d > 0.5 and gb_5d < other_5d - 0.5:
            impl = "BULLISH"
            note = (f"BREAK (r={corr:.2f}) — GOLDBEES lagging COMEX rally. "
                    f"COMEX +{other_5d:.1f}% but GOLDBEES only +{gb_5d:.1f}%. "
                    "ARBITRAGE WINDOW — GOLDBEES may catch up.")
        elif other_5d < -0.5 and gb_5d > other_5d + 0.5:
            impl = "BULLISH"
            note = (f"BREAK (r={corr:.2f}) — GOLDBEES holding up vs COMEX decline. "
                    "India-specific demand protecting GOLDBEES.")
        else:
            impl = "AMBIGUOUS"
            note = (f"BREAK (r={corr:.2f}) — unusual GOLDBEES/COMEX divergence. "
                    "Check for import duty change or ETF liquidity event.")
        return {"corr": corr, "status": "BREAK", "implication": impl,
                "color": "red", "note": note}

    # ── DXY ────────────────────────────────────────────────────────────────────
    if pair == "DXY":
        if corr <= DXY_WARN:
            return {"corr": corr, "status": "NORMAL", "implication": "NONE",
                    "color": "green",
                    "note": f"Normal inverse relationship with DXY (r={corr:.2f})"}
        if corr <= DXY_BREAK:
            return {"corr": corr, "status": "WARNING", "implication": "AMBIGUOUS",
                    "color": "yellow",
                    "note": f"Inverse relationship weakening (r={corr:.2f}) — watch DXY direction"}
        # BREAK (corr > -0.20, approaching 0 or positive)
        gb_5d    = gb_5d    or 0
        other_5d = other_5d or 0   # DXY 5d change
        if gb_5d > 0 and other_5d > 0:
            impl = "BULLISH"
            note = (f"BREAK (r={corr:.2f}) — Gold AND Dollar rising together. "
                    "CRISIS GOLD signal: flight-to-safety overriding normal inverse. "
                    f"GOLDBEES +{gb_5d:.1f}%, DXY +{other_5d:.1f}%.")
        elif gb_5d < 0 and other_5d < 0:
            impl = "BEARISH"
            note = (f"BREAK (r={corr:.2f}) — Gold AND Dollar falling together. "
                    "RISK-ON signal: investors selling safe havens for equities. "
                    f"GOLDBEES {gb_5d:.1f}%, DXY {other_5d:.1f}%.")
        else:
            impl = "AMBIGUOUS"
            note = (f"BREAK (r={corr:.2f}) — DXY-Gold relationship unstable. "
                    "Mixed signals — check geopolitical news.")
        return {"corr": corr, "status": "BREAK", "implication": impl,
                "color": "red", "note": note}

    # ── USDINR ─────────────────────────────────────────────────────────────────
    if pair == "USDINR":
        if corr >= USDINR_WARN:
            return {"corr": corr, "status": "NORMAL", "implication": "NONE",
                    "color": "green",
                    "note": f"Normal positive USDINR relationship (r={corr:.2f}) — INR weakness supporting gold"}
        if corr >= USDINR_BREAK:
            return {"corr": corr, "status": "WARNING", "implication": "AMBIGUOUS",
                    "color": "yellow",
                    "note": f"USDINR linkage weakening (r={corr:.2f}) — possible RBI intervention"}
        # BREAK
        gb_5d    = gb_5d    or 0
        other_5d = other_5d or 0   # USDINR 5d change (positive = rupee weaker)
        if gb_5d > 0 and other_5d < 0:
            impl = "BULLISH"
            note = (f"BREAK (r={corr:.2f}) — GOLDBEES rising despite STRONG RUPEE. "
                    "SILENT BULL: global COMEX demand overwhelming FX tailwind. "
                    f"GOLDBEES +{gb_5d:.1f}%, USDINR {other_5d:.1f}%.")
        elif gb_5d < 0 and other_5d > 0:
            impl = "BEARISH"
            note = (f"BREAK (r={corr:.2f}) — GOLDBEES NOT benefiting from rupee weakness. "
                    "Possible import duty change or GOLDBEES-specific pressure. "
                    f"GOLDBEES {gb_5d:.1f}%, USDINR +{other_5d:.1f}%.")
        else:
            impl = "AMBIGUOUS"
            note = (f"BREAK (r={corr:.2f}) — USDINR/GOLDBEES relationship unusual. "
                    "Possible RBI FX intervention or policy change.")
        return {"corr": corr, "status": "BREAK", "implication": impl,
                "color": "red", "note": note}

    # ── NIFTY ──────────────────────────────────────────────────────────────────
    if pair == "NIFTY":
        gb_5d    = gb_5d    or 0
        other_5d = other_5d or 0   # NIFTY 5d change
        # Check positive break first
        if corr > NIFTY_POS_BREAK:
            return {
                "corr": corr, "status": "BREAK", "implication": "BEARISH",
                "color": "red",
                "note": (f"BREAK (r={corr:.2f}) — GOLDBEES and Nifty co-moving UP. "
                         "LIQUIDITY TRAP: easy-money rally, not true gold demand. "
                         "Gold rise may not be sustainable when liquidity tightens.")
            }
        # Check negative break
        if corr < NIFTY_NEG_BREAK:
            if gb_5d > 0:
                impl = "BULLISH"
                note = (f"BREAK (r={corr:.2f}) — Gold up, Nifty down. "
                        "FLIGHT TO SAFETY: institutional rotation into gold. "
                        f"GOLDBEES +{gb_5d:.1f}%, Nifty {other_5d:.1f}%.")
            else:
                impl = "BEARISH"
                note = (f"BREAK (r={corr:.2f}) — Gold down, Nifty up. "
                        "RISK-ON DUMP: investors rotating from gold to equities. "
                        f"GOLDBEES {gb_5d:.1f}%, Nifty +{other_5d:.1f}%.")
            return {"corr": corr, "status": "BREAK", "implication": impl,
                    "color": "red", "note": note}
        # Positive warning zone
        if corr > NIFTY_POS_WARN:
            return {"corr": corr, "status": "WARNING", "implication": "AMBIGUOUS",
                    "color": "yellow",
                    "note": f"Nifty-Gold co-movement increasing (r={corr:.2f}) — watch for liquidity trap"}
        # Negative warning zone
        if corr < NIFTY_NEG_WARN:
            return {"corr": corr, "status": "WARNING", "implication": "AMBIGUOUS",
                    "color": "yellow",
                    "note": f"Nifty-Gold diverging unusually (r={corr:.2f}) — rotation signal forming"}
        return {"corr": corr, "status": "NORMAL", "implication": "NONE",
                "color": "green",
                "note": f"Normal low-correlation with Nifty (r={corr:.2f})"}

    return {"corr": corr, "status": "NORMAL", "implication": "NONE",
            "color": "green", "note": ""}


# =============================================================================
# SECTION 4 — COMPOUND ALERT DETECTOR
# Checks for the 5 named alert types from the plan.
# =============================================================================

def detect_alert_types(
    corr_comex: Optional[float],
    corr_dxy:   Optional[float],
    corr_usdinr: Optional[float],
    corr_nifty:  Optional[float],
    gb_prices:   Optional[pd.Series],
    comex_prices: Optional[pd.Series],
    usdinr_prices: Optional[pd.Series],
) -> list:
    """
    Returns list of detected alert type dicts:
    [{"type": "A", "label": "...", "message": "...", "severity": "HIGH"|"MEDIUM"}]
    """
    alerts = []

    gb_5d     = _recent_chg(gb_prices,     5) if gb_prices    is not None else None
    comex_5d  = _recent_chg(comex_prices,  5) if comex_prices is not None else None

    # ── Alert Type A: Crisis Gold ─────────────────────────────────────────────
    # DXY corr broken positive + Nifty strongly negative
    if (corr_dxy    is not None and corr_dxy   > DXY_BREAK and
        corr_nifty  is not None and corr_nifty < NIFTY_NEG_BREAK):
        alerts.append({
            "type":     "A",
            "label":    "CRISIS GOLD",
            "message":  (f"Gold and Dollar both rising (DXY corr={corr_dxy:.2f}) while "
                         f"Nifty falling (corr={corr_nifty:.2f}). "
                         "Classic flight-to-safety rotation into gold. "
                         "HIGH CONVICTION setup — check composite score."),
            "severity": "HIGH",
            "emoji":    "🚨"
        })

    # ── Alert Type B: Arbitrage Window ────────────────────────────────────────
    # COMEX corr broken + GOLDBEES lagging COMEX in price
    if corr_comex is not None and corr_comex < COMEX_BREAK:
        # Check if GOLDBEES is cheaper than COMEX fair value
        if (gb_prices is not None and comex_prices is not None and
                usdinr_prices is not None):
            gb_last     = float(gb_prices.iloc[-1])
            comex_last  = float(comex_prices.iloc[-1])
            usdinr_last = float(usdinr_prices.iloc[-1])
            comex_inr   = comex_last * usdinr_last / TROY_OZ_GRAMS * 10
            gb_10g      = gb_last * 1000
            premium     = (gb_10g - comex_inr) / comex_inr * 100 if comex_inr > 0 else 0
            if premium <= 1.0:
                alerts.append({
                    "type":     "B",
                    "label":    "ARBITRAGE WINDOW",
                    "message":  (f"GOLDBEES-COMEX correlation broken (r={corr_comex:.2f}) AND "
                                 f"GOLDBEES trading at {premium:+.1f}% vs COMEX fair value. "
                                 "GOLDBEES is lagging COMEX — should catch up. "
                                 "Best dip-buy value signal."),
                    "severity": "HIGH",
                    "emoji":    "⚡"
                })
        else:
            alerts.append({
                "type":     "B",
                "label":    "ARBITRAGE WINDOW (partial data)",
                "message":  (f"GOLDBEES-COMEX correlation broken (r={corr_comex:.2f}). "
                             "Cannot confirm premium — check S10 MCX spread for confirmation."),
                "severity": "MEDIUM",
                "emoji":    "⚡"
            })

    # ── Alert Type C: Liquidity Trap ──────────────────────────────────────────
    # Nifty corr strongly positive (both gold and stocks up together)
    if corr_nifty is not None and corr_nifty > NIFTY_POS_BREAK:
        alerts.append({
            "type":     "C",
            "label":    "LIQUIDITY TRAP",
            "message":  (f"GOLDBEES and Nifty both rising together (r={corr_nifty:.2f}). "
                         "This is a LIQUIDITY RALLY, not fundamental gold demand. "
                         "Gold rise may reverse when easy money tightens. "
                         "DO NOT chase — wait for real divergence."),
            "severity": "MEDIUM",
            "emoji":    "⚠️"
        })

    # ── Alert Type D: Risk-On Dump ────────────────────────────────────────────
    # Nifty strongly negative + gold falling
    if (corr_nifty is not None and corr_nifty < NIFTY_NEG_BREAK and
            gb_5d is not None and gb_5d < -0.5):
        alerts.append({
            "type":     "D",
            "label":    "RISK-ON DUMP",
            "message":  (f"Gold falling ({gb_5d:.1f}% over 5d) while Nifty correlation "
                         f"strongly negative (r={corr_nifty:.2f}). "
                         "Investors rotating FROM gold TO equities. "
                         "WAIT — risk appetite dominant. Not time to buy gold."),
            "severity": "MEDIUM",
            "emoji":    "🔴"
        })

    # ── Alert Type E: Silent Bull ─────────────────────────────────────────────
    # USDINR corr breaks negative + COMEX 5d > +1%
    if (corr_usdinr is not None and corr_usdinr < USDINR_BREAK and
            comex_5d is not None and comex_5d > 1.0 and
            gb_5d is not None and gb_5d > 0):
        alerts.append({
            "type":     "E",
            "label":    "SILENT BULL",
            "message":  (f"GOLDBEES rising ({gb_5d:.1f}% over 5d) despite rupee "
                         f"NOT weakening (USDINR corr={corr_usdinr:.2f}). "
                         f"COMEX up {comex_5d:.1f}% — global demand overwhelming FX. "
                         "VERY BULLISH: gold rising on pure demand, not currency."),
            "severity": "HIGH",
            "emoji":    "📈"
        })

    return alerts


# =============================================================================
# SECTION 5 — COMPOSITE SCORER
# Aggregates all four correlation statuses into a single signal + score.
# =============================================================================

def _classify_breaks(statuses: list) -> Tuple[int, str, str]:
    """
    Given a list of status dicts, count breaks and classify overall direction.
    Returns (n_breaks, overall_implication, score_category).
    """
    breaks = [s for s in statuses if s["status"] == "BREAK"]
    n = len(breaks)

    if n == 0:
        return 0, "NONE", "NORMAL"

    bullish  = sum(1 for b in breaks if b["implication"] == "BULLISH")
    bearish  = sum(1 for b in breaks if b["implication"] == "BEARISH")
    ambig    = sum(1 for b in breaks if b["implication"] == "AMBIGUOUS")

    if n == 1:
        imp = breaks[0]["implication"]
        if imp == "BULLISH":    return n, "BULLISH",   "1_BULLISH"
        if imp == "BEARISH":    return n, "BEARISH",   "1_BEARISH"
        return n, "AMBIGUOUS", "1_AMBIGUOUS"

    # 2+ breaks
    if bearish >= 2:            return n, "BEARISH",   "MULTI_BEARISH"
    if bullish >= 2:            return n, "BULLISH",   "MULTI_BULLISH"
    if bullish > bearish:       return n, "BULLISH",   "MULTI_BULLISH"
    if bearish > bullish:       return n, "BEARISH",   "MULTI_BEARISH"
    return n, "MIXED", "MULTI_MIXED"


def calculate_score(n_available: int, category: str) -> Tuple[float, str]:
    """
    Map break category to score and signal label.
    Returns (pts, signal_label).
    """
    if n_available == 0:
        return 0.0, "DATA UNAVAILABLE"

    table = {
        "NORMAL":       (5.0,  "NORMAL — All correlations stable"),
        "1_BULLISH":    (8.0,  "BULLISH BREAK — Extra bullish confirmation"),
        "1_BEARISH":    (0.0,  "BEARISH BREAK — Reduce confidence"),
        "1_AMBIGUOUS":  (3.0,  "AMBIGUOUS BREAK — Monitor closely"),
        "MULTI_BULLISH":(8.0,  "MULTI-BREAK BULLISH — Rare, high conviction"),
        "MULTI_BEARISH":(-5.0, "MULTI-BREAK BEARISH — PENALTY applied"),
        "MULTI_MIXED":  (0.0,  "MULTI-BREAK MIXED — Cannot interpret"),
    }
    pts, label = table.get(category, (0.0, "UNKNOWN"))
    return float(pts), label


# =============================================================================
# SECTION 6 — MAIN RUNNER
# =============================================================================

def run_signal_12() -> dict:
    """
    Main entry point for Signal 12.
    Returns a result dict compatible with Signal 08's scoring pattern.
    """
    log.info("=" * 60)
    log.info("SIGNAL 12 — CORRELATION BREAK ALERT — START")
    log.info("=" * 60)

    ts      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today   = date.today()
    weekday = today.weekday()   # 0=Mon, 4=Fri

    is_nontrading = (weekday >= 4)   # Fri, Sat, Sun
    if is_nontrading:
        log.info("Non-trading day — correlations computed but score = 0")

    # ── Step 1: Fetch all 5 instruments independently ─────────────────────────
    gb_prices     = fetch_goldbees()
    comex_prices  = fetch_comex()
    dxy_prices    = fetch_dxy()
    usdinr_prices = fetch_usdinr()
    nifty_prices  = fetch_nifty()

    availability = {
        "goldbees": gb_prices   is not None,
        "comex":    comex_prices is not None,
        "dxy":      dxy_prices   is not None,
        "usdinr":   usdinr_prices is not None,
        "nifty":    nifty_prices is not None,
    }
    log.info(f"Data availability: {availability}")

    # If GOLDBEES itself unavailable → full DATA UNAVAILABLE
    if gb_prices is None:
        log.error("GOLDBEES data unavailable — cannot compute any correlations")
        return {
            "signal":           "DATA UNAVAILABLE",
            "confidence":       "NONE",
            "score":            0,
            "timestamp":        ts,
            "is_nontrading":    is_nontrading,
            "correlations":     {},
            "breaks":           [],
            "alert_types":      [],
            "data_availability": availability,
        }

    n_available = sum(1 for v in availability.values() if v) - 1  # exclude GOLDBEES itself

    # ── Step 2: Compute 5-day price changes ───────────────────────────────────
    gb_5d     = _recent_chg(gb_prices,     5)
    comex_5d  = _recent_chg(comex_prices,  5) if comex_prices  is not None else None
    dxy_5d    = _recent_chg(dxy_prices,    5) if dxy_prices    is not None else None
    usdinr_5d = _recent_chg(usdinr_prices, 5) if usdinr_prices is not None else None
    nifty_5d  = _recent_chg(nifty_prices,  5) if nifty_prices  is not None else None

    log.info(f"5d changes — GOLDBEES:{gb_5d} COMEX:{comex_5d} DXY:{dxy_5d} "
             f"USDINR:{usdinr_5d} NIFTY:{nifty_5d}")

    # ── Step 3: Compute correlations ──────────────────────────────────────────
    def corr_pair(other_prices, label):
        if other_prices is None:
            return None, None
        c20, c10 = compute_correlation(gb_prices, other_prices, ROLLING_WIN)
        log.info(f"  {label}: 20d={c20}  10d={c10}")
        return c20, c10

    corr_comex_20,  corr_comex_10  = corr_pair(comex_prices,  "GOLDBEES-COMEX")
    corr_dxy_20,    corr_dxy_10    = corr_pair(dxy_prices,    "GOLDBEES-DXY")
    corr_usdinr_20, corr_usdinr_10 = corr_pair(usdinr_prices, "GOLDBEES-USDINR")
    corr_nifty_20,  corr_nifty_10  = corr_pair(nifty_prices,  "GOLDBEES-NIFTY")

    # ── Step 4: Evaluate each correlation status ──────────────────────────────
    st_comex  = _status(corr_comex_20,  "COMEX",  gb_5d, comex_5d)
    st_dxy    = _status(corr_dxy_20,    "DXY",    gb_5d, dxy_5d)
    st_usdinr = _status(corr_usdinr_20, "USDINR", gb_5d, usdinr_5d)
    st_nifty  = _status(corr_nifty_20,  "NIFTY",  gb_5d, nifty_5d)

    statuses = [st_comex, st_dxy, st_usdinr, st_nifty]

    # ── Step 5: Detect compound alert types ───────────────────────────────────
    alert_list = detect_alert_types(
        corr_comex_20, corr_dxy_20, corr_usdinr_20, corr_nifty_20,
        gb_prices, comex_prices, usdinr_prices
    )

    # ── Step 6: Score ──────────────────────────────────────────────────────────
    n_breaks, overall_impl, category = _classify_breaks(statuses)
    n_avail_corrs = sum(1 for s in statuses if s["status"] != "DATA_UNAVAILABLE")

    # If all correlations unavailable → DATA UNAVAILABLE
    if n_avail_corrs == 0:
        pts   = 0.0
        sig   = "DATA UNAVAILABLE"
        conf  = "NONE"
    else:
        pts, sig = calculate_score(n_avail_corrs, category)
        if n_avail_corrs < 3:
            sig  = f"PARTIAL DATA — {sig}"
            conf = "LOW"
        elif n_breaks == 0:
            conf = "HIGH"
        elif overall_impl == "BULLISH":
            conf = "HIGH"
        elif overall_impl == "BEARISH":
            conf = "HIGH"
        else:
            conf = "MEDIUM"

    # Non-trading day: score → 0 (correlations still displayed)
    score_to_return = 0.0 if is_nontrading else pts

    # ── Step 7: Regime label ──────────────────────────────────────────────────
    if is_nontrading:
        regime = "NON-TRADING DAY"
    elif n_breaks == 0:
        regime = "STANDARD (all signals reliable)"
    elif category == "MULTI_BEARISH":
        regime = "BEARISH BREAK CLUSTER"
    elif category in ("MULTI_BULLISH", "1_BULLISH"):
        # Use alert type for more specific regime label
        types = [a["type"] for a in alert_list]
        if "A" in types:   regime = "CRISIS GOLD"
        elif "B" in types: regime = "ARBITRAGE WINDOW"
        elif "E" in types: regime = "SILENT BULL"
        else:              regime = "BULLISH BREAK"
    elif category == "1_BEARISH":
        types = [a["type"] for a in alert_list]
        if "C" in types:   regime = "LIQUIDITY TRAP"
        elif "D" in types: regime = "RISK-ON DUMP"
        else:              regime = "BEARISH BREAK"
    else:
        regime = "AMBIGUOUS BREAK"

    log.info(f"Breaks: {n_breaks} | Category: {category} | Score: {score_to_return} | Regime: {regime}")
    for a in alert_list:
        log.info(f"  ALERT {a['type']}: {a['label']}")

    # ── Step 8: Build correlation detail dict for dashboard ───────────────────
    correlations = {
        "comex":  {**st_comex,  "corr_10d": corr_comex_10,  "pair": "GOLDBEES ↔ COMEX",
                   "normal_band": "+0.85 to +0.99", "break_threshold": f"< {COMEX_BREAK}"},
        "dxy":    {**st_dxy,    "corr_10d": corr_dxy_10,    "pair": "GOLDBEES ↔ DXY",
                   "normal_band": "-0.40 to -0.80", "break_threshold": f"> {DXY_BREAK}"},
        "usdinr": {**st_usdinr, "corr_10d": corr_usdinr_10, "pair": "GOLDBEES ↔ USDINR",
                   "normal_band": "+0.30 to +0.70", "break_threshold": f"< {USDINR_BREAK}"},
        "nifty":  {**st_nifty,  "corr_10d": corr_nifty_10,  "pair": "GOLDBEES ↔ NIFTY",
                   "normal_band": "-0.10 to -0.30",
                   "break_threshold": f"> {NIFTY_POS_BREAK} or < {NIFTY_NEG_BREAK}"},
    }

    # List of detected breaks (name + direction)
    breaks = [
        {
            "pair":        k,
            "corr":        v["corr"],
            "status":      v["status"],
            "implication": v["implication"],
            "note":        v["note"],
        }
        for k, v in correlations.items()
        if v["status"] == "BREAK"
    ]

    log.info("SIGNAL 12 — CORRELATION BREAK ALERT — END")

    return {
        "signal":           sig,
        "confidence":       conf,
        "score":            score_to_return,
        "raw_score":        pts,          # before non-trading day zeroing
        "regime":           regime,
        "is_nontrading":    is_nontrading,
        "n_breaks":         n_breaks,
        "overall_implication": overall_impl,
        "category":         category,
        "correlations":     correlations,
        "breaks":           breaks,
        "alert_types":      alert_list,
        "n_avail_corrs":    n_avail_corrs,
        "data_availability": availability,
        "price_changes": {
            "goldbees_5d": gb_5d,
            "comex_5d":    comex_5d,
            "dxy_5d":      dxy_5d,
            "usdinr_5d":   usdinr_5d,
            "nifty_5d":    nifty_5d,
        },
        "timestamp":        ts,
    }


# =============================================================================
# STANDALONE RUN
# =============================================================================

if __name__ == "__main__":
    result = run_signal_12()
    sig  = result.get("signal", "N/A")
    sc   = result.get("score",  0)
    reg  = result.get("regime", "N/A")
    ts   = result.get("timestamp", "")
    corrs = result.get("correlations", {})
    alerts = result.get("alert_types", [])

    print(f"\n{'='*60}")
    print(f"  SIGNAL 12 — CORRELATION BREAK ALERT")
    print(f"  {ts}")
    print(f"{'='*60}")
    print(f"\n  Signal : {sig}")
    print(f"  Score  : {sc}/8 pts")
    print(f"  Regime : {reg}")

    if corrs:
        print(f"\n  {'PAIR':<22} {'20d CORR':>9}  {'10d':>7}  STATUS")
        print(f"  {'-'*55}")
        icons = {"NORMAL": "🟢", "WARNING": "🟡", "BREAK": "🔴", "DATA_UNAVAILABLE": "⬛"}
        for k, v in corrs.items():
            c20 = f"{v['corr']:+.3f}" if v['corr'] is not None else "  N/A "
            c10 = f"{v['corr_10d']:+.3f}" if v.get('corr_10d') is not None else "  N/A "
            ico = icons.get(v['status'], "❓")
            print(f"  {v['pair']:<22} {c20:>9}  {c10:>7}  {ico} {v['status']}")

    breaks = result.get("breaks", [])
    if breaks:
        print(f"\n  BREAKS DETECTED ({len(breaks)}):")
        for b in breaks:
            print(f"    [{b['implication']}] {b['pair'].upper()}: {b['note'][:65]}")

    if alerts:
        print(f"\n  COMPOUND ALERTS:")
        for a in alerts:
            print(f"    {a['emoji']} TYPE {a['type']} — {a['label']}")
            print(f"       {a['message'][:70]}")

    print(f"\n{'='*60}\n")
