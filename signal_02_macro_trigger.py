# =============================================================================
# GOLD BOT — signal_02_macro_trigger.py
# Signal 02: Global Macro Trigger
#
# COMPLETELY INDEPENDENT — shares no data or logic with any other signal.
# Checks 5 macro factors. If 2+ are bullish → BUY AT EOD.
#
# Factors:
#   F1 — US Dollar Index (DXY)          → Yahoo Finance
#   F2 — US Federal Reserve Stance      → FRED API + NewsAPI
#   F3 — US Inflation (CPI)             → FRED API
#   F4 — Geopolitical Tension           → NewsAPI
#   F5 — INR vs USD Rate                → Yahoo Finance
#
# DATA RULE: If any factor's data fails → that factor = DATA UNAVAILABLE.
#            No assumed or estimated values are ever used.
# =============================================================================

import yfinance as yf
import requests
import pandas as pd
from datetime import datetime, timedelta
import logging
import os
import sys
from typing import Optional

# ── Setup ─────────────────────────────────────────────────────────────────────

# Add parent directory to path so config.py can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CONFIG

# Logging setup
os.makedirs(CONFIG["log_directory"], exist_ok=True)
log_file = os.path.join(
    CONFIG["log_directory"],
    f"signal02_{datetime.now().strftime('%Y-%m-%d')}.log"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SIGNAL02] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("signal02")

# ── Constants ─────────────────────────────────────────────────────────────────

FRED_BASE_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
NEWSAPI_BASE_URL = "https://newsapi.org/v2/everything"
TIMEOUT = CONFIG["fetch_timeout_seconds"]

# ── Data Classes ──────────────────────────────────────────────────────────────

class FactorResult:
    """Holds the result of one macro factor evaluation."""
    def __init__(self, factor_id: str):
        self.factor_id = factor_id
        self.available = False       # True if data was fetched successfully
        self.bullish = False         # True if this factor is bullish for gold
        self.score = 0               # 0 or 1
        self.status = ""             # Human-readable status line
        self.raw = {}                # Raw data values for logging

    def mark_unavailable(self, reason: str):
        self.available = False
        self.bullish = False
        self.score = 0
        self.status = f"{self.factor_id}: DATA UNAVAILABLE — {reason}"
        log.warning(self.status)

    def mark_bullish(self, message: str, raw: dict = None):
        self.available = True
        self.bullish = True
        self.score = 1
        self.status = f"{self.factor_id} ✅ {message}"
        self.raw = raw or {}
        log.info(self.status)

    def mark_neutral(self, message: str, raw: dict = None):
        self.available = True
        self.bullish = False
        self.score = 0
        self.status = f"{self.factor_id} ➡️  {message}"
        self.raw = raw or {}
        log.info(self.status)

    def mark_bearish(self, message: str, raw: dict = None):
        self.available = True
        self.bullish = False
        self.score = 0
        self.status = f"{self.factor_id} ❌ {message}"
        self.raw = raw or {}
        log.info(self.status)

# ── Helper: Fetch Yahoo Finance Price History ─────────────────────────────────

def fetch_yahoo(symbol: str, period_days: int) -> Optional[pd.DataFrame]:

    """
    Fetch daily OHLCV data from Yahoo Finance.
    Returns a DataFrame or None if fetch fails.
    """
    try:
        log.info(f"Fetching {symbol} for last {period_days} days...")
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=f"{period_days}d", auto_adjust=True)

        if df is None or df.empty:
            log.error(f"No data returned for {symbol}")
            return None

        df = df.dropna(subset=["Close"])

        if len(df) < 3:
            log.error(f"Too few data points for {symbol}: got {len(df)}")
            return None

        log.info(f"Fetched {len(df)} rows for {symbol}. Latest: {df.index[-1].date()}")
        return df

    except Exception as e:
        log.error(f"Yahoo Finance fetch failed for {symbol}: {e}")
        return None

# ── Helper: Fetch FRED Series ─────────────────────────────────────────────────

def fetch_fred(series_id: str, months: int = 12) -> Optional[pd.Series]:
    """
    Fetch a FRED data series as a pandas Series.
    Returns None if fetch fails or API key is not configured.
    """
    api_key = CONFIG.get("fred_api_key", "")

    if not api_key or api_key == "YOUR_FRED_API_KEY_HERE":
        log.error("FRED API key not configured in config.py")
        return None

    try:
        # Calculate start date
        start_date = (datetime.now() - timedelta(days=months * 31)).strftime("%Y-%m-%d")

        url = (
            f"https://api.stlouisfed.org/fred/series/observations"
            f"?series_id={series_id}"
            f"&api_key={api_key}"
            f"&file_type=json"
            f"&observation_start={start_date}"
            f"&sort_order=asc"
        )

        log.info(f"Fetching FRED series: {series_id}")
        response = requests.get(url, timeout=TIMEOUT)
        response.raise_for_status()

        data = response.json()
        observations = data.get("observations", [])

        if not observations:
            log.error(f"FRED returned empty observations for {series_id}")
            return None

        # Build Series — filter out "." (missing values)
        values = {}
        for obs in observations:
            if obs["value"] != ".":
                try:
                    date = pd.to_datetime(obs["date"])
                    values[date] = float(obs["value"])
                except ValueError:
                    continue

        if not values:
            log.error(f"No valid numeric values in FRED series {series_id}")
            return None

        series = pd.Series(values).sort_index()
        log.info(f"FRED {series_id}: {len(series)} observations. Latest: {series.index[-1].date()} = {series.iloc[-1]}")
        return series

    except requests.exceptions.Timeout:
        log.error(f"FRED API timeout for {series_id}")
        return None
    except requests.exceptions.RequestException as e:
        log.error(f"FRED API request failed for {series_id}: {e}")
        return None
    except Exception as e:
        log.error(f"Unexpected error fetching FRED {series_id}: {e}")
        return None

# ── Helper: Fetch News ────────────────────────────────────────────────────────

def fetch_news(keywords: list, days_back: int = 2) -> Optional[list]:
    """
    Fetch news articles matching keywords via NewsAPI.
    Returns list of articles or None if fetch fails.
    """
    api_key = CONFIG.get("news_api_key", "")

    if not api_key or api_key == "YOUR_NEWSAPI_KEY_HERE":
        log.error("NewsAPI key not configured in config.py")
        return None

    try:
        from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%S")
        query = " OR ".join(f'"{kw}"' for kw in keywords[:10])  # NewsAPI max OR limit

        params = {
            "q": query,
            "from": from_date,
            "language": "en",
            "sortBy": "publishedAt",
            "apiKey": api_key,
            "pageSize": 100
        }

        log.info(f"Fetching news: {len(keywords)} keywords, last {days_back} days")
        response = requests.get(NEWSAPI_BASE_URL, params=params, timeout=TIMEOUT)
        response.raise_for_status()

        data = response.json()

        if data.get("status") != "ok":
            log.error(f"NewsAPI error: {data.get('message', 'Unknown error')}")
            return None

        articles = data.get("articles", [])
        log.info(f"NewsAPI returned {len(articles)} articles")
        return articles

    except requests.exceptions.Timeout:
        log.error("NewsAPI fetch timeout")
        return None
    except requests.exceptions.RequestException as e:
        log.error(f"NewsAPI request failed: {e}")
        return None
    except Exception as e:
        log.error(f"Unexpected error fetching news: {e}")
        return None

# =============================================================================
# FACTOR 1 — US Dollar Index (DXY)
# Bullish for gold when DXY is FALLING
# =============================================================================

def evaluate_factor_1_dxy() -> FactorResult:
    """
    F1: Fetch DXY and check 5-day trend.
    BULLISH if DXY fell >= 0.5% over 5 days AND fell today.
    """
    result = FactorResult("F1-DXY")

    df = fetch_yahoo(CONFIG["dxy_symbol"], period_days=12)

    if df is None:
        result.mark_unavailable("DXY data fetch failed from Yahoo Finance")
        return result

    if len(df) < 6:
        result.mark_unavailable(f"Not enough DXY data points (got {len(df)}, need 6)")
        return result

    try:
        dxy_today = float(df["Close"].iloc[-1])
        dxy_5d_ago = float(df["Close"].iloc[-6])
        dxy_1d_ago = float(df["Close"].iloc[-2])

        change_5d = ((dxy_today - dxy_5d_ago) / dxy_5d_ago) * 100
        change_1d = ((dxy_today - dxy_1d_ago) / dxy_1d_ago) * 100

        raw = {
            "dxy_today": round(dxy_today, 3),
            "dxy_5d_ago": round(dxy_5d_ago, 3),
            "dxy_1d_ago": round(dxy_1d_ago, 3),
            "change_5d_pct": round(change_5d, 3),
            "change_1d_pct": round(change_1d, 3),
            "data_date": str(df.index[-1].date())
        }

        threshold = CONFIG["dxy_5d_change_threshold"]  # default -0.5

        if change_5d <= threshold and change_1d < 0:
            result.mark_bullish(
                f"DXY FALLING {change_5d:.2f}% over 5 days, also down {change_1d:.2f}% today "
                f"(DXY={dxy_today:.3f}). BULLISH FOR GOLD.",
                raw
            )

        elif change_5d <= -0.2:
            # Mild fall — available but not counted as fully bullish
            result.available = True
            result.bullish = False
            result.score = 0
            result.raw = raw
            result.status = (
                f"F1-DXY ⚠️  DXY MILDLY FALLING {change_5d:.2f}% over 5 days "
                f"(DXY={dxy_today:.3f}). Not strong enough to trigger."
            )
            log.info(result.status)

        elif change_5d >= 0.5:
            result.mark_bearish(
                f"DXY RISING {change_5d:.2f}% over 5 days (DXY={dxy_today:.3f}). "
                f"HEADWIND FOR GOLD.",
                raw
            )

        else:
            result.mark_neutral(
                f"DXY FLAT {change_5d:.2f}% over 5 days (DXY={dxy_today:.3f}). "
                f"No directional pressure.",
                raw
            )

    except Exception as e:
        result.mark_unavailable(f"DXY calculation error: {e}")

    return result

# =============================================================================
# FACTOR 2 — US Federal Reserve Stance
# Bullish when Fed is DOVISH (cutting rates or pausing)
# Uses FRED interest rate data + NewsAPI sentiment
# =============================================================================

def evaluate_factor_2_fed() -> FactorResult:
    """
    F2: Check Fed Funds Rate trend (FRED) + recent news sentiment.
    BULLISH if rate is falling OR news is dovish-leaning.
    """
    result = FactorResult("F2-FED")

    # ── Part A: FRED Rate Trend ──────────────────────────────────────────────
    fed_series = fetch_fred("FEDFUNDS", months=8)

    rate_trend = None
    rate_now = None
    rate_3m_ago = None

    if fed_series is not None and len(fed_series) >= 4:
        rate_now = float(fed_series.iloc[-1])
        rate_3m_ago = float(fed_series.iloc[-4])  # ~3 months back

        diff = rate_now - rate_3m_ago
        if diff < -0.1:
            rate_trend = "CUTTING"
        elif diff < 0.05:
            rate_trend = "PAUSED"
        else:
            rate_trend = "HIKING"

        log.info(f"Fed rate now={rate_now}%, 3m_ago={rate_3m_ago}%, trend={rate_trend}")
    else:
        log.warning("F2: FRED FEDFUNDS data unavailable — proceeding with news only")

    # ── Part B: News Sentiment ───────────────────────────────────────────────
    fed_keywords = [
        "Federal Reserve", "FOMC", "Fed rate", "rate cut", "rate hike",
        "dovish", "hawkish", "rate pause", "interest rate", "Powell"
    ]

    articles = fetch_news(fed_keywords, days_back=14)

    dovish_count = 0
    hawkish_count = 0
    news_sentiment = None

    dovish_words = ["cut", "pause", "hold", "dovish", "accommodative", "easing",
                    "lower rate", "rate reduction", "no hike"]
    hawkish_words = ["hike", "raise", "hawkish", "tighten", "restrictive",
                     "higher rate", "rate increase", "aggressive"]

    if articles is not None:
        for article in articles:
            text = (
                (article.get("title") or "") + " " +
                (article.get("description") or "")
            ).lower()

            for word in dovish_words:
                if word in text:
                    dovish_count += 1
                    break

            for word in hawkish_words:
                if word in text:
                    hawkish_count += 1
                    break

        if dovish_count > hawkish_count:
            news_sentiment = "DOVISH"
        elif hawkish_count > dovish_count:
            news_sentiment = "HAWKISH"
        else:
            news_sentiment = "NEUTRAL"

        log.info(f"Fed news: dovish={dovish_count}, hawkish={hawkish_count}, sentiment={news_sentiment}")
    else:
        log.warning("F2: NewsAPI unavailable for Fed sentiment")

    # ── Evaluate Combined ────────────────────────────────────────────────────
    raw = {
        "rate_now": rate_now,
        "rate_3m_ago": rate_3m_ago,
        "rate_trend": rate_trend,
        "news_dovish_count": dovish_count,
        "news_hawkish_count": hawkish_count,
        "news_sentiment": news_sentiment
    }

    # Both unavailable
    if rate_trend is None and news_sentiment is None:
        result.mark_unavailable("Both FRED rate data and NewsAPI feed failed")
        return result

    # Determine bullishness
    trend_bullish = rate_trend in ("CUTTING", "PAUSED")
    news_bullish = news_sentiment == "DOVISH"
    trend_bearish = rate_trend == "HIKING"
    news_bearish = news_sentiment == "HAWKISH"

    if trend_bullish and news_bullish:
        result.mark_bullish(
            f"FED STRONGLY DOVISH — Rate {rate_trend} "
            f"(now={rate_now}%) AND news dovish ({dovish_count} articles). "
            f"BULLISH FOR GOLD.",
            raw
        )

    elif trend_bullish or news_bullish:
        label = "CUTTING" if rate_trend == "CUTTING" else (rate_trend or "N/A")
        result.mark_bullish(
            f"FED LEANING DOVISH — Rate trend: {label}, "
            f"News sentiment: {news_sentiment or 'N/A'}. BULLISH FOR GOLD.",
            raw
        )

    elif trend_bearish or news_bearish:
        result.mark_bearish(
            f"FED HAWKISH — Rate trend: {rate_trend or 'N/A'}, "
            f"News: {news_sentiment or 'N/A'}. HEADWIND FOR GOLD.",
            raw
        )

    else:
        result.mark_neutral(
            f"FED NEUTRAL — Rate trend: {rate_trend or 'N/A'}, "
            f"News: {news_sentiment or 'N/A'}. No clear dovish signal.",
            raw
        )

    return result

# =============================================================================
# FACTOR 3 — US Inflation (CPI)
# Bullish for gold when CPI is HIGH or RISING
# =============================================================================

def evaluate_factor_3_cpi() -> FactorResult:
    """
    F3: Fetch US CPI from FRED (CPIAUCSL series).
    BULLISH if CPI rose >= 0.2% month-over-month.
    """
    result = FactorResult("F3-CPI")

    cpi_series = fetch_fred("CPIAUCSL", months=5)

    if cpi_series is None or len(cpi_series) < 3:
        result.mark_unavailable("FRED CPI (CPIAUCSL) data fetch failed or insufficient points")
        return result

    try:
        cpi_latest = float(cpi_series.iloc[-1])
        cpi_prev = float(cpi_series.iloc[-2])
        cpi_3m_ago = float(cpi_series.iloc[-4]) if len(cpi_series) >= 4 else None

        mom_change = ((cpi_latest - cpi_prev) / cpi_prev) * 100

        three_month_trend = None
        if cpi_3m_ago:
            three_month_trend = ((cpi_latest - cpi_3m_ago) / cpi_3m_ago) * 100

        # Check data age
        latest_date = cpi_series.index[-1]
        data_age_days = (datetime.now() - latest_date).days
        stale_flag = ""
        if data_age_days > 35:
            stale_flag = f" ⚠️ DATA IS {data_age_days} DAYS OLD (CPI is monthly)"

        raw = {
            "cpi_latest": round(cpi_latest, 3),
            "cpi_prev_month": round(cpi_prev, 3),
            "cpi_mom_change_pct": round(mom_change, 3),
            "cpi_3m_trend_pct": round(three_month_trend, 3) if three_month_trend else None,
            "data_date": str(latest_date.date()),
            "data_age_days": data_age_days
        }

        threshold = CONFIG["cpi_mom_threshold"]  # default 0.2

        if mom_change >= threshold:
            result.mark_bullish(
                f"INFLATION RISING — CPI +{mom_change:.3f}% MoM "
                f"(CPI={cpi_latest:.3f}){stale_flag}. BULLISH FOR GOLD.",
                raw
            )

        elif mom_change > 0:
            result.available = True
            result.bullish = False
            result.score = 0
            result.raw = raw
            result.status = (
                f"F3-CPI ⚠️  INFLATION MILD — CPI +{mom_change:.3f}% MoM. "
                f"Below threshold ({threshold}%). Weak signal.{stale_flag}"
            )
            log.info(result.status)

        else:
            result.mark_bearish(
                f"INFLATION FLAT/FALLING — CPI {mom_change:.3f}% MoM. "
                f"Not supportive for gold.{stale_flag}",
                raw
            )

    except Exception as e:
        result.mark_unavailable(f"CPI calculation error: {e}")

    return result

# =============================================================================
# FACTOR 4 — Geopolitical Tension
# Bullish when global conflict/crisis news is elevated
# =============================================================================

def evaluate_factor_4_geopolitical() -> FactorResult:
    """
    F4: Search news for geopolitical tension keywords.
    Score articles by severity. BULLISH if tension score >= threshold.
    """
    result = FactorResult("F4-GEO")

    geo_keywords = [
        "war", "conflict", "military strike", "invasion", "sanctions",
        "nuclear", "tension", "crisis", "terrorism",
        "Middle East", "Ukraine", "Russia", "Taiwan", "North Korea"
    ]

    articles = fetch_news(geo_keywords, days_back=2)

    if articles is None:
        result.mark_unavailable("NewsAPI geo-political fetch failed")
        return result

    if len(articles) == 0:
        result.mark_neutral("No geopolitical news returned by NewsAPI", {"articles_fetched": 0})
        return result

    try:
        high_severity = ["war", "invasion", "nuclear", "military strike", "attack"]
        medium_severity = ["conflict", "sanctions", "tension", "crisis", "terrorism"]

        high_count = 0
        medium_count = 0
        top_headline = None

        for i, article in enumerate(articles):
            text = (
                (article.get("title") or "") + " " +
                (article.get("description") or "")
            ).lower()

            is_high = any(kw in text for kw in high_severity)
            is_medium = any(kw in text for kw in medium_severity)

            if is_high:
                high_count += 1
            elif is_medium:
                medium_count += 1

            if i == 0 and article.get("title"):
                top_headline = article["title"]

        tension_score = (high_count * 2) + (medium_count * 1)

        raw = {
            "total_articles": len(articles),
            "high_severity_count": high_count,
            "medium_severity_count": medium_count,
            "tension_score": tension_score,
            "top_headline": top_headline or "N/A"
        }

        threshold = CONFIG["geo_tension_score_threshold"]  # default 5

        if tension_score >= threshold and high_count >= 1:
            result.mark_bullish(
                f"GEOPOLITICAL TENSION HIGH — score={tension_score} "
                f"(high_severity={high_count}, medium={medium_count}). "
                f"SAFE-HAVEN GOLD DEMAND. Top: \"{top_headline}\"",
                raw
            )

        elif tension_score >= threshold:
            result.mark_bullish(
                f"GEOPOLITICAL TENSION ELEVATED — score={tension_score} "
                f"({len(articles)} articles scanned). BULLISH FOR GOLD.",
                raw
            )

        elif tension_score >= 2:
            result.available = True
            result.bullish = False
            result.score = 0
            result.raw = raw
            result.status = (
                f"F4-GEO ⚠️  MILD TENSION — score={tension_score}. "
                f"Below threshold ({threshold}). Minor gold support."
            )
            log.info(result.status)

        else:
            result.mark_neutral(
                f"LOW GEOPOLITICAL TENSION — score={tension_score}. "
                f"No significant safe-haven premium.",
                raw
            )

    except Exception as e:
        result.mark_unavailable(f"Geopolitical calculation error: {e}")

    return result

# =============================================================================
# FACTOR 5 — INR vs USD Rate
# Bullish for Indian gold ETFs when INR weakens (USD/INR rises)
# =============================================================================

def evaluate_factor_5_inr() -> FactorResult:
    """
    F5: Fetch USD/INR rate. BULLISH if INR weakened >= 0.2% over 5 days.
    Higher USD/INR = weaker INR = Indian gold ETFs rise more.
    """
    result = FactorResult("F5-INR")

    df = fetch_yahoo(CONFIG["usdinr_symbol"], period_days=12)

    if df is None:
        result.mark_unavailable("USD/INR data fetch failed from Yahoo Finance")
        return result

    if len(df) < 6:
        result.mark_unavailable(f"Not enough USD/INR data (got {len(df)}, need 6)")
        return result

    try:
        usdinr_today = float(df["Close"].iloc[-1])
        usdinr_5d_ago = float(df["Close"].iloc[-6])
        usdinr_1d_ago = float(df["Close"].iloc[-2])

        change_5d = ((usdinr_today - usdinr_5d_ago) / usdinr_5d_ago) * 100
        change_1d = ((usdinr_today - usdinr_1d_ago) / usdinr_1d_ago) * 100

        raw = {
            "usdinr_today": round(usdinr_today, 4),
            "usdinr_5d_ago": round(usdinr_5d_ago, 4),
            "change_5d_pct": round(change_5d, 4),
            "change_1d_pct": round(change_1d, 4),
            "data_date": str(df.index[-1].date())
        }

        threshold = CONFIG["usdinr_5d_change_threshold"]  # default 0.2

        if change_5d >= threshold:
            result.mark_bullish(
                f"INR WEAKENING — USD/INR rose {change_5d:.3f}% over 5 days "
                f"(now ₹{usdinr_today:.4f}). Indian gold ETFs benefit. BULLISH.",
                raw
            )

        elif change_5d <= -0.5:
            result.mark_bearish(
                f"INR STRENGTHENING — USD/INR fell {change_5d:.3f}% over 5 days "
                f"(now ₹{usdinr_today:.4f}). Reduces Indian gold ETF gains.",
                raw
            )

        else:
            result.mark_neutral(
                f"INR FLAT — USD/INR {change_5d:.3f}% over 5 days "
                f"(now ₹{usdinr_today:.4f}). No significant currency impact.",
                raw
            )

    except Exception as e:
        result.mark_unavailable(f"USD/INR calculation error: {e}")

    return result

# =============================================================================
# FINAL MACRO VERDICT
# Combines F1–F5 and generates the final BUY / WAIT / DO NOT TRADE signal
# =============================================================================

def generate_final_verdict(
    f1: FactorResult,
    f2: FactorResult,
    f3: FactorResult,
    f4: FactorResult,
    f5: FactorResult,
    gold_etf_price: Optional[float]
) -> dict:
    """
    Combine all 5 factor results into a final macro signal verdict.
    Returns a dict with signal, confidence, recommendation, and trade levels.
    """

    factors = [f1, f2, f3, f4, f5]
    available = [f for f in factors if f.available]
    bullish = [f for f in available if f.bullish]

    available_count = len(available)
    bullish_count = len(bullish)
    min_required = CONFIG["macro_min_bullish_triggers"]  # default 2

    verdict = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST"),
        "factors_available": available_count,
        "factors_bullish": bullish_count,
        "signal": None,
        "confidence": None,
        "recommendation": None,
        "entry_price": None,
        "target_price": None,
        "stop_loss_price": None,
        "hold_days": "3–5 trading days",
        "error": None
    }

    # Minimum data gate
    if available_count < 3:
        verdict["signal"] = "INSUFFICIENT DATA"
        verdict["confidence"] = "NONE"
        verdict["recommendation"] = (
            f"Only {available_count} of 5 factors could be fetched. "
            f"Need at least 3. DO NOT TRADE — data too incomplete."
        )
        verdict["error"] = "INSUFFICIENT_DATA"
        return verdict

    # Determine signal
    if bullish_count >= 4:
        verdict["signal"] = "STRONG BUY"
        verdict["confidence"] = "VERY HIGH"
        verdict["recommendation"] = (
            f"{bullish_count} of {available_count} macro factors are BULLISH. "
            f"BUY AT END OF DAY. Target +2% in 3–5 days."
        )

    elif bullish_count == 3:
        verdict["signal"] = "STRONG BUY"
        verdict["confidence"] = "HIGH"
        verdict["recommendation"] = (
            f"{bullish_count} of {available_count} macro factors are BULLISH. "
            f"BUY AT END OF DAY. Target +2% in 3–5 days."
        )

    elif bullish_count == 2:
        verdict["signal"] = "BUY"
        verdict["confidence"] = "MEDIUM"
        verdict["recommendation"] = (
            f"{bullish_count} of {available_count} macro factors are BULLISH. "
            f"Minimum threshold met. BUY AT END OF DAY. Target +2% in 3–5 days."
        )

    elif bullish_count == 1:
        verdict["signal"] = "WATCH"
        verdict["confidence"] = "LOW"
        verdict["recommendation"] = (
            f"Only {bullish_count} of {available_count} factors bullish. "
            f"Need at least {min_required}. WAIT — do not enter today."
        )

    else:
        verdict["signal"] = "DO NOT TRADE"
        verdict["confidence"] = "NONE"
        verdict["recommendation"] = (
            f"0 of {available_count} macro factors are bullish. "
            f"No macro support for gold. STAY OUT."
        )

    # Add entry levels if BUY signal
    if verdict["signal"] in ("BUY", "STRONG BUY"):
        if gold_etf_price is not None:
            target_pct = CONFIG["profit_target_pct"] / 100
            stop_pct = CONFIG["stop_loss_pct"] / 100
            verdict["entry_price"] = round(gold_etf_price, 2)
            verdict["target_price"] = round(gold_etf_price * (1 + target_pct), 2)
            verdict["stop_loss_price"] = round(gold_etf_price * (1 - stop_pct), 2)
        else:
            verdict["recommendation"] += (
                " ⚠️ NOTE: EOD price unavailable — "
                "check GOLDBEES.NS price manually before placing order."
            )

    return verdict

# =============================================================================
# FORMATTED PRINT OUTPUT
# =============================================================================

def print_signal_output(
    f1: FactorResult,
    f2: FactorResult,
    f3: FactorResult,
    f4: FactorResult,
    f5: FactorResult,
    verdict: dict
):
    """Print a clean, formatted signal output to console."""

    W = 70  # box width
    line = "═" * W

    def box_line(text="", fill=False):
        if fill:
            print(f"║{'─' * W}║")
        else:
            # Pad or trim text to fit
            padded = text[:W].ljust(W)
            print(f"║{padded}║")

    print(f"╔{line}╗")
    box_line(f"  SIGNAL 02 — MACRO TRIGGER  |  {verdict['timestamp']}")
    print(f"╠{line}╣")
    box_line(f"  Factors Available : {verdict['factors_available']} of 5")
    box_line(f"  Factors Bullish   : {verdict['factors_bullish']}")
    print(f"╠{line}╣")

    for factor in [f1, f2, f3, f4, f5]:
        box_line(f"  {factor.status[:W-4]}")
        if factor.raw:
            # Print key raw values
            raw_str = "  └─ " + " | ".join(
                f"{k}={v}" for k, v in list(factor.raw.items())[:4]
            )
            box_line(raw_str[:W])

    print(f"╠{line}╣")
    box_line(f"  SIGNAL     : {verdict['signal']}")
    box_line(f"  CONFIDENCE : {verdict['confidence']}")
    box_line(f"  ACTION     : {verdict['recommendation'][:W-13]}")
    if len(verdict['recommendation']) > W - 13:
        box_line(f"               {verdict['recommendation'][W-13:W*2-26]}")

    if verdict["entry_price"]:
        print(f"╠{line}╣")
        box_line(f"  TRADE LEVELS (GOLDBEES.NS):")
        box_line(f"  Entry Price  : ₹{verdict['entry_price']}")
        box_line(f"  Target (+{CONFIG['profit_target_pct']}%): ₹{verdict['target_price']}")
        box_line(f"  Stop Loss (-{CONFIG['stop_loss_pct']}%) : ₹{verdict['stop_loss_price']}")
        box_line(f"  Hold Period  : {verdict['hold_days']}")

    if verdict.get("error"):
        print(f"╠{line}╣")
        box_line(f"  ⚠️  ERROR: {verdict['error']}")

    print(f"╚{line}╝")

# =============================================================================
# MAIN RUNNER
# =============================================================================

def run_signal_02() -> dict:
    """
    Main entry point. Runs all 5 factor evaluations and returns the verdict.
    Call this function from Signal 08 (Final Verdict) or standalone.
    """
    log.info("=" * 60)
    log.info("SIGNAL 02 — MACRO TRIGGER — START")
    log.info("=" * 60)

    # ── Run all 5 factors independently ──────────────────────────────────────
    log.info("Evaluating Factor 1: DXY...")
    f1 = evaluate_factor_1_dxy()

    log.info("Evaluating Factor 2: Fed Stance...")
    f2 = evaluate_factor_2_fed()

    log.info("Evaluating Factor 3: CPI Inflation...")
    f3 = evaluate_factor_3_cpi()

    log.info("Evaluating Factor 4: Geopolitical Tension...")
    f4 = evaluate_factor_4_geopolitical()

    log.info("Evaluating Factor 5: INR/USD Rate...")
    f5 = evaluate_factor_5_inr()

    # ── Fetch ETF price for entry level calculation ───────────────────────────
    gold_etf_price = None
    log.info(f"Fetching EOD price for {CONFIG['primary_etf']}...")
    etf_df = fetch_yahoo(CONFIG["primary_etf"], period_days=3)
    if etf_df is not None and not etf_df.empty:
        gold_etf_price = float(etf_df["Close"].iloc[-1])
        log.info(f"GOLDBEES.NS latest close: ₹{gold_etf_price}")
    else:
        log.warning("Could not fetch GOLDBEES.NS EOD price — trade levels will not be shown")

    # ── Generate final verdict ────────────────────────────────────────────────
    log.info("Generating final verdict...")
    verdict = generate_final_verdict(f1, f2, f3, f4, f5, gold_etf_price)

    # ── Print formatted output ────────────────────────────────────────────────
    print("\n")
    print_signal_output(f1, f2, f3, f4, f5, verdict)
    print("\n")

    log.info(f"SIGNAL 02 VERDICT: {verdict['signal']} | Confidence: {verdict['confidence']}")
    log.info("SIGNAL 02 — MACRO TRIGGER — END")

    return {
        "signal": verdict["signal"],
        "confidence": verdict["confidence"],
        "factors_bullish": verdict["factors_bullish"],
        "factors_available": verdict["factors_available"],
        "recommendation": verdict["recommendation"],
        "entry_price": verdict.get("entry_price"),
        "target_price": verdict.get("target_price"),
        "stop_loss_price": verdict.get("stop_loss_price"),
        "timestamp": verdict["timestamp"],
        "raw_factors": {
            "f1_dxy": f1.raw,
            "f2_fed": f2.raw,
            "f3_cpi": f3.raw,
            "f4_geo": f4.raw,
            "f5_inr": f5.raw,
        }
    }


# =============================================================================
# RUN AS STANDALONE SCRIPT
# =============================================================================

if __name__ == "__main__":
    result = run_signal_02()
