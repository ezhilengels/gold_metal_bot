# =============================================================================
# GOLD BOT — config.py
# Central configuration for all signals
# Edit this file to set your API keys and trading preferences
# =============================================================================

CONFIG = {
    # ── ETF & Market Symbols ──────────────────────────────────────────────
    "primary_etf":       "GOLDBEES.NS",       # Primary Indian Gold ETF (NSE)
    "alt_etfs":          ["AXISGOLD.NS", "HDFCGOLD.NS"],
    "comex_symbol":      "GC=F",              # COMEX Gold Futures
    "dxy_symbol":        "DX-Y.NYB",          # US Dollar Index
    "usdinr_symbol":     "USDINR=X",          # USD/INR Exchange Rate

    # ── API Keys ──────────────────────────────────────────────────────────
    # Get FRED API key free at: https://fred.stlouisfed.org/docs/api/api_key.html
    "fred_api_key":      "476bcc80bbd8594b00119b1cced3da9e",

    # Get NewsAPI key free at: https://newsapi.org/register
    "news_api_key":      "3ddbde7ed75d4a34a8e7e88d8c643980",

    # Telegram (optional — for alerts)
    "telegram_bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
    "telegram_chat_id":   "YOUR_TELEGRAM_CHAT_ID",

    # ── Trading Parameters ────────────────────────────────────────────────
    "profit_target_pct":        3.0,   # Target profit % per trade
    "stop_loss_pct":            1.0,   # Stop loss % below entry
    "transaction_cost_pct":     0.3,   # Round-trip brokerage + charges estimate

    # ── Signal 02 Specific ────────────────────────────────────────────────
    "macro_min_bullish_triggers": 2,   # Min bullish factors needed for BUY signal
    "dxy_5d_change_threshold":   -0.5, # DXY must fall by this % to count as bullish
    "usdinr_5d_change_threshold": 0.2, # USDINR must rise by this % to count as bullish
    "cpi_mom_threshold":          0.2, # CPI MoM % to count as bullish
    "geo_tension_score_threshold": 5,  # Geo news tension score to count as bullish

    # ── Timeouts & Retry ─────────────────────────────────────────────────
    "fetch_timeout_seconds":    15,    # Max seconds to wait for any data fetch
    "max_data_age_hours":       26,    # Data older than this is flagged as stale

    # ── Logging ───────────────────────────────────────────────────────────
    "log_to_file":   True,
    "log_directory": "./logs",
}
