# =============================================================================
# GOLD BOT — signal_04_bollinger_bands.py
# Signal 04: Bollinger Bands Range Trading
#
# COMPLETELY INDEPENDENT — shares no data or logic with any other signal.
#
# Logic:
#   Step 1  — Fetch 30+ days of GOLDBEES.NS OHLCV
#   Step 2  — Calculate 20-period Bollinger Bands (2 standard deviations)
#   Step 3  — Calculate %B  (0 = lower band, 1 = upper band)
#   Step 4  — Calculate Bandwidth  (volatility gauge)
#   Step 5  — Detect Bollinger Squeeze (low bandwidth → breakout incoming)
#   Step 6  — Determine market state (Ranging / Mild Trend / Strong Trend)
#   Step 7  — Generate BUY / SELL / HOLD / WAIT signal
#   Step 8  — Compute entry, target 1 (mid band), target 2 (upper band), stop
#
# DATA RULE: If price data cannot be fetched → DATA UNAVAILABLE.
#            No assumed or estimated values are ever used.
#            Minimum 22 rows required. Fewer → INSUFFICIENT DATA.
# =============================================================================

import yfinance as yf
import pandas as pd
import math
from datetime import datetime
import logging
import os
import sys
from typing import Optional, Union

# ── Setup ─────────────────────────────────────────────────────────────────────

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CONFIG

os.makedirs(CONFIG["log_directory"], exist_ok=True)
log_file = os.path.join(
    CONFIG["log_directory"],
    f"signal04_{datetime.now().strftime('%Y-%m-%d')}.log"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SIGNAL04] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("signal04")

# ── Constants ─────────────────────────────────────────────────────────────────

BB_PERIOD         = 20      # Bollinger Band lookback period
BB_STD_MULT       = 2.0     # Number of standard deviations
MIN_ROWS_REQUIRED = 22      # Minimum data rows needed
SQUEEZE_THRESHOLD = 1.5     # Bandwidth % below which squeeze is active
NEAR_BAND_PCT     = 0.005   # "Near" a band = within 0.5%

# =============================================================================
# DATA FETCH
# =============================================================================

def fetch_etf_data(symbol: str, period_days: int = 40) -> Optional[pd.DataFrame]:
    """
    Fetch daily OHLCV data for the Gold ETF from Yahoo Finance.
    Returns a clean DataFrame sorted ascending, or None on failure.
    """
    try:
        log.info(f"Fetching {symbol} — last {period_days} days...")
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=f"{period_days}d", auto_adjust=True)

        if df is None or df.empty:
            log.error(f"No data returned for {symbol}")
            return None

        df = df.dropna(subset=["Close", "High", "Low", "Open"])
        df = df.sort_index()

        if len(df) < MIN_ROWS_REQUIRED:
            log.error(
                f"Insufficient data for {symbol}: "
                f"got {len(df)} rows, need at least {MIN_ROWS_REQUIRED}"
            )
            return None

        latest_date = df.index[-1].date()
        log.info(
            f"Fetched {len(df)} rows. "
            f"Latest: {latest_date}  close=₹{df['Close'].iloc[-1]:.2f}"
        )
        return df

    except Exception as e:
        log.error(f"Fetch failed for {symbol}: {e}")
        return None

# =============================================================================
# BOLLINGER BAND CALCULATIONS
# =============================================================================

def calculate_bollinger_bands(
    closes: pd.Series,
    period: int = BB_PERIOD,
    std_mult: float = BB_STD_MULT
) -> Optional[dict]:
    """
    Calculate Bollinger Bands for the latest bar.

    Returns dict with:
        mb      — Middle Band (20-day SMA)
        ub      — Upper Band  (MB + 2σ)
        lb      — Lower Band  (MB - 2σ)
        std     — Standard deviation of the period
        pct_b   — %B indicator (0 = lower, 1 = upper, can go outside 0–1)
        bw      — Bandwidth % = (UB - LB) / MB * 100
    Returns None if calculation fails.
    """
    try:
        if len(closes) < period:
            log.error(f"Need {period} closes for BB, got {len(closes)}")
            return None

        window = closes.iloc[-period:]

        mb  = float(window.mean())
        std = float(window.std(ddof=0))   # population std (not sample)

        if std == 0:
            log.error("Standard deviation is zero — flat price data, cannot compute BB")
            return None

        ub = mb + (std_mult * std)
        lb = mb - (std_mult * std)

        current_price = float(closes.iloc[-1])

        # %B: position within the band
        band_width = ub - lb
        if band_width == 0:
            log.error("Band width is zero — cannot compute %B")
            return None

        pct_b = (current_price - lb) / band_width
        bw    = (band_width / mb) * 100   # bandwidth as % of mid band

        return {
            "mb":            round(mb, 4),
            "ub":            round(ub, 4),
            "lb":            round(lb, 4),
            "std":           round(std, 4),
            "pct_b":         round(pct_b, 4),
            "bw":            round(bw, 4),
            "current_price": round(current_price, 2),
        }

    except Exception as e:
        log.error(f"Bollinger Band calculation error: {e}")
        return None


def detect_squeeze(bw: float) -> tuple[bool, str]:
    """
    Bollinger Squeeze: when bandwidth is very low, a breakout is imminent.
    Returns (is_squeeze, alert_message).
    """
    if bw <= SQUEEZE_THRESHOLD:
        return True, (
            f"⚡ BOLLINGER SQUEEZE — Bandwidth={bw:.2f}% (below {SQUEEZE_THRESHOLD}%). "
            f"Low volatility. A sharp breakout in either direction is likely soon. "
            f"Wait for direction before entering."
        )
    elif bw <= SQUEEZE_THRESHOLD * 1.5:
        return False, (
            f"⚠️  Bandwidth narrowing ({bw:.2f}%) — possible squeeze forming. Monitor."
        )
    else:
        return False, f"Bandwidth normal ({bw:.2f}%) — no squeeze."


def determine_market_state(closes: pd.Series) -> tuple[str, str, str]:
    """
    Assess whether the market is ranging, mildly trending, or strongly trending.
    Bollinger Bands are most reliable in ranging markets.

    Returns (state, reliability, description).
    """
    try:
        if len(closes) < 21:
            return "UNKNOWN", "UNKNOWN", "Not enough data to assess market state"

        current  = float(closes.iloc[-1])
        price_5d  = float(closes.iloc[-6])
        price_20d = float(closes.iloc[-21])

        trend_5d  = ((current - price_5d)  / price_5d)  * 100
        trend_20d = ((current - price_20d) / price_20d) * 100

        abs_20d = abs(trend_20d)

        if abs_20d > 5:
            state       = "STRONG TREND"
            reliability = "LOW"
            desc = (
                f"Gold moved {trend_20d:+.1f}% over 20 days. "
                f"BB signals less reliable in strong trends — price can walk the band."
            )
        elif abs_20d > 2:
            state       = "MILD TREND"
            reliability = "MEDIUM"
            desc = (
                f"Gold moved {trend_20d:+.1f}% over 20 days. "
                f"BB moderately reliable. Use with other signals."
            )
        else:
            state       = "SIDEWAYS / RANGING"
            reliability = "HIGH"
            desc = (
                f"Gold flat {trend_20d:+.1f}% over 20 days. "
                f"BB signals most reliable in this environment."
            )

        return state, reliability, desc

    except Exception as e:
        log.error(f"Market state error: {e}")
        return "UNKNOWN", "UNKNOWN", f"Calculation error: {e}"

# =============================================================================
# SIGNAL ZONE EVALUATION
# =============================================================================

def evaluate_zone(bb: dict) -> tuple[str, str, str]:
    """
    Determine which Bollinger Band zone the price is in.

    %B zones:
       < 0.00  →  Below lower band  (extreme oversold)
      0.00–0.05 → At lower band     (strong buy)
      0.05–0.15 → Near lower band   (buy zone)
      0.15–0.85 → Mid band          (neutral)
      0.85–0.95 → Near upper band   (approaching target)
      0.95–1.00 → At upper band     (take profit)
       > 1.00  →  Above upper band  (strong momentum / overbought)

    Returns (zone_code, zone_label, zone_description).
    """
    pct_b = bb["pct_b"]

    if pct_b < 0.0:
        return (
            "BELOW_LOWER",
            "PRICE BELOW LOWER BAND",
            f"Extremely oversold (%B={pct_b:.3f}). "
            f"Price broke below lower band. Strong mean-reversion buy candidate "
            f"if broader trend is up."
        )
    elif pct_b <= 0.05:
        return (
            "AT_LOWER",
            "AT LOWER BAND",
            f"Price at lower Bollinger Band (%B={pct_b:.3f}). "
            f"Statistically oversold. High probability bounce zone."
        )
    elif pct_b <= 0.15:
        return (
            "NEAR_LOWER",
            "NEAR LOWER BAND",
            f"Price near lower band (%B={pct_b:.3f}). "
            f"Good buy zone — approaching statistical support."
        )
    elif pct_b >= 1.0:
        return (
            "ABOVE_UPPER",
            "PRICE ABOVE UPPER BAND",
            f"Price broke above upper band (%B={pct_b:.3f}). "
            f"Momentum breakout — if already holding, consider partial profit. "
            f"Do NOT enter new long here."
        )
    elif pct_b >= 0.95:
        return (
            "AT_UPPER",
            "AT UPPER BAND — TAKE PROFIT",
            f"Price at upper Bollinger Band (%B={pct_b:.3f}). "
            f"Statistically overbought. Book profits if holding."
        )
    elif pct_b >= 0.85:
        return (
            "NEAR_UPPER",
            "APPROACHING UPPER BAND",
            f"Price approaching upper band (%B={pct_b:.3f}). "
            f"Prepare to take profit soon. Tighten stop loss."
        )
    else:
        return (
            "MID_BAND",
            "MID BAND — NEUTRAL",
            f"Price inside Bollinger Bands (%B={pct_b:.3f}). "
            f"No clear entry or exit. Wait for price to reach a band."
        )


# =============================================================================
# TRADE LEVELS
# =============================================================================

def calculate_trade_levels(bb: dict) -> dict:
    """
    If a BUY signal is generated, compute entry, two targets, and stop.
    Target 1 = middle band (mid-term)
    Target 2 = upper band (full target)
    Stop     = lower band - 1% (just below the band)
    """
    entry   = bb["current_price"]
    target1 = bb["mb"]          # middle band
    target2 = bb["ub"]          # upper band
    stop    = round(bb["lb"] * 0.99, 2)   # 1% below lower band

    pct_to_t1 = ((target1 - entry) / entry) * 100
    pct_to_t2 = ((target2 - entry) / entry) * 100
    pct_to_stop = ((stop - entry) / entry) * 100

    return {
        "entry":         round(entry, 2),
        "target1":       round(target1, 2),
        "target2":       round(target2, 2),
        "stop":          round(stop, 2),
        "pct_to_t1":     round(pct_to_t1, 2),
        "pct_to_t2":     round(pct_to_t2, 2),
        "pct_to_stop":   round(pct_to_stop, 2),
    }


# =============================================================================
# FINAL SIGNAL GENERATOR
# =============================================================================

def generate_signal(
    zone: str,
    market_state: str,
    reliability: str,
    is_squeeze: bool,
    bb: dict,
) -> tuple[str, str, str]:
    """
    Combine zone, market state, and squeeze flag into a final signal.
    Returns (signal, confidence, action_note).
    """

    # ── Squeeze override ──────────────────────────────────────────────────────
    if is_squeeze:
        return (
            "WAIT — SQUEEZE ACTIVE",
            "NONE",
            "Bollinger Squeeze detected. Volatility is compressed — "
            "a sharp move in either direction is imminent. "
            "Do NOT enter until the direction of the breakout is confirmed."
        )

    # ── Sell / Exit signals ───────────────────────────────────────────────────
    if zone in ("AT_UPPER", "ABOVE_UPPER"):
        return (
            "SELL / TAKE PROFIT",
            "HIGH" if reliability != "LOW" else "MEDIUM",
            "Price at or above upper Bollinger Band. "
            "If holding a position, consider exiting now to lock in profit. "
            "Do NOT enter a new long position here."
        )

    if zone == "NEAR_UPPER":
        return (
            "APPROACHING TARGET",
            "MEDIUM",
            "Price near upper band. If holding, tighten stop to -0.5% and "
            "prepare to exit. Do not chase with a new entry."
        )

    # ── Buy signals ───────────────────────────────────────────────────────────
    if zone == "BELOW_LOWER":
        if market_state == "STRONG TREND" and bb["pct_b"] < -0.1:
            # In a downtrend, below-lower-band can mean continuation, not reversal
            return (
                "CAUTION — POSSIBLE DOWNTREND CONTINUATION",
                "LOW",
                "Price broke below lower band in a strong downtrend. "
                "This may be a continuation, NOT a bounce. "
                "Wait for price to close BACK ABOVE the lower band before entering."
            )
        return (
            "STRONG BUY",
            "HIGH" if reliability == "HIGH" else "MEDIUM",
            "Price broke below lower band — statistically extreme. "
            "Strong mean-reversion entry. Use tight stop 1% below entry."
        )

    if zone == "AT_LOWER":
        if reliability == "HIGH":
            return (
                "STRONG BUY",
                "HIGH",
                "Price at lower Bollinger Band in a ranging market. "
                "Highest-probability bounce setup. Enter with full planned size."
            )
        elif reliability == "MEDIUM":
            return (
                "BUY",
                "MEDIUM",
                "Price at lower band. Mildly trending market — "
                "use 75% of planned position size."
            )
        else:
            return (
                "WATCH ONLY",
                "LOW",
                "Price at lower band but market is in a STRONG TREND. "
                "BB unreliable here. Confirm with Signal 01 (RSI) before entering."
            )

    if zone == "NEAR_LOWER":
        if reliability == "HIGH":
            return (
                "BUY",
                "MEDIUM",
                "Price near lower band in ranging market. "
                "Good entry zone. Use 50–75% of planned size."
            )
        else:
            return (
                "WATCH",
                "LOW",
                "Price near lower band but trend is active — "
                "wait for AT_LOWER or BELOW_LOWER for higher conviction."
            )

    # ── Mid band ──────────────────────────────────────────────────────────────
    return (
        "WAIT",
        "NONE",
        "Price in mid-band zone — no actionable signal. "
        "Wait for price to reach upper or lower band."
    )


# =============================================================================
# PRINT OUTPUT
# =============================================================================

def print_signal_output(data: dict):
    """Render clean formatted box output."""
    W = 70
    line = "═" * W

    def row(text=""):
        print(f"║{str(text)[:W].ljust(W)}║")

    def sep():
        print(f"╠{line}╣")

    print(f"\n╔{line}╗")
    row(f"  SIGNAL 04 — BOLLINGER BANDS RANGE TRADING")
    row(f"  {data['timestamp']}")
    sep()
    row(f"  ETF            : {data['symbol']}")
    row(f"  Current Price  : ₹{data['current_price']:.2f}")
    sep()
    row(f"  BOLLINGER BANDS  (Period={BB_PERIOD}, Std={BB_STD_MULT}σ)")
    row(f"  Upper Band (UB) : ₹{data['ub']:.4f}")
    row(f"  Middle Band(MB) : ₹{data['mb']:.4f}  ← 20-day SMA")
    row(f"  Lower Band (LB) : ₹{data['lb']:.4f}")
    row(f"  %B Indicator    : {data['pct_b']:.4f}  (0=lower, 1=upper)")
    row(f"  Bandwidth       : {data['bw']:.2f}%")
    sep()
    row(f"  Market State    : {data['market_state']}")
    row(f"  BB Reliability  : {data['reliability']}")
    row(f"  Market Note     : {data['market_desc'][:W-18]}")
    sep()
    row(f"  SQUEEZE         : {data['squeeze_msg'][:W-16]}")
    sep()
    row(f"  ZONE            : {data['zone_label']}")
    row(f"  ZONE DETAIL     : {data['zone_desc'][:W-18]}")
    sep()
    row(f"  SIGNAL          : {data['signal']}")
    row(f"  CONFIDENCE      : {data['confidence']}")

    # Wrap action note
    action = data.get("action", "")
    chunks = [action[i:i+W-18] for i in range(0, min(len(action), (W-18)*3), W-18)]
    for i, chunk in enumerate(chunks):
        label = "  ACTION         :" if i == 0 else "                 "
        row(f"{label} {chunk}")

    # Trade levels (only if BUY signal)
    levels = data.get("trade_levels")
    if levels and data["signal"] in ("STRONG BUY", "BUY"):
        sep()
        row(f"  ── TRADE LEVELS ────────────────────────────────────────────")
        row(f"  Entry            : ₹{levels['entry']}")
        row(f"  Target 1 (mid)   : ₹{levels['target1']}  ({levels['pct_to_t1']:+.2f}%)")
        row(f"  Target 2 (upper) : ₹{levels['target2']}  ({levels['pct_to_t2']:+.2f}%)")
        row(f"  Stop Loss        : ₹{levels['stop']}  ({levels['pct_to_stop']:+.2f}%)")
        row(f"  Hold Period      : 1–3 trading days")

        # Reward/risk check
        if levels["pct_to_t2"] < 1.0:
            row(f"  ⚠️  WARNING: Target only {levels['pct_to_t2']:.2f}% away — "
                f"reward too small after costs")
        elif levels["pct_to_t2"] >= 2.0:
            row(f"  ✅  Reward/Risk: {levels['pct_to_t2']:.2f}% target vs "
                f"{abs(levels['pct_to_stop']):.2f}% stop — acceptable")

    print(f"╚{line}╝\n")


# =============================================================================
# MAIN RUNNER
# =============================================================================

def run_signal_04() -> dict:
    """
    Main entry point. Runs the full Bollinger Band signal.
    Returns result dict — can be called standalone or by Signal 08.
    """
    log.info("=" * 60)
    log.info("SIGNAL 04 — BOLLINGER BANDS — START")
    log.info("=" * 60)

    symbol = CONFIG["primary_etf"]

    # ── Step 1: Fetch data ────────────────────────────────────────────────────
    df = fetch_etf_data(symbol, period_days=40)

    if df is None:
        msg = f"DATA UNAVAILABLE — cannot fetch {symbol}"
        log.error(f"SIGNAL 04: {msg}")
        print(f"\n{'═'*70}")
        print(f"  SIGNAL 04: {msg}")
        print(f"  DO NOT TRADE — no estimated values used.")
        print(f"{'═'*70}\n")
        return {
            "signal": "DATA UNAVAILABLE",
            "confidence": "NONE",
            "error": "FETCH_FAILED",
            "symbol": symbol,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    closes = df["Close"]

    # ── Step 2: Bollinger Bands ───────────────────────────────────────────────
    bb = calculate_bollinger_bands(closes, BB_PERIOD, BB_STD_MULT)

    if bb is None:
        msg = "CALCULATION ERROR — Bollinger Bands could not be computed"
        log.error(f"SIGNAL 04: {msg}")
        print(f"\n{'═'*70}")
        print(f"  SIGNAL 04: DATA UNAVAILABLE — {msg}")
        print(f"  DO NOT TRADE.")
        print(f"{'═'*70}\n")
        return {
            "signal": "DATA UNAVAILABLE",
            "confidence": "NONE",
            "error": "CALC_FAILED",
            "symbol": symbol,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    log.info(
        f"BB: MB=₹{bb['mb']} | UB=₹{bb['ub']} | LB=₹{bb['lb']} | "
        f"%B={bb['pct_b']} | BW={bb['bw']}% | Price=₹{bb['current_price']}"
    )

    # ── Step 3: Squeeze detection ─────────────────────────────────────────────
    is_squeeze, squeeze_msg = detect_squeeze(bb["bw"])

    # ── Step 4: Market state ──────────────────────────────────────────────────
    market_state, reliability, market_desc = determine_market_state(closes)
    log.info(f"Market state: {market_state} | BB reliability: {reliability}")

    # ── Step 5: Zone evaluation ───────────────────────────────────────────────
    zone_code, zone_label, zone_desc = evaluate_zone(bb)
    log.info(f"Zone: {zone_code} | %B={bb['pct_b']}")

    # ── Step 6: Final signal ──────────────────────────────────────────────────
    signal, confidence, action = generate_signal(
        zone_code, market_state, reliability, is_squeeze, bb
    )
    log.info(f"VERDICT: {signal} | Confidence: {confidence}")

    # ── Step 7: Trade levels (BUY signals only) ───────────────────────────────
    trade_levels = None
    if signal in ("STRONG BUY", "BUY"):
        trade_levels = calculate_trade_levels(bb)
        log.info(
            f"Trade: Entry=₹{trade_levels['entry']} | "
            f"T1=₹{trade_levels['target1']} ({trade_levels['pct_to_t1']:+.1f}%) | "
            f"T2=₹{trade_levels['target2']} ({trade_levels['pct_to_t2']:+.1f}%) | "
            f"Stop=₹{trade_levels['stop']} ({trade_levels['pct_to_stop']:+.1f}%)"
        )

    # ── Step 8: Assemble result ───────────────────────────────────────────────
    result = {
        "signal":       signal,
        "confidence":   confidence,
        "action":       action,
        "zone":         zone_code,
        "zone_label":   zone_label,
        "zone_desc":    zone_desc,
        "market_state": market_state,
        "reliability":  reliability,
        "market_desc":  market_desc,
        "is_squeeze":   is_squeeze,
        "squeeze_msg":  squeeze_msg,
        "trade_levels": trade_levels,
        "symbol":       symbol,
        "timestamp":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "error":        None,
        # Raw values for Signal 08
        "current_price": bb["current_price"],
        "mb":            bb["mb"],
        "ub":            bb["ub"],
        "lb":            bb["lb"],
        "pct_b":         bb["pct_b"],
        "bw":            bb["bw"],
        "std":           bb["std"],
    }

    # ── Step 9: Print ─────────────────────────────────────────────────────────
    print_signal_output(result)

    log.info("SIGNAL 04 — BOLLINGER BANDS — END")
    return result


# =============================================================================
# RUN AS STANDALONE SCRIPT
# =============================================================================

if __name__ == "__main__":
    run_signal_04()
