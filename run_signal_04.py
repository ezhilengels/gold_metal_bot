#!/usr/bin/env python3
# =============================================================================
# GOLD BOT — run_signal_04.py
# Launcher for Signal 04: Bollinger Bands Range Trading
#
# USAGE:
#   python run_signal_04.py
#
# No API keys needed — uses Yahoo Finance only.
# Requires:  pip install -r requirements.txt
# =============================================================================

import sys
import os

print("\n" + "=" * 70)
print("  GOLD BOT — Signal 04: Bollinger Bands Range Trading")
print("=" * 70)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from config import CONFIG
except ImportError:
    print("❌ ERROR: config.py not found. Run from the gold_bot/ directory.")
    sys.exit(1)

print(f"  ETF        : {CONFIG['primary_etf']}")
print(f"  BB Period  : 20 days, 2 standard deviations")
print(f"  Target     : Upper Band (typically +2–4% from lower band)")
print(f"  Stop Loss  : 1% below lower band")
print(f"  Data       : Yahoo Finance only — no API keys required")
print()

try:
    from signal_04_bollinger_bands import run_signal_04
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

result = run_signal_04()

# ── Quick summary ─────────────────────────────────────────────────────────────
print("─" * 70)
print("QUICK SUMMARY")
print("─" * 70)
print(f"  Signal      : {result['signal']}")
print(f"  Confidence  : {result.get('confidence', 'N/A')}")
print(f"  Zone        : {result.get('zone_label', 'N/A')}")
print(f"  %B          : {result.get('pct_b', 'N/A')}")
print(f"  Bandwidth   : {result.get('bw', 'N/A')}%")
print(f"  Squeeze     : {'YES ⚡' if result.get('is_squeeze') else 'No'}")

levels = result.get("trade_levels")
if levels:
    print(f"  Entry       : ₹{levels['entry']}")
    print(f"  Target 1    : ₹{levels['target1']}  ({levels['pct_to_t1']:+.2f}%)")
    print(f"  Target 2    : ₹{levels['target2']}  ({levels['pct_to_t2']:+.2f}%)")
    print(f"  Stop Loss   : ₹{levels['stop']}  ({levels['pct_to_stop']:+.2f}%)")

print("─" * 70)
print()
