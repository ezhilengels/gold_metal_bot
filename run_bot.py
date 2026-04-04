#!/usr/bin/env python3
# =============================================================================
# GOLD BOT — run_bot.py
# Master Runner + Scheduler
#
# USAGE
# ─────
#   python3 run_bot.py                  Run once immediately (bypass time check)
#   python3 run_bot.py --schedule       Loop mode: fire daily at bot_run_time_ist
#   python3 run_bot.py --force          Run once, skip trading day / holiday check
#   python3 run_bot.py --dry-run        Run signals but skip Telegram and history write
#   python3 run_bot.py --open           Open dashboard.html in browser after run
#   python3 run_bot.py --schedule --open  Loop mode + auto-open dashboard each run
#
# SCHEDULING
# ──────────
#   --schedule mode checks every 60 seconds. When the clock matches
#   bot_run_time_ist AND today is a configured trading day AND not a
#   market holiday, it fires run_signal_08() automatically.
#
#   To run at startup / cron:
#     crontab entry (fires at 9:15 IST = 3:45 UTC):
#       45 3 * * 1-5  cd /path/to/gold_bot && python3 run_bot.py --force >> logs/cron.log 2>&1
#
#   Windows Task Scheduler: create a task pointing to run_bot.py with
#   --force flag, triggered at 9:15 AM IST on weekdays.
#
# RUN HISTORY
# ───────────
#   Every successful run appends a record to run_history.json:
#   { "ts", "signal", "score", "confidence", "entry_price", "s12_regime" }
#   View history with:  python3 bot_status.py
# =============================================================================

import os
import sys
import json
import time
import logging
import argparse
import webbrowser
from datetime import datetime, timezone, timedelta
from typing import Optional

# ── Path setup ─────────────────────────────────────────────────────────────────
BOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BOT_DIR)

from config import CONFIG

# ── Logging ────────────────────────────────────────────────────────────────────
os.makedirs(CONFIG["log_directory"], exist_ok=True)
_log_path = os.path.join(
    CONFIG["log_directory"],
    f"run_bot_{datetime.now().strftime('%Y-%m-%d')}.log"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [RUN_BOT] %(message)s",
    handlers=[
        logging.FileHandler(_log_path),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("run_bot")

# ── ANSI colours (auto-disabled on Windows without ANSI support) ───────────────
_USE_COLOR = sys.stdout.isatty() and os.name != "nt"

def _c(code: str, text: str) -> str:
    if not _USE_COLOR:
        return text
    CODES = {
        "green":  "\033[92m", "yellow": "\033[93m",
        "red":    "\033[91m", "cyan":   "\033[96m",
        "bold":   "\033[1m",  "dim":    "\033[2m",
        "reset":  "\033[0m",
    }
    return f"{CODES.get(code,'')}{text}{CODES['reset']}"


# =============================================================================
# IST CLOCK  (no pytz dependency — use UTC + 5:30 offset)
# =============================================================================

IST = timezone(timedelta(hours=5, minutes=30))

def _now_ist() -> datetime:
    """Current time in IST."""
    return datetime.now(tz=IST)

def _ist_hhmm(dt: datetime) -> str:
    return dt.strftime("%H:%M")

def _parse_run_time(hhmm: str) -> tuple[int, int]:
    """Parse 'HH:MM' → (hour, minute)."""
    try:
        h, m = hhmm.split(":")
        return int(h), int(m)
    except Exception:
        log.warning(f"Invalid bot_run_time_ist '{hhmm}' — defaulting to 09:15")
        return 9, 15


# =============================================================================
# TRADING DAY CHECK
# =============================================================================

def is_trading_day(dt: Optional[datetime] = None) -> tuple[bool, str]:
    """
    Returns (is_trading, reason).
    Checks:
      1. Day of week — only CONFIG['bot_run_days'] are trading days
      2. NSE market holiday list from CONFIG['market_holidays']
    """
    if dt is None:
        dt = _now_ist()

    dow      = dt.weekday()   # 0=Mon … 6=Sun
    date_str = dt.strftime("%Y-%m-%d")

    run_days  = CONFIG.get("bot_run_days", [0, 1, 2, 3])
    holidays  = CONFIG.get("market_holidays", [])

    if dow not in run_days:
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        return False, f"{day_names[dow]} is not a configured trading day (bot_run_days: Mon–Thu)"

    if date_str in holidays:
        return False, f"{date_str} is an NSE market holiday"

    return True, "Trading day — OK"


# =============================================================================
# RUN HISTORY  (append-only JSON log)
# =============================================================================

def _load_history() -> list:
    path = os.path.join(BOT_DIR, CONFIG.get("run_history_path", "./run_history.json"))
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []
    return []


def _save_history(records: list) -> None:
    path = os.path.join(BOT_DIR, CONFIG.get("run_history_path", "./run_history.json"))
    max_entries = CONFIG.get("max_run_history_entries", 90)
    # Trim to last N entries
    records = records[-max_entries:]
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log.error(f"Could not save run history: {e}")


def _append_run_record(result: dict) -> None:
    """Append a summary of this run to run_history.json."""
    record = {
        "ts":           result.get("timestamp", _now_ist().strftime("%Y-%m-%d %H:%M:%S")),
        "signal":       result.get("signal", ""),
        "score":        result.get("final_score", 0),
        "confidence":   result.get("confidence", ""),
        "entry_price":  result.get("entry_price"),
        "target_price": result.get("target_price"),
        "stop_price":   result.get("stop_price"),
        "s07_penalty":  result.get("s07_penalty", 0),
        "s12_regime":   result.get("s12_result", {}).get("regime", ""),
        "blocked":      "BLOCKED" in result.get("signal", "").upper(),
    }
    history = _load_history()
    history.append(record)
    _save_history(history)
    log.info(f"Run record saved to run_history.json ({len(history)} total entries)")


# =============================================================================
# DASHBOARD WRITER  (safe import)
# =============================================================================

def _write_dashboard(result: dict) -> Optional[str]:
    """Write dashboard.html. Returns path on success, None on failure."""
    try:
        from dashboard_writer import write_dashboard
        out_path = os.path.join(BOT_DIR, CONFIG.get("dashboard_output_path", "./dashboard.html"))
        path = write_dashboard(result, config=CONFIG, output_path=out_path)
        log.info(f"Dashboard written → {path}")
        return path
    except Exception as e:
        log.error(f"Dashboard write failed: {e}")
        return None


# =============================================================================
# PRINT HELPERS
# =============================================================================

W = 68

def _banner(text: str) -> None:
    line = "═" * W
    print(f"\n╔{line}╗")
    print(f"║  {_c('bold', text):<{W-2}}║")
    print(f"╚{line}╝")

def _row(label: str, value: str, color: str = "") -> None:
    val = _c(color, value) if color else value
    print(f"  {label:<22} {val}")

def _sep() -> None:
    print(f"  {'─' * (W - 2)}")

def _print_run_summary(result: dict, elapsed: float) -> None:
    signal   = result.get("signal", "")
    score    = result.get("final_score", 0)
    conf     = result.get("confidence", "")
    entry    = result.get("entry_price")
    target   = result.get("target_price")
    stop_p   = result.get("stop_price")
    ts       = result.get("timestamp", "")
    s12_r    = result.get("s12_result", {})
    regime   = s12_r.get("regime", "")

    # Signal colour
    sig_up = signal.upper()
    if "STRONG BUY" in sig_up:    sig_col = "green"
    elif "BUY" in sig_up:         sig_col = "green"
    elif "WATCH" in sig_up:       sig_col = "yellow"
    elif "BLOCKED" in sig_up:     sig_col = "red"
    elif "DO NOT" in sig_up:      sig_col = "red"
    else:                          sig_col = "yellow"

    # Score bar
    pct    = min(score / 95.0, 1.0)
    filled = int(pct * 30)
    bar    = "█" * filled + "░" * (30 - filled)

    _banner("GOLD BOT — RUN COMPLETE")
    _row("Timestamp:",    ts)
    _row("Verdict:",      signal, sig_col)
    _row("Score:",        f"{score:.1f} / 95  [{bar}]")
    _row("Confidence:",   conf)
    if "BLOCKED" not in sig_up:
        _row("S12 Regime:", regime if regime else "—")
    if entry and "BUY" in sig_up:
        _sep()
        _row("Entry Price:",  f"₹{entry}")
        _row("Target (+3%):", f"₹{target}", "green")
        _row("Stop  (-1%):",  f"₹{stop_p}",  "red")
    _sep()
    _row("Run time:",     f"{elapsed:.1f}s")
    print()


# =============================================================================
# CORE RUN FUNCTION
# =============================================================================

def run_once(dry_run: bool = False, open_browser: bool = False) -> dict:
    """
    Execute a single full bot run:
      1. Import and run signal_08_verdict_score.run_signal_08()
      2. Write dashboard.html
      3. Append to run_history.json (unless --dry-run)
      4. Open browser if requested

    Returns the Signal 08 result dict.
    """
    t_start = time.time()
    log.info("─" * 60)
    log.info("BOT RUN — START")
    log.info(f"dry_run={dry_run}  open_browser={open_browser}")

    # ── Load and run Signal 08 ─────────────────────────────────────────────
    try:
        from signal_08_verdict_score import run_signal_08
    except ImportError as e:
        log.error(f"Cannot import run_signal_08: {e}")
        print(_c("red", f"\n❌ FATAL: Cannot import signal_08_verdict_score.py\n   {e}"))
        sys.exit(2)

    result = run_signal_08()

    elapsed = round(time.time() - t_start, 1)

    # ── Write dashboard ────────────────────────────────────────────────────
    dash_path = _write_dashboard(result)

    # ── Save run history ───────────────────────────────────────────────────
    if not dry_run:
        _append_run_record(result)
    else:
        log.info("--dry-run: run history not saved")

    # ── Print summary ──────────────────────────────────────────────────────
    _print_run_summary(result, elapsed)

    if dash_path:
        print(f"  📊 Dashboard → {dash_path}")

    hist = _load_history()
    if hist and not dry_run:
        _wins = sum(1 for r in hist if "BUY" in r.get("signal", "").upper()
                    and "BLOCKED" not in r.get("signal", "").upper())
        print(f"  📁 Run #{len(hist)} recorded  "
              f"({_wins} BUY signals in last {len(hist)} runs)")

    # ── Open browser ───────────────────────────────────────────────────────
    should_open = open_browser or CONFIG.get("auto_open_dashboard", False)
    if should_open and dash_path:
        try:
            webbrowser.open(f"file://{os.path.abspath(dash_path)}")
            log.info("Dashboard opened in default browser")
        except Exception as e:
            log.warning(f"Could not open browser: {e}")

    log.info(f"BOT RUN — END  ({elapsed}s)")
    return result


# =============================================================================
# SCHEDULER LOOP
# =============================================================================

def run_schedule(dry_run: bool = False, open_browser: bool = False) -> None:
    """
    Persistent scheduler loop.
    Wakes every 60 seconds, fires run_once() when:
      • Current IST time matches bot_run_time_ist (within the same minute)
      • Today is a configured trading day (Mon–Thu by default)
      • Today is not an NSE market holiday
    """
    run_h, run_m = _parse_run_time(CONFIG.get("bot_run_time_ist", "09:15"))
    run_days     = CONFIG.get("bot_run_days", [0, 1, 2, 3])
    day_names    = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    days_str     = "/".join(day_names[d] for d in run_days)

    _banner("GOLD BOT — SCHEDULER STARTED")
    print(f"  Fire time  : {run_h:02d}:{run_m:02d} IST")
    print(f"  Trading days : {days_str}")
    print(f"  Dry run    : {dry_run}")
    print(f"  Auto-open  : {open_browser or CONFIG.get('auto_open_dashboard', False)}")
    print(f"\n  Press Ctrl+C to stop.\n")

    fired_today: Optional[str] = None   # date string of last fire, prevents double-fire

    while True:
        try:
            now = _now_ist()
            today_str = now.strftime("%Y-%m-%d")

            # Fire condition: correct hour:minute and not already fired today
            if now.hour == run_h and now.minute == run_m and fired_today != today_str:
                tradable, reason = is_trading_day(now)

                if tradable:
                    print(_c("cyan", f"\n⏰  {now.strftime('%Y-%m-%d %H:%M')} IST — FIRING BOT RUN"))
                    log.info(f"Scheduler: firing run at {now.strftime('%H:%M')} IST")
                    run_once(dry_run=dry_run, open_browser=open_browser)
                    fired_today = today_str
                else:
                    log.info(f"Scheduler: skipping run — {reason}")
                    print(_c("dim", f"  [{now.strftime('%H:%M')}] Skipped: {reason}"))
                    fired_today = today_str  # Mark so we don't spam this every minute

            else:
                # Heartbeat every 10 minutes so user knows it's alive
                if now.minute % 10 == 0 and now.second < 5:
                    next_run = now.replace(hour=run_h, minute=run_m, second=0, microsecond=0)
                    if next_run <= now:
                        next_run += timedelta(days=1)
                    delta = int((next_run - now).total_seconds() / 60)
                    print(_c("dim",
                        f"  [{now.strftime('%H:%M')}] Waiting… next run in ~{delta}min "
                        f"({next_run.strftime('%Y-%m-%d %H:%M')} IST)"
                    ))

            time.sleep(60)

        except KeyboardInterrupt:
            print(_c("yellow", "\n\n  Scheduler stopped by user. Goodbye.\n"))
            log.info("Scheduler stopped by KeyboardInterrupt")
            break
        except Exception as e:
            log.error(f"Scheduler loop error: {e}", exc_info=True)
            print(_c("red", f"  ⚠ Scheduler error: {e} — retrying in 60s"))
            time.sleep(60)


# =============================================================================
# NEXT FIRE INFO  (print when not scheduling)
# =============================================================================

def _print_next_fire_info() -> None:
    """Print when the next scheduled run would fire."""
    now      = _now_ist()
    run_h, run_m = _parse_run_time(CONFIG.get("bot_run_time_ist", "09:15"))
    holidays = CONFIG.get("market_holidays", [])
    run_days = CONFIG.get("bot_run_days", [0, 1, 2, 3])

    # Walk forward up to 10 days to find next trading day
    candidate = now.replace(hour=run_h, minute=run_m, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)

    for _ in range(14):
        if candidate.weekday() in run_days and candidate.strftime("%Y-%m-%d") not in holidays:
            delta_min = int((candidate - now).total_seconds() / 60)
            delta_h   = delta_min // 60
            delta_m   = delta_min % 60
            print(f"  ⏰  Next scheduled run: "
                  f"{_c('cyan', candidate.strftime('%Y-%m-%d %H:%M IST'))} "
                  f"(in {delta_h}h {delta_m}m)")
            break
        candidate += timedelta(days=1)


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gold Bot — Master Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 run_bot.py                   Run once now (respects time/day config)
  python3 run_bot.py --force           Run once now, bypass trading-day check
  python3 run_bot.py --dry-run         Run signals, skip Telegram + history
  python3 run_bot.py --open            Run + open dashboard in browser
  python3 run_bot.py --schedule        Start scheduler loop (fires at 09:15 IST)
  python3 run_bot.py --schedule --open Scheduler + auto-open dashboard each run
        """,
    )
    parser.add_argument("--schedule",  action="store_true",
                        help="Run in loop mode — fires daily at bot_run_time_ist")
    parser.add_argument("--force",     action="store_true",
                        help="Skip trading-day and holiday checks")
    parser.add_argument("--dry-run",   action="store_true",
                        help="Run signals but skip Telegram and history write")
    parser.add_argument("--open",      action="store_true",
                        help="Open dashboard.html in browser after run")
    args = parser.parse_args()

    # ── Scheduler mode ─────────────────────────────────────────────────────
    if args.schedule:
        run_schedule(dry_run=args.dry_run, open_browser=args.open)
        return

    # ── Single run ─────────────────────────────────────────────────────────
    now = _now_ist()
    print(f"\n  Gold Bot  ·  {_c('cyan', now.strftime('%Y-%m-%d %H:%M IST'))}")
    _print_next_fire_info()

    if not args.force:
        tradable, reason = is_trading_day(now)
        if not tradable:
            print(_c("yellow", f"\n  ⚠  {reason}"))
            print(  "     Signals still run — use --force to suppress this warning.\n")
            # We still run, but let user know. S06 will handle the verdict cap.

    run_once(dry_run=args.dry_run, open_browser=args.open)


if __name__ == "__main__":
    main()
