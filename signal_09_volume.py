# =============================================================================
# GOLD BOT — signal_09_volume.py
# Signal 09: Volume Confirmation
#
# PURPOSE : Validate that price dips are happening on LOW volume (weak selling)
#           and breakouts are happening on HIGH volume (strong conviction).
#           A BUY signal on high volume = panic selling (wait).
#           A BUY signal on low volume  = weak dip (good entry).
#
# LOGIC:
#   V1 — Today's GOLDBEES volume vs 20-day average volume
#   V2 — Volume trend (rising or falling over last 5 days)
#   V3 — Price-volume divergence (price down + volume down = weak selling = BUY)
#
# INDEPENDENCE: 100% standalone — no shared data or logic with any other signal.
# NO ASSUMPTION RULE: Any fetch failure → DATA UNAVAILABLE. Never estimate.
#
# SCORING (max 10 pts for Signal 08):
#   V1 Volume level    : 0 / 3 / 5  pts
#   V2 Volume trend    : 0 / 2      pts
#   V3 Price-Vol diverg: 0 / 3      pts
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
    f"signal09_{datetime.now().strftime('%Y-%m-%d')}.log"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SIGNAL09] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("signal09")


# =============================================================================
# DATA FETCH
# =============================================================================

def fetch_goldbees_volume() -> dict:
    """
    Fetch GOLDBEES.NS OHLCV for last 25 trading days.
    Returns closes, volumes, and computed averages.
    Failure → DATA UNAVAILABLE.
    """
    try:
        import yfinance as yf

        etf = CONFIG.get("primary_etf", "GOLDBEES.NS")
        df  = yf.download(etf, period="35d", interval="1d",
                          auto_adjust=True, progress=False)

        if df is None or len(df) < 6:
            raise ValueError(f"Insufficient data for {etf}")

        # Flatten MultiIndex columns (yfinance 0.2.x returns MultiIndex)
        if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
            df.columns = df.columns.get_level_values(0)

        df = df.dropna()

        closes  = df["Close"].values.flatten().tolist()
        volumes = df["Volume"].values.flatten().tolist()

        if len(closes) < 6 or len(volumes) < 6:
            raise ValueError("Not enough rows after dropna")

        log.info(f"Fetched {len(closes)} days of {etf} OHLCV data")

        return {
            "available": True,
            "closes":    closes,
            "volumes":   volumes,
            "etf":       etf,
        }

    except Exception as e:
        log.warning(f"Volume fetch failed: {e}")
        return {
            "available": False,
            "error":     str(e),
        }


# =============================================================================
# V1 — TODAY'S VOLUME vs 20-DAY AVERAGE
# =============================================================================

def check_v1_volume_level(volumes: list) -> dict:
    """
    Compare today's volume to 20-day average.
    Low volume dip = weak selling = potential good entry.
    High volume dip = panic selling = wait for capitulation.
    """
    if len(volumes) < 6:
        return {
            "available": False,
            "score":     0,
            "status":    "V1: DATA UNAVAILABLE — insufficient volume history",
        }

    today_vol = volumes[-1]
    lookback  = min(20, len(volumes) - 1)
    avg_vol   = sum(volumes[-lookback - 1:-1]) / lookback
    vol_ratio = today_vol / avg_vol if avg_vol > 0 else 1.0

    log.info(f"V1: today_vol={today_vol:,.0f} | 20d_avg={avg_vol:,.0f} | ratio={vol_ratio:.2f}x")

    if vol_ratio <= 0.60:
        score  = 5
        bias   = "VERY LOW VOLUME"
        status = (f"V1 ✅✅ VERY LOW VOLUME — {vol_ratio:.2f}x avg. "
                  f"Weak selling. Strong dip-buy setup.")
    elif vol_ratio <= 0.85:
        score  = 3
        bias   = "LOW VOLUME"
        status = (f"V1 ✅ LOW VOLUME — {vol_ratio:.2f}x avg. "
                  f"Mild weakness. Decent entry setup.")
    elif vol_ratio <= 1.20:
        score  = 0
        bias   = "NORMAL VOLUME"
        status = (f"V1 ➡️ NORMAL VOLUME — {vol_ratio:.2f}x avg. "
                  f"No strong signal from volume.")
    elif vol_ratio <= 1.80:
        score  = 0
        bias   = "HIGH VOLUME"
        status = (f"V1 ⚠️ HIGH VOLUME — {vol_ratio:.2f}x avg. "
                  f"Strong selling. Wait — don't catch falling knife.")
    else:
        score  = 0
        bias   = "VERY HIGH VOLUME"
        status = (f"V1 ❌ VERY HIGH VOLUME — {vol_ratio:.2f}x avg. "
                  f"Panic selling. Avoid entry today.")

    return {
        "available":   True,
        "score":       score,
        "max_score":   5,
        "bias":        bias,
        "status":      status,
        "today_vol":   int(today_vol),
        "avg_vol_20d": int(avg_vol),
        "vol_ratio":   round(vol_ratio, 2),
    }


# =============================================================================
# V2 — VOLUME TREND (5-day)
# =============================================================================

def check_v2_volume_trend(volumes: list) -> dict:
    """
    Is volume expanding or contracting over last 5 days?
    Contracting volume on a dip = selling is exhausting = bullish.
    Expanding volume on a dip = selling is accelerating = bearish.
    """
    if len(volumes) < 6:
        return {
            "available": False,
            "score":     0,
            "status":    "V2: DATA UNAVAILABLE — insufficient volume history",
        }

    recent_5  = volumes[-5:]
    first_half  = sum(recent_5[:2]) / 2
    second_half = sum(recent_5[3:]) / 2
    trend_ratio = second_half / first_half if first_half > 0 else 1.0

    log.info(f"V2: 5d_vol_trend ratio={trend_ratio:.2f} (recent/earlier)")

    if trend_ratio <= 0.75:
        score  = 2
        bias   = "VOLUME CONTRACTING"
        status = (f"V2 ✅ VOLUME CONTRACTING — {trend_ratio:.2f}x. "
                  f"Selling pressure easing. Bullish for dip entry.")
    elif trend_ratio <= 1.10:
        score  = 1
        bias   = "VOLUME STABLE"
        status = f"V2 ➡️ VOLUME STABLE — {trend_ratio:.2f}x. No strong trend signal."
    else:
        score  = 0
        bias   = "VOLUME EXPANDING"
        status = (f"V2 ❌ VOLUME EXPANDING — {trend_ratio:.2f}x. "
                  f"Selling accelerating. Caution.")

    return {
        "available":   True,
        "score":       score,
        "max_score":   2,
        "bias":        bias,
        "status":      status,
        "trend_ratio": round(trend_ratio, 2),
    }


# =============================================================================
# V3 — PRICE-VOLUME DIVERGENCE
# =============================================================================

def check_v3_price_volume_divergence(closes: list, volumes: list) -> dict:
    """
    Best signal: price falling + volume falling = weak selling = BUY.
    Worst signal: price falling + volume rising = panic = AVOID.
    """
    if len(closes) < 3 or len(volumes) < 3:
        return {
            "available": False,
            "score":     0,
            "status":    "V3: DATA UNAVAILABLE — insufficient data",
        }

    # 3-day price and volume change
    price_change = ((closes[-1] - closes[-3]) / closes[-3]) * 100
    vol_3d_avg   = sum(volumes[-3:]) / 3
    vol_prev_avg = sum(volumes[-6:-3]) / 3 if len(volumes) >= 6 else vol_3d_avg
    vol_change   = ((vol_3d_avg - vol_prev_avg) / vol_prev_avg * 100) if vol_prev_avg > 0 else 0

    log.info(
        f"V3: price_3d={price_change:+.2f}% | vol_change_3d={vol_change:+.2f}%"
    )

    # Price down + volume down = BEST dip-buy setup
    if price_change < -0.3 and vol_change < -10:
        score  = 3
        bias   = "BULLISH DIVERGENCE"
        status = (f"V3 ✅✅ PRICE DOWN + VOLUME DOWN — "
                  f"price {price_change:+.1f}%, vol {vol_change:+.1f}%. "
                  f"Weak selling = ideal dip-buy setup.")

    # Price flat/down + volume flat = neutral
    elif price_change <= 0.3 and abs(vol_change) <= 10:
        score  = 1
        bias   = "NEUTRAL DIVERGENCE"
        status = (f"V3 ➡️ PRICE FLAT, VOLUME FLAT — "
                  f"price {price_change:+.1f}%, vol {vol_change:+.1f}%. No clear signal.")

    # Price up + volume up = strong bullish momentum
    elif price_change > 0.5 and vol_change > 10:
        score  = 2
        bias   = "BULLISH MOMENTUM"
        status = (f"V3 ✅ PRICE UP + VOLUME UP — "
                  f"price {price_change:+.1f}%, vol {vol_change:+.1f}%. "
                  f"Bullish momentum confirmed.")

    # Price down + volume up = panic selling = avoid
    elif price_change < -0.3 and vol_change > 10:
        score  = 0
        bias   = "BEARISH PRESSURE"
        status = (f"V3 ❌ PRICE DOWN + VOLUME UP — "
                  f"price {price_change:+.1f}%, vol {vol_change:+.1f}%. "
                  f"Panic selling. Do not buy into this.")

    else:
        score  = 0
        bias   = "MIXED"
        status = (f"V3 ➡️ MIXED — price {price_change:+.1f}%, vol {vol_change:+.1f}%. "
                  f"No clear divergence.")

    return {
        "available":    True,
        "score":        score,
        "max_score":    3,
        "bias":         bias,
        "status":       status,
        "price_3d_pct": round(price_change, 2),
        "vol_3d_pct":   round(vol_change,   2),
    }


# =============================================================================
# PRINT OUTPUT
# =============================================================================

def print_signal_output(v1: dict, v2: dict, v3: dict,
                        total_score: int, signal: str,
                        confidence: str, action: str, ts: str):
    W    = 66
    line = "═" * W

    def row(text=""):
        print(f"║ {str(text)[:(W-2)].ljust(W-2)} ║")

    def sep():
        print(f"╠{line}╣")

    print(f"\n╔{line}╗")
    row("SIGNAL 09 — VOLUME CONFIRMATION")
    sep()
    row(f"Date/Time : {ts}")
    sep()
    row(f"V1 VOLUME LEVEL  : {v1.get('status', 'N/A')}")
    if v1.get("available"):
        row(f"   Today={v1['today_vol']:,} | 20d Avg={v1['avg_vol_20d']:,} | Ratio={v1['vol_ratio']}x")
    sep()
    row(f"V2 VOLUME TREND  : {v2.get('status', 'N/A')}")
    sep()
    row(f"V3 PRICE-VOL DIV : {v3.get('status', 'N/A')}")
    sep()
    row(f"TOTAL SCORE : {total_score} / 10")
    row(f"SIGNAL      : {signal}")
    row(f"CONFIDENCE  : {confidence}")
    sep()
    words, buf, lines = action.split(), [], []
    for w in words:
        if len(" ".join(buf + [w])) > W - 4:
            lines.append(" ".join(buf)); buf = [w]
        else:
            buf.append(w)
    if buf: lines.append(" ".join(buf))
    for l in lines:
        row(f"  {l}")
    print(f"╚{line}╝\n")


# =============================================================================
# MAIN RUNNER
# =============================================================================

def run_signal_09() -> dict:
    """
    Main entry point for Signal 09 — Volume Confirmation.
    Returns result dict compatible with signal_08_verdict_score.py scorer.
    FAILURE CONTRACT: Any fetch failure → DATA UNAVAILABLE. Never assumes.
    """
    log.info("=" * 60)
    log.info("SIGNAL 09 — VOLUME CONFIRMATION — START")
    log.info("=" * 60)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Fetch data ────────────────────────────────────────────────────────────
    log.info("Fetching GOLDBEES OHLCV data...")
    data = fetch_goldbees_volume()

    if not data["available"]:
        log.warning("Volume data unavailable — signal cannot run")
        result = {
            "signal":     "DATA UNAVAILABLE",
            "confidence": "NONE",
            "score":      0,
            "action":     "SIGNAL 09: Volume data unavailable. Cannot confirm dip quality.",
            "timestamp":  ts,
            "source":     "signal_09",
        }
        print(f"\n⬛ SIGNAL 09: DATA UNAVAILABLE — {data.get('error', 'fetch failed')}\n")
        return result

    closes  = data["closes"]
    volumes = data["volumes"]

    # ── Run checks ───────────────────────────────────────────────────────────
    log.info("Checking V1 (volume level)...")
    v1 = check_v1_volume_level(volumes)

    log.info("Checking V2 (volume trend)...")
    v2 = check_v2_volume_trend(volumes)

    log.info("Checking V3 (price-volume divergence)...")
    v3 = check_v3_price_volume_divergence(closes, volumes)

    # ── Score ────────────────────────────────────────────────────────────────
    total_score = v1.get("score", 0) + v2.get("score", 0) + v3.get("score", 0)
    available   = sum(1 for v in [v1, v2, v3] if v.get("available"))

    log.info(f"V1={v1.get('score',0)} V2={v2.get('score',0)} V3={v3.get('score',0)} | Total={total_score}/10")

    if available == 0:
        signal     = "DATA UNAVAILABLE"
        confidence = "NONE"
        action     = "All volume checks failed. Cannot confirm dip quality."
    elif total_score >= 8:
        signal     = "STRONG VOLUME BUY"
        confidence = "HIGH"
        action     = ("Excellent volume setup — low/contracting volume with price-volume divergence. "
                      "Dip is weak selling. Strong conviction to enter.")
    elif total_score >= 5:
        signal     = "VOLUME BUY"
        confidence = "MEDIUM"
        action     = ("Good volume setup — dip is happening on below-average volume. "
                      "Reasonable entry. Confirm with other signals.")
    elif total_score >= 3:
        signal     = "WATCH"
        confidence = "LOW"
        action     = ("Mixed volume signals. Entry possible but wait for one more "
                      "volume confirmation (e.g. volume drops further tomorrow).")
    else:
        signal     = "VOLUME CAUTION"
        confidence = "NONE"
        action     = ("High or expanding volume on dip — selling pressure is real. "
                      "Avoid entry today. Wait for volume to dry up.")

    log.info(f"SIGNAL: {signal} | Score: {total_score}/10 | Confidence: {confidence}")

    # ── Print ─────────────────────────────────────────────────────────────────
    print_signal_output(v1, v2, v3, total_score, signal, confidence, action, ts)

    log.info("SIGNAL 09 — VOLUME CONFIRMATION — END")

    return {
        "signal":      signal,
        "confidence":  confidence,
        "score":       total_score,       # 0–10, used by signal_08 scorer
        "v1":          v1,
        "v2":          v2,
        "v3":          v3,
        "action":      action,
        "timestamp":   ts,
        "source":      "signal_09",
    }


# =============================================================================
# STANDALONE LAUNCHER
# =============================================================================

if __name__ == "__main__":
    result = run_signal_09()
    log.info(f"Exit: {result.get('signal')} | Score: {result.get('score')}/10")
