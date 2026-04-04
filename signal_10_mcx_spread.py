# =============================================================================
# GOLD BOT — signal_10_mcx_spread.py
# Signal 10: MCX–COMEX Spread Monitor
#
# PURPOSE : GOLDBEES tracks MCX gold (rupee-denominated), not COMEX directly.
#           When MCX gold premium over fair COMEX equivalent is unusually WIDE,
#           the ETF is overpriced → avoid buying, potential correction coming.
#           When the spread is NARROW or NEGATIVE, Indian gold is cheap vs global
#           → better entry value.
#
# FORMULA:
#   COMEX_INR_equivalent = COMEX_price_USD_per_oz * USDINR_rate / 31.1035 * 10
#                          (converts $/oz → ₹/10g, the MCX standard unit)
#   MCX_premium_pct = ((MCX_price - COMEX_INR_equiv) / COMEX_INR_equiv) * 100
#
# SIGNALS:
#   Premium > +2.5%  → Indian gold OVERPRICED → avoid new entry
#   Premium +1–2.5%  → Mild premium → caution, smaller size
#   Premium -1 to +1% → Fair value → neutral, follow other signals
#   Premium < -1%    → Indian gold CHEAP vs global → BUY setup confirmed
#
# INDEPENDENCE: 100% standalone. No shared data or logic with any other signal.
# NO ASSUMPTION RULE: If any fetch fails → DATA UNAVAILABLE. Never estimate.
#
# SCORING (max 5 pts for Signal 08):
#   Fair value or below  : 5 pts
#   Mild premium         : 2 pts
#   High premium         : 0 pts
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
    f"signal10_{datetime.now().strftime('%Y-%m-%d')}.log"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SIGNAL10] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("signal10")

# Conversion constants
OZ_TO_GRAMS  = 31.1035     # 1 troy oz = 31.1035 grams
MCX_UNIT     = 10          # MCX quotes gold per 10 grams


# =============================================================================
# DATA FETCHERS (all independent)
# =============================================================================

def fetch_comex_price() -> dict:
    """Fetch COMEX gold spot price (GC=F) in USD/oz."""
    try:
        import yfinance as yf
        df = yf.download("GC=F", period="3d", interval="1d",
                         auto_adjust=True, progress=False)
        if df is None or len(df) == 0:
            raise ValueError("No COMEX data returned")

        if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
            df.columns = df.columns.get_level_values(0)
        price = float(df["Close"].dropna().iloc[-1])
        log.info(f"COMEX: ${price:.2f}/oz")
        return {"available": True, "price_usd_oz": price}

    except Exception as e:
        log.warning(f"COMEX fetch failed: {e}")
        return {"available": False, "error": str(e)}


def fetch_usdinr_rate() -> dict:
    """Fetch USD/INR exchange rate."""
    try:
        import yfinance as yf
        df = yf.download("USDINR=X", period="3d", interval="1d",
                         auto_adjust=True, progress=False)
        if df is None or len(df) == 0:
            raise ValueError("No USDINR data returned")

        if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
            df.columns = df.columns.get_level_values(0)
        rate = float(df["Close"].dropna().iloc[-1])
        log.info(f"USDINR: ₹{rate:.2f}")
        return {"available": True, "rate": rate}

    except Exception as e:
        log.warning(f"USDINR fetch failed: {e}")
        return {"available": False, "error": str(e)}


def fetch_goldbees_price() -> dict:
    """
    Fetch GOLDBEES.NS latest NAV/price as MCX proxy.
    GOLDBEES ≈ 1/100th of 1 gram of gold. We convert to ₹/10g equivalent.
    1 GOLDBEES unit ≈ 0.01g gold → price × 1000 ≈ ₹/10g equivalent.
    """
    try:
        import yfinance as yf
        etf = CONFIG.get("primary_etf", "GOLDBEES.NS")
        df  = yf.download(etf, period="3d", interval="1d",
                          auto_adjust=True, progress=False)
        if df is None or len(df) == 0:
            raise ValueError(f"No data for {etf}")

        if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
            df.columns = df.columns.get_level_values(0)
        price_per_unit = float(df["Close"].dropna().iloc[-1])
        # GOLDBEES: 1 unit = approximately 1/100 gram of gold
        # So price per 10g equivalent = price_per_unit * 1000
        price_per_10g  = price_per_unit * 1000

        log.info(f"GOLDBEES: ₹{price_per_unit:.2f}/unit → ₹{price_per_10g:.2f}/10g equiv")
        return {
            "available":       True,
            "price_per_unit":  price_per_unit,
            "price_per_10g":   price_per_10g,
            "etf":             etf,
        }

    except Exception as e:
        log.warning(f"GOLDBEES fetch failed: {e}")
        return {"available": False, "error": str(e)}


# =============================================================================
# SPREAD CALCULATOR
# =============================================================================

def calculate_mcx_comex_spread(comex: dict, usdinr: dict,
                                goldbees: dict) -> dict:
    """
    Calculate the MCX premium over COMEX fair value.
    All three inputs must be available.
    Returns spread dict with premium_pct, signal, score.
    """
    if not (comex["available"] and usdinr["available"] and goldbees["available"]):
        missing = []
        if not comex["available"]:   missing.append("COMEX")
        if not usdinr["available"]:  missing.append("USDINR")
        if not goldbees["available"]: missing.append("GOLDBEES")
        return {
            "available": False,
            "status":    f"DATA UNAVAILABLE — could not fetch: {', '.join(missing)}",
        }

    comex_usd_oz    = comex["price_usd_oz"]
    usdinr_rate     = usdinr["rate"]
    goldbees_10g    = goldbees["price_per_10g"]

    # Fair COMEX equivalent in INR per 10 grams
    comex_inr_per_10g = (comex_usd_oz * usdinr_rate / OZ_TO_GRAMS) * MCX_UNIT

    # Premium of Indian gold over global equivalent
    premium_pct = ((goldbees_10g - comex_inr_per_10g) / comex_inr_per_10g) * 100

    log.info(
        f"COMEX equiv: ₹{comex_inr_per_10g:.2f}/10g | "
        f"GOLDBEES equiv: ₹{goldbees_10g:.2f}/10g | "
        f"Premium: {premium_pct:+.2f}%"
    )

    # ── Signal determination ──────────────────────────────────────────────────
    if premium_pct > 2.5:
        score  = 0
        bias   = "OVERPRICED"
        status = (f"M1 ❌ INDIAN GOLD OVERPRICED — MCX premium {premium_pct:+.2f}% over COMEX. "
                  f"Avoid new entry. Wait for premium to compress.")

    elif premium_pct > 1.0:
        score  = 2
        bias   = "MILD PREMIUM"
        status = (f"M1 ⚠️ MILD MCX PREMIUM — {premium_pct:+.2f}% over COMEX. "
                  f"Reduce position size. Slight overpay vs global price.")

    elif premium_pct >= -1.0:
        score  = 5
        bias   = "FAIR VALUE"
        status = (f"M1 ✅ FAIR VALUE — MCX premium {premium_pct:+.2f}%. "
                  f"Indian gold fairly priced vs global. Good entry zone.")

    else:
        score  = 5
        bias   = "DISCOUNT — STRONG BUY"
        status = (f"M1 ✅✅ INDIA GOLD AT DISCOUNT — {premium_pct:+.2f}% BELOW COMEX. "
                  f"Rare opportunity. Strong entry value.")

    return {
        "available":          True,
        "score":              score,
        "max_score":          5,
        "bias":               bias,
        "status":             status,
        "comex_usd_oz":       round(comex_usd_oz,       2),
        "usdinr_rate":        round(usdinr_rate,         2),
        "comex_inr_per_10g":  round(comex_inr_per_10g,  2),
        "goldbees_inr_10g":   round(goldbees_10g,        2),
        "premium_pct":        round(premium_pct,          2),
    }


# =============================================================================
# PRINT OUTPUT
# =============================================================================

def print_signal_output(spread: dict, signal: str, confidence: str,
                        action: str, ts: str):
    W    = 66
    line = "═" * W

    def row(text=""):
        print(f"║ {str(text)[:(W-2)].ljust(W-2)} ║")

    def sep():
        print(f"╠{line}╣")

    print(f"\n╔{line}╗")
    row("SIGNAL 10 — MCX–COMEX SPREAD MONITOR")
    sep()
    row(f"Date/Time    : {ts}")
    sep()

    if spread.get("available"):
        row(f"COMEX Gold   : ${spread['comex_usd_oz']:.2f} / oz")
        row(f"USD/INR Rate : ₹{spread['usdinr_rate']:.2f}")
        row(f"COMEX Equiv  : ₹{spread['comex_inr_per_10g']:,.2f} / 10g")
        row(f"GOLDBEES     : ₹{spread['goldbees_inr_10g']:,.2f} / 10g")
        row(f"MCX Premium  : {spread['premium_pct']:+.2f}%")
        sep()
        row(f"SPREAD CHECK : {spread['status']}")
    else:
        row(f"SPREAD CHECK : {spread.get('status', 'DATA UNAVAILABLE')}")

    sep()
    row(f"SIGNAL       : {signal}")
    row(f"CONFIDENCE   : {confidence}")
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

def run_signal_10() -> dict:
    """
    Main entry point for Signal 10 — MCX-COMEX Spread Monitor.
    Returns result dict compatible with signal_08_verdict_score.py scorer.
    FAILURE CONTRACT: Any fetch failure → DATA UNAVAILABLE. Never assumes.
    """
    log.info("=" * 60)
    log.info("SIGNAL 10 — MCX-COMEX SPREAD — START")
    log.info("=" * 60)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Fetch all 3 independently ─────────────────────────────────────────────
    log.info("Fetching COMEX gold price...")
    comex = fetch_comex_price()

    log.info("Fetching USD/INR rate...")
    usdinr = fetch_usdinr_rate()

    log.info("Fetching GOLDBEES price...")
    goldbees = fetch_goldbees_price()

    # ── Calculate spread ──────────────────────────────────────────────────────
    log.info("Calculating MCX-COMEX spread...")
    spread = calculate_mcx_comex_spread(comex, usdinr, goldbees)

    # ── Determine signal ─────────────────────────────────────────────────────
    if not spread["available"]:
        signal     = "DATA UNAVAILABLE"
        confidence = "NONE"
        score      = 0
        action     = f"SIGNAL 10: {spread.get('status', 'Data unavailable.')} Cannot assess spread."
    else:
        score = spread["score"]
        bias  = spread["bias"]

        if "DISCOUNT" in bias:
            signal     = "STRONG BUY — DISCOUNT"
            confidence = "HIGH"
            action     = ("Indian gold trading at a discount to global COMEX price. "
                          "This is rare and a strong entry value signal. "
                          "Combine with other signals for maximum conviction.")
        elif bias == "FAIR VALUE":
            signal     = "BUY — FAIR VALUE"
            confidence = "HIGH"
            action     = ("Indian gold at fair value vs COMEX. "
                          "No premium overpay risk. Good entry if other signals confirm.")
        elif bias == "MILD PREMIUM":
            signal     = "WATCH — MILD PREMIUM"
            confidence = "MEDIUM"
            action     = ("Mild MCX premium exists. You are slightly overpaying vs global price. "
                          "Reduce position size by 25–50%. Wait for premium to compress.")
        else:
            signal     = "AVOID — OVERPRICED"
            confidence = "HIGH"
            action     = ("Indian gold significantly overpriced vs COMEX equivalent. "
                          "Premium will compress — do NOT buy now. "
                          "Wait for MCX premium to fall below 1%.")

    log.info(f"SIGNAL: {signal} | Score: {score}/5 | Confidence: {confidence}")

    # ── Print ─────────────────────────────────────────────────────────────────
    print_signal_output(spread, signal, confidence, action, ts)

    log.info("SIGNAL 10 — MCX-COMEX SPREAD — END")

    return {
        "signal":      signal,
        "confidence":  confidence,
        "score":       score,           # 0–5, used by signal_08 scorer
        "spread":      spread,
        "action":      action,
        "timestamp":   ts,
        "source":      "signal_10",
    }


# =============================================================================
# STANDALONE LAUNCHER
# =============================================================================

if __name__ == "__main__":
    result = run_signal_10()
    log.info(f"Exit: {result.get('signal')} | Score: {result.get('score')}/5")
