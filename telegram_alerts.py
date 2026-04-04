# =============================================================================
# GOLD BOT — telegram_alerts.py
# Telegram Alert Module
#
# Sends alerts to your Telegram when:
#   • STRONG BUY or BUY verdict fires       → entry price, target, stop
#   • SELL / TAKE PROFIT fires (Signal 04)  → exit alert for open position
#   • AVOID triggered (Signal 07)           → risk block notification
#   • WATCH verdict fires                   → heads-up, no trade yet
#
# Message format matches the output spec in signal_08_verdict_score.md exactly.
#
# SETUP:
#   1. Create a bot: message @BotFather on Telegram → /newbot
#   2. Copy the token into config.py → telegram_bot_token
#   3. Find your chat_id: message your bot, then visit:
#      https://api.telegram.org/bot<TOKEN>/getUpdates
#      Look for "chat":{"id": YOUR_NUMBER}
#   4. Paste that number into config.py → telegram_chat_id
#
# DATA RULE: If Telegram send fails → log the error silently.
#            Never crash the main bot because of a failed alert.
# =============================================================================

import requests
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CONFIG

log = logging.getLogger("telegram")

# ── Telegram API ──────────────────────────────────────────────────────────────

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
TIMEOUT      = 10    # seconds


# =============================================================================
# CORE SENDER
# =============================================================================

def _send(text: str, parse_mode: str = "HTML") -> bool:
    """
    Send a Telegram message to the configured chat.
    Returns True on success, False on any failure.
    Never raises — all errors are logged silently.
    """
    token    = CONFIG.get("telegram_bot_token", "")
    chat_id  = CONFIG.get("telegram_chat_id", "")

    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN":
        log.warning("Telegram: bot token not configured in config.py — alert skipped")
        return False

    if not chat_id or chat_id == "YOUR_TELEGRAM_CHAT_ID":
        log.warning("Telegram: chat_id not configured in config.py — alert skipped")
        return False

    url = TELEGRAM_API.format(token=token)

    try:
        resp = requests.post(
            url,
            json={
                "chat_id":    chat_id,
                "text":       text,
                "parse_mode": parse_mode,
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("ok"):
            log.info(f"Telegram: message sent successfully (msg_id={data['result']['message_id']})")
            return True
        else:
            log.error(f"Telegram API error: {data.get('description', 'Unknown')}")
            return False

    except requests.exceptions.Timeout:
        log.error("Telegram: request timed out")
        return False
    except requests.exceptions.ConnectionError:
        log.error("Telegram: connection error — check internet")
        return False
    except Exception as e:
        log.error(f"Telegram: unexpected error — {e}")
        return False


# =============================================================================
# MESSAGE BUILDERS  (one per alert type)
# =============================================================================

def _score_bar(score: float, max_score: float = 80.0, width: int = 20) -> str:
    """Compact ASCII bar for Telegram."""
    pct    = min(score / max_score, 1.0)
    filled = int(pct * width)
    return "█" * filled + "░" * (width - filled)


def build_buy_alert(result: dict) -> str:
    """
    BUY / STRONG BUY alert.
    Matches the output format from signal_08_verdict_score.md.
    """
    signal  = result.get("signal", "BUY")
    score   = result.get("final_score", 0)
    conf    = result.get("confidence", "—")
    ts      = result.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    entry   = result.get("entry_price")
    target  = result.get("target_price")
    stop    = result.get("stop_price")
    action  = result.get("action", "")
    scores  = result.get("signal_scores", {})

    icon = "🟢🟢" if "STRONG" in signal else "🟢"
    bar  = _score_bar(score)

    lines = [
        f"{icon} <b>GOLD BOT — {signal}</b>",
        f"<code>{ts}</code>",
        "",
        f"<b>SCORE: {score:.1f} / 80</b>",
        f"<code>[{bar}]</code>",
        "",
        "📊 <b>Signal Breakdown:</b>",
        f"  S01 Buy Dip   : {scores.get('s01', {}).get('pts', '—'):.0f}/15" if isinstance(scores.get('s01', {}).get('pts'), (int, float)) else "  S01 Buy Dip   : —/15",
        f"  S02 Macro     : {scores.get('s02', {}).get('pts', '—'):.0f}/25" if isinstance(scores.get('s02', {}).get('pts'), (int, float)) else "  S02 Macro     : —/25",
        f"  S03 Seasonality: {scores.get('s03', {}).get('pts', '—'):.0f}/5" if isinstance(scores.get('s03', {}).get('pts'), (int, float)) else "  S03 Seasonality: —/5",
        f"  S04 BB Bands  : {scores.get('s04', {}).get('pts', '—'):.0f}/15" if isinstance(scores.get('s04', {}).get('pts'), (int, float)) else "  S04 BB Bands  : —/15",
        f"  S05 Outlook   : {scores.get('s05', {}).get('pts', '—'):.0f}/10" if isinstance(scores.get('s05', {}).get('pts'), (int, float)) else "  S05 Outlook   : —/10",
        f"  S06 Weekly    : {scores.get('s06', {}).get('pts', '—'):.0f}/10" if isinstance(scores.get('s06', {}).get('pts'), (int, float)) else "  S06 Weekly    : —/10",
        f"  S07 Penalty   : -{scores.get('s07_penalty', 0):.0f} pts",
        "",
        f"<b>Confidence  : {conf}</b>",
    ]

    if entry and target and stop:
        target_pct = CONFIG.get("profit_target_pct", 3.0)
        stop_pct   = CONFIG.get("stop_loss_pct", 1.0)
        lines += [
            "",
            "💰 <b>TRADE PARAMETERS:</b>",
            f"  ETF    : {CONFIG.get('primary_etf', 'GOLDBEES.NS')}",
            f"  Entry  : ₹{entry}",
            f"  Target : ₹{target}  (+{target_pct}%)",
            f"  Stop   : ₹{stop}  (-{stop_pct}%)",
            f"  Hold   : 1–5 trading days (exit by Thursday)",
        ]

    if action:
        lines += ["", f"📌 {action}"]

    lines += [
        "",
        "⚠️ <i>This is a signal, not financial advice.</i>",
        "<i>Always use a stop loss. Manage your risk.</i>",
    ]

    return "\n".join(lines)


def build_sell_alert(result: dict) -> str:
    """
    SELL / TAKE PROFIT alert — triggered when Signal 04 reaches upper BB.
    Matches sell_alert note from signal_08_verdict_score.md.
    """
    ts       = result.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    price    = result.get("current_price") or result.get("entry_price")
    sell_msg = result.get("sell_alert", "Price at/near upper Bollinger Band.")

    lines = [
        "📤 <b>GOLD BOT — SELL / TAKE PROFIT ALERT</b>",
        f"<code>{ts}</code>",
        "",
        "⚡ <b>Signal 04 (Bollinger Bands) says EXIT</b>",
        f"{sell_msg}",
        "",
        "✅ <b>Action:</b> If you are holding a position, consider taking profit now.",
        "   Price is at or near the upper Bollinger Band.",
        "   Do NOT enter a new long position at this level.",
    ]

    if price:
        lines += [
            "",
            f"  Current ETF Price : ₹{price}",
        ]

    lines += [
        "",
        "⚠️ <i>This is a signal, not financial advice.</i>",
    ]

    return "\n".join(lines)


def build_avoid_alert(result: dict) -> str:
    """
    AVOID / BLOCKED alert — triggered when Signal 07 fires AVOID.
    Matches the Signal 07 AVOID block spec.
    """
    ts      = result.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    reasons = result.get("avoid_reasons") or result.get("reason", [])
    action  = result.get("action", "Risk condition triggered. Do not trade.")

    lines = [
        "🚫 <b>GOLD BOT — TRADE BLOCKED (AVOID)</b>",
        f"<code>{ts}</code>",
        "",
        "⛔ <b>Signal 07 Risk Filter has triggered AVOID.</b>",
        "   ALL other signals are overridden.",
        "   Do NOT enter any new gold positions today.",
        "",
    ]

    if reasons:
        lines.append("🔴 <b>Blocked because:</b>")
        for r in reasons:
            lines.append(f"  • {r}")
        lines.append("")

    lines += [
        f"📌 {action}",
        "",
        "⚠️ <i>This is a signal, not financial advice.</i>",
    ]

    return "\n".join(lines)


def build_watch_alert(result: dict) -> str:
    """
    WATCH alert — partial signal alignment. Heads-up, no trade yet.
    Matches WATCH / CONDITIONAL BUY from signal_08_verdict_score.md.
    """
    score  = result.get("final_score", 0)
    ts     = result.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    action = result.get("action", "")
    bar    = _score_bar(score)

    lines = [
        "🟡 <b>GOLD BOT — WATCH / CONDITIONAL BUY</b>",
        f"<code>{ts}</code>",
        "",
        f"<b>Score: {score:.1f} / 80</b>",
        f"<code>[{bar}]</code>",
        "",
        "⚠️ Partial signal alignment. <b>Enter 50% position only.</b>",
        "   Wait for one more confirmation before adding.",
        "",
    ]

    if action:
        lines.append(f"📌 {action}")

    lines += [
        "",
        "<i>Set a price alert. Re-run the bot when conditions improve.</i>",
        "⚠️ <i>This is a signal, not financial advice.</i>",
    ]

    return "\n".join(lines)


def build_data_unavailable_alert(result: dict) -> str:
    """
    Sent when critical data could not be fetched and no verdict can be formed.
    """
    ts = result.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    lines = [
        "⬛ <b>GOLD BOT — DATA UNAVAILABLE</b>",
        f"<code>{ts}</code>",
        "",
        "Could not fetch sufficient data to generate a reliable verdict.",
        "DO NOT TRADE based on incomplete data.",
        "",
        "Check your internet connection and API keys in config.py.",
        "Re-run the bot when data is available.",
        "",
        "⚠️ <i>No estimated values were used.</i>",
    ]

    return "\n".join(lines)


# =============================================================================
# MAIN DISPATCH  — called by Signal 08
# =============================================================================

def send_verdict_alert(result: dict) -> bool:
    """
    Main entry point called by run_signal_08() after the verdict is generated.
    Picks the correct alert type based on the verdict signal.
    Returns True if message was sent, False otherwise.

    Alert triggers (from planning doc):
        STRONG BUY / BUY   → buy_alert  (entry, target, stop)
        SELL / TAKE PROFIT → sell_alert (exit if holding)
        AVOID / BLOCKED    → avoid_alert (trade blocked)
        WATCH              → watch_alert (heads-up)
        DO NOT TRADE       → no alert (silent — avoid alert fatigue)
        WAIT               → no alert (silent)
        DATA UNAVAILABLE   → data_unavailable_alert
    """
    signal = result.get("signal", "")
    ts     = result.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    log.info(f"Telegram dispatch: signal={signal}")

    # ── STRONG BUY or BUY ────────────────────────────────────────────────────
    if "STRONG BUY" in signal or (signal.startswith("BUY") and "BLOCKED" not in signal):
        msg = build_buy_alert(result)
        ok  = _send(msg)
        log.info(f"Telegram BUY alert sent: {ok}")
        return ok

    # ── SELL / TAKE PROFIT (from Signal 04 exit note) ────────────────────────
    if result.get("sell_alert") and "SELL" in result.get("sell_alert", "").upper():
        msg = build_sell_alert(result)
        ok  = _send(msg)
        log.info(f"Telegram SELL alert sent: {ok}")
        return ok

    # ── AVOID / BLOCKED ───────────────────────────────────────────────────────
    if "BLOCKED" in signal or "AVOID" in signal:
        msg = build_avoid_alert(result)
        ok  = _send(msg)
        log.info(f"Telegram AVOID alert sent: {ok}")
        return ok

    # ── WATCH ─────────────────────────────────────────────────────────────────
    if "WATCH" in signal:
        msg = build_watch_alert(result)
        ok  = _send(msg)
        log.info(f"Telegram WATCH alert sent: {ok}")
        return ok

    # ── DATA UNAVAILABLE ──────────────────────────────────────────────────────
    if "DATA UNAVAILABLE" in signal or "INSUFFICIENT" in signal:
        msg = build_data_unavailable_alert(result)
        ok  = _send(msg)
        log.info(f"Telegram DATA_UNAVAILABLE alert sent: {ok}")
        return ok

    # ── DO NOT TRADE / WAIT — silent, no alert ────────────────────────────────
    log.info(f"Telegram: no alert sent for verdict '{signal}' (silent verdict)")
    return False


# =============================================================================
# TEST SENDER — run standalone to verify your bot token and chat_id
# =============================================================================

def send_test_message() -> bool:
    """
    Send a test message to verify your Telegram bot is connected.
    Run:  python telegram_alerts.py
    """
    ts  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = (
        "✅ <b>GOLD BOT — Test Message</b>\n"
        f"<code>{ts}</code>\n\n"
        "Your Telegram alert integration is working correctly.\n\n"
        "<b>Alert types configured:</b>\n"
        "  🟢 BUY / STRONG BUY — entry price, target, stop\n"
        "  📤 SELL / TAKE PROFIT — exit signal\n"
        "  🚫 AVOID — trade blocked by risk filter\n"
        "  🟡 WATCH — partial alignment heads-up\n"
        "  ⬛ DATA UNAVAILABLE — fetch failure warning\n\n"
        "<i>Gold Bot is ready.</i>"
    )
    ok = _send(msg)
    if ok:
        print("✅ Test message sent successfully! Check your Telegram.")
    else:
        print("❌ Test message failed. Check your token and chat_id in config.py.")
        print("   Token  : telegram_bot_token")
        print("   Chat ID: telegram_chat_id")
    return ok


if __name__ == "__main__":
    send_test_message()
