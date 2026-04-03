# =============================================================================
# GOLD BOT — signal_01_buy_the_dip.py
# Signal 01: Buy the Dip (Mean Reversion)
#
# COMPLETELY INDEPENDENT — shares no data or logic with any other signal.
#
# Logic:
#   A — Price has dipped 1–4% from recent swing high (last 10 days)
#   B — RSI (14-period) is below 35 (oversold)
#   C — Price is near a support level (20-day MA or previous day low)
#   D — Price is still above the 20-day MA (uptrend intact)
#
# Score 0–4. BUY if score >= 3. WATCH if score >= 2.
#
# DATA RULE: If price data cannot be fetched → DATA UNAVAILABLE.
#            No assumed or estimated values are ever used.
# =============================================================================

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import logging
import os
import sys

# ── Setup ─────────────────────────────────────────────────────────────────────

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CONFIG

os.makedirs(CONFIG["log_directory"], exist_ok=True)
log_file = os.path.join(
    CONFIG["log_directory"],
    f"signal01_{datetime.now().strftime('%Y-%m-%d')}.log"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SIGNAL01] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("signal01")

# =============================================================================
# DATA FETCH
# =============================================================================

def fetch_etf_data(symbol: str, period_days: int = 35) -> pd.DataFrame | None:
    """
    Fetch daily OHLCV data for the Gold ETF.
    Requires at least 25 rows (for 20-day MA + RSI buffer).
    Returns None on any failure — no fallback values.
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

        if len(df) < 22:
            log.error(
                f"Insufficient data for {symbol}: got {len(df)} rows, need at least 22"
            )
            return None

        log.info(
            f"Fetched {len(df)} rows for {symbol}. "
            f"Latest: {df.index[-1].date()} close=₹{df['Close'].iloc[-1]:.2f}"
        )
        return df

    except Exception as e:
        log.error(f"Fetch failed for {symbol}: {e}")
        return None

# =============================================================================
# CALCULATIONS
# =============================================================================

def calculate_rsi(closes: pd.Series, period: int = 14) -> float | None:
    """
    Calculate RSI for the latest bar using Wilder's smoothing method.
    Returns the RSI value (0–100) or None if calculation fails.
    """
    try:
        if len(closes) < period + 1:
            log.error(f"Not enough data for RSI-{period}: got {len(closes)} rows")
            return None

        delta = closes.diff()

        gains = delta.clip(lower=0)
        losses = (-delta).clip(lower=0)

        # Initial averages (simple average for first window)
        avg_gain = gains.iloc[1:period + 1].mean()
        avg_loss = losses.iloc[1:period + 1].mean()

        # Wilder's smoothing for remaining bars
        for i in range(period + 1, len(closes)):
            avg_gain = (avg_gain * (period - 1) + gains.iloc[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses.iloc[i]) / period

        if avg_loss == 0:
            return 100.0  # No losses = max RSI

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return round(float(rsi), 2)

    except Exception as e:
        log.error(f"RSI calculation error: {e}")
        return None


def calculate_sma(closes: pd.Series, period: int = 20) -> float | None:
    """
    Calculate Simple Moving Average for the latest bar.
    Returns the SMA value or None if calculation fails.
    """
    try:
        if len(closes) < period:
            log.error(f"Not enough data for SMA-{period}")
            return None

        sma = float(closes.iloc[-period:].mean())
        return round(sma, 4)

    except Exception as e:
        log.error(f"SMA calculation error: {e}")
        return None


def find_swing_high(highs: pd.Series, lookback: int = 10) -> tuple[float, str] | tuple[None, None]:
    """
    Find the highest high in the last `lookback` bars.
    Returns (swing_high_price, date_string) or (None, None).
    """
    try:
        if len(highs) < lookback:
            lookback = len(highs)

        window = highs.iloc[-lookback:]
        swing_high = float(window.max())
        swing_date = str(window.idxmax().date())
        return swing_high, swing_date

    except Exception as e:
        log.error(f"Swing high calculation error: {e}")
        return None, None

# =============================================================================
# CONDITION EVALUATORS
# =============================================================================

def condition_a_dip_from_swing(
    current_price: float,
    swing_high: float
) -> tuple[float, float, str, str]:
    """
    Condition A: Price has dipped 1–4% from recent swing high.
    Returns: (score, dip_pct, flag_emoji, flag_message)
    """
    dip_pct = ((swing_high - current_price) / swing_high) * 100

    if 1.0 <= dip_pct <= 4.0:
        score = 1.0
        emoji = "✅"
        msg = f"Price dipped {dip_pct:.2f}% from swing high (ideal 1–4% range)"
    elif 0.5 <= dip_pct < 1.0:
        score = 0.5
        emoji = "⚠️ "
        msg = f"Price dipped {dip_pct:.2f}% from swing high (minor dip, below ideal 1%)"
    elif 4.0 < dip_pct <= 6.0:
        score = 0.5
        emoji = "⚠️ "
        msg = f"Price dipped {dip_pct:.2f}% from swing high (larger dip — higher risk entry)"
    elif dip_pct > 6.0:
        score = 0.0
        emoji = "❌"
        msg = f"Price dipped {dip_pct:.2f}% from swing high — too deep, possible downtrend"
    else:
        score = 0.0
        emoji = "❌"
        msg = f"Price near swing high (dip only {dip_pct:.2f}%) — not a dip entry"

    return score, dip_pct, emoji, msg


def condition_b_rsi(rsi: float) -> tuple[float, str, str]:
    """
    Condition B: RSI (14) is below 35 (oversold bounce signal).
    Returns: (score, flag_emoji, flag_message)
    """
    if rsi < 30:
        score = 1.0
        emoji = "✅"
        msg = f"RSI = {rsi} — DEEPLY OVERSOLD (strong bounce probability)"
    elif rsi < 35:
        score = 1.0
        emoji = "✅"
        msg = f"RSI = {rsi} — OVERSOLD (solid bounce signal, below 35)"
    elif rsi < 45:
        score = 0.5
        emoji = "⚠️ "
        msg = f"RSI = {rsi} — MILDLY OVERSOLD (weak signal, below 45)"
    elif rsi > 65:
        score = 0.0
        emoji = "❌"
        msg = f"RSI = {rsi} — OVERBOUGHT (not a dip buy zone)"
    else:
        score = 0.0
        emoji = "❌"
        msg = f"RSI = {rsi} — NEUTRAL (not oversold, no bounce signal)"

    return score, emoji, msg


def condition_c_support(
    current_price: float,
    ma_20: float,
    prev_day_low: float
) -> tuple[float, str, str]:
    """
    Condition C: Price is near a support level (20-day MA or previous day low).
    'Near' = within 0.5% of the support level.
    Returns: (score, flag_emoji, flag_message)
    """
    near_ma20 = current_price <= ma_20 * 1.005   # within 0.5% above MA
    at_or_below_ma20 = current_price <= ma_20
    near_prev_low = current_price <= prev_day_low * 1.005

    pct_from_ma = ((current_price - ma_20) / ma_20) * 100
    pct_from_prev_low = ((current_price - prev_day_low) / prev_day_low) * 100

    if at_or_below_ma20 and near_prev_low:
        score = 1.0
        emoji = "✅"
        msg = (
            f"Price at/below 20MA (₹{ma_20:.2f}) AND near prev-day-low (₹{prev_day_low:.2f}) "
            f"— strong double support"
        )
    elif near_ma20:
        score = 1.0
        emoji = "✅"
        msg = (
            f"Price within 0.5% of 20-day MA (₹{ma_20:.2f}) "
            f"[{pct_from_ma:+.2f}%] — at support"
        )
    elif near_prev_low:
        score = 1.0
        emoji = "✅"
        msg = (
            f"Price near previous day low (₹{prev_day_low:.2f}) "
            f"[{pct_from_prev_low:+.2f}%] — at support"
        )
    elif current_price <= ma_20 * 1.01:
        score = 0.5
        emoji = "⚠️ "
        msg = (
            f"Price within 1% of 20MA (₹{ma_20:.2f}) [{pct_from_ma:+.2f}%] "
            f"— close to support"
        )
    else:
        score = 0.0
        emoji = "❌"
        msg = (
            f"Price not near any defined support. "
            f"Distance from 20MA: {pct_from_ma:+.2f}%, "
            f"from prev-low: {pct_from_prev_low:+.2f}%"
        )

    return score, emoji, msg


def condition_d_trend(
    current_price: float,
    ma_20: float
) -> tuple[float, str, str]:
    """
    Condition D: Price is above 20-day MA — confirms uptrend context.
    A dip buy in a downtrend is much riskier.
    Returns: (score, flag_emoji, flag_message)
    """
    pct_vs_ma = ((current_price - ma_20) / ma_20) * 100

    if current_price > ma_20 * 1.005:
        score = 1.0
        emoji = "✅"
        msg = f"Price {pct_vs_ma:+.2f}% above 20-day MA — UPTREND intact. Dip buy favored."
    elif current_price >= ma_20 * 0.995:
        score = 0.5
        emoji = "⚠️ "
        msg = f"Price hugging 20-day MA ({pct_vs_ma:+.2f}%) — trend neutral. Caution."
    elif current_price >= ma_20 * 0.98:
        score = 0.0
        emoji = "⚠️ "
        msg = f"Price {pct_vs_ma:+.2f}% below 20-day MA — mild downtrend. Higher risk entry."
    else:
        score = 0.0
        emoji = "❌"
        msg = f"Price {pct_vs_ma:+.2f}% below 20-day MA — DOWNTREND. Avoid dip buy."

    return score, emoji, msg

# =============================================================================
# FINAL VERDICT
# =============================================================================

def generate_verdict(
    score: float,
    current_price: float,
    dip_pct: float
) -> tuple[str, str, str | None]:
    """
    Convert raw score into final signal, confidence, and action.
    Returns: (signal, confidence, action)
    """
    target_pct = CONFIG["profit_target_pct"] / 100
    stop_pct = CONFIG["stop_loss_pct"] / 100

    target_price = round(current_price * (1 + target_pct), 2)
    stop_price = round(current_price * (1 - stop_pct), 2)

    if score >= 3.5:
        return (
            "BUY",
            "HIGH",
            f"Enter at ₹{current_price:.2f} | "
            f"Target: ₹{target_price} (+{CONFIG['profit_target_pct']}%) | "
            f"Stop: ₹{stop_price} (-{CONFIG['stop_loss_pct']}%) | "
            f"Hold: 1–5 days"
        )
    elif score >= 2.5:
        return (
            "BUY",
            "MEDIUM",
            f"Enter at ₹{current_price:.2f} | "
            f"Target: ₹{target_price} (+{CONFIG['profit_target_pct']}%) | "
            f"Stop: ₹{stop_price} (-{CONFIG['stop_loss_pct']}%) | "
            f"Hold: 1–5 days | Use 50–75% of planned size"
        )
    elif score >= 1.5:
        return (
            "WATCH",
            "LOW",
            f"Set price alert at ₹{current_price * 0.99:.2f} (another 1% dip). "
            f"Do not enter yet — wait for more confirmation."
        )
    else:
        return (
            "DO NOT TRADE",
            "NONE",
            "Conditions not met. Wait for a clearer dip setup."
        )

# =============================================================================
# PRINT OUTPUT
# =============================================================================

def print_signal_output(data: dict):
    """Render a clean formatted box output to the console."""
    W = 68
    line = "═" * W

    def row(text=""):
        padded = str(text)[:W].ljust(W)
        print(f"║{padded}║")

    def sep():
        print(f"╠{line}╣")

    print(f"\n╔{line}╗")
    row(f"  SIGNAL 01 — BUY THE DIP (MEAN REVERSION)")
    row(f"  {data['timestamp']}")
    sep()
    row(f"  ETF          : {data['symbol']}")
    row(f"  Current Price: ₹{data['current_price']:.2f}")
    row(f"  Swing High   : ₹{data['swing_high']:.2f}  ({data['swing_date']})")
    row(f"  Dip from High: {data['dip_pct']:.2f}%")
    row(f"  RSI (14)     : {data['rsi']}")
    row(f"  20-Day MA    : ₹{data['ma_20']:.2f}")
    row(f"  Prev Day Low : ₹{data['prev_day_low']:.2f}")
    sep()
    row(f"  COND A (Dip 1–4%)  : {data['a_emoji']} {data['a_msg'][:W - 25]}")
    row(f"  COND B (RSI < 35)  : {data['b_emoji']} {data['b_msg'][:W - 25]}")
    row(f"  COND C (Support)   : {data['c_emoji']} {data['c_msg'][:W - 25]}")
    row(f"  COND D (Above MA)  : {data['d_emoji']} {data['d_msg'][:W - 25]}")
    sep()
    row(f"  SCORE      : {data['score']:.1f} / 4.0")
    row(f"  SIGNAL     : {data['signal']}")
    row(f"  CONFIDENCE : {data['confidence']}")
    sep()

    if data["action"]:
        # Word-wrap action across multiple lines
        action = data["action"]
        chunks = [action[i:i + W - 4] for i in range(0, len(action), W - 4)]
        for chunk in chunks:
            row(f"  {chunk}")

    print(f"╚{line}╝\n")

# =============================================================================
# MAIN RUNNER
# =============================================================================

def run_signal_01() -> dict:
    """
    Main entry point. Evaluates all conditions and returns the result dict.
    Can be called standalone or by Signal 08 (Final Verdict).
    """
    log.info("=" * 60)
    log.info("SIGNAL 01 — BUY THE DIP — START")
    log.info("=" * 60)

    symbol = CONFIG["primary_etf"]

    # ── Step 1: Fetch Data ────────────────────────────────────────────────────
    df = fetch_etf_data(symbol, period_days=35)

    if df is None:
        result = {
            "signal": "DATA UNAVAILABLE",
            "confidence": "NONE",
            "score": 0,
            "error": "FETCH_FAILED",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
        }
        log.error("SIGNAL 01: DATA UNAVAILABLE — fetch failed")
        print(f"\n{'═'*68}")
        print(f"  SIGNAL 01: DATA UNAVAILABLE — Cannot fetch {symbol}")
        print(f"  DO NOT TRADE — No estimated values used.")
        print(f"{'═'*68}\n")
        return result

    closes = df["Close"]
    highs = df["High"]
    lows = df["Low"]

    # ── Step 2: Current prices ────────────────────────────────────────────────
    current_price = float(closes.iloc[-1])
    prev_day_low = float(lows.iloc[-2])

    # ── Step 3: Calculate Indicators ─────────────────────────────────────────
    rsi = calculate_rsi(closes, period=14)
    ma_20 = calculate_sma(closes, period=20)
    swing_high, swing_date = find_swing_high(highs, lookback=10)

    if rsi is None or ma_20 is None or swing_high is None:
        result = {
            "signal": "DATA UNAVAILABLE",
            "confidence": "NONE",
            "score": 0,
            "error": "CALCULATION_FAILED",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
        }
        log.error(
            f"SIGNAL 01: CALCULATION FAILED — "
            f"RSI={rsi}, MA20={ma_20}, SwingHigh={swing_high}"
        )
        print(f"\n{'═'*68}")
        print(f"  SIGNAL 01: CALCULATION ERROR — DATA UNAVAILABLE")
        print(f"  RSI={rsi} | MA20={ma_20} | SwingHigh={swing_high}")
        print(f"  DO NOT TRADE — No estimated values used.")
        print(f"{'═'*68}\n")
        return result

    log.info(
        f"Indicators: price=₹{current_price:.2f}, RSI={rsi}, "
        f"MA20=₹{ma_20:.2f}, SwingHigh=₹{swing_high:.2f} ({swing_date}), "
        f"PrevLow=₹{prev_day_low:.2f}"
    )

    # ── Step 4: Evaluate Each Condition ──────────────────────────────────────
    a_score, dip_pct, a_emoji, a_msg = condition_a_dip_from_swing(current_price, swing_high)
    b_score, b_emoji, b_msg = condition_b_rsi(rsi)
    c_score, c_emoji, c_msg = condition_c_support(current_price, ma_20, prev_day_low)
    d_score, d_emoji, d_msg = condition_d_trend(current_price, ma_20)

    total_score = a_score + b_score + c_score + d_score

    log.info(
        f"Scores: A={a_score} B={b_score} C={c_score} D={d_score} "
        f"Total={total_score:.1f}/4.0"
    )

    # ── Step 5: Generate Verdict ──────────────────────────────────────────────
    signal, confidence, action = generate_verdict(total_score, current_price, dip_pct)

    log.info(f"VERDICT: {signal} | Confidence: {confidence} | Score: {total_score:.1f}")

    # ── Step 6: Build result dict ─────────────────────────────────────────────
    result = {
        "signal": signal,
        "confidence": confidence,
        "score": total_score,
        "action": action,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "symbol": symbol,
        "current_price": current_price,
        "swing_high": swing_high,
        "swing_date": swing_date,
        "dip_pct": round(dip_pct, 3),
        "rsi": rsi,
        "ma_20": ma_20,
        "prev_day_low": prev_day_low,
        "a_score": a_score, "a_emoji": a_emoji, "a_msg": a_msg,
        "b_score": b_score, "b_emoji": b_emoji, "b_msg": b_msg,
        "c_score": c_score, "c_emoji": c_emoji, "c_msg": c_msg,
        "d_score": d_score, "d_emoji": d_emoji, "d_msg": d_msg,
        "error": None,
    }

    # ── Step 7: Print output ──────────────────────────────────────────────────
    print_signal_output(result)

    log.info("SIGNAL 01 — BUY THE DIP — END")
    return result


# =============================================================================
# RUN AS STANDALONE SCRIPT
# =============================================================================

if __name__ == "__main__":
    run_signal_01()
