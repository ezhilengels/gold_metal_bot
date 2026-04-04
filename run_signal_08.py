#!/usr/bin/env python3
# =============================================================================
# GOLD BOT — run_signal_08.py
# Full pipeline launcher — runs ALL signals and produces the Final Verdict
#
# USAGE:
#   python run_signal_08.py
#
# This is the main daily script you run each trading day.
# It calls Signals 07 → 01 → 02 → 04 → 03(stub) → 05(stub) → 06(stub)
# then combines them into a 0–80 score and final BUY / WAIT / AVOID verdict.
#
# Requires:  pip install -r requirements.txt
# API keys:  set fred_api_key and news_api_key in config.py
# =============================================================================

import sys
import os
import webbrowser
from datetime import datetime

print("\n" + "╔" + "═"*68 + "╗")
print("║" + "  🥇 GOLD BOT — Full Signal Pipeline".ljust(68) + "║")
print("║" + f"  {datetime.now().strftime('%A %d %B %Y  %H:%M:%S IST')}".ljust(68) + "║")
print("╚" + "═"*68 + "╝")
print()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from config import CONFIG
except ImportError:
    print("❌ ERROR: config.py not found. Run from the gold_bot/ directory.")
    sys.exit(1)

# ── Config summary ────────────────────────────────────────────────────────────
fred_ok  = CONFIG.get("fred_api_key", "") not in ("", "YOUR_FRED_API_KEY_HERE")
news_ok  = CONFIG.get("news_api_key", "") not in ("", "YOUR_NEWSAPI_KEY_HERE")

print("  CONFIGURATION")
print(f"  Primary ETF  : {CONFIG['primary_etf']}")
print(f"  Profit Target: +{CONFIG['profit_target_pct']}%  |  Stop Loss: -{CONFIG['stop_loss_pct']}%")
print(f"  FRED API     : {'✅ Set' if fred_ok else '⚠️  Not set — S02 Fed/CPI factors will show DATA UNAVAILABLE'}")
print(f"  NewsAPI      : {'✅ Set' if news_ok else '⚠️  Not set — S02 Geo/Fed news factors will show DATA UNAVAILABLE'}")
print()
print("  Running all signals now. This may take 20–40 seconds...")
print()

try:
    from signal_08_verdict_score import run_signal_08
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

result = run_signal_08()

# ── Final summary block ───────────────────────────────────────────────────────
print("─" * 70)
print("  BOT SUMMARY")
print("─" * 70)
print(f"  Final Verdict  : {result.get('signal', 'N/A')}")
print(f"  Confidence     : {result.get('confidence', 'N/A')}")
print(f"  Score          : {result.get('final_score', 0):.1f} / 80.0")

scores = result.get("signal_scores", {})
if scores:
    print(f"  ├ S01 Buy Dip  : {scores.get('s01', {}).get('pts', 0):.0f} / 15")
    print(f"  ├ S02 Macro    : {scores.get('s02', {}).get('pts', 0):.0f} / 25")
    print(f"  ├ S03 Season   : {scores.get('s03', {}).get('pts', 0):.0f} / 5")
    print(f"  ├ S04 BB Bands : {scores.get('s04', {}).get('pts', 0):.0f} / 15")
    print(f"  ├ S05 Outlook  : {scores.get('s05', {}).get('pts', 0):.0f} / 10")
    print(f"  ├ S06 Weekly   : {scores.get('s06', {}).get('pts', 0):.0f} / 10")
    print(f"  ├ S09 Volume   : {scores.get('s09', {}).get('pts', 0):.0f} / 10")
    print(f"  ├ S10 MCX Sprd : {scores.get('s10', {}).get('pts', 0):.0f} / 5")
    print(f"  └ S07 Penalty  : -{scores.get('s07_penalty', 0):.0f} pts")

if result.get("entry_price"):
    print()
    print(f"  Entry  : ₹{result['entry_price']}")
    print(f"  Target : ₹{result['target_price']}  (+{CONFIG['profit_target_pct']}%)")
    print(f"  Stop   : ₹{result['stop_price']}  (-{CONFIG['stop_loss_pct']}%)")

if result.get("sell_alert"):
    print()
    print(f"  ⚡ {result['sell_alert']}")

print("─" * 70)
print()

# ── Generate HTML dashboard ───────────────────────────────────────────────────
try:
    from dashboard_writer import write_dashboard
    dashboard_path = write_dashboard(result, CONFIG)
    dashboard_url  = "file://" + os.path.abspath(dashboard_path)
    print(f"  📊 Dashboard : {dashboard_path}")
    print(f"  🌐 Opening in browser...")
    webbrowser.open(dashboard_url)
    print()
except Exception as e:
    print(f"  ⚠️  Dashboard generation failed (non-fatal): {e}")
    print()

# Exit code: 0 = BUY/WATCH, 1 = blocked/no trade
blocked = "BLOCKED" in result.get("signal", "") or "DO NOT" in result.get("signal", "")
sys.exit(1 if blocked else 0)
