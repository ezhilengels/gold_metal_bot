#!/usr/bin/env python3
# =============================================================================
# GOLD BOT — bot_status.py
# Run History Viewer
#
# USAGE
# ─────
#   python3 bot_status.py            Show last 10 runs
#   python3 bot_status.py --all      Show all runs
#   python3 bot_status.py --n 20     Show last N runs
#   python3 bot_status.py --summary  Show performance summary only
#   python3 bot_status.py --clear    Clear run history (asks for confirmation)
#
# Run history is stored in run_history.json (see config.py → run_history_path)
# =============================================================================

import os
import sys
import json
import argparse
from datetime import datetime

BOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BOT_DIR)

from config import CONFIG

# ── ANSI colours ──────────────────────────────────────────────────────────────
_USE_COLOR = sys.stdout.isatty()

def _c(code: str, text: str) -> str:
    if not _USE_COLOR:
        return text
    CODES = {
        "green":  "\033[92m", "yellow": "\033[93m", "red":   "\033[91m",
        "cyan":   "\033[96m", "dim":    "\033[2m",  "bold":  "\033[1m",
        "reset":  "\033[0m",
    }
    return f"{CODES.get(code,'')}{text}{CODES['reset']}"


# =============================================================================
# LOAD HISTORY
# =============================================================================

def load_history() -> list:
    path = os.path.join(BOT_DIR, CONFIG.get("run_history_path", "./run_history.json"))
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"  Error reading run_history.json: {e}")
        return []


def save_history(records: list) -> None:
    path = os.path.join(BOT_DIR, CONFIG.get("run_history_path", "./run_history.json"))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)


# =============================================================================
# SIGNAL → DISPLAY HELPERS
# =============================================================================

def _signal_icon(signal: str) -> str:
    s = signal.upper()
    if "STRONG BUY" in s: return "🟢🟢"
    if "BUY"        in s and "BLOCKED" not in s: return "🟢"
    if "WATCH"      in s: return "🟡"
    if "WAIT"       in s: return "🟡"
    if "BLOCKED"    in s or "AVOID" in s: return "🚫"
    if "DO NOT"     in s: return "🔴"
    if "NON-TRADING" in s: return "⏸"
    return "⬛"

def _signal_color(signal: str) -> str:
    s = signal.upper()
    if "STRONG BUY" in s: return "green"
    if "BUY"        in s and "BLOCKED" not in s: return "green"
    if "WATCH"      in s or "WAIT" in s: return "yellow"
    if "BLOCKED"    in s or "DO NOT" in s: return "red"
    return "dim"

def _score_bar(score: float, width: int = 20) -> str:
    pct    = min(max(score, 0) / 95.0, 1.0)
    filled = int(pct * width)
    return "█" * filled + "░" * (width - filled)

def _is_buy(signal: str) -> bool:
    s = signal.upper()
    return ("BUY" in s) and ("BLOCKED" not in s) and ("DO NOT" not in s)


# =============================================================================
# DISPLAY FUNCTIONS
# =============================================================================

W = 70

def print_run_table(records: list) -> None:
    """Print a table of run records — one row per run."""
    if not records:
        print("  No run history found.")
        return

    # Header
    print(f"\n  {'#':<4} {'Date/Time':<20} {'Signal':<22} {'Score':>6} {'Entry':>8} {'S12 Regime':<18}")
    print(f"  {'─'*4} {'─'*20} {'─'*22} {'─'*6} {'─'*8} {'─'*18}")

    for i, r in enumerate(records, 1):
        ts      = r.get("ts", "—")[:19]
        signal  = r.get("signal", "—")
        score   = r.get("score", 0)
        entry   = r.get("entry_price")
        regime  = r.get("s12_regime", "—") or "—"
        blocked = r.get("blocked", False)

        icon    = _signal_icon(signal)
        col     = _signal_color(signal)

        # Truncate long signal names for table
        sig_short = signal.replace(" 🟢", "").replace(" 🔴", "").replace(" 🟡", "")
        sig_short = sig_short[:20]

        entry_str = f"₹{entry}" if entry else "—"
        score_str = f"{score:.1f}"

        row = (f"  {i:<4} {ts:<20} "
               f"{icon} {_c(col, sig_short):<20} "
               f"{score_str:>6} {entry_str:>8} {regime:<18}")
        print(row)

    print()


def print_summary(records: list) -> None:
    """Print overall performance statistics."""
    if not records:
        print("  No run history found.")
        return

    total     = len(records)
    buys      = [r for r in records if _is_buy(r.get("signal", ""))]
    strong    = [r for r in records if "STRONG BUY" in r.get("signal", "").upper()]
    watches   = [r for r in records if "WATCH" in r.get("signal", "").upper()]
    blocked   = [r for r in records if r.get("blocked", False)]
    avg_score = sum(r.get("score", 0) for r in records) / total if total else 0

    # Date range
    first_ts  = records[0].get("ts", "")[:10]
    last_ts   = records[-1].get("ts", "")[:10]

    # Score distribution
    scores = [r.get("score", 0) for r in records]
    max_s  = max(scores) if scores else 0
    min_s  = min(scores) if scores else 0

    # S12 regimes
    regimes: dict[str, int] = {}
    for r in records:
        reg = r.get("s12_regime", "—") or "—"
        regimes[reg] = regimes.get(reg, 0) + 1
    top_regimes = sorted(regimes.items(), key=lambda x: -x[1])[:4]

    line = "═" * W
    print(f"\n╔{line}╗")
    print(f"║  {'GOLD BOT — PERFORMANCE SUMMARY':<{W}}║")
    print(f"╠{line}╣")

    def row(label, value, color=""):
        val = _c(color, str(value)) if color else str(value)
        print(f"║  {label:<30} {val:<{W-32}}║")

    def sep():
        print(f"╠{line}╣")

    row("Period",            f"{first_ts}  →  {last_ts}")
    row("Total runs",        f"{total}")
    sep()
    row("BUY signals",       f"{len(buys)}  ({len(buys)/total*100:.0f}%)",
        "green" if buys else "dim")
    row("  of which STRONG BUY", f"{len(strong)}", "green" if strong else "dim")
    row("WATCH signals",     f"{len(watches)}", "yellow" if watches else "dim")
    row("BLOCKED (AVOID)",   f"{len(blocked)}", "red" if blocked else "dim")
    sep()
    row("Average score",     f"{avg_score:.1f} / 95")
    row("Highest score",     f"{max_s:.1f} / 95", "green")
    row("Lowest score",      f"{min_s:.1f} / 95", "red" if min_s < 15 else "")
    row("Score bar (avg)",   f"[{_score_bar(avg_score)}]")
    sep()
    row("S12 Correlation Regimes (top 4)", "")
    for reg, cnt in top_regimes:
        row(f"  {reg[:28]}", f"{cnt} runs  ({cnt/total*100:.0f}%)")

    print(f"╚{line}╝\n")


# =============================================================================
# CLI
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gold Bot — Run History Viewer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 bot_status.py              Last 10 runs (table + summary)
  python3 bot_status.py --all        All runs
  python3 bot_status.py --n 20       Last 20 runs
  python3 bot_status.py --summary    Summary stats only
  python3 bot_status.py --clear      Clear run history
        """,
    )
    parser.add_argument("--all",     action="store_true",   help="Show all runs")
    parser.add_argument("--n",       type=int, default=10,  help="Number of recent runs to show")
    parser.add_argument("--summary", action="store_true",   help="Summary stats only")
    parser.add_argument("--clear",   action="store_true",   help="Clear run history")
    args = parser.parse_args()

    history = load_history()

    if not history:
        print(_c("yellow", "\n  No run history found."))
        print("  Run the bot at least once: python3 run_bot.py\n")
        return

    if args.clear:
        confirm = input(f"  Clear {len(history)} run records? (yes/no): ").strip().lower()
        if confirm == "yes":
            save_history([])
            print(_c("green", "  ✅ Run history cleared."))
        else:
            print("  Aborted.")
        return

    if args.summary:
        print_summary(history)
        return

    # Default: show last N records + summary
    n = len(history) if args.all else args.n
    subset = history[-n:]

    print(f"\n  Showing last {len(subset)} of {len(history)} total runs")
    print_run_table(subset)
    print_summary(history)  # always show full summary


if __name__ == "__main__":
    main()
