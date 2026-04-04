#!/usr/bin/env python3
# GOLD BOT — run_signal_09.py  |  Volume Confirmation
import sys, os
from datetime import date
print("\n" + "=" * 60)
print("  GOLD BOT — Signal 09  Volume Confirmation")
print("=" * 60)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from config import CONFIG
except ImportError:
    print("❌ config.py not found."); sys.exit(1)
try:
    from signal_09_volume import run_signal_09
except ImportError as e:
    print(f"❌ Import error: {e}"); sys.exit(1)
result = run_signal_09()
print("\n" + "─" * 60)
print("QUICK SUMMARY")
print("─" * 60)
print(f"  Signal    : {result.get('signal')}")
print(f"  Score     : {result.get('score',0)} / 10")
print(f"  Confidence: {result.get('confidence')}")
v1 = result.get('v1', {}); v2 = result.get('v2', {}); v3 = result.get('v3', {})
if v1.get('available'):
    print(f"  Vol Ratio : {v1.get('vol_ratio')}x 20d avg ({v1.get('bias')})")
if v3.get('available'):
    print(f"  Price 3d  : {v3.get('price_3d_pct',0):+.2f}% | Vol 3d: {v3.get('vol_3d_pct',0):+.2f}%")
print("─" * 60)
sig = result.get("signal", "")
sys.exit(2 if "UNAVAILABLE" in sig else (1 if "CAUTION" in sig else 0))
