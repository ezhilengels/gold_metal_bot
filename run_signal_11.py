#!/usr/bin/env python3
# =============================================================================
# GOLD BOT — run_signal_11.py
# Launcher for Signal 11: ML Backtester
#
# Usage:
#   python3 run_signal_11.py            # Full backtest (fetches 4 years of data)
#   python3 run_signal_11.py --quick    # Quick run (2 years, faster)
#   python3 run_signal_11.py --open     # Auto-open HTML report in browser after run
#
# Runtime estimate:
#   Full run  : ~3–6 minutes (data fetch + feature reconstruction + ML)
#   Quick run : ~1–2 minutes (2 years of data)
#
# Output:
#   gold_bot/backtest_results/backtest_YYYY_MM.html  ← dated HTML report
#   gold_bot/backtest_results/backtest_latest.html   ← always the latest
#   gold_bot/backtest_results/backtest_YYYY_MM.txt   ← text version
#
# When to run:
#   • Monthly (last Saturday) — review weight adjustment suggestions
#   • After 10 new live trades — check if win rate is holding
#   • Any time you want to validate the strategy
#
# IMPORTANT:
#   This does NOT change any weights automatically.
#   Review the report and edit config.py manually if you agree with suggestions.
# =============================================================================

import os
import sys
import time
import argparse
import webbrowser
from datetime import datetime

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Config warnings ───────────────────────────────────────────────────────────
def check_config_warnings():
    try:
        from config import CONFIG
        warnings = []
        if not CONFIG.get("fred_api_key") or "YOUR" in str(CONFIG.get("fred_api_key", "")):
            warnings.append(
                "  ⚠️  FRED API key not set — S02/S05 macro factors will be SKIPPED.\n"
                "     Get a free key at: https://fred.stlouisfed.org/docs/api/api_key.html\n"
                "     Set it in config.py → fred_api_key"
            )
        if warnings:
            print("\n" + "─" * 60)
            print("CONFIG WARNINGS (backtester will still run with reduced data):")
            for w in warnings:
                print(w)
            print("─" * 60 + "\n")
    except ImportError:
        pass


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Gold Bot — Signal 11 ML Backtester",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 run_signal_11.py              Full 4-year backtest
  python3 run_signal_11.py --quick      Faster 2-year backtest
  python3 run_signal_11.py --open       Run and auto-open HTML report
        """
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="Use 2 years of history instead of 4 (faster, less data)"
    )
    parser.add_argument(
        "--open", action="store_true",
        help="Auto-open HTML report in browser after run"
    )
    args = parser.parse_args()

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║   🧪  GOLD BOT — ML BACKTESTER (Signal 11)              ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  Started : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Mode    : {'QUICK (2 years)' if args.quick else 'FULL (4 years)'}")
    print()

    check_config_warnings()

    # ── Override HISTORY_YEARS if quick mode ──────────────────────────────────
    if args.quick:
        import signal_11_ml_backtester as s11
        s11.HISTORY_YEARS = 2
        print("  [QUICK MODE] Using 2 years of history.\n")

    print("  This may take 3–6 minutes. Please wait...\n")
    print("  Steps:")
    print("    1/8  Fetching GOLDBEES historical data")
    print("    2/8  Fetching COMEX, DXY, USDINR, FRED data")
    print("    3/8  Building feature matrix (reconstructing all signals)")
    print("    4/8  Labelling trade outcomes (WIN / STOP / TIMEOUT)")
    print("    5/8  Running Threshold Optimizer")
    print("    6/8  Running Logistic Regression")
    print("    7/8  Running Walk-Forward Validation")
    print("    8/8  Generating HTML + text reports")
    print()

    t_start = time.time()

    try:
        from signal_11_ml_backtester import run_signal_11
        result = run_signal_11()
    except Exception as e:
        print(f"\n  ❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)

    elapsed = round(time.time() - t_start, 1)

    # ── Handle result ─────────────────────────────────────────────────────────
    status = result.get("status", "UNKNOWN")

    if status == "DATA_UNAVAILABLE":
        print("╔══════════════════════════════════════════════════════════╗")
        print("║  ⚠️   DATA UNAVAILABLE                                   ║")
        print("╚══════════════════════════════════════════════════════════╝")
        print(f"  Error: {result.get('error', 'Unknown')}")
        print()
        print("  Possible causes:")
        print("    • No internet connection")
        print("    • yfinance rate limit — try again in a few minutes")
        print("    • GOLDBEES.NS ticker unavailable on Yahoo Finance")
        sys.exit(2)

    if status == "INSUFFICIENT_DATA":
        print("╔══════════════════════════════════════════════════════════╗")
        print("║  ⚠️   INSUFFICIENT DATA                                  ║")
        print("╚══════════════════════════════════════════════════════════╝")
        print(f"  Error: {result.get('error', 'Unknown')}")
        print()
        print("  Try running in FULL mode (without --quick) for more data.")
        sys.exit(2)

    if status != "OK":
        print(f"  ❌ Unexpected status: {status}")
        print(f"  Error: {result.get('error', 'Unknown')}")
        sys.exit(2)

    # ── Print text report ─────────────────────────────────────────────────────
    print()
    print(result.get("text_report", "No text report generated."))

    # ── Summary banner ────────────────────────────────────────────────────────
    wf      = result.get("wf_results", {})
    thr     = result.get("threshold_results", {})
    ds      = result.get("data_summary", {})
    avg_wr  = wf.get("avg_win_rate", 0)
    best_t  = thr.get("best_threshold", 45)
    best_wr = thr.get("best_win_rate", 0)
    rows    = ds.get("total_rows", 0)

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  ✅  BACKTEST COMPLETE                                   ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print(f"║  Runtime            : {elapsed}s{' ' * (25 - len(str(elapsed)))}║")
    print(f"║  Rows analysed      : {rows}{' ' * (25 - len(str(rows)))}║")
    print(f"║  Walk-fwd win rate  : {avg_wr}%{' ' * (24 - len(str(avg_wr)))}║")
    print(f"║  Optimal threshold  : {best_t}/95  ({best_wr:.0f}% win rate){' ' * max(0, 13 - len(str(best_t)) - len(f'{best_wr:.0f}'))}║")
    print("╠══════════════════════════════════════════════════════════╣")

    html_path = result.get("report_latest_path", "")
    if html_path and os.path.exists(html_path):
        print(f"║  📄 HTML Report saved                                    ║")
        print(f"║  {html_path[:55]:<55}║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    # ── Threshold recommendation ──────────────────────────────────────────────
    if best_t != 45:
        direction = "RAISE" if best_t > 45 else "LOWER"
        print(f"  💡 SUGGESTION: {direction} composite score threshold to {best_t}/95")
        print(f"     Current: 45/95 | Optimal: {best_t}/95 | Win rate gain: "
              f"+{max(0, best_wr - (thr.get('current_threshold_stats', {}).get('win_rate', best_wr))):.1f}%")
        print()
        print("  To apply: edit config.py and update the threshold comments,")
        print("  then adjust Signal 08 threshold constants accordingly.")
        print("  NOTE: Do not change anything automatically — human review required.")
    else:
        print("  ✅ Current threshold (45/95) is already optimal. No changes needed.")

    print()

    # ── Auto-open HTML report ─────────────────────────────────────────────────
    if args.open or True:   # Always open HTML report for easy review
        if html_path and os.path.exists(html_path):
            try:
                webbrowser.open(f"file://{os.path.abspath(html_path)}")
                print(f"  🌐 HTML report opened in browser.")
            except Exception:
                print(f"  ℹ️  Open manually: {html_path}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
