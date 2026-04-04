# =============================================================================
# GOLD BOT — signal_03_seasonality.py
# Signal 03: Seasonality Play (India Specific)
#
# PURPOSE    : Identify which seasonal phase Indian gold demand is in.
# INPUTS     : System date ONLY — no external API calls whatsoever.
# FAILURE    : System date error → "SYSTEM DATE ERROR". Any unexpected exception
#              → "DATA UNAVAILABLE". NEVER assume or estimate.
# INDEPENDENCE: 100% standalone — shares NO data or logic with any other signal.
#
# SEASON LOGIC (India Gold Demand Cycle):
#   Jan       → POST_HOLIDAY_LULL         (Low demand)
#   Feb       → PRE_WEDDING_EARLY         (Rising demand)
#   Mar 1–15  → WEDDING_SEASON_START      (High demand)
#   Mar 16–31 → WEDDING_SEASON_PEAK       (Very high)
#   Apr       → AKSHAYA_TRITIYA_BUILDUP   (Very high)
#   May 1–15  → AKSHAYA_TRITIYA_PEAK      (Peak demand)
#   May 16–31 → POST_TRITIYA_DECLINE      (Falling)
#   Jun       → SUMMER_LULL               (Low)
#   Jul       → MONSOON_LULL              (Low)
#   Aug 1–20  → MONSOON_LULL              (Low)
#   Aug 21–31 → PRE_FESTIVE_EARLY         (Recovering)
#   Sep       → PRE_NAVRATRI_WARMUP       (Recovering)
#   Oct 1–15  → NAVRATRI_DUSSEHRA         (High)
#   Oct 16–31 → DHANTERAS_APPROACH        (Very high)
#   Nov 1–15  → DHANTERAS_DIWALI_PEAK     (Peak)
#   Nov 16–30 → POST_DIWALI_WEDDING       (High)
#   Dec 1–20  → WINTER_WEDDING_SEASON     (High)
#   Dec 21–31 → YEAR_END_HOLIDAY          (Falling)
#
# SIGNAL CATEGORIES:
#   ACCUMULATE       → demand lull, prices soft → 4 pts (buy zone)
#   BUY / BUILD      → demand rising, buy before crowd → 5 pts
#   HOLD / SELL TARGET → peak demand, exit existing positions → 1 pt
#   NEUTRAL / WATCH  → transition, follow other signals → 2 pts
#
# SCORING (for signal_08):
#   score field: 0–5  (used directly by signal_08 scorer, max 5 pts)
# =============================================================================

import os
import sys
import logging
from datetime import datetime, date, timedelta
from typing import Optional

# ── Setup ─────────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CONFIG

os.makedirs(CONFIG["log_directory"], exist_ok=True)
log_file = os.path.join(
    CONFIG["log_directory"],
    f"signal03_{datetime.now().strftime('%Y-%m-%d')}.log"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SIGNAL03] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("signal03")


# =============================================================================
# CONSTANTS — UPCOMING FESTIVALS (static calendar, approximate windows)
# days_range = [days_before_month_start, days_after_month_start]
# used to calculate "event approaching within 30 days"
# =============================================================================

UPCOMING_EVENTS = [
    # Akshaya Tritiya: roughly April 20 – May 5 window
    {"name": "Akshaya Tritiya",  "month": 4, "day_start": 20, "approx_range_days": 15},
    # Navratri: roughly Oct 1–10
    {"name": "Navratri",         "month": 10, "day_start": 1,  "approx_range_days": 10},
    # Dussehra: roughly Oct 10–15
    {"name": "Dussehra",         "month": 10, "day_start": 10, "approx_range_days": 5},
    # Dhanteras: roughly Oct 25–Nov 2
    {"name": "Dhanteras",        "month": 10, "day_start": 25, "approx_range_days": 8},
    # Diwali: roughly Nov 1–10
    {"name": "Diwali",           "month": 11, "day_start": 1,  "approx_range_days": 10},
]

MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]


# =============================================================================
# STEP 1 — GET CURRENT DATE
# =============================================================================

def get_current_date() -> Optional[dict]:
    """
    Returns dict with today's date components.
    Returns None if system date cannot be determined.
    """
    try:
        today = date.today()

        # Sanity check — year must be reasonable
        if not (2020 <= today.year <= 2035):
            log.error(f"Suspicious system date: {today} — year out of expected range")
            return None

        return {
            "today":       today,
            "year":        today.year,
            "month":       today.month,
            "day":         today.day,
            "day_of_week": today.weekday(),   # 0=Mon, 6=Sun
            "month_name":  MONTH_NAMES[today.month],
        }

    except Exception as e:
        log.error(f"System date error: {e}")
        return None


# =============================================================================
# STEP 2 — DETERMINE SEASON PHASE
# Exact logic from planning MD, month + day-of-month splits
# =============================================================================

def determine_season_phase(month: int, day: int) -> dict:
    """
    Returns dict with:
      season     — internal season code
      demand     — LOW / RISING / HIGH / VERY_HIGH / PEAK / FALLING / RECOVERING
      description — human readable season name
    """
    if month == 1:
        return {
            "season":      "POST_HOLIDAY_LULL",
            "demand":      "LOW",
            "description": "Post-Holiday Cool Down",
        }

    elif month == 2:
        return {
            "season":      "PRE_WEDDING_EARLY",
            "demand":      "RISING",
            "description": "Pre-Wedding Early Season",
        }

    elif month == 3:
        if day <= 15:
            return {
                "season":      "WEDDING_SEASON_START",
                "demand":      "HIGH",
                "description": "Wedding Season Start",
            }
        else:
            return {
                "season":      "WEDDING_SEASON_PEAK",
                "demand":      "VERY_HIGH",
                "description": "Wedding Season Peak",
            }

    elif month == 4:
        return {
            "season":      "AKSHAYA_TRITIYA_BUILDUP",
            "demand":      "VERY_HIGH",
            "description": "Akshaya Tritiya Build-Up",
            "note":        "Akshaya Tritiya falls in April or May — demand surge imminent",
        }

    elif month == 5:
        if day <= 15:
            return {
                "season":      "AKSHAYA_TRITIYA_PEAK",
                "demand":      "PEAK",
                "description": "Akshaya Tritiya Peak",
            }
        else:
            return {
                "season":      "POST_TRITIYA_DECLINE",
                "demand":      "FALLING",
                "description": "Post-Tritiya Correction",
            }

    elif month == 6:
        return {
            "season":      "SUMMER_LULL",
            "demand":      "LOW",
            "description": "Summer Lull",
        }

    elif month == 7:
        return {
            "season":      "MONSOON_LULL",
            "demand":      "LOW",
            "description": "Monsoon Lull",
        }

    elif month == 8:
        if day <= 20:
            return {
                "season":      "MONSOON_LULL",
                "demand":      "LOW",
                "description": "Monsoon Lull (continues)",
            }
        else:
            return {
                "season":      "PRE_FESTIVE_EARLY",
                "demand":      "RECOVERING",
                "description": "Pre-Festive Early Recovery",
            }

    elif month == 9:
        return {
            "season":      "PRE_NAVRATRI_WARMUP",
            "demand":      "RECOVERING",
            "description": "Pre-Navratri Warm-Up",
        }

    elif month == 10:
        if day <= 15:
            return {
                "season":      "NAVRATRI_DUSSEHRA",
                "demand":      "HIGH",
                "description": "Navratri + Dussehra",
            }
        else:
            return {
                "season":      "DHANTERAS_APPROACH",
                "demand":      "VERY_HIGH",
                "description": "Dhanteras Approach",
            }

    elif month == 11:
        if day <= 15:
            return {
                "season":      "DHANTERAS_DIWALI_PEAK",
                "demand":      "PEAK",
                "description": "Dhanteras + Diwali Peak",
            }
        else:
            return {
                "season":      "POST_DIWALI_WEDDING",
                "demand":      "HIGH",
                "description": "Post-Diwali Wedding Season",
            }

    elif month == 12:
        if day <= 20:
            return {
                "season":      "WINTER_WEDDING_SEASON",
                "demand":      "HIGH",
                "description": "Winter Wedding Season",
            }
        else:
            return {
                "season":      "YEAR_END_HOLIDAY",
                "demand":      "FALLING",
                "description": "Year-End Holiday Lull",
            }

    # Should never reach here — but handle safely
    log.error(f"Unknown month {month} — this should never happen")
    return {
        "season":      "UNKNOWN",
        "demand":      "UNKNOWN",
        "description": "Unknown Season",
    }


# =============================================================================
# STEP 3 — GENERATE SEASON SIGNAL
# Maps season code to actionable signal with score
# =============================================================================

# Season code → (signal_label, action_text, strength_label, score_0_to_5)
SEASON_SIGNAL_MAP = {
    # ── ACCUMULATE PHASES: demand lull → soft prices → buy zone ──────────────
    "MONSOON_LULL": (
        "ACCUMULATE",
        "This is a demand lull — prices may be soft. Good phase to slowly build "
        "position. In monsoon months, even a flat/falling gold price is a gift — "
        "you are buying before the Oct–Nov demand surge.",
        "BUY ZONE",
        4,
    ),
    "SUMMER_LULL": (
        "ACCUMULATE",
        "Summer lull — post-Akshaya Tritiya correction phase. Demand subdued. "
        "Good opportunity to accumulate on dips before festive season recovery.",
        "BUY ZONE",
        4,
    ),
    "POST_HOLIDAY_LULL": (
        "ACCUMULATE",
        "Post-holiday cool down. Demand is low after December festivities. "
        "Soft prices can be used to slowly build position for Feb–Mar wedding season.",
        "BUY ZONE",
        4,
    ),
    "POST_TRITIYA_DECLINE": (
        "ACCUMULATE",
        "Post-Akshaya Tritiya correction — demand falling from peak. "
        "Prices may dip 2–5%. Use the dip to accumulate for the festive season.",
        "BUY ZONE",
        4,
    ),

    # ── BUY / BUILD PHASES: demand rising → buy before the crowd ─────────────
    "PRE_WEDDING_EARLY": (
        "BUY / BUILD",
        "Demand is rising — pre-wedding season early stage. "
        "Good entry before the March peak. Buy dips in this phase.",
        "BUILDING PHASE",
        5,
    ),
    "PRE_NAVRATRI_WARMUP": (
        "BUY / BUILD",
        "Pre-Navratri warm-up — demand recovering from monsoon lull. "
        "Good entry before the Oct–Nov festive surge. Buy dips.",
        "BUILDING PHASE",
        5,
    ),
    "PRE_FESTIVE_EARLY": (
        "BUY / BUILD",
        "Late August pre-festive recovery — demand starting to build. "
        "Excellent phase to enter before Navratri/Dussehra/Diwali demand surge.",
        "BUILDING PHASE",
        5,
    ),
    "AKSHAYA_TRITIYA_BUILDUP": (
        "BUY / BUILD",
        "Akshaya Tritiya build-up — one of the strongest gold demand catalysts in India. "
        "Buy dips in April. Akshaya Tritiya falls in April or May — confirm exact date.",
        "BUILDING PHASE",
        5,
    ),

    # ── HOLD / SELL TARGET PHASES: peak demand → exit existing positions ──────
    "WEDDING_SEASON_PEAK": (
        "HOLD / SELL TARGET",
        "Wedding season peak — if holding a position from accumulation phase, "
        "consider taking 2–4% profit. High demand supports price.",
        "SELL ZONE",
        1,
    ),
    "AKSHAYA_TRITIYA_PEAK": (
        "HOLD / SELL TARGET",
        "Akshaya Tritiya peak demand — prime sell window. "
        "If holding from accumulation, exit with +3–5% target. "
        "Do NOT enter new long positions at this peak.",
        "SELL ZONE",
        1,
    ),
    "NAVRATRI_DUSSEHRA": (
        "HOLD / SELL TARGET",
        "Navratri + Dussehra — high festive demand. "
        "Hold existing positions. Target +2–4% profit. "
        "Avoid new entries at these elevated prices.",
        "SELL ZONE",
        1,
    ),
    "DHANTERAS_DIWALI_PEAK": (
        "HOLD / SELL TARGET",
        "Dhanteras + Diwali peak — strongest demand of the year. "
        "Sell into this strength. Exit all accumulated positions. "
        "Maximum +4–6% profit capture window.",
        "SELL ZONE",
        1,
    ),
    "WINTER_WEDDING_SEASON": (
        "HOLD / SELL TARGET",
        "Winter wedding season — good demand but post-Diwali momentum slowing. "
        "Exit remaining positions. Hold only if carrying profit from accumulation phase.",
        "SELL ZONE",
        1,
    ),

    # ── NEUTRAL / WATCH PHASES: transition → follow other signals ────────────
    "WEDDING_SEASON_START": (
        "NEUTRAL / WATCH",
        "Wedding season start — demand building but not yet at peak. "
        "Watch for a dip entry. Follow other signals (macro, Bollinger) for timing.",
        "NEUTRAL",
        2,
    ),
    "DHANTERAS_APPROACH": (
        "NEUTRAL / WATCH",
        "Dhanteras approach — high demand but already elevated prices. "
        "Transition period. Do not chase — follow macro and Bollinger signals.",
        "NEUTRAL",
        2,
    ),
    "POST_DIWALI_WEDDING": (
        "NEUTRAL / WATCH",
        "Post-Diwali wedding season — demand still present but fading from peak. "
        "Transition period. Reduce exposure gradually.",
        "NEUTRAL",
        2,
    ),
    "YEAR_END_HOLIDAY": (
        "NEUTRAL / WATCH",
        "Year-end holiday lull — demand falling. "
        "Wait for January reset before next accumulation cycle begins.",
        "NEUTRAL",
        2,
    ),
}

def generate_season_signal(season: str) -> dict:
    """
    Returns (signal, action, strength, score) for the given season code.
    Falls back to NEUTRAL/WATCH if season code not recognized.
    """
    if season == "UNKNOWN":
        return {
            "signal":   "DATA UNAVAILABLE",
            "action":   "Season could not be determined.",
            "strength": "NONE",
            "score":    0,
        }

    entry = SEASON_SIGNAL_MAP.get(season)

    if entry is None:
        log.warning(f"Season '{season}' not found in signal map — defaulting to NEUTRAL")
        return {
            "signal":   "NEUTRAL / WATCH",
            "action":   "Unknown season phase — follow other signals for direction.",
            "strength": "NEUTRAL",
            "score":    2,
        }

    signal_label, action_text, strength_label, score = entry
    return {
        "signal":   signal_label,
        "action":   action_text,
        "strength": strength_label,
        "score":    score,
    }


# =============================================================================
# STEP 4 — UPCOMING EVENT ALERT (within 30 days)
# =============================================================================

def get_upcoming_event_alert(today: date) -> str:
    """
    Scan upcoming festivals within 30 days.
    Returns alert string. Never raises.
    """
    try:
        alerts = []

        for event in UPCOMING_EVENTS:
            # Build the event date for this year first, then next year if past
            for year_offset in [0, 1]:
                try:
                    event_date = date(
                        today.year + year_offset,
                        event["month"],
                        event["day_start"]
                    )
                except ValueError:
                    continue

                days_until = (event_date - today).days

                if 0 <= days_until <= 30:
                    alerts.append(
                        f"⚡ UPCOMING: {event['name']} in ~{days_until} day(s) "
                        f"({event_date.strftime('%d %b %Y')}) — demand spike expected"
                    )
                    break   # found a match for this event, move to next

        if alerts:
            return " | ".join(alerts)

        return "No major gold festival within 30 days"

    except Exception as e:
        log.warning(f"Upcoming event check failed: {e}")
        return "Upcoming event check unavailable"


# =============================================================================
# PRINT OUTPUT — matches planning MD format exactly
# =============================================================================

def print_signal_output(
    date_info:     dict,
    phase_info:    dict,
    signal_info:   dict,
    upcoming:      str,
    ts:            str,
):
    W = 60
    line = "═" * W

    def row(text=""):
        print(f"║ {str(text)[:(W-2)].ljust(W-2)} ║")

    def sep():
        print(f"╠{line}╣")

    print(f"\n╔{line}╗")
    row("SIGNAL 03 — SEASONALITY PLAY (INDIA)")
    sep()
    row(f"Date Today    : {date_info['today'].strftime('%d %b %Y')}")
    row(f"Month         : {date_info['month_name']} {date_info['year']}")
    row(f"Season Phase  : {phase_info['season']}")
    row(f"Description   : {phase_info['description']}")
    row(f"Demand Level  : {phase_info['demand']}")

    # Optional note (Akshaya Tritiya warning etc.)
    if phase_info.get("note"):
        row(f"Note          : {phase_info['note']}")

    sep()
    row(f"SEASON SIGNAL : {signal_info['signal']}")
    row(f"STRENGTH      : {signal_info['strength']}")
    row(f"SCORE         : {signal_info['score']} / 5")
    sep()
    row("ACTION GUIDANCE:")

    # Wrap action text
    words  = signal_info["action"].split()
    line_buf, wrapped = [], []
    for w in words:
        if len(" ".join(line_buf + [w])) > W - 4:
            wrapped.append(" ".join(line_buf))
            line_buf = [w]
        else:
            line_buf.append(w)
    if line_buf:
        wrapped.append(" ".join(line_buf))
    for line_text in wrapped:
        row(f"  {line_text}")

    sep()
    row(f"UPCOMING EVENT: {upcoming[:W-18]}")
    if len(upcoming) > W - 18:
        row(f"  {upcoming[W-18:]}")
    sep()
    row("SEASON STRATEGY:")
    row("  Jul–Aug lull    → Accumulate slowly")
    row("  Sep–Oct rising  → Hold accumulated, add on dips")
    row("  Oct–Nov peak    → Sell into strength (+3–4%)")
    row("  Post-Diwali     → Exit remaining, wait for lull")
    print(f"╚{line}╝\n")


# =============================================================================
# MAIN RUNNER
# =============================================================================

def run_signal_03() -> dict:
    """
    Main entry point for Signal 03.
    Returns result dict compatible with signal_08_verdict_score.py scorer.

    FAILURE CONTRACT:
      - System date error       → signal = "DATA UNAVAILABLE", score = 0
      - Any unexpected exception → signal = "DATA UNAVAILABLE", score = 0
      - NEVER estimates, never assumes.
    """
    log.info("=" * 60)
    log.info("SIGNAL 03 — SEASONALITY PLAY — START")
    log.info("=" * 60)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── STEP 1: Get current date ──────────────────────────────────────────────
    date_info = get_current_date()

    if date_info is None:
        log.error("SYSTEM DATE ERROR — cannot determine seasonality")
        err_result = {
            "signal":     "DATA UNAVAILABLE",
            "confidence": "NONE",
            "score":      0,
            "phase":      "SYSTEM_DATE_ERROR",
            "action":     "SIGNAL 03: SYSTEM DATE ERROR — check your system clock.",
            "timestamp":  ts,
            "source":     "signal_03",
        }
        print(f"\n{'⚠️ '  * 20}")
        print(f"  SIGNAL 03: SYSTEM DATE ERROR — cannot determine seasonality.")
        print(f"  Please check your system clock and re-run.")
        print(f"{'⚠️ '  * 20}\n")
        return err_result

    log.info(
        f"Date: {date_info['today']} | Month: {date_info['month_name']} "
        f"| Day: {date_info['day']}"
    )

    # ── STEP 2: Determine season phase ────────────────────────────────────────
    try:
        phase_info = determine_season_phase(date_info["month"], date_info["day"])
        log.info(
            f"Season: {phase_info['season']} | Demand: {phase_info['demand']}"
        )
    except Exception as e:
        log.error(f"Season phase determination failed: {e}")
        return {
            "signal":     "DATA UNAVAILABLE",
            "confidence": "NONE",
            "score":      0,
            "phase":      "CALCULATION_ERROR",
            "action":     f"SIGNAL 03: Calculation error — {e}",
            "timestamp":  ts,
            "source":     "signal_03",
        }

    # ── STEP 3: Generate season signal ───────────────────────────────────────
    try:
        signal_info = generate_season_signal(phase_info["season"])
        log.info(
            f"Signal: {signal_info['signal']} | Strength: {signal_info['strength']} "
            f"| Score: {signal_info['score']}/5"
        )
    except Exception as e:
        log.error(f"Signal generation failed: {e}")
        return {
            "signal":     "DATA UNAVAILABLE",
            "confidence": "NONE",
            "score":      0,
            "phase":      phase_info.get("season", "UNKNOWN"),
            "action":     f"SIGNAL 03: Signal generation error — {e}",
            "timestamp":  ts,
            "source":     "signal_03",
        }

    # Early exit if signal itself is DATA UNAVAILABLE (unknown season)
    if signal_info["signal"] == "DATA UNAVAILABLE":
        log.error("Season signal returned DATA UNAVAILABLE — unknown season code")
        return {
            "signal":     "DATA UNAVAILABLE",
            "confidence": "NONE",
            "score":      0,
            "phase":      phase_info.get("season", "UNKNOWN"),
            "action":     "SIGNAL 03: Unknown season — DATA UNAVAILABLE",
            "timestamp":  ts,
            "source":     "signal_03",
        }

    # ── STEP 4: Upcoming event alert ──────────────────────────────────────────
    try:
        upcoming_alert = get_upcoming_event_alert(date_info["today"])
        log.info(f"Upcoming event: {upcoming_alert}")
    except Exception as e:
        log.warning(f"Upcoming event check error: {e}")
        upcoming_alert = "Upcoming event check unavailable"

    # ── Confidence ────────────────────────────────────────────────────────────
    # Signal 03 uses ONLY system date — always HIGH confidence if we got here
    confidence = "HIGH"

    # ── Print output ──────────────────────────────────────────────────────────
    try:
        print_signal_output(date_info, phase_info, signal_info, upcoming_alert, ts)
    except Exception as e:
        log.warning(f"Print output error (non-fatal): {e}")

    log.info(
        f"FINAL: {signal_info['signal']} | Score: {signal_info['score']}/5 "
        f"| Confidence: {confidence}"
    )
    log.info("SIGNAL 03 — SEASONALITY PLAY — END")

    return {
        "signal":         signal_info["signal"],
        "confidence":     confidence,
        "score":          signal_info["score"],         # 0–5, used by signal_08 scorer
        "phase":          phase_info["season"],         # internal season code
        "description":    phase_info["description"],    # human readable
        "demand":         phase_info["demand"],
        "strength":       signal_info["strength"],
        "action":         signal_info["action"],
        "upcoming_event": upcoming_alert,
        "month":          date_info["month"],
        "month_name":     date_info["month_name"],
        "timestamp":      ts,
        "source":         "signal_03",
    }


# =============================================================================
# STANDALONE LAUNCHER
# =============================================================================

if __name__ == "__main__":
    result = run_signal_03()
    log.info(f"Exit: {result.get('signal')} | Score: {result.get('score')}/5")
