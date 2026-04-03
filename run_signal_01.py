#!/usr/bin/env python3
# =============================================================================
# GOLD BOT — run_signal_01.py
# Launcher for Signal 01: Buy the Dip (Mean Reversion)
#
# USAGE:
#   python run_signal_01.py
#
# SETUP (first time):
#   pip install -r requirements.txt
#   (No API keys needed — Signal 01 uses only Yahoo Finance)
# =============================================================================

import sys
import os

print("\n" + "=" * 68)
print("  GOLD BOT — Signal 01: Buy the Dip (Mean Reversion)")
print("=" * 68)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from config import CONFIG
except ImportError:
    print("❌ ERROR: config.py not found. Run from the gold_bot/ directory.")
    sys.exit(1)

print(f"  ETF        : {CONFIG['primary_etf']}")
print(f"  Target     : +{CONFIG['profit_target_pct']}%")
print(f"  Stop Loss  : -{CONFIG['stop_loss_pct']}%")
print(f"  Data needed: No API keys required (Yahoo Finance only)")
print()

try:
    from signal_01_buy_the_dip import run_signal_01
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

result = run_signal_01()

# ── Summary ───────────────────────────────────────────────────────────────────
print("─" * 68)
print("QUICK SUMMARY")
print("─" * 68)
print(f"  Signal     : {result['signal']}")
print(f"  Confidence : {result.get('confidence', 'N/A')}")
print(f"  Score      : {result.get('score', 0):.1f} / 4.0")

if result.get("signal") in ("BUY",) and result.get("current_price"):
    print(f"  Entry      : ₹{result['current_price']:.2f}")

if result.get("action"):
    print(f"  Action     : {result['action']}")

print("─" * 68)
print()
