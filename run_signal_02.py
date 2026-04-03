#!/usr/bin/env python3
# =============================================================================
# GOLD BOT — run_signal_02.py
# Quick launcher for Signal 02 (Macro Trigger)
#
# USAGE:
#   python run_signal_02.py
#
# SETUP (first time):
#   1. pip install -r requirements.txt
#   2. Open config.py and set:
#        fred_api_key  → get free at https://fred.stlouisfed.org/docs/api/api_key.html
#        news_api_key  → get free at https://newsapi.org/register
#   3. Run: python run_signal_02.py
# =============================================================================

import sys
import os

# ── Pre-flight config check ───────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  GOLD BOT — Signal 02 Macro Trigger")
print("=" * 60)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from config import CONFIG
except ImportError:
    print("❌ ERROR: config.py not found. Run from the gold_bot/ directory.")
    sys.exit(1)

# Check API keys
warnings = []
if CONFIG.get("fred_api_key") == "YOUR_FRED_API_KEY_HERE":
    warnings.append("⚠️  FRED API key not set — Factors F2 (Fed) and F3 (CPI) will show DATA UNAVAILABLE")
if CONFIG.get("news_api_key") == "YOUR_NEWSAPI_KEY_HERE":
    warnings.append("⚠️  NewsAPI key not set — Factors F2 (Fed news) and F4 (Geo) will show DATA UNAVAILABLE")

if warnings:
    print("\nCONFIGURATION WARNINGS:")
    for w in warnings:
        print(f"  {w}")
    print("\n  → Edit gold_bot/config.py to add your API keys")
    print("  → Signal will run but affected factors will show DATA UNAVAILABLE")
    print()

# ── Import and run ────────────────────────────────────────────────────────────
try:
    from signal_02_macro_trigger import run_signal_02
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you are running from the gold_bot/ directory.")
    sys.exit(1)

result = run_signal_02()

# ── Summary print ─────────────────────────────────────────────────────────────
print("\n" + "─" * 60)
print("QUICK SUMMARY")
print("─" * 60)
print(f"  Signal   : {result['signal']}")
print(f"  Bullish  : {result['factors_bullish']} of {result['factors_available']} factors")
if result.get("entry_price"):
    print(f"  Entry    : ₹{result['entry_price']}")
    print(f"  Target   : ₹{result['target_price']}")
    print(f"  Stop     : ₹{result['stop_loss_price']}")
print("─" * 60)
print()
