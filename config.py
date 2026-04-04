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

    # ── Signal 12 — Correlation Break Alert ──────────────────────────────
    "s12_enabled":                 True,
    "s12_lookback_days":           60,   # Days of history for correlation calculation
    "s12_rolling_window":          20,   # Rolling Pearson window (main)
    "s12_early_warning_window":    10,   # Short window for early divergence detection
    "s12_comex_break_threshold":   0.75, # GOLDBEES↔COMEX: correlation below this = break
    "s12_dxy_break_threshold":    -0.20, # GOLDBEES↔DXY: correlation above this = break
    "s12_usdinr_break_threshold":  0.10, # GOLDBEES↔USDINR: correlation below this = break
    "s12_nifty_positive_break":    0.40, # GOLDBEES↔Nifty: corr above this = bullish break
    "s12_nifty_negative_break":   -0.50, # GOLDBEES↔Nifty: corr below this = bearish break
    "s12_max_pts":                  8,   # Max points S12 can contribute to composite
    "s12_penalty_pts":             -5,   # Penalty when 2+ correlations break bearishly

    # ── Timeouts & Retry ─────────────────────────────────────────────────
    "fetch_timeout_seconds":    15,    # Max seconds to wait for any data fetch
    "max_data_age_hours":       26,    # Data older than this is flagged as stale

    # ── Scheduler / Runner ───────────────────────────────────────────────
    # NSE trading hours: 9:15 AM – 3:30 PM IST, Monday–Thursday (S06 skips Fri)
    "bot_run_time_ist":        "09:15",  # HH:MM — time to fire in IST every trading day
    "bot_run_days":            [0,1,2,3],# 0=Mon 1=Tue 2=Wed 3=Thu (Friday = no new entries)
    "bot_run_timezone_offset": 5.5,      # IST = UTC +5:30 (used when pytz not available)
    "auto_open_dashboard":     False,    # Open dashboard.html in browser after each run
    "dashboard_output_path":   "./dashboard.html",
    "run_history_path":        "./run_history.json",
    "max_run_history_entries": 90,       # Keep last N run records
    "holding_entry_price":     0,        # Set to your buy price when holding (0 = not holding)

    # ── NSE Market Holidays 2025–2026 ────────────────────────────────────
    # Source: NSE India official holiday calendar
    # Format: "YYYY-MM-DD"
    "market_holidays": [
        # 2025
        "2025-01-26",  # Republic Day
        "2025-02-26",  # Mahashivratri
        "2025-03-14",  # Holi
        "2025-03-31",  # Id-Ul-Fitr (Ramzan Id) — tentative
        "2025-04-10",  # Dr. Baba Saheb Ambedkar Jayanti (Good Friday alt)
        "2025-04-14",  # Dr. Baba Saheb Ambedkar Jayanti
        "2025-04-18",  # Good Friday
        "2025-05-01",  # Maharashtra Day
        "2025-08-15",  # Independence Day
        "2025-08-27",  # Ganesh Chaturthi
        "2025-10-02",  # Gandhi Jayanti / Dussehra
        "2025-10-24",  # Diwali Laxmi Puja (Muhurat Trading day — special session)
        "2025-10-31",  # Diwali Balipratipada
        "2025-11-05",  # Prakash Gurpurb / Guru Nanak Jayanti
        "2025-12-25",  # Christmas
        # 2026
        "2026-01-26",  # Republic Day
        "2026-03-03",  # Mahashivratri (tentative)
        "2026-03-20",  # Holi (tentative)
        "2026-04-03",  # Good Friday (tentative)
        "2026-04-14",  # Dr. Baba Saheb Ambedkar Jayanti
        "2026-05-01",  # Maharashtra Day
        "2026-08-15",  # Independence Day
        "2026-10-02",  # Gandhi Jayanti
        "2026-11-14",  # Diwali (tentative)
        "2026-12-25",  # Christmas
    ],

    # ── Logging ───────────────────────────────────────────────────────────
    "log_to_file":   True,
    "log_directory": "./logs",
}
