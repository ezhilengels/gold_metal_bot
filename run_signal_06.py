#!/usr/bin/env python3
# =============================================================================
# GOLD BOT — run_signal_06.py
# Quick launcher for Signal 06 (Weekly Routine Checker)
#
# USAGE:
#   python run_signal_06.py
#
# ACTIVE DAYS: MONDAY to THURSDAY ONLY
#   Friday / Saturday / Sunday → outputs NON-TRADING DAY immediately.
#
# DATA FETCHED:
#   W1 — COMEX Gold (GC=F)     via Yahoo Finance — no API key needed
#   W2 — DXY (DX-Y.NYB)        via Yahoo Finance — no API key needed
#   W3 — Economic calendar      via hardcoded 2026 FOMC + dynamic NFP/CPI
#
# SETUP (first time):
#   1. pip install -r requirements.txt
#   2. Run: python run_signal_06.py
#
# RECOMMENDED FREQUENCY:
#   Run every Sunday evening (8–10 PM IST) to get the week's plan.
#   Re-run Monday morning before 9:15 AM IST to confirm with latest prices.
# =============================================================================

import sys
import os
from datetime import date

# ── Header ────────────────────────────────────────────────────────────────────
day_names  = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
today_name = day_names[date.today().weekday()]

print("\n" + "=" * 60)
print("  GOLD BOT — Signal 06  Weekly Routine Checker")
print(f"  Today: {today_name} {date.today().strftime('%d %b %Y')}")
print("  Active: Monday to Thursday only")
print("=" * 60)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Config check ──────────────────────────────────────────────────────────────
try:
    from config import CONFIG
except ImportError:
    print("❌ ERROR: config.py not found. Run from the gold_bot/ directory.")
    sys.exit(1)

# ── Import and run ────────────────────────────────────────────────────────────
try:
    from signal_06_weekly_routine import run_signal_06
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you are running from the gold_bot/ directory.")
    sys.exit(1)

result = run_signal_06()

# ── Summary print ─────────────────────────────────────────────────────────────
print("\n" + "─" * 60)
print("QUICK SUMMARY")
print("─" * 60)
print(f"  Signal      : {result.get('signal')}")
print(f"  Confidence  : {result.get('confidence')}")
print(f"  Weekly Bias : {result.get('weekly_bias', 'N/A')}")
print(f"  Week        : {result.get('week_range', 'N/A')}")

# Today's action
ta = result.get("todays_action", {})
if ta:
    print(f"\n  TODAY ({today_name}):")
    print(f"  Action : {ta.get('action', 'N/A')}")
    if ta.get("entry_allowed"):
        print(f"  ✅ ENTRY ALLOWED today")
        if ta.get("stop_loss"):
            print(f"  Stop   : {ta.get('stop_loss')}")
        if ta.get("hold_until"):
            print(f"  Hold   : {ta.get('hold_until')}")
    else:
        print(f"  ❌ No new entries today")
    if ta.get("instruction"):
        print(f"  Tip    : {ta.get('instruction')[:70]}")

# Economic risk this week
w3 = result.get("w3", {})
if w3.get("available"):
    print(f"\n  ECONOMIC RISK: {w3.get('risk_level', 'N/A')}")
    for e in w3.get("high_risk_events", []):
        print(f"  ⚠️  {e['day']}: {e['name']} at {e['time']}")

print("─" * 60)
print()

# ── Exit code ─────────────────────────────────────────────────────────────────
sig = result.get("signal", "")
if sig == "NON-TRADING DAY":
    sys.exit(3)   # non-trading day — not an error
elif "UNAVAILABLE" in sig:
    sys.exit(2)   # data unavailable
elif sig == "HIGH RISK WEEK":
    sys.exit(1)   # high risk — caution
else:
    sys.exit(0)   # entry zone or wait
