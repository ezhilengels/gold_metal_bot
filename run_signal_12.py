#!/usr/bin/env python3
# =============================================================================
# GOLD BOT — run_signal_12.py
# Standalone launcher for Signal 12: Correlation Break Alert
#
# Usage:
#   python3 run_signal_12.py          # Full run (60-day lookback)
#   python3 run_signal_12.py --quick  # Short run (30-day lookback)
#
# Output:
#   Terminal table showing all 4 correlations with status + any alerts.
#   Signal 12 does NOT produce a standalone HTML report —
#   correlation data is shown in the main Signal 08 dashboard instead.
#
# Typical use:
#   • Run standalone to check correlation regime before running Signal 08
#   • Run when you see unexpected gold price behaviour
#   • Run after major macro events (FOMC, RBI, geopolitical news)
# =============================================================================

import os
import sys
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(description="Gold Bot — Signal 12 Correlation Break Alert")
    parser.add_argument("--quick", action="store_true",
                        help="Use 30-day lookback instead of 60 (faster)")
    args = parser.parse_args()

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║   📡  GOLD BOT — CORRELATION BREAK ALERT (Signal 12)   ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  Started : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    if args.quick:
        import signal_12_correlation_break as s12
        s12.LOOKBACK_DAYS = 30
        print("  [QUICK MODE] 30-day lookback.\n")

    print("  Fetching 5 instruments independently...")
    print("  (GOLDBEES, COMEX, DXY, USDINR, Nifty50)\n")

    try:
        from signal_12_correlation_break import run_signal_12
        result = run_signal_12()
    except Exception as e:
        print(f"\n  ❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)

    # ── Parse result ──────────────────────────────────────────────────────────
    sig      = result.get("signal",    "N/A")
    score    = result.get("score",     0)
    regime   = result.get("regime",    "N/A")
    conf     = result.get("confidence","N/A")
    corrs    = result.get("correlations", {})
    breaks   = result.get("breaks",    [])
    alerts   = result.get("alert_types", [])
    avail    = result.get("data_availability", {})
    pchg     = result.get("price_changes", {})
    is_nt    = result.get("is_nontrading", False)
    n_avail  = result.get("n_avail_corrs", 0)
    ts       = result.get("timestamp", "")

    # ── Summary banner ────────────────────────────────────────────────────────
    if "DATA UNAVAILABLE" in sig:
        print("╔══════════════════════════════════════════════════════════╗")
        print("║  ⬛  DATA UNAVAILABLE                                    ║")
        print("╚══════════════════════════════════════════════════════════╝")
        print()
        print("  Could not fetch enough data to compute correlations.")
        missing = [k for k, v in avail.items() if not v]
        if missing:
            print(f"  Missing: {', '.join(missing).upper()}")
        print()
        print("  Possible causes:")
        print("    • No internet connection")
        print("    • yfinance rate limit — wait a few minutes and retry")
        print("    • ^NSEI (Nifty) sometimes unavailable on weekends")
        sys.exit(2)

    # Signal → emoji + colour hint
    def sig_icon(s):
        s = s.upper()
        if "CRISIS" in s or "ARBITRAGE" in s or "SILENT BULL" in s: return "✅"
        if "BEARISH" in s or "LIQUIDITY" in s or "DUMP" in s:       return "⚠️ "
        if "AMBIGUOUS" in s:                                          return "🔵"
        if "NORMAL" in s:                                             return "✅"
        return "  "

    print("╔══════════════════════════════════════════════════════════╗")
    icon = sig_icon(sig)
    verdict_line = f"  {icon} {sig}"
    print(f"║{verdict_line:<58}║")
    score_line   = f"  Score: {score}/8 pts  |  Confidence: {conf}"
    print(f"║{score_line:<58}║")
    regime_line  = f"  Regime: {regime}"
    print(f"║{regime_line:<58}║")
    if is_nt:
        print(f"║{'  🚫 NON-TRADING DAY — score capped at 0':<58}║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    # ── 5-day price changes ───────────────────────────────────────────────────
    print("  5-DAY PRICE CHANGES")
    print(f"  {'Instrument':<14} {'5d Change':>10}")
    print(f"  {'-'*26}")
    for label, key in [("GOLDBEES", "goldbees_5d"), ("COMEX", "comex_5d"),
                        ("DXY", "dxy_5d"), ("USDINR", "usdinr_5d"), ("Nifty50", "nifty_5d")]:
        val = pchg.get(key)
        if val is not None:
            arrow = "↑" if val > 0 else ("↓" if val < 0 else "→")
            print(f"  {label:<14} {val:>+9.2f}%  {arrow}")
        else:
            print(f"  {label:<14} {'N/A':>10}")
    print()

    # ── Correlation table ─────────────────────────────────────────────────────
    icons = {"NORMAL": "🟢", "WARNING": "🟡", "BREAK": "🔴", "DATA_UNAVAILABLE": "⬛"}
    print("  CORRELATION MONITOR (20-day rolling Pearson)")
    print(f"  {'Pair':<22} {'20d':>7}  {'10d':>7}  {'Normal Band':<16}  Status")
    print(f"  {'-'*72}")

    for k, v in corrs.items():
        c20   = f"{v['corr']:+.3f}"  if v['corr']          is not None else "  N/A "
        c10   = f"{v['corr_10d']:+.3f}" if v.get('corr_10d') is not None else "  N/A "
        nb    = v.get('normal_band', '')
        ico   = icons.get(v['status'], "❓")
        stat  = v['status'].replace("_", " ")
        print(f"  {v['pair']:<22} {c20:>7}  {c10:>7}  {nb:<16}  {ico} {stat}")

    if n_avail < 4:
        missing_corrs = [k for k, v in corrs.items() if v.get("status") == "DATA_UNAVAILABLE"]
        print(f"\n  ⚠️  {4 - n_avail} correlation(s) unavailable: {', '.join(missing_corrs).upper()}")

    print()

    # ── Break details ─────────────────────────────────────────────────────────
    if breaks:
        print(f"  BREAKS DETECTED: {len(breaks)}")
        print(f"  {'-'*60}")
        for b in breaks:
            impl_icon = {"BULLISH": "↑", "BEARISH": "↓", "AMBIGUOUS": "?"}.get(b['implication'], " ")
            print(f"  [{impl_icon} {b['implication']:9}] {b['pair'].upper()}")
            # Word-wrap the note
            note = b['note']
            while len(note) > 58:
                print(f"    {note[:58]}")
                note = note[58:]
            print(f"    {note}")
            print()
    else:
        print("  ✅ No correlation breaks detected — all relationships normal.\n")

    # ── Compound alerts ───────────────────────────────────────────────────────
    if alerts:
        print(f"  {'='*58}")
        print(f"  COMPOUND ALERT{'S' if len(alerts)>1 else ''} ({len(alerts)} detected)")
        print(f"  {'='*58}")
        for a in alerts:
            print(f"\n  {a['emoji']}  TYPE {a['type']} — {a['label']}  [{a['severity']}]")
            msg = a['message']
            while len(msg) > 58:
                print(f"     {msg[:58]}")
                msg = msg[58:]
            print(f"     {msg}")
        print()
    else:
        print("  No compound alerts triggered.\n")

    # ── Data availability ─────────────────────────────────────────────────────
    ok_list   = [k.upper() for k, v in avail.items() if v]
    fail_list = [k.upper() for k, v in avail.items() if not v]
    print(f"  Data: ✅ {', '.join(ok_list)}", end="")
    if fail_list:
        print(f"  |  ❌ {', '.join(fail_list)}", end="")
    print()

    print()
    print(f"  ℹ️  Signal 12 contributes up to 8 pts to the composite score.")
    print(f"     Penalty: -5 pts applied when 2+ correlations break BEARISHLY.")
    print(f"     Run Signal 08 for the full composite verdict.")
    print()

    # Exit code
    if breaks and result.get("overall_implication") == "BEARISH":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
