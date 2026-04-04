# =============================================================================
# GOLD BOT — signal_05_2026_outlook.py
# Signal 05: Will Gold Go Up? 2026 Outlook Monitor
#
# PURPOSE   : Determine the OVERALL structural environment for gold in 2026.
# TIMEFRAME : Weeks to months — sets the directional bias for all other signals.
# INDEPENDENCE: 100% standalone — shares NO data or logic with any other signal.
#
# FACTORS (5 total):
#   O1 — Geopolitical Tension   : NewsAPI, 30-day keyword count   (max 2 pts)
#   O2 — Central Bank Buying    : WGC gold.org press releases      (max 2 pts)
#   O3 — Fed Rate Expectations  : FRED FEDFUNDS, 12M trend         (max 2 pts)
#   O4 — DXY 30-day Trend       : Yahoo Finance DX-Y.NYB           (max 2 pts)
#   O5 — NFP Jobs Risk (reversal): FRED PAYEMS, MoM change         (max 1 pt)
#
# STRICT DATA RULE:
#   Any factor that fails → score 0, marked DATA UNAVAILABLE.
#   If < 3 factors available → INSUFFICIENT DATA output. NEVER assume.
#
# NORMALIZATION:
#   normalized_pct = (actual_score / max_possible_from_available) * 100
#   Thresholds: >=75 STRONGLY BULLISH | >=50 BULLISH | >=30 NEUTRAL
#               >=15 MILDLY BEARISH   | <15 BEARISH
#
# SIGNAL 08 COMPATIBILITY:
#   Returns `signal` as one of: STRONGLY BULLISH / BULLISH / NEUTRAL /
#   MILDLY BEARISH / BEARISH / DATA UNAVAILABLE
# =============================================================================

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Optional

# ── Setup ─────────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CONFIG

os.makedirs(CONFIG["log_directory"], exist_ok=True)
log_file = os.path.join(
    CONFIG["log_directory"],
    f"signal05_{datetime.now().strftime('%Y-%m-%d')}.log"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SIGNAL05] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("signal05")


# =============================================================================
# FACTOR O1 — GEOPOLITICAL TENSION (NewsAPI, 30-day keyword scan)
# =============================================================================

GEO_HIGH_KEYWORDS   = ["war", "invasion", "nuclear", "military strike", "airstrike"]
GEO_MEDIUM_KEYWORDS = ["conflict", "sanctions", "tension", "crisis", "trade war",
                        "geopolitical", "attack", "terrorism"]
GEO_SEARCH_KEYWORDS = [
    "war", "conflict", "military", "invasion", "sanctions", "nuclear",
    "geopolitical", "crisis", "attack", "terrorism", "trade war",
    "Middle East", "Ukraine", "Russia", "Taiwan", "China", "North Korea"
]


def fetch_o1_geopolitical() -> dict:
    """
    Fetch 30 days of geopolitical news from NewsAPI.
    Returns dict with score (0–2), bias, status, raw counts.
    Failure → DATA UNAVAILABLE, score=0.
    """
    try:
        import requests

        api_key = CONFIG.get("news_api_key", "")
        if not api_key or api_key.startswith("YOUR_"):
            raise ValueError("NewsAPI key not configured in config.py")

        from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        query     = " OR ".join(GEO_SEARCH_KEYWORDS[:10])  # NewsAPI query limit

        url    = "https://newsapi.org/v2/everything"
        params = {
            "q":        query,
            "from":     from_date,
            "language": "en",
            "pageSize": 100,
            "sortBy":   "publishedAt",
            "apiKey":   api_key,
        }

        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "ok":
            raise ValueError(f"NewsAPI error: {data.get('message', 'unknown')}")

        articles = data.get("articles", [])
        log.info(f"O1: fetched {len(articles)} articles from NewsAPI (30 days)")

        # Count by severity
        high_count   = 0
        medium_count = 0

        for article in articles:
            text = " ".join([
                (article.get("title")       or ""),
                (article.get("description") or ""),
            ]).lower()

            if any(kw.lower() in text for kw in GEO_HIGH_KEYWORDS):
                high_count += 1
            elif any(kw.lower() in text for kw in GEO_MEDIUM_KEYWORDS):
                medium_count += 1

        tension_score = (high_count * 2) + (medium_count * 1)
        log.info(
            f"O1: high_articles={high_count}, medium_articles={medium_count}, "
            f"tension_score={tension_score}"
        )

        if tension_score >= 30:
            score = 2.0
            bias  = "STRONGLY BULLISH"
            status = (f"O1 ✅✅ VERY HIGH GEOPOLITICAL TENSION "
                      f"(score={tension_score}) — strong safe-haven gold demand")
        elif tension_score >= 15:
            score = 1.0
            bias  = "BULLISH"
            status = (f"O1 ✅ ELEVATED GEOPOLITICAL TENSION "
                      f"(score={tension_score}) — supportive for gold")
        elif tension_score >= 5:
            score = 0.5
            bias  = "MILDLY BULLISH"
            status = (f"O1 ⚠️ MILD TENSION (score={tension_score}) — minor gold support")
        else:
            score = 0.0
            bias  = "NEUTRAL"
            status = (f"O1 ➡️ LOW GEOPOLITICAL TENSION "
                      f"(score={tension_score}) — no safe-haven premium")

        return {
            "available":     True,
            "score":         score,
            "max_score":     2.0,
            "bias":          bias,
            "status":        status,
            "high_count":    high_count,
            "medium_count":  medium_count,
            "tension_score": tension_score,
        }

    except Exception as e:
        log.warning(f"O1 fetch failed: {e}")
        return {
            "available":  False,
            "score":      0.0,
            "max_score":  2.0,
            "bias":       "UNKNOWN",
            "status":     f"O1: DATA UNAVAILABLE — NEWS API FAILED ({type(e).__name__})",
        }


# =============================================================================
# FACTOR O2 — CENTRAL BANK GOLD BUYING (WGC — attempt fetch)
# NOTE: WGC (gold.org) has no free public API. Attempts a headlines fetch.
#       If unavailable → DATA UNAVAILABLE, score=0 (no assumption made).
# =============================================================================

def fetch_o2_central_bank() -> dict:
    """
    Attempt to retrieve central bank gold buying data from WGC press releases.
    Because WGC has no free API, this searches news for WGC reports.
    On any failure → DATA UNAVAILABLE, score=0. Never assumes.
    """
    try:
        import requests

        api_key = CONFIG.get("news_api_key", "")
        if not api_key or api_key.startswith("YOUR_"):
            raise ValueError("NewsAPI key not configured")

        # Search for WGC central bank buying news (most reliable free approach)
        url    = "https://newsapi.org/v2/everything"
        params = {
            "q":        "central bank gold buying World Gold Council tonnes",
            "language": "en",
            "pageSize": 10,
            "sortBy":   "publishedAt",
            "apiKey":   api_key,
        }

        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "ok":
            raise ValueError(f"NewsAPI error: {data.get('message', 'unknown')}")

        articles = data.get("articles", [])
        log.info(f"O2: found {len(articles)} WGC articles via NewsAPI")

        if not articles:
            raise ValueError("No WGC articles found")

        # Scan for tonne figures in headlines/descriptions
        import re
        tonnes_found = []
        for article in articles[:5]:
            text = " ".join([
                (article.get("title")       or ""),
                (article.get("description") or ""),
            ])
            # Look for patterns like "200 tonnes", "183t", "150 tons"
            matches = re.findall(r'(\d{2,4})\s*(?:tonnes?|tons?|t\b)', text, re.IGNORECASE)
            for m in matches:
                val = int(m)
                if 10 <= val <= 1000:   # plausible range for quarterly buying
                    tonnes_found.append(val)

        if not tonnes_found:
            raise ValueError("Could not parse tonne figures from WGC articles")

        latest_tonnes = max(tonnes_found)
        log.info(f"O2: estimated central bank buying ≈ {latest_tonnes} tonnes (from news)")

        if latest_tonnes >= 250:
            score  = 2.0
            bias   = "STRONGLY BULLISH"
            status = (f"O2 ✅✅ VERY STRONG CENTRAL BANK BUYING — ~{latest_tonnes} tonnes. "
                      f"Structural gold demand high.")
        elif latest_tonnes >= 150:
            score  = 1.0
            bias   = "BULLISH"
            status = f"O2 ✅ STRONG CENTRAL BANK BUYING — ~{latest_tonnes} tonnes. Bullish."
        elif latest_tonnes >= 50:
            score  = 0.5
            bias   = "MILDLY BULLISH"
            status = f"O2 ⚠️ MODERATE CENTRAL BANK BUYING — ~{latest_tonnes} tonnes."
        else:
            score  = 0.0
            bias   = "NEUTRAL / BEARISH"
            status = (f"O2 ❌ LOW CENTRAL BANK BUYING — ~{latest_tonnes} tonnes. "
                      f"Demand weak.")

        return {
            "available":       True,
            "score":           score,
            "max_score":       2.0,
            "bias":            bias,
            "status":          status,
            "tonnes_estimate": latest_tonnes,
            "source":          "news_articles",
            "note":            "WGC has no free API — estimate derived from press coverage",
        }

    except Exception as e:
        log.warning(f"O2 fetch failed: {e}")
        return {
            "available": False,
            "score":     0.0,
            "max_score": 2.0,
            "bias":      "UNKNOWN",
            "status":    "O2: DATA UNAVAILABLE — WGC data could not be fetched",
            "note":      "WGC has no free public API. Data unavailable is expected.",
        }


# =============================================================================
# FACTOR O3 — US FED RATE CUT EXPECTATIONS (FRED FEDFUNDS, 12M trend)
# =============================================================================

def fetch_o3_fed_rates() -> dict:
    """
    Fetch FEDFUNDS from FRED for last 12 months.
    Compare current rate vs 6M ago and 12M ago.
    Failure → DATA UNAVAILABLE, score=0.
    """
    try:
        import requests

        fred_key = CONFIG.get("fred_api_key", "")
        if not fred_key or fred_key.startswith("YOUR_"):
            raise ValueError("FRED API key not configured in config.py")

        url    = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id":      "FEDFUNDS",
            "api_key":        fred_key,
            "file_type":      "json",
            "sort_order":     "desc",
            "limit":          14,           # 14 months to ensure 12 full months
            "observation_start": (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d"),
        }

        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        observations = data.get("observations", [])
        # Filter out missing values
        valid_obs = [
            o for o in observations
            if o.get("value") and o["value"] != "."
        ]

        if len(valid_obs) < 7:
            raise ValueError(f"Insufficient FEDFUNDS data: {len(valid_obs)} months available")

        # Sort ascending (oldest first)
        valid_obs.sort(key=lambda x: x["date"])

        rate_now    = float(valid_obs[-1]["value"])
        rate_6m_ago = float(valid_obs[-7]["value"])   # 6 months back
        rate_12m_ago = float(valid_obs[0]["value"])   # oldest available

        rate_change_6m  = rate_now - rate_6m_ago
        rate_change_12m = rate_now - rate_12m_ago

        log.info(
            f"O3: FEDFUNDS current={rate_now}% | "
            f"6M_ago={rate_6m_ago}% | 12M_ago={rate_12m_ago}% | "
            f"6M_change={rate_change_6m:+.2f}% | 12M_change={rate_change_12m:+.2f}%"
        )

        if rate_change_6m < -0.5:
            score = 2.0
            bias  = "STRONGLY BULLISH"
            status = (f"O3 ✅✅ FED ACTIVELY CUTTING RATES — "
                      f"down {abs(rate_change_6m):.2f}% in 6M. Very bullish for gold.")

        elif rate_change_6m < 0 or rate_change_12m < 0:
            score = 1.0
            bias  = "BULLISH"
            status = (f"O3 ✅ FED CUTTING / EASING CYCLE — "
                      f"rate {rate_change_6m:+.2f}% over 6M. Bullish for gold.")

        elif abs(rate_change_6m) < 0.01 and abs(rate_change_12m) < 0.01:
            score = 0.5
            bias  = "NEUTRAL / MILDLY BULLISH"
            status = (f"O3 ⚠️ FED ON PAUSE — rate flat at {rate_now}%. "
                      f"No hikes, mild gold support.")

        else:   # rate_change_6m > 0
            score = 0.0
            bias  = "BEARISH"
            status = (f"O3 ❌ FED STILL HIKING — "
                      f"rate +{rate_change_6m:.2f}% over 6M. Headwind for gold.")

        return {
            "available":      True,
            "score":          score,
            "max_score":      2.0,
            "bias":           bias,
            "status":         status,
            "rate_now":       rate_now,
            "rate_6m_ago":    rate_6m_ago,
            "rate_12m_ago":   rate_12m_ago,
            "change_6m":      round(rate_change_6m,  3),
            "change_12m":     round(rate_change_12m, 3),
            "data_date":      valid_obs[-1]["date"],
        }

    except Exception as e:
        log.warning(f"O3 fetch failed: {e}")
        return {
            "available": False,
            "score":     0.0,
            "max_score": 2.0,
            "bias":      "UNKNOWN",
            "status":    f"O3: DATA UNAVAILABLE — FRED FEDFUNDS API FAILED ({type(e).__name__})",
        }


# =============================================================================
# FACTOR O4 — DXY 30-DAY TREND (Yahoo Finance)
# =============================================================================

def fetch_o4_dxy_trend() -> dict:
    """
    Fetch DXY (DX-Y.NYB) for last 35 trading days.
    Calculate 30-day and 10-day % change.
    Inverse relationship: DXY down = bullish for gold.
    Failure → DATA UNAVAILABLE, score=0.
    """
    try:
        import yfinance as yf

        df = yf.download("DX-Y.NYB", period="50d", interval="1d",
                         auto_adjust=True, progress=False)

        if df is None or len(df) < 12:
            raise ValueError("Insufficient DXY data rows")

        if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
            df.columns = df.columns.get_level_values(0)
        closes = df["Close"].dropna()
        if len(closes) < 12:
            raise ValueError("Insufficient DXY close prices")

        dxy_now  = float(closes.iloc[-1])

        # 30-day: use iloc[-31] if available, else earliest
        idx_30d  = -31 if len(closes) >= 31 else -len(closes)
        idx_10d  = -11 if len(closes) >= 11 else -len(closes)

        dxy_30d_ago = float(closes.iloc[idx_30d])
        dxy_10d_ago = float(closes.iloc[idx_10d])

        change_30d = ((dxy_now - dxy_30d_ago) / dxy_30d_ago) * 100
        change_10d = ((dxy_now - dxy_10d_ago) / dxy_10d_ago) * 100

        log.info(
            f"O4: DXY={dxy_now:.3f} | 30d_change={change_30d:+.2f}% | "
            f"10d_change={change_10d:+.2f}%"
        )

        if change_30d <= -2.0 and change_10d < 0:
            score = 2.0
            bias  = "STRONGLY BULLISH"
            status = (f"O4 ✅✅ DXY FALLING STRONGLY — "
                      f"{change_30d:+.2f}% over 30 days. Very bullish for gold.")

        elif change_30d <= -0.5:
            score = 1.0
            bias  = "BULLISH"
            status = (f"O4 ✅ DXY DECLINING — "
                      f"{change_30d:+.2f}% over 30 days. Bullish for gold.")

        elif change_30d >= 2.0:
            score = 0.0
            bias  = "BEARISH"
            status = (f"O4 ❌ DXY RISING STRONGLY — "
                      f"{change_30d:+.2f}% over 30 days. Bearish for gold.")

        elif change_30d >= 0.5:
            score = 0.0
            bias  = "MILDLY BEARISH"
            status = (f"O4 ⚠️ DXY RISING MILDLY — "
                      f"{change_30d:+.2f}% over 30 days. Minor headwind.")

        else:
            score = 0.5
            bias  = "NEUTRAL"
            status = (f"O4 ➡️ DXY FLAT — {change_30d:+.2f}%. "
                      f"No strong directional pressure.")

        return {
            "available":  True,
            "score":      score,
            "max_score":  2.0,
            "bias":       bias,
            "status":     status,
            "dxy_now":    round(dxy_now,    3),
            "dxy_30d_ago": round(dxy_30d_ago, 3),
            "change_30d": round(change_30d,  3),
            "change_10d": round(change_10d,  3),
        }

    except Exception as e:
        log.warning(f"O4 fetch failed: {e}")
        return {
            "available": False,
            "score":     0.0,
            "max_score": 2.0,
            "bias":      "UNKNOWN",
            "status":    f"O4: DATA UNAVAILABLE — DXY FETCH FAILED ({type(e).__name__})",
        }


# =============================================================================
# FACTOR O5 — US JOBS DATA / NFP (FRED PAYEMS, RISK REVERSAL FACTOR)
# NOTE: Strong jobs = gold headwind = potential dip-buy opportunity
# NOTE: PAYEMS is in thousands of persons. Diff × 1000 = actual jobs added.
# =============================================================================

def fetch_o5_nfp() -> dict:
    """
    Fetch PAYEMS (non-farm payrolls) from FRED for last 4+ months.
    Calculate month-over-month job additions.
    Flags if data is older than 40 days (monthly lag).
    Failure → DATA UNAVAILABLE, score=0.
    """
    try:
        import requests

        fred_key = CONFIG.get("fred_api_key", "")
        if not fred_key or fred_key.startswith("YOUR_"):
            raise ValueError("FRED API key not configured in config.py")

        url    = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id":       "PAYEMS",
            "api_key":         fred_key,
            "file_type":       "json",
            "sort_order":      "desc",
            "limit":           5,           # last 5 months
        }

        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        observations = data.get("observations", [])
        valid_obs = [
            o for o in observations
            if o.get("value") and o["value"] != "."
        ]

        if len(valid_obs) < 3:
            raise ValueError(f"Insufficient PAYEMS data: {len(valid_obs)} months")

        # Sort ascending (oldest first)
        valid_obs.sort(key=lambda x: x["date"])

        # PAYEMS is in thousands — multiply diff by 1000 to get actual jobs
        latest_level = float(valid_obs[-1]["value"])
        prev_level   = float(valid_obs[-2]["value"])
        prev2_level  = float(valid_obs[-3]["value"])

        nfp_latest   = (latest_level - prev_level) * 1000     # jobs added (persons)
        nfp_prev     = (prev_level   - prev2_level) * 1000
        data_date    = valid_obs[-1]["date"]

        # Age check — NFP is monthly, flag if >40 days old
        from datetime import date
        data_dt    = datetime.strptime(data_date, "%Y-%m-%d").date()
        days_old   = (date.today() - data_dt).days
        stale_flag = days_old > 40

        log.info(
            f"O5: PAYEMS latest={nfp_latest:,.0f} jobs | prev={nfp_prev:,.0f} | "
            f"data_date={data_date} | days_old={days_old}"
        )

        stale_note = f" [DATA AGE: {days_old} days — stale]" if stale_flag else ""

        if nfp_latest >= 300_000:
            score       = 0.0
            bias        = "BEARISH RISK"
            status      = (f"O5 ❌ VERY STRONG JOBS REPORT — {nfp_latest:,.0f} jobs added. "
                           f"Gold headwind. BUT: any dip = BUY opportunity.{stale_note}")
            risk_alert  = (f"⚠️ NFP RISK HIGH — strong jobs reduces Fed cut bets. "
                           f"Watch for gold dip to use as entry.")

        elif nfp_latest >= 150_000:
            score       = 0.5
            bias        = "NEUTRAL"
            status      = (f"O5 ➡️ MODERATE JOBS — {nfp_latest:,.0f} jobs. "
                           f"No major gold impact.{stale_note}")
            risk_alert  = "NFP within normal range — no significant risk flag"

        else:   # < 150k or negative
            score       = 1.0
            bias        = "BULLISH"
            status      = (f"O5 ✅ WEAK JOBS DATA — {nfp_latest:,.0f} jobs. "
                           f"Supports Fed cut case. Bullish for gold.{stale_note}")
            risk_alert  = "Weak jobs supports gold — no NFP risk currently"

        return {
            "available":   True,
            "score":       score,
            "max_score":   1.0,
            "bias":        bias,
            "status":      status,
            "risk_alert":  risk_alert,
            "nfp_latest":  nfp_latest,
            "nfp_prev":    nfp_prev,
            "data_date":   data_date,
            "days_old":    days_old,
            "stale":       stale_flag,
        }

    except Exception as e:
        log.warning(f"O5 fetch failed: {e}")
        return {
            "available":  False,
            "score":      0.0,
            "max_score":  1.0,
            "bias":       "UNKNOWN",
            "status":     f"O5: DATA UNAVAILABLE — NFP DATA FETCH FAILED ({type(e).__name__})",
            "risk_alert": "Cannot assess NFP risk — treat as neutral",
        }


# =============================================================================
# FINAL OUTLOOK EVALUATION
# =============================================================================

def calculate_final_outlook(o1: dict, o2: dict, o3: dict,
                             o4: dict, o5: dict) -> dict:
    """
    Combine all 5 factors into a final 2026 outlook.
    Normalizes score against available factors only.
    Returns dict with outlook, bias_note, scores, normalized_pct.
    """
    factors = [
        ("O1", o1),
        ("O2", o2),
        ("O3", o3),
        ("O4", o4),
        ("O5", o5),
    ]

    actual_score  = 0.0
    max_possible  = 0.0
    available_count = 0

    for name, f in factors:
        if f.get("available"):
            available_count += 1
            actual_score    += f.get("score",     0.0)
            max_possible    += f.get("max_score", 0.0)

    log.info(
        f"Outlook calc: available={available_count}/5 | "
        f"score={actual_score:.1f} / max_possible={max_possible:.1f}"
    )

    # Insufficient data gate
    if available_count < 3:
        return {
            "outlook":          "DATA UNAVAILABLE",
            "bias_note":        (f"Only {available_count} of 5 factors fetched. "
                                 f"Outlook cannot be determined."),
            "actual_score":     actual_score,
            "max_possible":     max_possible,
            "available_count":  available_count,
            "normalized_pct":   0.0,
            "insufficient":     True,
        }

    # Normalize
    normalized_pct = (actual_score / max_possible * 100) if max_possible > 0 else 0.0

    log.info(f"Normalized: {normalized_pct:.1f}%")

    if normalized_pct >= 75:
        outlook   = "STRONGLY BULLISH"
        bias_note = ("Multiple structural tailwinds for gold. "
                     "High conviction long bias.")
    elif normalized_pct >= 50:
        outlook   = "BULLISH"
        bias_note = "More tailwinds than headwinds. Favor long positions on dips."
    elif normalized_pct >= 30:
        outlook   = "NEUTRAL"
        bias_note = "Mixed signals. Proceed with caution. Reduce position size."
    elif normalized_pct >= 15:
        outlook   = "MILDLY BEARISH"
        bias_note = "More headwinds than tailwinds. Wait for clearer setup."
    else:
        outlook   = "BEARISH"
        bias_note = ("Multiple headwinds. Avoid new gold longs. "
                     "Wait for environment to change.")

    return {
        "outlook":         outlook,
        "bias_note":       bias_note,
        "actual_score":    actual_score,
        "max_possible":    max_possible,
        "available_count": available_count,
        "normalized_pct":  round(normalized_pct, 1),
        "insufficient":    False,
    }


# =============================================================================
# PRINT OUTPUT — matches planning MD format exactly
# =============================================================================

def print_signal_output(
    o1: dict, o2: dict, o3: dict, o4: dict, o5: dict,
    evaluation: dict,
    ts: str,
):
    W = 70
    line = "═" * W

    def row(text=""):
        print(f"║ {str(text)[:(W-2)].ljust(W-2)} ║")

    def sep():
        print(f"╠{line}╣")

    print(f"\n╔{line}╗")
    row("SIGNAL 05 — 2026 GOLD OUTLOOK MONITOR")
    sep()
    row(f"Date/Time          : {ts}")
    row(f"Factors Available  : {evaluation['available_count']} of 5")
    sep()
    row(f"O1 Geopolitical    : {o1['status']}")
    row(f"O2 Central Banks   : {o2['status']}")
    if o2.get("note"):
        row(f"   Note            : {o2['note']}")
    row(f"O3 Fed Rates       : {o3['status']}")
    if o3.get("available"):
        row(f"   Raw             : FEDFUNDS={o3.get('rate_now')}% | "
            f"6M: {o3.get('change_6m',0):+.2f}% | "
            f"12M: {o3.get('change_12m',0):+.2f}%")
    row(f"O4 DXY 30-day      : {o4['status']}")
    if o4.get("available"):
        row(f"   Raw             : DXY={o4.get('dxy_now')} | "
            f"30d: {o4.get('change_30d',0):+.2f}% | "
            f"10d: {o4.get('change_10d',0):+.2f}%")
    row(f"O5 US Jobs (Risk)  : {o5['status']}")
    sep()
    row(f"RAW SCORE          : {evaluation['actual_score']:.1f} / {evaluation['max_possible']:.1f}")
    row(f"NORMALIZED         : {evaluation['normalized_pct']:.1f}%")
    sep()

    if evaluation.get("insufficient"):
        row("2026 OUTLOOK  : INSUFFICIENT DATA")
        row(f"REASON        : {evaluation['bias_note']}")
    else:
        row(f"2026 OUTLOOK  : {evaluation['outlook']}")
        # Wrap bias note
        words, line_buf, wrapped = evaluation["bias_note"].split(), [], []
        for w in words:
            if len(" ".join(line_buf + [w])) > W - 18:
                wrapped.append(" ".join(line_buf))
                line_buf = [w]
            else:
                line_buf.append(w)
        if line_buf:
            wrapped.append(" ".join(line_buf))
        for i, txt in enumerate(wrapped):
            prefix = "BIAS NOTE     : " if i == 0 else "               "
            row(f"{prefix}{txt}")

    sep()
    row(f"RISK ALERT    : {o5.get('risk_alert', 'N/A')}")
    row("ACTION IF DIP : Any sharp 2–3% pullback from strong USD or")
    row("                NFP surprise = HIGH QUALITY BUY ENTRY")
    print(f"╚{line}╝\n")


# =============================================================================
# MAIN RUNNER
# =============================================================================

def run_signal_05() -> dict:
    """
    Main entry point for Signal 05.
    Returns result dict compatible with signal_08_verdict_score.py scorer.

    FAILURE CONTRACT:
      - Any factor that fails → DATA UNAVAILABLE for that factor, score=0.
      - < 3 factors available → signal = "DATA UNAVAILABLE".
      - NEVER estimates. NEVER assumes values.
    """
    log.info("=" * 60)
    log.info("SIGNAL 05 — 2026 GOLD OUTLOOK — START")
    log.info("=" * 60)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── STEP 1–5: Fetch all 5 factors independently ───────────────────────────
    log.info("Fetching O1 (Geopolitical tension via NewsAPI)...")
    o1 = fetch_o1_geopolitical()
    log.info(f"O1: available={o1['available']} | score={o1['score']} | bias={o1['bias']}")

    log.info("Fetching O2 (Central bank buying via WGC/news)...")
    o2 = fetch_o2_central_bank()
    log.info(f"O2: available={o2['available']} | score={o2['score']} | bias={o2['bias']}")

    log.info("Fetching O3 (Fed rates via FRED FEDFUNDS)...")
    o3 = fetch_o3_fed_rates()
    log.info(f"O3: available={o3['available']} | score={o3['score']} | bias={o3['bias']}")

    log.info("Fetching O4 (DXY 30-day via Yahoo Finance)...")
    o4 = fetch_o4_dxy_trend()
    log.info(f"O4: available={o4['available']} | score={o4['score']} | bias={o4['bias']}")

    log.info("Fetching O5 (NFP via FRED PAYEMS)...")
    o5 = fetch_o5_nfp()
    log.info(f"O5: available={o5['available']} | score={o5['score']} | bias={o5['bias']}")

    # ── FINAL EVALUATION ──────────────────────────────────────────────────────
    log.info("Calculating final 2026 outlook...")
    evaluation = calculate_final_outlook(o1, o2, o3, o4, o5)

    # ── PRINT OUTPUT ──────────────────────────────────────────────────────────
    try:
        print_signal_output(o1, o2, o3, o4, o5, evaluation, ts)
    except Exception as e:
        log.warning(f"Print output error (non-fatal): {e}")

    # ── SIGNAL LABEL (for Signal 08 scorer) ──────────────────────────────────
    signal = evaluation["outlook"]   # already one of the 5 labels or DATA UNAVAILABLE

    # ── CONFIDENCE ────────────────────────────────────────────────────────────
    count = evaluation["available_count"]
    if count == 5:
        confidence = "HIGH"
    elif count >= 3:
        confidence = "MEDIUM"
    else:
        confidence = "NONE"

    log.info(
        f"FINAL: {signal} | Score: {evaluation['actual_score']:.1f}/"
        f"{evaluation['max_possible']:.1f} | "
        f"Normalized: {evaluation['normalized_pct']:.1f}% | "
        f"Available: {count}/5 | Confidence: {confidence}"
    )
    log.info("SIGNAL 05 — 2026 GOLD OUTLOOK — END")

    return {
        "signal":          signal,
        "confidence":      confidence,
        "actual_score":    evaluation["actual_score"],
        "max_possible":    evaluation["max_possible"],
        "normalized_pct":  evaluation["normalized_pct"],
        "available_count": count,
        "bias_note":       evaluation["bias_note"],
        "risk_alert":      o5.get("risk_alert", "N/A"),
        "o1":              o1,
        "o2":              o2,
        "o3":              o3,
        "o4":              o4,
        "o5":              o5,
        "timestamp":       ts,
        "source":          "signal_05",
    }


# =============================================================================
# STANDALONE LAUNCHER
# =============================================================================

if __name__ == "__main__":
    result = run_signal_05()
    log.info(f"Exit: {result.get('signal')} | "
             f"Score: {result.get('actual_score'):.1f}/{result.get('max_possible'):.1f} "
             f"({result.get('normalized_pct'):.1f}%)")
