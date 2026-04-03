#!/usr/bin/env python3
# =============================================================================
# GOLD BOT — run_signal_07.py
# Launcher for Signal 07: Avoid Signal (Risk Filter)
#
# USAGE:
#   python run_signal_07.py
#
# Run this FIRST every day before checking any other signal.
# If output is AVOID → stop. Do not run any other signal today.
#
# Requires: pip install -r requirements.txt
# API keys in config.py — NewsAPI recommended for A2 bonus news scan.
#            Yahoo Finance (A1) works without keys.
# =============================================================================

import sys
import os

print("\n" + "=" * 70)
print("  GOLD BOT — Signal 07: Avoid Signal  (Risk Gate)")
print("=" * 70)
print("  ⚠️  Run this FIRST. If output = AVOID, do not trade today.")
print()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from config import CONFIG
except ImportError:
    print("❌ ERROR: config.py not found. Run from the gold_bot/ directory.")
    sys.exit(1)

news_key = CONFIG.get("news_api_key", "")
print(f"  NewsAPI key : {'✅ Configured' if news_key and news_key != 'YOUR_NEWSAPI_KEY_HERE' else '⚠️  Not set (A2 news scan disabled)'}")
print(f"  Yahoo Finance: No key needed")
print()

try:
    from signal_07_avoid_signal import run_signal_07
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

result = run_signal_07()

# ── Exit code based on verdict ────────────────────────────────────────────────
print("─" * 70)
print("QUICK SUMMARY")
print("─" * 70)
verdict = result["signal"]
print(f"  Final Verdict : {verdict}")
print(f"  A1 (Move)     : {result['check_verdicts']['a1']}")
print(f"  A2 (Events)   : {result['check_verdicts']['a2']}")
print(f"  A3 (Costs)    : {result['check_verdicts']['a3']}")
print(f"  Override Rule : {result['override_note']}")
print()

if verdict == "AVOID":
    print("  🚫 TRADE BLOCKED — Do not run other signals today.")
elif verdict == "CAUTION":
    print("  ⚠️  Proceed carefully. Reduce size. Tighten stops.")
else:
    print("  ✅ Clear to trade. Run Signal 01, 02, 04 for entry signals.")

print("─" * 70)
print()

# Use exit code 1 for AVOID so shell scripts can check it
sys.exit(1 if verdict == "AVOID" else 0)
