#!/usr/bin/env python3
# =============================================================================
# GOLD BOT — run_signal_05.py
# Quick launcher for Signal 05 (2026 Gold Outlook Monitor)
#
# USAGE:
#   python run_signal_05.py
#
# FACTORS FETCHED:
#   O1 — Geopolitical tension  (NewsAPI — requires news_api_key)
#   O2 — Central bank buying   (WGC / news — requires news_api_key)
#   O3 — Fed rate trend        (FRED — requires fred_api_key)
#   O4 — DXY 30-day trend      (Yahoo Finance — no key needed)
#   O5 — US NFP jobs risk      (FRED — requires fred_api_key)
#
# SETUP (first time):
#   1. pip install -r requirements.txt
#   2. Open config.py and set:
#        fred_api_key → get free at https://fred.stlouisfed.org/docs/api/api_key.html
#        news_api_key → get free at https://newsapi.org/register
#   3. Run: python run_signal_05.py
#
# RECOMMENDED FREQUENCY:
#   Run once per week (Sunday or Monday morning).
#   Re-run after: US NFP release, FOMC meeting, major geopolitical event.
# =============================================================================

import sys
import os

# ── Header ────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  GOLD BOT — Signal 05  2026 Gold Outlook Monitor")
print("=" * 60)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Config check ──────────────────────────────────────────────────────────────
try:
    from config import CONFIG
except ImportError:
    print("❌ ERROR: config.py not found. Run from the gold_bot/ directory.")
    sys.exit(1)

# Check API keys — warn but don't stop (factors handle their own failures)
warnings = []
if not CONFIG.get("fred_api_key") or CONFIG.get("fred_api_key", "").startswith("YOUR_"):
    warnings.append("⚠️  FRED API key not set — O3 (Fed) and O5 (NFP) will show DATA UNAVAILABLE")
if not CONFIG.get("news_api_key") or CONFIG.get("news_api_key", "").startswith("YOUR_"):
    warnings.append("⚠️  NewsAPI key not set — O1 (Geopolitical) and O2 (Central Banks) will show DATA UNAVAILABLE")

if warnings:
    print("\nCONFIGURATION WARNINGS:")
    for w in warnings:
        print(f"  {w}")
    print()
    print("  → Signal will run. Available factors will still be scored.")
    print("  → If < 3 factors available, signal outputs INSUFFICIENT DATA.")
    print("  → Edit gold_bot/config.py to add your API keys.")
    print()

# ── Import and run ────────────────────────────────────────────────────────────
try:
    from signal_05_2026_outlook import run_signal_05
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you are running from the gold_bot/ directory.")
    sys.exit(1)

result = run_signal_05()

# ── Summary print ─────────────────────────────────────────────────────────────
print("\n" + "─" * 60)
print("QUICK SUMMARY")
print("─" * 60)
print(f"  Outlook      : {result.get('signal')}")
print(f"  Confidence   : {result.get('confidence')}")
print(f"  Factors Used : {result.get('available_count')} of 5")
print(f"  Score        : {result.get('actual_score', 0):.1f} / {result.get('max_possible', 0):.1f}")
print(f"  Normalized   : {result.get('normalized_pct', 0):.1f}%")
if result.get("bias_note"):
    print(f"  Bias Note    : {result.get('bias_note')}")
if result.get("risk_alert") and result["risk_alert"] != "N/A":
    print(f"  Risk Alert   : {result.get('risk_alert')}")
print("─" * 60)

# Per-factor quick view
print("\nFACTOR BREAKDOWN:")
for key, label in [("o1", "O1 Geopolitical"), ("o2", "O2 Cent.Banks"),
                   ("o3", "O3 Fed Rates  "), ("o4", "O4 DXY 30d   "),
                   ("o5", "O5 NFP Risk   ")]:
    f = result.get(key, {})
    avail = "✅" if f.get("available") else "⬛"
    score = f.get("score", 0)
    mx    = f.get("max_score", 0)
    print(f"  {avail} {label}: {score}/{mx} pts — {f.get('bias', 'N/A')}")
print("─" * 60)
print()

# ── Exit code ─────────────────────────────────────────────────────────────────
sig = result.get("signal", "")
if "UNAVAILABLE" in sig or "INSUFFICIENT" in sig:
    sys.exit(2)   # insufficient data
elif sig in ("BEARISH", "MILDLY BEARISH"):
    sys.exit(1)   # bearish outlook — trade with caution
else:
    sys.exit(0)   # neutral to bullish
