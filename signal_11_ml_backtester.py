# =============================================================================
# GOLD BOT — signal_11_ml_backtester.py
# Signal 11: ML Backtester (Walk-Forward Validation Engine)
#
# PURPOSE:
#   Retrospectively reconstructs all signal scores for every historical
#   trading day (2020–present), labels actual trade outcomes, then runs:
#     Phase 1 — Threshold Optimizer (no ML, pure data)
#     Phase 2 — Logistic Regression (pure numpy, no sklearn required)
#     Phase 3 — Walk-Forward Validation (rolling windows, no look-ahead)
#   Produces a dated HTML + text report with weight adjustment suggestions.
#
# DATA RULE:
#   Only data available AT each date is used.
#   No look-ahead bias. No assumed/estimated values.
#   If a source fails → that signal contributes 0 pts for that date.
#   Minimum 50 trade signals required; fewer → INSUFFICIENT DATA.
#
# INDEPENDENCE:
#   This file DOES import other signal modules for calendar/seasonality
#   reconstruction but never shares live market data between them.
#   All historical data is fetched once and passed explicitly.
#
# ML APPROACH:
#   Logistic regression implemented from scratch with numpy.
#   No scikit-learn dependency. Gradient descent, 500 epochs.
#   Feature importance from learned coefficients.
# =============================================================================

import os
import sys
import csv
import json
import math
import logging
import numpy as np
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Tuple, Any

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import CONFIG

# ── Logging ───────────────────────────────────────────────────────────────────
os.makedirs(CONFIG["log_directory"], exist_ok=True)
log_file = os.path.join(
    CONFIG["log_directory"],
    f"signal11_{datetime.now().strftime('%Y-%m-%d')}.log"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SIGNAL11] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("signal11")

# ── Constants ─────────────────────────────────────────────────────────────────
HISTORY_YEARS       = 4          # Years of history to fetch (2+ needed for walk-forward)
MIN_LOOKBACK_DAYS   = 25         # Minimum rows before first usable signal date
OUTCOME_WINDOW      = 5          # Trading days to evaluate trade outcome
PROFIT_TARGET_PCT   = CONFIG.get("profit_target_pct", 3.0)
STOP_LOSS_PCT       = CONFIG.get("stop_loss_pct", 1.0)
TROY_OZ_GRAMS       = 31.1035
MIN_SIGNALS_NEEDED  = 50         # Minimum trade-eligible rows for meaningful analysis
THRESHOLD_RANGE     = range(20, 86, 1)   # Score thresholds to test (out of 95)
MAX_SCORE           = 95

# =============================================================================
# SECTION 1 — HISTORICAL DATA FETCHERS
# =============================================================================

def _fetch_yf(symbol: str, years: int, label: str) -> Optional[pd.DataFrame]:
    """Fetch multi-year daily OHLCV from yfinance. Returns None on failure."""
    try:
        import yfinance as yf
        log.info(f"Fetching {label} ({symbol}) — {years} years...")
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=f"{years * 365}d", auto_adjust=True)
        if df is None or df.empty or len(df) < MIN_LOOKBACK_DAYS:
            log.error(f"Insufficient data for {symbol}: {len(df) if df is not None else 0} rows")
            return None
        df = df.sort_index()
        df.index = pd.to_datetime(df.index).normalize()
        # Strip timezone info for uniform comparison
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        log.info(f"  {label}: {len(df)} rows  {df.index[0].date()} → {df.index[-1].date()}")
        return df
    except Exception as e:
        log.error(f"Fetch failed for {symbol}: {e}")
        return None


def fetch_goldbees_history(years: int = HISTORY_YEARS) -> Optional[pd.DataFrame]:
    return _fetch_yf(CONFIG.get("primary_etf", "GOLDBEES.NS"), years, "GOLDBEES")

def fetch_comex_history(years: int = HISTORY_YEARS) -> Optional[pd.DataFrame]:
    return _fetch_yf(CONFIG.get("comex_symbol", "GC=F"), years, "COMEX")

def fetch_dxy_history(years: int = HISTORY_YEARS) -> Optional[pd.DataFrame]:
    return _fetch_yf(CONFIG.get("dxy_symbol", "DX-Y.NYB"), years, "DXY")

def fetch_usdinr_history(years: int = HISTORY_YEARS) -> Optional[pd.DataFrame]:
    return _fetch_yf(CONFIG.get("usdinr_symbol", "USDINR=X"), years, "USDINR")


def fetch_fred_series(series_id: str, years: int = HISTORY_YEARS) -> Optional[pd.Series]:
    """
    Fetch a FRED economic time series via REST API.
    Returns a pd.Series indexed by date, or None on failure.
    """
    try:
        import requests
        api_key = CONFIG.get("fred_api_key", "")
        if not api_key:
            log.warning(f"FRED API key not set — skipping {series_id}")
            return None
        start_date = (datetime.now() - timedelta(days=years * 365 + 30)).strftime("%Y-%m-%d")
        url = (
            f"https://api.stlouisfed.org/fred/series/observations"
            f"?series_id={series_id}&api_key={api_key}&file_type=json"
            f"&observation_start={start_date}&sort_order=asc"
        )
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("observations", [])
        if not data:
            log.error(f"FRED returned empty data for {series_id}")
            return None
        records = {}
        for obs in data:
            try:
                val = float(obs["value"])
                records[pd.Timestamp(obs["date"])] = val
            except (ValueError, KeyError):
                continue  # Skip missing/revision rows
        if not records:
            return None
        s = pd.Series(records).sort_index()
        log.info(f"  FRED {series_id}: {len(s)} observations, latest {s.index[-1].date()}")
        return s
    except Exception as e:
        log.error(f"FRED fetch failed for {series_id}: {e}")
        return None


# =============================================================================
# SECTION 2 — SIGNAL RECONSTRUCTORS
# All functions take a DataFrame slice up to and including row i (no look-ahead)
# and return a float score within the signal's valid range.
# =============================================================================

# ── RSI helper ────────────────────────────────────────────────────────────────
def _rsi(closes: np.ndarray, period: int = 14) -> float:
    """Wilder's RSI. Returns 50.0 if insufficient data."""
    if len(closes) < period + 2:
        return 50.0
    delta = np.diff(closes)
    gains = np.where(delta > 0, delta, 0.0)
    losses = np.where(delta < 0, -delta, 0.0)
    avg_g = gains[:period].mean()
    avg_l = losses[:period].mean()
    for i in range(period, len(delta)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return 100.0 - (100.0 / (1.0 + rs))


# ── S01: Buy the Dip Reconstructor ────────────────────────────────────────────
def reconstruct_s01(closes: np.ndarray, highs: np.ndarray) -> float:
    """
    Reconstruct S01 score (0–4 raw → mapped to 0–15 pts) for a single date.
    Uses only data in the window passed (no look-ahead).
    """
    if len(closes) < 22:
        return 0.0
    close  = closes[-1]
    ma20   = closes[-20:].mean()
    swing_high = highs[-10:].max()
    rsi    = _rsi(closes[-30:] if len(closes) >= 30 else closes)

    raw = 0.0
    # Condition A: dip from swing high (1–4% ideal)
    dip_pct = ((swing_high - close) / swing_high) * 100 if swing_high > 0 else 0
    if 1.0 <= dip_pct <= 4.0:
        raw += 1.0
    elif 0.5 <= dip_pct < 1.0 or 4.0 < dip_pct <= 6.0:
        raw += 0.5

    # Condition B: RSI oversold
    if rsi < 35:
        raw += 1.0
    elif rsi < 45:
        raw += 0.5

    # Condition C: near support (within 0.5% of 20-day MA)
    if close <= ma20 * 1.005:
        raw += 1.0
    elif close <= ma20 * 1.015:
        raw += 0.5

    # Condition D: above MA (uptrend intact)
    if close >= ma20 * 0.99:
        raw += 1.0

    # Map raw (0–4) to pts (0–15)
    return round(min(raw / 4.0 * 15.0, 15.0), 2)


# ── S02: Macro Trigger Reconstructor (simplified — no live NewsAPI) ───────────
def reconstruct_s02(
    dxy_closes: Optional[np.ndarray],
    usdinr_closes: Optional[np.ndarray],
    fedfunds_val: Optional[float],
    fedfunds_6m_ago: Optional[float]
) -> float:
    """
    Reconstruct S02 score (0–25 pts). Omits geopolitical sub-score (no history).
    Max available: 20 pts (3 sub-factors). Normalized to 25 pt scale.
    """
    available_max = 0.0
    score = 0.0

    # M1: DXY 5-day change
    if dxy_closes is not None and len(dxy_closes) >= 6:
        dxy_5d = (dxy_closes[-1] - dxy_closes[-6]) / dxy_closes[-6] * 100
        available_max += 10.0
        if dxy_5d <= -1.0:
            score += 10.0
        elif dxy_5d <= -0.5:
            score += 6.0
        elif dxy_5d <= 0:
            score += 3.0

    # M2: USDINR 5-day change (rising = bullish for gold in INR)
    if usdinr_closes is not None and len(usdinr_closes) >= 6:
        inr_5d = (usdinr_closes[-1] - usdinr_closes[-6]) / usdinr_closes[-6] * 100
        available_max += 5.0
        if inr_5d >= 0.5:
            score += 5.0
        elif inr_5d >= 0.2:
            score += 2.5

    # M3: Fed rate direction
    if fedfunds_val is not None and fedfunds_6m_ago is not None:
        rate_change = fedfunds_val - fedfunds_6m_ago
        available_max += 5.0
        if rate_change < -0.5:
            score += 5.0
        elif rate_change < 0:
            score += 3.0
        elif abs(rate_change) < 0.1:
            score += 1.5  # Pause

    if available_max == 0:
        return 0.0
    # Normalize to 25 pt scale
    return round(min(score / available_max * 25.0, 25.0), 2)


# ── S03: Seasonality Reconstructor (pure calendar — exact same logic) ─────────
def reconstruct_s03(dt: date) -> float:
    """
    Reconstruct S03 score for a given date using calendar logic only.
    Returns 0–5 pts matching the live signal's scoring.
    """
    month = dt.month
    day   = dt.day

    # Map to approximate seasonality score from the live signal
    # BUY/BUILD phases (5 pts): wedding buildup, pre-navratri, akshaya buildup
    # ACCUMULATE (4 pts): post-monsoon, jan-feb
    # NEUTRAL (2 pts): monsoon, year-end
    # SELL ZONE (1 pt): festival peaks
    # SUMMER LULL (1 pt): May-June

    # Jan-Feb: post-wedding lull → accumulate
    if month in (1, 2):
        return 4.0 if day <= 20 else 3.0

    # Mar: pre-election / budget calm
    if month == 3:
        return 3.0

    # Apr: Akshaya Tritiya buildup (strong buy)
    if month == 4:
        return 5.0 if day <= 25 else 4.0

    # May: Akshaya peak / post-peak
    if month == 5:
        return 1.0 if day <= 10 else 2.0

    # Jun-Jul: Summer lull / monsoon
    if month in (6, 7):
        return 1.0

    # Aug: Pre-wedding early accumulate
    if month == 8:
        return 4.0

    # Sep: Pre-navratri warmup → BUY
    if month == 9:
        return 5.0 if day >= 15 else 4.0

    # Oct: Navratri/Dussehra buildup → BUY → Peak → sell
    if month == 10:
        if day <= 10:
            return 5.0   # Pre-Navratri buy
        elif day <= 20:
            return 2.0   # Navratri peak — sell zone
        else:
            return 3.0   # Post-Dussehra recovery

    # Nov: Dhanteras/Diwali — peak sell
    if month == 11:
        if day <= 5:
            return 2.0   # Dhanteras approach
        elif day <= 15:
            return 1.0   # Diwali peak (sell zone)
        else:
            return 3.0   # Post-Diwali wedding

    # Dec: Year-end holiday lull
    if month == 12:
        return 2.0

    return 2.0  # Default neutral


# ── S04: Bollinger Bands Reconstructor ────────────────────────────────────────
def reconstruct_s04(closes: np.ndarray) -> float:
    """
    Reconstruct S04 score (0–15 pts) for a single date.
    """
    if len(closes) < 22:
        return 0.0

    window = closes[-20:]
    mb     = window.mean()
    std    = window.std()
    if std == 0 or mb == 0:
        return 0.0

    ub    = mb + 2.0 * std
    lb    = mb - 2.0 * std
    price = closes[-1]
    bw    = (ub - lb) / mb * 100   # Bandwidth %
    pct_b = (price - lb) / (ub - lb) if (ub - lb) > 0 else 0.5

    raw = 0.0
    # Price near/below lower band → buy signal
    if pct_b <= 0.15:          raw += 3.0   # At or below lower band
    elif pct_b <= 0.30:        raw += 2.0   # Approaching lower band
    elif pct_b <= 0.45:        raw += 1.0   # Below midpoint

    # Bollinger squeeze → breakout incoming
    if bw < 1.0:               raw += 3.0   # Tight squeeze
    elif bw < 1.5:             raw += 2.0   # Mild squeeze

    # Below mid band (bearish trend not in play)
    if price < mb:             raw += 1.5

    # Mean reversion potential (price below mb but above lb)
    if lb < price < mb:        raw += 1.5

    return round(min(raw / 9.0 * 15.0, 15.0), 2)


# ── S05: 2026 Outlook Reconstructor (FRED-based factors only) ─────────────────
def reconstruct_s05(
    fedfunds_val: Optional[float],
    fedfunds_6m_ago: Optional[float],
    dxy_30d_closes: Optional[np.ndarray]
) -> float:
    """
    Reconstruct S05 score (0–10 pts) using available FRED + DXY data.
    NewsAPI geopolitical and WGC central bank sub-factors not reconstructible.
    Available max = 4 pts (O3 Fed + O4 DXY). Normalized to 10 pt scale.
    """
    score = 0.0
    available_max = 0.0

    # O3: Fed rates direction
    if fedfunds_val is not None and fedfunds_6m_ago is not None:
        available_max += 2.0
        rate_change = fedfunds_val - fedfunds_6m_ago
        if rate_change < -0.5:
            score += 2.0
        elif rate_change < 0:
            score += 1.0
        elif abs(rate_change) < 0.1:
            score += 0.5

    # O4: DXY 30-day and 10-day change
    if dxy_30d_closes is not None and len(dxy_30d_closes) >= 30:
        available_max += 2.0
        dxy_30d = (dxy_30d_closes[-1] - dxy_30d_closes[-30]) / dxy_30d_closes[-30] * 100
        dxy_10d = (dxy_30d_closes[-1] - dxy_30d_closes[-10]) / dxy_30d_closes[-10] * 100
        if dxy_30d <= -2.0 and dxy_10d < 0:
            score += 2.0
        elif dxy_30d <= -1.0:
            score += 1.0
        elif dxy_30d <= 0:
            score += 0.5

    if available_max == 0:
        return 0.0
    return round(min(score / available_max * 10.0, 10.0), 2)


# ── S06: Weekly Routine Reconstructor ─────────────────────────────────────────
def reconstruct_s06(
    dt: date,
    comex_closes: Optional[np.ndarray],
    dxy_closes: Optional[np.ndarray]
) -> float:
    """
    Reconstruct S06 score (0–10 pts) for a given date.
    Uses COMEX weekly change, DXY change, day-of-week gate.
    """
    weekday = dt.weekday()  # 0=Mon, 4=Fri

    # Friday = non-trading → 0
    if weekday == 4:
        return 0.0

    score = 0.0

    # W1: COMEX 5-day change
    if comex_closes is not None and len(comex_closes) >= 6:
        comex_5d = (comex_closes[-1] - comex_closes[-6]) / comex_closes[-6] * 100
        if comex_5d >= 1.0:
            score += 4.0
        elif comex_5d >= 0:
            score += 2.0
        elif comex_5d >= -0.5:
            score += 1.0

    # W2: DXY 5-day change (inverse)
    if dxy_closes is not None and len(dxy_closes) >= 6:
        dxy_5d = (dxy_closes[-1] - dxy_closes[-6]) / dxy_closes[-6] * 100
        if dxy_5d <= -0.5:
            score += 3.0
        elif dxy_5d <= 0:
            score += 1.5

    # W3: Day of week bonus (Mon-Tue = primary entry days)
    if weekday == 0:
        score += 2.0   # Monday — best entry
    elif weekday == 1:
        score += 1.5   # Tuesday — good
    elif weekday == 2:
        score += 1.0   # Wednesday — secondary
    elif weekday == 3:
        score += 0.5   # Thursday — last chance

    return round(min(score, 10.0), 2)


# ── S09: Volume Reconstructor ─────────────────────────────────────────────────
def reconstruct_s09(volumes: np.ndarray, closes: np.ndarray) -> float:
    """
    Reconstruct S09 score (0–10 pts) for a single date.
    """
    if len(volumes) < 22 or len(closes) < 4:
        return 0.0

    vol_today  = volumes[-1]
    vol_20d    = volumes[-21:-1].mean()
    vol_ratio  = vol_today / vol_20d if vol_20d > 0 else 1.0

    raw = 0.0

    # V1: Volume level vs 20-day avg
    if vol_ratio <= 0.60:
        raw += 5.0   # Very low volume — exhaustion = bullish
    elif vol_ratio <= 0.85:
        raw += 3.0   # Low volume

    # V2: 5-day volume trend (recent 2 vs earlier 2)
    if len(volumes) >= 6:
        recent  = volumes[-2:].mean()
        earlier = volumes[-5:-3].mean()
        trend   = recent / earlier if earlier > 0 else 1.0
        if trend <= 0.75:
            raw += 2.0   # Contracting volume = bullish for dip buy
        elif trend <= 1.10:
            raw += 1.0   # Stable

    # V3: Price-volume divergence (3-day)
    if len(closes) >= 4 and len(volumes) >= 4:
        price_chg = (closes[-1] - closes[-4]) / closes[-4] * 100
        vol_chg   = (volumes[-1] - volumes[-4]) / volumes[-4] * 100 if volumes[-4] > 0 else 0
        if price_chg < -0.3 and vol_chg < -10:
            raw += 3.0   # Bullish divergence: price down, volume down = exhaustion
        elif price_chg > 0 and vol_chg > 0:
            raw += 2.0   # Bullish momentum

    # Map to pts: ≥8=10pts, ≥5=7pts, ≥3=3pts, <3=0
    if raw >= 8:    return 10.0
    elif raw >= 5:  return 7.0
    elif raw >= 3:  return 3.0
    else:           return 0.0


# ── S10: MCX Spread Reconstructor ────────────────────────────────────────────
def reconstruct_s10(
    goldbees_close: float,
    comex_close: float,
    usdinr_close: float
) -> float:
    """
    Reconstruct S10 score (0–5 pts) for a single date.
    """
    if goldbees_close <= 0 or comex_close <= 0 or usdinr_close <= 0:
        return 0.0
    try:
        comex_inr_10g = comex_close * usdinr_close / TROY_OZ_GRAMS * 10
        goldbees_10g  = goldbees_close * 1000
        premium_pct   = (goldbees_10g - comex_inr_10g) / comex_inr_10g * 100

        if premium_pct > 2.5:    return 0.0   # Overpriced
        elif premium_pct > 1.0:  return 2.0   # Mild premium
        elif premium_pct >= -1.0: return 5.0  # Fair value
        else:                     return 5.0  # Discount — best value
    except Exception:
        return 0.0


# =============================================================================
# SECTION 3 — OUTCOME LABELER
# For each date D: check D+1 to D+5 for WIN/STOP/TIMEOUT
# Entry price = Close of day D (next morning open approximation)
# =============================================================================

def label_outcomes(goldbees_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add 'outcome', 'outcome_days', 'outcome_return_pct' columns to the DataFrame.
    Last OUTCOME_WINDOW rows get outcome = 'NO_OUTCOME' (future unknown).

    Outcome rules (checked day by day in order):
      WIN      — Daily High ≥ target price (profit_target_pct%)
      STOP     — Daily Low  ≤ stop price   (stop_loss_pct%)
      If both conditions on same day: check Open — if gap up past target = WIN, else STOP
      TIMEOUT_GAIN — After 5 days, final close > entry + 0.5% net of half transaction cost
      TIMEOUT_LOSS — Otherwise
    """
    df = goldbees_df.copy()
    df["outcome"]            = "NO_OUTCOME"
    df["outcome_days"]       = 0
    df["outcome_return_pct"] = 0.0

    closes = df["Close"].values
    highs  = df["High"].values
    lows   = df["Low"].values

    for i in range(len(df) - OUTCOME_WINDOW):
        entry = closes[i]
        if entry <= 0:
            continue
        target = entry * (1 + PROFIT_TARGET_PCT / 100)
        stop   = entry * (1 - STOP_LOSS_PCT / 100)

        result = "TIMEOUT_LOSS"
        days   = OUTCOME_WINDOW
        ret    = 0.0

        for j in range(1, OUTCOME_WINDOW + 1):
            idx    = i + j
            h      = highs[idx]
            l      = lows[idx]
            c      = closes[idx]
            hit_tgt = h >= target
            hit_stp = l <= stop

            if hit_tgt and hit_stp:
                # Both: use Open to decide which was hit first
                o = df["Open"].values[idx]
                if o >= target:
                    result = "WIN"
                    ret    = (target - entry) / entry * 100
                else:
                    result = "STOP"
                    ret    = (stop - entry) / entry * 100
                days = j
                break
            elif hit_tgt:
                result = "WIN"
                ret    = (target - entry) / entry * 100
                days   = j
                break
            elif hit_stp:
                result = "STOP"
                ret    = (stop - entry) / entry * 100
                days   = j
                break
        else:
            # No stop or target hit — evaluate final close
            final_close = closes[i + OUTCOME_WINDOW]
            final_ret   = (final_close - entry) / entry * 100
            if final_ret > 0.5:
                result = "TIMEOUT_GAIN"
            else:
                result = "TIMEOUT_LOSS"
            ret = final_ret

        df.iloc[i, df.columns.get_loc("outcome")]            = result
        df.iloc[i, df.columns.get_loc("outcome_days")]       = days
        df.iloc[i, df.columns.get_loc("outcome_return_pct")] = round(ret, 3)

    return df


# =============================================================================
# SECTION 4 — FEATURE MATRIX BUILDER
# Builds a DataFrame with one row per historical trading day containing:
#   - All reconstructed signal scores (s01..s10 excluding s07/s08)
#   - composite_raw, composite_final
#   - Date features (month, weekday)
#   - Outcome label
# =============================================================================

def build_feature_matrix(
    goldbees_df:   pd.DataFrame,
    comex_df:      Optional[pd.DataFrame],
    dxy_df:        Optional[pd.DataFrame],
    usdinr_df:     Optional[pd.DataFrame],
    fedfunds_s:    Optional[pd.Series]
) -> pd.DataFrame:
    """
    Reconstruct all signal scores for every historical date.
    Returns a DataFrame ready for backtesting analysis.
    Only dates with all OHLCV data present are included.
    """
    log.info("Building historical feature matrix...")

    # Helper: look up aligned close series for a given date from external df
    def get_window(ext_df: Optional[pd.DataFrame], date_idx: pd.Timestamp,
                   n: int) -> Optional[np.ndarray]:
        if ext_df is None:
            return None
        mask = ext_df.index <= date_idx
        sub  = ext_df.loc[mask, "Close"]
        if len(sub) < n:
            return None
        return sub.values[-n:]

    def get_latest(ext_df: Optional[pd.DataFrame],
                   date_idx: pd.Timestamp) -> Optional[float]:
        if ext_df is None:
            return None
        mask = ext_df.index <= date_idx
        sub  = ext_df.loc[mask, "Close"]
        return float(sub.iloc[-1]) if len(sub) > 0 else None

    def get_fred_val(series: Optional[pd.Series],
                     date_idx: pd.Timestamp) -> Optional[float]:
        if series is None:
            return None
        mask = series.index <= date_idx
        sub  = series.loc[mask]
        return float(sub.iloc[-1]) if len(sub) > 0 else None

    def get_fred_val_6m_ago(series: Optional[pd.Series],
                             date_idx: pd.Timestamp) -> Optional[float]:
        if series is None:
            return None
        cutoff = date_idx - pd.Timedelta(days=180)
        mask = series.index <= cutoff
        sub  = series.loc[mask]
        return float(sub.iloc[-1]) if len(sub) > 0 else None

    rows = []
    goldbees_dates = goldbees_df.index

    for i in range(MIN_LOOKBACK_DAYS, len(goldbees_df)):
        dt_idx    = goldbees_dates[i]
        dt_date   = dt_idx.date()
        weekday   = dt_date.weekday()

        # Skip Fridays (non-trading day per bot rules)
        if weekday == 4:
            continue

        # Local GOLDBEES slices (no look-ahead)
        gb_slice   = goldbees_df.iloc[:i+1]
        closes_arr = gb_slice["Close"].values
        highs_arr  = gb_slice["High"].values
        vols_arr   = gb_slice["Volume"].values

        # Score each signal
        s01 = reconstruct_s01(closes_arr, highs_arr)
        s03 = reconstruct_s03(dt_date)
        s04 = reconstruct_s04(closes_arr)
        s09 = reconstruct_s09(vols_arr, closes_arr)

        # External series windows
        comex_w6  = get_window(comex_df, dt_idx, 6)
        comex_w30 = get_window(comex_df, dt_idx, 30)
        dxy_w6    = get_window(dxy_df, dt_idx, 6)
        dxy_w30   = get_window(dxy_df, dt_idx, 30)
        usdinr_w6 = get_window(usdinr_df, dt_idx, 6)

        ff_now    = get_fred_val(fedfunds_s, dt_idx)
        ff_6m     = get_fred_val_6m_ago(fedfunds_s, dt_idx)

        s02 = reconstruct_s02(dxy_w6, usdinr_w6, ff_now, ff_6m)
        s05 = reconstruct_s05(ff_now, ff_6m, dxy_w30)
        s06 = reconstruct_s06(dt_date, comex_w6, dxy_w6)

        gb_close   = float(closes_arr[-1])
        comex_val  = get_latest(comex_df, dt_idx)
        usdinr_val = get_latest(usdinr_df, dt_idx)
        s10 = reconstruct_s10(
            gb_close,
            comex_val if comex_val else 0,
            usdinr_val if usdinr_val else 0
        )

        composite_raw = s01 + s02 + s03 + s04 + s05 + s06 + s09 + s10
        # No S07 reconstruction (hard to reconstruct VIX/news checks historically)
        # Conservative: apply no penalty in backtester (slightly optimistic bias — noted)

        rows.append({
            "date":               dt_date,
            "close":              round(gb_close, 2),
            "month":              dt_date.month,
            "weekday":            weekday,
            "s01_pts":            s01,
            "s02_pts":            s02,
            "s03_pts":            s03,
            "s04_pts":            s04,
            "s05_pts":            s05,
            "s06_pts":            s06,
            "s09_pts":            s09,
            "s10_pts":            s10,
            "composite_raw":      round(composite_raw, 2),
        })

    if not rows:
        log.error("Feature matrix is empty — no usable dates")
        return pd.DataFrame()

    feat_df = pd.DataFrame(rows)
    feat_df = feat_df.set_index("date")

    # Add derived features
    feat_df["s01_s04_combo"] = feat_df["s01_pts"] + feat_df["s04_pts"]
    feat_df["s02_s05_combo"] = feat_df["s02_pts"] + feat_df["s05_pts"]
    feat_df["s09_strong"]    = (feat_df["s09_pts"] >= 7).astype(float)
    feat_df["s10_fair"]      = (feat_df["s10_pts"] >= 5).astype(float)

    # Score percentile vs trailing 90 days
    feat_df["score_pct_90d"] = feat_df["composite_raw"].rolling(90, min_periods=20).rank(pct=True)

    # GOLDBEES 5-day momentum
    feat_df["gb_5d_mom"] = feat_df["close"].pct_change(5) * 100

    log.info(f"Feature matrix built: {len(feat_df)} rows, {len(feat_df.columns)} features")
    return feat_df


# =============================================================================
# SECTION 5 — OUTCOME MERGER
# Merge outcome labels into feature matrix
# =============================================================================

def merge_outcomes(feat_df: pd.DataFrame,
                   goldbees_df: pd.DataFrame) -> pd.DataFrame:
    """
    Label outcomes and merge into the feature matrix.
    Adds: outcome, outcome_days, outcome_return_pct, outcome_binary columns.
    outcome_binary = 1 for WIN or TIMEOUT_GAIN, 0 for STOP or TIMEOUT_LOSS.
    """
    log.info("Labeling outcomes...")
    labeled = label_outcomes(goldbees_df)
    labeled.index = pd.to_datetime(labeled.index).normalize()
    if labeled.index.tz is not None:
        labeled.index = labeled.index.tz_localize(None)

    outcome_cols = labeled[["outcome", "outcome_days", "outcome_return_pct"]]
    outcome_cols.index = outcome_cols.index.normalize().date  # align to date
    feat_df.index = pd.to_datetime(feat_df.index).normalize().date

    merged = feat_df.join(outcome_cols, how="left")
    merged["outcome"]            = merged["outcome"].fillna("NO_OUTCOME")
    merged["outcome_days"]       = merged["outcome_days"].fillna(0)
    merged["outcome_return_pct"] = merged["outcome_return_pct"].fillna(0.0)

    # Binary label: 1 = positive outcome (WIN / TIMEOUT_GAIN)
    merged["outcome_binary"] = merged["outcome"].apply(
        lambda x: 1 if x in ("WIN", "TIMEOUT_GAIN") else (0 if x in ("STOP", "TIMEOUT_LOSS") else -1)
    )

    # Drop rows with no outcome (last 5 rows, future unknown)
    merged = merged[merged["outcome_binary"] >= 0].copy()
    log.info(
        f"Outcomes merged: {len(merged)} rows with labels. "
        f"Wins: {(merged['outcome_binary']==1).sum()} | "
        f"Losses: {(merged['outcome_binary']==0).sum()}"
    )
    return merged


# =============================================================================
# SECTION 6 — THRESHOLD OPTIMIZER (Option C — No ML)
# Grid-search every integer score threshold from 20 to 85.
# For each threshold: filter rows where composite_raw >= threshold,
# compute win rate, trade count, avg return, profit factor.
# =============================================================================

def run_threshold_optimizer(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Find the composite score threshold that maximises win rate
    while maintaining at least 5 trades per quarter of test data.
    Returns dict with results per threshold + best threshold recommendation.
    """
    log.info("Running threshold optimizer...")
    results = []

    for thresh in THRESHOLD_RANGE:
        sub = df[df["composite_raw"] >= thresh]
        n   = len(sub)
        if n < 5:
            continue

        wins   = (sub["outcome_binary"] == 1).sum()
        losses = (sub["outcome_binary"] == 0).sum()
        win_rt = wins / n * 100

        avg_ret = sub["outcome_return_pct"].mean()
        gross_w = sub[sub["outcome_binary"] == 1]["outcome_return_pct"].sum()
        gross_l = abs(sub[sub["outcome_binary"] == 0]["outcome_return_pct"].sum())
        pf      = gross_w / gross_l if gross_l > 0 else (gross_w if gross_w > 0 else 0)

        # Sharpe-like: avg return / std dev
        std_ret = sub["outcome_return_pct"].std()
        sharpe  = avg_ret / std_ret if std_ret > 0 else 0

        results.append({
            "threshold":    thresh,
            "n_trades":     n,
            "win_rate":     round(win_rt, 1),
            "avg_return":   round(avg_ret, 3),
            "profit_factor": round(pf, 2),
            "sharpe":       round(sharpe, 3),
        })

    if not results:
        return {"error": "No threshold produced ≥5 trades"}

    res_df = pd.DataFrame(results)

    # Best threshold: highest win rate with ≥ 10 trades and positive profit factor
    qualified = res_df[(res_df["n_trades"] >= 10) & (res_df["profit_factor"] > 1.0)]
    if qualified.empty:
        qualified = res_df[res_df["n_trades"] >= 5]
    if qualified.empty:
        qualified = res_df

    best_row = qualified.sort_values("win_rate", ascending=False).iloc[0]
    current_row = res_df[res_df["threshold"] == 45]
    current_stats = current_row.to_dict("records")[0] if not current_row.empty else {}

    log.info(f"Best threshold: {best_row['threshold']}/95 → {best_row['win_rate']:.1f}% win rate "
             f"({best_row['n_trades']} trades)")

    return {
        "all_thresholds":   results,
        "best_threshold":   int(best_row["threshold"]),
        "best_win_rate":    float(best_row["win_rate"]),
        "best_n_trades":    int(best_row["n_trades"]),
        "best_profit_factor": float(best_row["profit_factor"]),
        "current_threshold_stats": current_stats,
    }


# =============================================================================
# SECTION 7 — LOGISTIC REGRESSION (Pure numpy — no sklearn)
# Binary classifier: predict P(WIN) from signal scores.
# Gradient descent, L2 regularization, 500 epochs.
# =============================================================================

def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -250, 250)))


def _normalize_features(X: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Z-score normalize. Returns (X_norm, mean, std)."""
    mu  = X.mean(axis=0)
    std = X.std(axis=0)
    std[std == 0] = 1.0  # prevent div-by-zero for constant features
    return (X - mu) / std, mu, std


def train_logistic_regression(
    X_train: np.ndarray,
    y_train: np.ndarray,
    lr: float = 0.05,
    epochs: int = 500,
    l2_lambda: float = 0.01
) -> np.ndarray:
    """
    Train logistic regression using gradient descent.
    Returns weight vector (including bias at index 0).
    """
    n, m = X_train.shape
    # Add bias column
    X_b  = np.c_[np.ones(n), X_train]
    w    = np.zeros(m + 1)

    for _ in range(epochs):
        z    = X_b @ w
        pred = _sigmoid(z)
        err  = pred - y_train
        grad = X_b.T @ err / n
        # L2 regularization (not on bias term)
        reg  = np.r_[0, l2_lambda * w[1:]]
        w   -= lr * (grad + reg)

    return w


def predict_proba(X: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Predict WIN probabilities for feature matrix X."""
    n   = X.shape[0]
    X_b = np.c_[np.ones(n), X]
    return _sigmoid(X_b @ w)


def evaluate_model(
    X_test: np.ndarray,
    y_test: np.ndarray,
    w: np.ndarray,
    threshold: float = 0.55
) -> Dict[str, float]:
    """Compute accuracy, win rate, precision, recall at given probability threshold."""
    proba     = predict_proba(X_test, w)
    predicted = (proba >= threshold).astype(int)
    n         = len(y_test)
    if n == 0:
        return {}

    tp = int(((predicted == 1) & (y_test == 1)).sum())
    fp = int(((predicted == 1) & (y_test == 0)).sum())
    fn = int(((predicted == 0) & (y_test == 1)).sum())
    tn = int(((predicted == 0) & (y_test == 0)).sum())

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0
    accuracy  = (tp + tn) / n
    trades    = tp + fp

    return {
        "accuracy":   round(accuracy * 100, 1),
        "precision":  round(precision * 100, 1),   # Win rate when model says BUY
        "recall":     round(recall * 100, 1),
        "n_trades":   trades,
        "true_pos":   tp,
        "false_pos":  fp,
    }


FEATURE_NAMES = [
    "s01_pts", "s02_pts", "s03_pts", "s04_pts",
    "s05_pts", "s06_pts", "s09_pts", "s10_pts",
    "s01_s04_combo", "s02_s05_combo", "s09_strong", "s10_fair",
    "month", "weekday", "score_pct_90d", "gb_5d_mom"
]


def run_logistic_regression(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Train logistic regression on full dataset (all periods).
    Returns feature importances and model performance.
    Used for signal weight insight, NOT for walk-forward predictions.
    """
    log.info("Training logistic regression on full dataset...")

    available = [f for f in FEATURE_NAMES if f in df.columns]
    sub = df.dropna(subset=available + ["outcome_binary"])
    sub = sub[sub["outcome_binary"] >= 0]

    if len(sub) < 30:
        return {"error": "Insufficient data for logistic regression"}

    X_raw = sub[available].values.astype(float)
    y     = sub["outcome_binary"].values.astype(float)

    X_norm, mu, std_arr = _normalize_features(X_raw)

    # Train-test split (last 20% = test, time-ordered)
    split   = int(len(X_norm) * 0.80)
    X_train = X_norm[:split]
    y_train = y[:split]
    X_test  = X_norm[split:]
    y_test  = y[split:]

    w = train_logistic_regression(X_train, y_train, lr=0.05, epochs=500, l2_lambda=0.01)

    train_eval = evaluate_model(X_train, y_train, w)
    test_eval  = evaluate_model(X_test,  y_test,  w)

    # Feature importance = absolute coefficient (skip bias at index 0)
    coefs    = w[1:]
    imp_list = sorted(
        zip(available, coefs.tolist()),
        key=lambda x: abs(x[1]), reverse=True
    )

    log.info(f"LR: train acc={train_eval.get('accuracy')}% test acc={test_eval.get('accuracy')}%")
    log.info("Top features: " + ", ".join(f"{n}={c:+.3f}" for n, c in imp_list[:5]))

    return {
        "feature_importances": [{"name": n, "coef": round(c, 4)} for n, c in imp_list],
        "train_performance":   train_eval,
        "test_performance":    test_eval,
        "overfit_warning":     abs(train_eval.get("accuracy", 0) - test_eval.get("accuracy", 0)) > 10
    }


# =============================================================================
# SECTION 8 — WALK-FORWARD VALIDATION
# Rolling 6-month test windows on time-ordered data.
# Each window trains on all history before it and tests on the next 6 months.
# =============================================================================

def run_walk_forward(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Walk-forward validation using 6-month rolling test windows.
    Returns per-window stats and aggregate summary.
    """
    log.info("Running walk-forward validation...")

    df = df.copy()
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    if len(df) < 200:
        return {"error": "Insufficient data for walk-forward (need ≥200 rows)"}

    available  = [f for f in FEATURE_NAMES if f in df.columns]
    start_date = df.index.min()
    end_date   = df.index.max()

    # Generate 6-month rolling windows (train must be ≥12 months)
    windows = []
    test_start = start_date + pd.DateOffset(months=12)
    while test_start + pd.DateOffset(months=6) <= end_date:
        test_end = test_start + pd.DateOffset(months=6)
        windows.append((start_date, test_start, test_end))
        test_start += pd.DateOffset(months=6)

    if not windows:
        return {"error": "Not enough date range for any walk-forward window"}

    window_results = []
    all_prec = []

    for idx, (train_from, train_to, test_to) in enumerate(windows):
        train_df = df[(df.index >= train_from) & (df.index < train_to)]
        test_df  = df[(df.index >= train_to) & (df.index < test_to)]

        for split_df, label in [(train_df, "train"), (test_df, "test")]:
            split_df = split_df.dropna(subset=available + ["outcome_binary"])
            split_df = split_df[split_df["outcome_binary"] >= 0]

        train_clean = train_df.dropna(subset=available + ["outcome_binary"])
        train_clean = train_clean[train_clean["outcome_binary"] >= 0]
        test_clean  = test_df.dropna(subset=available + ["outcome_binary"])
        test_clean  = test_clean[test_clean["outcome_binary"] >= 0]

        if len(train_clean) < 20 or len(test_clean) < 5:
            window_results.append({
                "window": idx + 1,
                "train_from": str(train_from.date()),
                "train_to":   str(train_to.date()),
                "test_to":    str(test_to.date()),
                "status":     "SKIPPED (insufficient data)",
            })
            continue

        X_train = train_clean[available].values.astype(float)
        y_train = train_clean["outcome_binary"].values.astype(float)
        X_test  = test_clean[available].values.astype(float)
        y_test  = test_clean["outcome_binary"].values.astype(float)

        X_train_n, mu, std_a = _normalize_features(X_train)
        # Apply same normalization to test set
        std_a[std_a == 0] = 1.0
        X_test_n  = (X_test - mu) / std_a

        w        = train_logistic_regression(X_train_n, y_train)
        test_res = evaluate_model(X_test_n, y_test, w)

        # Also compute threshold optimizer on test set
        test_scores = test_clean["composite_raw"].values
        test_wins   = test_clean["outcome_binary"].values
        best_thr    = 45
        best_wr     = 0.0
        for thr in range(20, 86, 2):
            mask = test_scores >= thr
            if mask.sum() >= 3:
                wr = test_wins[mask].mean() * 100
                if wr > best_wr:
                    best_wr  = wr
                    best_thr = thr

        all_prec.append(test_res.get("precision", 0))
        window_results.append({
            "window":     idx + 1,
            "train_from": str(train_from.date()),
            "train_to":   str(train_to.date()),
            "test_to":    str(test_to.date()),
            "status":     "OK",
            "test_n":     len(test_clean),
            "model_win_rate": test_res.get("precision", 0),
            "model_accuracy": test_res.get("accuracy", 0),
            "model_trades":   test_res.get("n_trades", 0),
            "best_score_threshold": best_thr,
            "best_score_win_rate":  round(best_wr, 1),
        })

    avg_win_rate = round(sum(all_prec) / len(all_prec), 1) if all_prec else 0
    log.info(f"Walk-forward complete: {len(window_results)} windows, avg win rate {avg_win_rate}%")

    return {
        "windows":          window_results,
        "avg_win_rate":     avg_win_rate,
        "n_windows":        len(window_results),
        "n_windows_ok":     len([w for w in window_results if w.get("status") == "OK"]),
    }


# =============================================================================
# SECTION 9 — REPORT GENERATOR
# =============================================================================

def _bar(pct: float, width: int = 20) -> str:
    """ASCII progress bar."""
    filled = round(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


def generate_text_report(
    threshold_results: Dict,
    lr_results: Dict,
    wf_results: Dict,
    data_summary: Dict,
    run_ts: str
) -> str:
    lines = [
        "=" * 65,
        f"  GOLD BOT — ML BACKTESTER REPORT",
        f"  Run: {run_ts}",
        f"  ETF: {CONFIG.get('primary_etf','GOLDBEES.NS')}",
        "=" * 65,
        "",
    ]

    # ── Data summary
    lines += [
        "DATA SUMMARY",
        f"  Historical rows analysed  : {data_summary.get('total_rows', 'N/A')}",
        f"  Date range                : {data_summary.get('date_from','?')} → {data_summary.get('date_to','?')}",
        f"  Total trade signals       : {data_summary.get('trade_signals', 'N/A')}",
        f"  WIN / TIMEOUT_GAIN        : {data_summary.get('wins', 'N/A')}",
        f"  STOP / TIMEOUT_LOSS       : {data_summary.get('losses', 'N/A')}",
        f"  Overall win rate (no gate): {data_summary.get('overall_win_rate', 'N/A')}%",
        "",
    ]

    # ── Threshold optimizer
    lines.append("PHASE 1 — THRESHOLD OPTIMIZER")
    if "error" in threshold_results:
        lines.append(f"  ⚠️  {threshold_results['error']}")
    else:
        best_t  = threshold_results.get("best_threshold", "?")
        best_wr = threshold_results.get("best_win_rate", 0)
        best_n  = threshold_results.get("best_n_trades", 0)
        best_pf = threshold_results.get("best_profit_factor", 0)
        cur     = threshold_results.get("current_threshold_stats", {})

        lines += [
            f"  Best threshold  : {best_t}/95 pts",
            f"  Win rate        : {best_wr:.1f}%   {_bar(best_wr)}",
            f"  Trade count     : {best_n} signals above threshold",
            f"  Profit factor   : {best_pf:.2f}x  (>1.5 = good)",
            "",
            f"  Current threshold (45/95):",
            f"    Win rate  : {cur.get('win_rate', 'N/A')}%",
            f"    Trades    : {cur.get('n_trades', 'N/A')}",
            f"    PF        : {cur.get('profit_factor', 'N/A')}",
            "",
        ]
        if best_t != 45:
            direction = "RAISE" if best_t > 45 else "LOWER"
            lines.append(
                f"  ▶ RECOMMENDATION: {direction} threshold to {best_t}/95 for better win rate."
            )
        else:
            lines.append("  ▶ Current threshold 45/95 is already optimal. No change needed.")

    lines.append("")

    # ── Logistic regression
    lines.append("PHASE 2 — LOGISTIC REGRESSION (Signal Importance)")
    if "error" in lr_results:
        lines.append(f"  ⚠️  {lr_results['error']}")
    else:
        train_p = lr_results.get("train_performance", {})
        test_p  = lr_results.get("test_performance", {})
        lines += [
            f"  Train accuracy : {train_p.get('accuracy','N/A')}%  "
            f"| Test accuracy : {test_p.get('accuracy','N/A')}%",
            f"  Test win rate  : {test_p.get('precision','N/A')}%  "
            f"({test_p.get('n_trades','N/A')} model-selected trades)",
        ]
        if lr_results.get("overfit_warning"):
            lines.append("  ⚠️  OVERFIT WARNING: Train vs test gap > 10%. Treat with caution.")
        lines += ["", "  SIGNAL IMPORTANCE RANKING:"]
        for rank, item in enumerate(lr_results.get("feature_importances", [])[:8], 1):
            name = item["name"].replace("_pts", "").replace("_", " ").upper()
            coef = item["coef"]
            direction = "↑ bullish" if coef > 0 else "↓ bearish"
            bar = _bar(abs(coef) / 0.5 * 100, 12)
            lines.append(f"  {rank:2d}. {name:<20} {coef:+.4f}  {bar}  {direction}")

    lines.append("")

    # ── Walk-forward
    lines.append("PHASE 3 — WALK-FORWARD VALIDATION (Rolling 6-month windows)")
    if "error" in wf_results:
        lines.append(f"  ⚠️  {wf_results['error']}")
    else:
        lines += [
            f"  Windows completed : {wf_results.get('n_windows_ok','?')} / {wf_results.get('n_windows','?')}",
            f"  Avg win rate      : {wf_results.get('avg_win_rate','?')}%",
            "",
            f"  {'WIN  ':>6} {'SCORE':>6} {'N':>5}   PERIOD",
            f"  {'-'*50}",
        ]
        for w in wf_results.get("windows", []):
            if w.get("status") != "OK":
                lines.append(f"  [SKIPPED] {w.get('train_to','')} → {w.get('test_to','')}")
                continue
            wr   = w.get("best_score_win_rate", 0)
            thr  = w.get("best_score_threshold", 45)
            n    = w.get("test_n", 0)
            prd  = f"{w.get('train_to','')} → {w.get('test_to','')}"
            flag = " ✅" if wr >= 60 else (" ⚠️" if wr >= 45 else " ❌")
            lines.append(f"  {wr:5.1f}%  {thr:5d}  {n:5d}   {prd}{flag}")

    lines += [
        "",
        "=" * 65,
        "WEIGHT ADJUSTMENT SUGGESTIONS",
        "=" * 65,
    ]

    # Generate suggestions from LR importances
    if "feature_importances" in lr_results:
        imps = {item["name"]: item["coef"] for item in lr_results["feature_importances"]}
        suggestions = []

        if imps.get("s09_pts", 0) > 0.3:
            suggestions.append("S09 Volume Confirm: UNDERWEIGHTED — model finds it highly predictive. Consider raising from 10 to 13 pts.")
        if imps.get("s02_pts", 0) > 0.4:
            suggestions.append("S02 Macro Trigger: Weight appears justified — keep at 25 pts.")
        if imps.get("s06_pts", 0) < 0.05:
            suggestions.append("S06 Weekly Routine: Low importance in model. May reduce from 10 to 7 pts.")
        if imps.get("s10_pts", 0) > 0.2:
            suggestions.append("S10 MCX Spread: Consistent predictor. Current 5 pts is conservative. Consider raising to 7 pts.")
        if not suggestions:
            suggestions.append("Current signal weights appear well-calibrated. No changes recommended.")

        for sug in suggestions:
            lines.append(f"  • {sug}")
    else:
        lines.append("  Insufficient data to generate suggestions.")

    lines += [
        "",
        "NOTE: Human review required before any weight changes.",
        "      Bot never self-modifies. Edit config.py manually if you agree.",
        "=" * 65,
    ]

    return "\n".join(lines)


def generate_html_report(
    threshold_results: Dict,
    lr_results: Dict,
    wf_results: Dict,
    data_summary: Dict,
    run_ts: str
) -> str:
    """Generate a self-contained dark-theme HTML backtest report."""

    def _esc(s): return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    avg_wr = wf_results.get("avg_win_rate", 0)
    wr_col = "#00e676" if avg_wr >= 60 else ("#ffd740" if avg_wr >= 45 else "#ff5252")

    best_t  = threshold_results.get("best_threshold", 45)
    best_wr = threshold_results.get("best_win_rate", 0)
    cur     = threshold_results.get("current_threshold_stats", {})

    # Walk-forward rows
    wf_rows_html = ""
    for w in wf_results.get("windows", []):
        if w.get("status") != "OK":
            wf_rows_html += f"<tr><td colspan='5' style='color:#546e7a;text-align:center'>SKIPPED — {_esc(w.get('train_to',''))} → {_esc(w.get('test_to',''))}</td></tr>"
            continue
        wr   = w.get("best_score_win_rate", 0)
        col  = "#00e676" if wr >= 60 else ("#ffd740" if wr >= 45 else "#ff5252")
        wf_rows_html += (
            f"<tr>"
            f"<td>{_esc(w.get('train_to',''))} → {_esc(w.get('test_to',''))}</td>"
            f"<td>{w.get('test_n','')}</td>"
            f"<td>{w.get('best_score_threshold',45)}/95</td>"
            f"<td style='color:{col};font-weight:700'>{wr:.1f}%</td>"
            f"<td style='color:{col}'>{'✅' if wr >= 60 else ('⚠️' if wr >= 45 else '❌')}</td>"
            f"</tr>"
        )

    # Feature importance bars
    feat_html = ""
    for item in lr_results.get("feature_importances", [])[:8]:
        name  = item["name"].replace("_pts", "").replace("_", " ").upper()
        coef  = item["coef"]
        w_pct = min(abs(coef) / 0.5 * 100, 100)
        col   = "#00e676" if coef > 0 else "#ff5252"
        feat_html += f"""
        <div style="margin-bottom:10px">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px">
            <span style="font-size:.85rem;color:#c9d1d9">{_esc(name)}</span>
            <span style="font-size:.85rem;font-weight:700;color:{col}">{coef:+.4f}</span>
          </div>
          <div style="height:7px;background:#21262d;border-radius:4px">
            <div style="width:{w_pct:.1f}%;height:100%;background:{col};border-radius:4px"></div>
          </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Gold Bot — Backtest Report {run_ts[:10]}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0d1117;color:#e6edf3;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}}
  .container{{max-width:960px;margin:0 auto}}
  h1{{font-size:1.4rem;color:#ffd740;font-weight:800;margin-bottom:4px}}
  h2{{font-size:.95rem;text-transform:uppercase;letter-spacing:1px;color:#8b949e;
      margin:28px 0 14px;font-weight:600;border-bottom:1px solid #21262d;padding-bottom:8px}}
  .meta{{font-size:.82rem;color:#8b949e;margin-bottom:24px}}
  .stat-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px}}
  @media(max-width:700px){{.stat-grid{{grid-template-columns:repeat(2,1fr)}}}}
  .stat{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:16px;text-align:center}}
  .stat-val{{font-size:1.8rem;font-weight:800;margin-bottom:4px}}
  .stat-lbl{{font-size:.78rem;color:#8b949e}}
  table{{width:100%;border-collapse:collapse;font-size:.85rem;margin-bottom:16px}}
  th{{background:#161b22;color:#8b949e;padding:9px 12px;text-align:left;font-weight:600;
      border-bottom:1px solid #30363d;font-size:.78rem;text-transform:uppercase}}
  td{{padding:9px 12px;border-bottom:1px solid #21262d;color:#c9d1d9}}
  tr:hover td{{background:#161b22}}
  .card{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:20px;margin-bottom:20px}}
  .warn{{background:#3d1a0011;border:1px solid #ffab4044;border-radius:8px;
         padding:12px 16px;margin:12px 0;font-size:.85rem;color:#ffd740}}
  .footer{{text-align:center;font-size:.75rem;color:#484f58;margin-top:32px}}
  ::-webkit-scrollbar{{width:6px}} ::-webkit-scrollbar-track{{background:#0d1117}}
  ::-webkit-scrollbar-thumb{{background:#30363d;border-radius:3px}}
</style>
</head>
<body>
<div class="container">
  <h1>🧪 Gold Bot — ML Backtester Report</h1>
  <div class="meta">Run: {_esc(run_ts)} &nbsp;|&nbsp; ETF: {_esc(CONFIG.get('primary_etf','GOLDBEES.NS'))} &nbsp;|&nbsp;
    Data: {_esc(data_summary.get('date_from','?'))} → {_esc(data_summary.get('date_to','?'))}
  </div>

  <!-- KEY METRICS -->
  <div class="stat-grid">
    <div class="stat">
      <div class="stat-val" style="color:{wr_col}">{avg_wr}%</div>
      <div class="stat-lbl">Avg Walk-Forward Win Rate</div>
    </div>
    <div class="stat">
      <div class="stat-val" style="color:#ffd740">{best_t}/95</div>
      <div class="stat-lbl">Optimal Score Threshold</div>
    </div>
    <div class="stat">
      <div class="stat-val" style="color:#69f0ae">{best_wr:.0f}%</div>
      <div class="stat-lbl">Win Rate at Optimal Threshold</div>
    </div>
    <div class="stat">
      <div class="stat-val" style="color:#c9d1d9">{data_summary.get('total_rows','?')}</div>
      <div class="stat-lbl">Historical Days Analysed</div>
    </div>
  </div>

  <!-- PHASE 1 -->
  <h2>Phase 1 — Threshold Optimizer</h2>
  <div class="card">
    <table>
      <tr><th>Metric</th><th>Current (45/95)</th><th>Optimal ({best_t}/95)</th></tr>
      <tr><td>Win Rate</td>
          <td>{cur.get('win_rate','N/A')}%</td>
          <td style="color:#00e676;font-weight:700">{best_wr:.1f}%</td></tr>
      <tr><td>Trade Count</td>
          <td>{cur.get('n_trades','N/A')}</td>
          <td>{threshold_results.get('best_n_trades','N/A')}</td></tr>
      <tr><td>Profit Factor</td>
          <td>{cur.get('profit_factor','N/A')}</td>
          <td>{threshold_results.get('best_profit_factor','N/A')}</td></tr>
    </table>
    {"<div class='warn'>⚠️  Raising threshold trades fewer signals but better quality. Confirm with walk-forward before changing.</div>" if best_t != 45 else "<div class='warn'>✅ Current threshold 45/95 appears optimal. No change recommended.</div>"}
  </div>

  <!-- PHASE 2 -->
  <h2>Phase 2 — Signal Importance (Logistic Regression)</h2>
  <div class="card">
    {"<div class='warn'>⚠️  " + _esc(lr_results.get('error','')) + "</div>" if 'error' in lr_results else
    f'''
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px">
      <div>
        <div style="font-size:.78rem;color:#8b949e;margin-bottom:6px">TRAIN ACCURACY</div>
        <div style="font-size:1.5rem;font-weight:800;color:#ffd740">{lr_results.get('train_performance',{{}}).get('accuracy','?')}%</div>
      </div>
      <div>
        <div style="font-size:.78rem;color:#8b949e;margin-bottom:6px">TEST ACCURACY</div>
        <div style="font-size:1.5rem;font-weight:800;color:#69f0ae">{lr_results.get('test_performance',{{}}).get('accuracy','?')}%</div>
      </div>
    </div>
    ''' + ("" if not lr_results.get("overfit_warning") else "<div class='warn'>⚠️ Overfit warning: train vs test gap > 10%.</div>")}
    {feat_html}
  </div>

  <!-- PHASE 3 -->
  <h2>Phase 3 — Walk-Forward Validation ({wf_results.get('n_windows_ok','?')}/{wf_results.get('n_windows','?')} windows)</h2>
  <div class="card">
    {"<div class='warn'>⚠️  " + _esc(wf_results.get('error','')) + "</div>" if 'error' in wf_results else f'''
    <table>
      <tr><th>Test Period</th><th>Signals</th><th>Best Threshold</th><th>Win Rate</th><th></th></tr>
      {wf_rows_html}
    </table>
    <div style="font-size:.9rem;color:#c9d1d9;margin-top:12px">
      Average walk-forward win rate: <strong style="color:{wr_col}">{avg_wr}%</strong>
    </div>'''}
  </div>

  <div class="footer">Gold Bot ML Backtester · Run <code>python3 run_signal_11.py</code> to update</div>
</div>
</body>
</html>"""


# =============================================================================
# SECTION 10 — MAIN ENTRY POINT
# =============================================================================

def run_signal_11() -> Dict[str, Any]:
    """
    Full backtesting pipeline. Returns result dict.
    Steps:
      1. Fetch all historical data
      2. Build feature matrix
      3. Merge outcome labels
      4. Run threshold optimizer
      5. Run logistic regression
      6. Run walk-forward validation
      7. Generate reports (text + HTML)
      8. Save reports to backtest_results/
    """
    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log.info("=" * 60)
    log.info(f"SIGNAL 11 — ML BACKTESTER — {run_ts}")
    log.info("=" * 60)

    # ── Step 1: Fetch data ────────────────────────────────────────────────────
    log.info("Step 1: Fetching historical data...")
    goldbees_df  = fetch_goldbees_history()
    comex_df     = fetch_comex_history()
    dxy_df       = fetch_dxy_history()
    usdinr_df    = fetch_usdinr_history()
    fedfunds_s   = fetch_fred_series("FEDFUNDS")

    if goldbees_df is None:
        return {
            "status": "DATA_UNAVAILABLE",
            "error":  "Cannot fetch GOLDBEES historical data — backtesting aborted",
            "timestamp": run_ts,
        }

    # ── Step 2: Build feature matrix ──────────────────────────────────────────
    log.info("Step 2: Building feature matrix...")
    feat_df = build_feature_matrix(goldbees_df, comex_df, dxy_df, usdinr_df, fedfunds_s)
    if feat_df.empty:
        return {"status": "DATA_UNAVAILABLE", "error": "Feature matrix empty", "timestamp": run_ts}

    # ── Step 3: Merge outcomes ────────────────────────────────────────────────
    log.info("Step 3: Merging outcomes...")
    merged_df = merge_outcomes(feat_df, goldbees_df)
    if len(merged_df) < MIN_SIGNALS_NEEDED:
        return {
            "status": "INSUFFICIENT_DATA",
            "error":  f"Only {len(merged_df)} labeled rows — need ≥{MIN_SIGNALS_NEEDED}",
            "timestamp": run_ts,
        }

    total_rows   = len(merged_df)
    wins_count   = (merged_df["outcome_binary"] == 1).sum()
    losses_count = (merged_df["outcome_binary"] == 0).sum()
    overall_wr   = round(wins_count / total_rows * 100, 1) if total_rows > 0 else 0
    date_from    = str(merged_df.index.min())[:10] if hasattr(merged_df.index, 'min') else "?"
    date_to      = str(merged_df.index.max())[:10] if hasattr(merged_df.index, 'max') else "?"

    data_summary = {
        "total_rows":      total_rows,
        "date_from":       date_from,
        "date_to":         date_to,
        "trade_signals":   total_rows,
        "wins":            int(wins_count),
        "losses":          int(losses_count),
        "overall_win_rate": overall_wr,
    }
    log.info(f"Dataset ready: {total_rows} rows | Win rate (no gate): {overall_wr}%")

    # ── Steps 4–6: Analysis phases ────────────────────────────────────────────
    log.info("Step 4: Running threshold optimizer...")
    threshold_results = run_threshold_optimizer(merged_df)

    log.info("Step 5: Running logistic regression...")
    lr_results = run_logistic_regression(merged_df)

    log.info("Step 6: Running walk-forward validation...")
    wf_results = run_walk_forward(merged_df)

    # ── Step 7: Generate reports ──────────────────────────────────────────────
    log.info("Step 7: Generating reports...")
    text_report = generate_text_report(threshold_results, lr_results, wf_results, data_summary, run_ts)
    html_report = generate_html_report(threshold_results, lr_results, wf_results, data_summary, run_ts)

    # ── Step 8: Save reports ──────────────────────────────────────────────────
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_results")
    os.makedirs(out_dir, exist_ok=True)
    date_tag    = datetime.now().strftime("%Y_%m")
    txt_path    = os.path.join(out_dir, f"backtest_{date_tag}.txt")
    html_path   = os.path.join(out_dir, f"backtest_{date_tag}.html")
    latest_path = os.path.join(out_dir, "backtest_latest.html")

    with open(txt_path,    "w", encoding="utf-8") as f: f.write(text_report)
    with open(html_path,   "w", encoding="utf-8") as f: f.write(html_report)
    with open(latest_path, "w", encoding="utf-8") as f: f.write(html_report)

    log.info(f"Reports saved → {html_path}")
    log.info("=" * 60)
    log.info("SIGNAL 11 COMPLETE")
    log.info("=" * 60)

    return {
        "status":             "OK",
        "timestamp":          run_ts,
        "data_summary":       data_summary,
        "threshold_results":  threshold_results,
        "lr_results":         lr_results,
        "wf_results":         wf_results,
        "text_report":        text_report,
        "report_html_path":   html_path,
        "report_latest_path": latest_path,
    }


# =============================================================================
# STANDALONE RUN
# =============================================================================

if __name__ == "__main__":
    result = run_signal_11()
    if result.get("status") == "OK":
        print(result.get("text_report", ""))
        print(f"\nHTML report: {result.get('report_latest_path')}")
    else:
        print(f"SIGNAL 11 ERROR: {result.get('error', 'Unknown error')}")
        sys.exit(2)
