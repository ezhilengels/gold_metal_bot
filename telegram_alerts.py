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

def _score_bar(score: float, max_score: float = 95.0, width: int = 20) -> str:
    """Compact ASCII bar for Telegram."""
    pct    = min(max(score, 0) / max_score, 1.0)
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

    def _pts(key, mx):
        v = scores.get(key, {}).get('pts')
        if isinstance(v, (int, float)):
            return f"{v:.0f}/{mx}"
        return f"—/{mx}"

    lines = [
        f"{icon} <b>GOLD BOT — {signal}</b>",
        f"<code>{ts}</code>",
        "",
        f"<b>SCORE: {score:.1f} / 95</b>",
        f"<code>[{bar}]</code>",
        "",
        "📊 <b>Signal Breakdown:</b>",
        f"  S01 Buy Dip    : {_pts('s01', 15)}",
        f"  S02 Macro      : {_pts('s02', 25)}",
        f"  S03 Seasonality: {_pts('s03', 5)}",
        f"  S04 BB Bands   : {_pts('s04', 15)}",
        f"  S05 Outlook    : {_pts('s05', 10)}",
        f"  S06 Weekly     : {_pts('s06', 10)}",
        f"  S09 Volume     : {_pts('s09', 10)}",
        f"  S10 MCX Spread : {_pts('s10', 5)}",
        f"  S12 Corr Break : {_pts('s12', 8)}",
        f"  S07 Penalty    : -{scores.get('s07_penalty', 0):.0f} pts",
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
        f"<b>Score: {score:.1f} / 95</b>",
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


def build_correlation_break_alert(s12_result: dict, ts: str = "") -> str:
    """
    Compound correlation break alert — sent when Signal 12 detects a
    compound alert type (A-E). Single breaks are dashboard-only; compound
    breaks trigger a Telegram notification per the planning spec (Section 10).

    Called separately from send_verdict_alert with result.get("s12_result").
    Only called when s12_result contains one or more alert_types entries.
    """
    if not ts:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    alerts  = s12_result.get("alert_types", [])
    regime  = s12_result.get("regime", "")
    s12_sig = s12_result.get("signal", "")
    s12_pts = s12_result.get("score", 0)
    breaks  = s12_result.get("breaks", [])
    pchg    = s12_result.get("price_changes", {})

    # Headline icon based on overall implication
    overall = s12_result.get("overall_implication", "")
    if overall == "BULLISH":
        headline_icon = "📡🟢"
    elif overall == "BEARISH":
        headline_icon = "📡🔴"
    else:
        headline_icon = "📡🔵"

    lines = [
        f"{headline_icon} <b>GOLD BOT — CORRELATION BREAK ALERT (S12)</b>",
        f"<code>{ts}</code>",
        "",
        f"<b>Regime:</b> {regime}",
        f"<b>Signal:</b> {s12_sig}",
        f"<b>S12 Score:</b> {s12_pts:+.0f}/8 pts",
        "",
        "⚠️ <b>COMPOUND ALERT(S) DETECTED:</b>",
    ]

    # One block per alert type
    for a in alerts:
        sev     = a.get("severity", "MEDIUM")
        sev_str = f"[{sev}]"
        lines += [
            "",
            f"  {a.get('emoji', '🔔')} <b>Type {a.get('type', '?')} — {a.get('label', '')}</b> {sev_str}",
            f"  {a.get('message', '')}",
        ]

    # Show which correlations broke
    if breaks:
        lines += ["", "🔗 <b>Correlation Breaks:</b>"]
        for b in breaks:
            impl   = b.get("implication", "")
            arrow  = "↑" if impl == "BULLISH" else ("↓" if impl == "BEARISH" else "?")
            lines.append(f"  {arrow} {b.get('pair','').upper()} — {impl}")

    # 5-day price changes summary
    gb_5d = pchg.get("goldbees_5d")
    cx_5d = pchg.get("comex_5d")
    if gb_5d is not None or cx_5d is not None:
        lines.append("")
        lines.append("📈 <b>5-Day Changes:</b>")
        if gb_5d is not None:
            lines.append(f"  GOLDBEES : {gb_5d:+.2f}%")
        if cx_5d is not None:
            lines.append(f"  COMEX    : {cx_5d:+.2f}%")
        dxy_5d = pchg.get("dxy_5d")
        if dxy_5d is not None:
            lines.append(f"  DXY      : {dxy_5d:+.2f}%")

    lines += [
        "",
        "ℹ️ <i>Correlation breaks affect S12 composite score.</i>",
        "<i>Review full dashboard before making any trade decision.</i>",
        "",
        "⚠️ <i>This is a signal, not financial advice.</i>",
    ]

    return "\n".join(lines)


# =============================================================================
# MAIN DISPATCH  — called by Signal 08
# =============================================================================

def send_verdict_alert(result: dict) -> bool:
    """
    Main entry point called by run_signal_08() after the verdict is generated.
    Picks the correct alert type based on the verdict signal.
    Returns True if at least one message was sent, False otherwise.

    Alert triggers:
        STRONG BUY / BUY   → buy_alert  (entry, target, stop)
        SELL / TAKE PROFIT → sell_alert (exit if holding)
        AVOID / BLOCKED    → avoid_alert (trade blocked)
        WATCH              → watch_alert (heads-up)
        DO NOT TRADE       → no alert (silent — avoid alert fatigue)
        WAIT               → no alert (silent)
        DATA UNAVAILABLE   → data_unavailable_alert

    Signal 12 compound alerts (Types A-E) are ALWAYS sent independently
    whenever detected, regardless of the main verdict.
    Single correlation breaks are dashboard-only (not sent here).
    """
    signal = result.get("signal", "")
    ts     = result.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    sent   = False

    log.info(f"Telegram dispatch: signal={signal}")

    # ── STRONG BUY or BUY ────────────────────────────────────────────────────
    if "STRONG BUY" in signal or (signal.startswith("BUY") and "BLOCKED" not in signal):
        msg = build_buy_alert(result)
        ok  = _send(msg)
        log.info(f"Telegram BUY alert sent: {ok}")
        sent = sent or ok

    # ── SELL / TAKE PROFIT (from Signal 04 exit note) ────────────────────────
    elif result.get("sell_alert") and "SELL" in result.get("sell_alert", "").upper():
        msg = build_sell_alert(result)
        ok  = _send(msg)
        log.info(f"Telegram SELL alert sent: {ok}")
        sent = sent or ok

    # ── AVOID / BLOCKED ───────────────────────────────────────────────────────
    elif "BLOCKED" in signal or "AVOID" in signal:
        msg = build_avoid_alert(result)
        ok  = _send(msg)
        log.info(f"Telegram AVOID alert sent: {ok}")
        sent = sent or ok

    # ── WATCH ─────────────────────────────────────────────────────────────────
    elif "WATCH" in signal:
        msg = build_watch_alert(result)
        ok  = _send(msg)
        log.info(f"Telegram WATCH alert sent: {ok}")
        sent = sent or ok

    # ── DATA UNAVAILABLE ──────────────────────────────────────────────────────
    elif "DATA UNAVAILABLE" in signal or "INSUFFICIENT" in signal:
        msg = build_data_unavailable_alert(result)
        ok  = _send(msg)
        log.info(f"Telegram DATA_UNAVAILABLE alert sent: {ok}")
        sent = sent or ok

    else:
        # ── DO NOT TRADE / WAIT — silent, no verdict alert ───────────────────
        log.info(f"Telegram: no verdict alert sent for '{signal}' (silent verdict)")

    # ── Signal 12 compound break alerts (ALWAYS sent independently) ──────────
    # Single breaks are dashboard-only; compound alert_types trigger Telegram.
    s12_result = result.get("s12_result", {})
    if s12_result and s12_result.get("alert_types"):
        corr_msg = build_correlation_break_alert(s12_result, ts=ts)
        ok = _send(corr_msg)
        log.info(f"Telegram S12 compound break alert sent: {ok} "
                 f"({len(s12_result['alert_types'])} alert type(s))")
        sent = sent or ok

    return sent


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
        "  ⬛ DATA UNAVAILABLE — fetch failure warning\n"
        "  📡 S12 COMPOUND BREAK — correlation regime alert (A–E)\n\n"
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
