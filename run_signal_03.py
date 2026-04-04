#!/usr/bin/env python3
# =============================================================================
# GOLD BOT — run_signal_03.py
# Quick launcher for Signal 03 (Seasonality Play — India Specific)
#
# USAGE:
#   python run_signal_03.py
#
# NO API KEYS REQUIRED — this signal uses only the system date.
# It cannot fail due to data unavailability.
#
# SETUP (first time):
#   1. pip install -r requirements.txt
#   2. Run: python run_signal_03.py
#
# RECOMMENDED FREQUENCY:
#   Run once per week (Sunday evening).
#   Re-run if a major festival date is confirmed in the news.
# =============================================================================

import sys
import os

# ── Header ────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  GOLD BOT — Signal 03 Seasonality Play (India)")
print("  No API keys required — uses system date only")
print("=" * 60)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Config check ─────────────────────────────────────────────────────────────
try:
    from config import CONFIG
except ImportError:
    print("❌ ERROR: config.py not found. Run from the gold_bot/ directory.")
    sys.exit(1)

# ── Import and run ────────────────────────────────────────────────────────────
try:
    from signal_03_seasonality import run_signal_03
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you are running from the gold_bot/ directory.")
    sys.exit(1)

result = run_signal_03()

# ── Summary print ─────────────────────────────────────────────────────────────
print("\n" + "─" * 60)
print("QUICK SUMMARY")
print("─" * 60)
print(f"  Signal    : {result.get('signal')}")
print(f"  Score     : {result.get('score', 0)} / 5")
print(f"  Phase     : {result.get('phase')}")
print(f"  Demand    : {result.get('demand')}")
print(f"  Strength  : {result.get('strength')}")
print(f"  Confidence: {result.get('confidence')}")
if result.get("upcoming_event"):
    print(f"  Upcoming  : {result.get('upcoming_event')}")
print("─" * 60)
print()

# ── Exit code ─────────────────────────────────────────────────────────────────
sig = result.get("signal", "")
if "UNAVAILABLE" in sig or "ERROR" in sig:
    sys.exit(2)   # data error
elif sig in ("HOLD / SELL TARGET",):
    sys.exit(1)   # sell zone — no new entries
else:
    sys.exit(0)   # all other cases (accumulate, buy, neutral)
