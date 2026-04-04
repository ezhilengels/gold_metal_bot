#!/usr/bin/env python3
# GOLD BOT — run_signal_10.py  |  MCX-COMEX Spread
import sys, os
print("\n" + "=" * 60)
print("  GOLD BOT — Signal 10  MCX-COMEX Spread Monitor")
print("=" * 60)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from config import CONFIG
except ImportError:
    print("❌ config.py not found."); sys.exit(1)
try:
    from signal_10_mcx_spread import run_signal_10
except ImportError as e:
    print(f"❌ Import error: {e}"); sys.exit(1)
result = run_signal_10()
print("\n" + "─" * 60)
print("QUICK SUMMARY")
print("─" * 60)
print(f"  Signal    : {result.get('signal')}")
print(f"  Score     : {result.get('score',0)} / 5")
print(f"  Confidence: {result.get('confidence')}")
sp = result.get('spread', {})
if sp.get('available'):
    print(f"  COMEX Eq  : ₹{sp.get('comex_inr_per_10g',0):,.2f}/10g")
    print(f"  GOLDBEES  : ₹{sp.get('goldbees_inr_10g',0):,.2f}/10g")
    print(f"  Premium   : {sp.get('premium_pct',0):+.2f}%")
print("─" * 60)
sig = result.get("signal", "")
sys.exit(2 if "UNAVAILABLE" in sig else (1 if "AVOID" in sig or "OVERPRICED" in sig else 0))
