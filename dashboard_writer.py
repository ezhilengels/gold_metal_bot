# =============================================================================
# GOLD BOT — dashboard_writer.py
# Generates a self-contained HTML dashboard from Signal 08 result dict.
# Called automatically by run_signal_08.py after every run.
# Output: gold_bot/dashboard.html  (open directly in any browser)
#
# Signals shown: S01–S07 (original) + S09 Volume + S10 MCX Spread
# Max score    : 95 pts  (S01=15, S02=25, S03=5, S04=15, S05=10,
#                          S06=10, S09=10, S10=5, minus S07 penalty)
# =============================================================================

import os
import math
import json
from datetime import datetime
from typing import Optional


# =============================================================================
# HELPERS
# =============================================================================

def _verdict_color(signal: str) -> str:
    s = signal.upper()
    if "STRONG BUY" in s:       return "#00e676"
    if "BUY" in s:              return "#69f0ae"
    if "WATCH" in s:            return "#ffd740"
    if "WAIT" in s:             return "#ffab40"
    if "BLOCKED" in s or "AVOID" in s or "DO NOT" in s: return "#ff5252"
    if "NON-TRADING" in s:      return "#90a4ae"
    return "#90a4ae"

def _verdict_bg(signal: str) -> str:
    s = signal.upper()
    if "STRONG BUY" in s:       return "rgba(0,230,118,0.12)"
    if "BUY" in s:              return "rgba(105,240,174,0.10)"
    if "WATCH" in s:            return "rgba(255,215,64,0.10)"
    if "WAIT" in s:             return "rgba(255,171,64,0.10)"
    if "BLOCKED" in s or "AVOID" in s or "DO NOT" in s: return "rgba(255,82,82,0.12)"
    if "NON-TRADING" in s:      return "rgba(144,164,174,0.10)"
    return "rgba(144,164,174,0.10)"

def _score_color(pct: float) -> str:
    if pct >= 75:  return "#00e676"
    if pct >= 56:  return "#69f0ae"
    if pct >= 37:  return "#ffd740"
    if pct >= 18:  return "#ffab40"
    return "#ff5252"

def _signal_badge(pts, mx) -> str:
    pct = (pts / mx * 100) if mx else 0
    if pct >= 80:  return "#00e676"
    elif pct >= 50: return "#ffd740"
    elif pct > 0:  return "#ffab40"
    else:          return "#546e7a"

def _esc(s) -> str:
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def _phase_color(phase: str) -> str:
    phase = phase.upper()
    if "TRAIL_75" in phase: return "#00e676"
    if "TRAIL_50" in phase: return "#69f0ae"
    if "BREAKEVEN" in phase: return "#ffd740"
    if "PROTECT" in phase:  return "#ffab40"
    return "#8b949e"

def _phase_label(phase: str) -> str:
    m = {
        "NOT_HOLDING": "Not Holding",
        "PROTECT":     "Phase 1 — Capital Protection",
        "BREAKEVEN":   "Phase 2 — Breakeven Stop",
        "TRAIL_50":    "Phase 3 — Trail at 50% of Gain",
        "TRAIL_75":    "Phase 4 — Trail at 75% (Target Hit!)",
    }
    return m.get(phase.upper(), phase)


# =============================================================================
# HTML BUILDER
# =============================================================================

MAX_SCORE = 95   # S01(15)+S02(25)+S03(5)+S04(15)+S05(10)+S06(10)+S09(10)+S10(5)+S12(8)

def build_html(result: dict, config: Optional[dict] = None) -> str:
    cfg    = config or {}
    signal = result.get("signal", "N/A")
    conf   = result.get("confidence", "N/A")
    final  = result.get("final_score", 0.0)
    raw    = result.get("raw_score", final)
    pen    = result.get("s07_penalty", 0.0)
    action = result.get("action", "")
    ts     = result.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    etf    = cfg.get("primary_etf", "GOLDBEES.NS")
    scores = result.get("signal_scores", {})

    score_pct   = round((final / MAX_SCORE) * 100, 1)
    v_color     = _verdict_color(signal)
    v_bg        = _verdict_bg(signal)
    bar_color   = _score_color(score_pct)

    # ── Signal score rows ────────────────────────────────────────────────────
    sig_rows = [
        ("S01", "Buy the Dip",        scores.get("s01", {}), 15),
        ("S02", "Macro Trigger",      scores.get("s02", {}), 25),
        ("S03", "Seasonality",        scores.get("s03", {}),  5),
        ("S04", "Bollinger Bands",    scores.get("s04", {}), 15),
        ("S05", "2026 Outlook",       scores.get("s05", {}), 10),
        ("S06", "Weekly Routine",     scores.get("s06", {}), 10),
        ("S09", "Volume Confirm",     scores.get("s09", {}), 10),
        ("S10", "MCX–COMEX Spread",   scores.get("s10", {}),  5),
        ("S12", "Correlation Break",  scores.get("s12", {}),  8),
    ]

    def signal_card(code, label, sc, mx):
        pts   = sc.get("pts", 0)
        # negative pts (S12 penalty) get red colouring; bar shows 0
        if pts < 0:
            col   = "#ff5252"
            bar_w = 0
            pts_label = f"{pts:.0f}"
        else:
            col   = _signal_badge(pts, mx)
            bar_w = round((pts / mx * 100) if mx else 0)
            pts_label = f"{pts:.0f}"
        sub   = sc.get("sub", "")  # optional sub-label (signal text)
        sub_html = f'<div class="sig-sub">{_esc(sub)}</div>' if sub else ""
        return f"""
        <div class="sig-card">
          <div class="sig-header">
            <span class="sig-code">{_esc(code)}</span>
            <span class="sig-label">{_esc(label)}</span>
            <span class="sig-pts" style="color:{col}">{pts_label}<span class="sig-max">/{mx}</span></span>
          </div>
          {sub_html}
          <div class="sig-bar-bg">
            <div class="sig-bar-fill" style="width:{bar_w}%;background:{col}"></div>
          </div>
        </div>"""

    cards_html = "".join(signal_card(c, l, s, m) for c, l, s, m in sig_rows)

    # ── Trade parameters ─────────────────────────────────────────────────────
    trade_html = ""
    if result.get("entry_price") and "BUY" in signal.upper():
        trade_html = f"""
      <div class="trade-box">
        <div class="section-title">📊 Trade Parameters</div>
        <div class="trade-grid">
          <div class="trade-item">
            <div class="trade-lbl">ETF</div>
            <div class="trade-val">{_esc(etf)}</div>
          </div>
          <div class="trade-item">
            <div class="trade-lbl">Entry Price</div>
            <div class="trade-val">₹{result['entry_price']}</div>
          </div>
          <div class="trade-item green">
            <div class="trade-lbl">Target (+{cfg.get('profit_target_pct',3)}%)</div>
            <div class="trade-val">₹{result['target_price']}</div>
          </div>
          <div class="trade-item red">
            <div class="trade-lbl">Stop Loss (-{cfg.get('stop_loss_pct',1)}%)</div>
            <div class="trade-val">₹{result['stop_price']}</div>
          </div>
        </div>
        <div class="trade-note">Hold Period: 1–5 trading days. Exit by Thursday if entered Monday.</div>
      </div>"""

    # ── Trailing stop section ────────────────────────────────────────────────
    ts_html = ""
    trailing = result.get("trailing_stop", {})
    if trailing and trailing.get("active"):
        phase     = trailing.get("phase", "PROTECT")
        ph_color  = _phase_color(phase)
        ph_label  = _phase_label(phase)
        stop_p    = trailing.get("stop_price", 0)
        entry_p   = trailing.get("entry_price", cfg.get("holding_entry_price", 0))
        gain_pct  = trailing.get("gain_pct", 0)
        ts_action = trailing.get("action", trailing.get("message", ""))
        gain_col  = "#00e676" if gain_pct >= 0 else "#ff5252"
        ts_html = f"""
      <div class="trailing-box">
        <div class="section-title">🔒 Trailing Stop — Active Position</div>
        <div class="ts-phase" style="color:{ph_color}">{_esc(ph_label)}</div>
        <div class="ts-grid">
          <div class="ts-item">
            <div class="ts-lbl">Entry Price</div>
            <div class="ts-val">₹{entry_p}</div>
          </div>
          <div class="ts-item">
            <div class="ts-lbl">Current Stop</div>
            <div class="ts-val" style="color:{ph_color}">₹{stop_p}</div>
          </div>
          <div class="ts-item">
            <div class="ts-lbl">Gain / Loss</div>
            <div class="ts-val" style="color:{gain_col}">{gain_pct:+.2f}%</div>
          </div>
          <div class="ts-item">
            <div class="ts-lbl">Target</div>
            <div class="ts-val" style="color:#00e676">+{cfg.get('profit_target_pct',3)}%</div>
          </div>
        </div>
        <div class="ts-action">{_esc(ts_action)}</div>
      </div>"""
    elif trailing and not trailing.get("active") and trailing.get("phase") != "NOT_HOLDING":
        # Has entry price set but not active for some reason
        pass

    # ── Correlation Monitor (Signal 12) ─────────────────────────────────────
    corr_monitor_html = ""
    s12_result = result.get("s12_result", {})
    if s12_result and "DATA UNAVAILABLE" not in s12_result.get("signal", "DATA UNAVAILABLE"):
        corrs      = s12_result.get("correlations", {})
        s12_breaks = s12_result.get("breaks", [])
        s12_alerts = s12_result.get("alert_types", [])
        s12_regime = s12_result.get("regime", "")
        s12_conf   = s12_result.get("confidence", "")
        s12_pchg   = s12_result.get("price_changes", {})

        # Status → color + icon
        def _corr_color(status: str) -> str:
            s = status.upper()
            if s == "NORMAL":           return "#00e676"
            if s == "WARNING":          return "#ffd740"
            if s == "BREAK":            return "#ff5252"
            if s == "DATA_UNAVAILABLE": return "#546e7a"
            return "#8b949e"

        def _corr_dot(status: str) -> str:
            s = status.upper()
            if s == "NORMAL":           return "🟢"
            if s == "WARNING":          return "🟡"
            if s == "BREAK":            return "🔴"
            if s == "DATA_UNAVAILABLE": return "⬛"
            return "❓"

        # Build correlation rows
        corr_rows_html = ""
        for k, v in corrs.items():
            pair    = v.get("pair", k)
            c20     = v.get("corr")
            c10     = v.get("corr_10d")
            nb      = v.get("normal_band", "")
            status  = v.get("status", "DATA_UNAVAILABLE")
            impl    = v.get("implication", "")
            col     = _corr_color(status)
            dot     = _corr_dot(status)
            c20_str = f"{c20:+.3f}" if c20 is not None else "N/A"
            c10_str = f"{c10:+.3f}" if c10 is not None else "N/A"
            impl_badge = ""
            if impl and impl != "NONE":
                impl_col = "#00e676" if impl == "BULLISH" else ("#ff5252" if impl == "BEARISH" else "#8b949e")
                impl_badge = f'<span style="font-size:.68rem;padding:1px 5px;border-radius:3px;background:{impl_col}22;color:{impl_col};margin-left:4px">{_esc(impl)}</span>'
            corr_rows_html += f"""
            <div class="corr-row">
              <span class="corr-pair">{_esc(pair)}</span>
              <span class="corr-val" style="color:{col}">{_esc(c20_str)}</span>
              <span class="corr-val dim">{_esc(c10_str)}</span>
              <span class="corr-band">{_esc(nb)}</span>
              <span class="corr-status">{dot} {_esc(status.replace('_',' '))}{impl_badge}</span>
            </div>"""

        # Build breaks rows
        breaks_html = ""
        if s12_breaks:
            for b in s12_breaks:
                impl_b  = b.get("implication", "")
                impl_c  = "#00e676" if impl_b == "BULLISH" else ("#ff5252" if impl_b == "BEARISH" else "#8b949e")
                arrow   = "↑" if impl_b == "BULLISH" else ("↓" if impl_b == "BEARISH" else "?")
                note_b  = b.get("note", "")
                breaks_html += f"""
            <div class="break-row">
              <span class="break-pair" style="color:{impl_c}">{arrow} {_esc(b.get('pair','').upper())}</span>
              <span class="break-note">{_esc(note_b[:120])}</span>
            </div>"""
        else:
            breaks_html = '<div class="break-ok">✅ All correlations normal — no breaks detected</div>'

        # Build alert badges
        alerts_html = ""
        if s12_alerts:
            for a in s12_alerts:
                sev     = a.get("severity", "")
                sev_col = "#ff5252" if sev == "HIGH" else ("#ffd740" if sev == "MEDIUM" else "#8b949e")
                alerts_html += f"""
            <div class="alert-badge" style="border-color:{sev_col}44">
              <span style="font-size:1.1rem">{_esc(a.get('emoji',''))}</span>
              <div>
                <div style="font-size:.82rem;font-weight:700;color:{sev_col}">{_esc(a.get('label',''))}</div>
                <div style="font-size:.75rem;color:#8b949e">{_esc(a.get('message','')[:120])}</div>
              </div>
            </div>"""

        # Regime badge color
        regime_col = "#00e676" if "BULLISH" in s12_regime.upper() else (
                     "#ff5252" if "BEARISH" in s12_regime.upper() else "#ffd740")

        corr_monitor_html = f"""
      <div class="corr-card">
        <div class="section-title" style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
          📡 Correlation Monitor
          <span style="font-size:.78rem;padding:3px 8px;border-radius:4px;background:{regime_col}22;color:{regime_col};font-weight:700">{_esc(s12_regime)}</span>
          <span style="font-size:.75rem;color:#8b949e;margin-left:auto">Confidence: {_esc(s12_conf)}</span>
        </div>
        <div class="corr-header">
          <span class="corr-pair" style="color:#8b949e">Pair</span>
          <span class="corr-val" style="color:#8b949e">20d r</span>
          <span class="corr-val" style="color:#8b949e">10d r</span>
          <span class="corr-band" style="color:#8b949e">Normal Band</span>
          <span class="corr-status" style="color:#8b949e">Status</span>
        </div>
        {corr_rows_html}
        <div class="corr-section-title">CORRELATION BREAKS</div>
        {breaks_html}
        {"<div class='corr-section-title'>COMPOUND ALERTS</div>" + alerts_html if s12_alerts else ""}
      </div>"""

    # ── Sell alert ───────────────────────────────────────────────────────────
    sell_html = ""
    if result.get("sell_alert"):
        sell_html = f"""
      <div class="alert-box">
        ⚡ <strong>EXIT ALERT:</strong> {_esc(result['sell_alert'])}
      </div>"""

    # ── Score gauge arc ──────────────────────────────────────────────────────
    # Zones (absolute pts, sum=95): 0-14 No Trade, 15-29 Wait, 30-44 Watch, 45-59 Buy, 60-95 Strong Buy
    zones = [
        (15, "#ff5252", "No Trade"),
        (15, "#ffab40", "Wait"),
        (15, "#ffd740", "Watch"),
        (15, "#69f0ae", "Buy"),
        (35, "#00e676", "Strong Buy"),
    ]
    zone_bars = ""
    for width_pts, col, lbl in zones:
        w = round(width_pts / MAX_SCORE * 100)
        zone_bars += f'<div class="zone-seg" style="width:{w}%;background:{col}" title="{lbl}"></div>'

    thresholds = """
      <div class="thresh-row">
        <span>0</span>
        <span>15<br><small>WAIT</small></span>
        <span>30<br><small>WATCH</small></span>
        <span>45<br><small>BUY</small></span>
        <span>60<br><small>STR BUY</small></span>
        <span>95</span>
      </div>"""

    # ── S07 penalty card ─────────────────────────────────────────────────────
    pen_color = "#ff5252" if pen >= 20 else ("#ffab40" if pen > 0 else "#546e7a")
    pen_html = f"""
        <div class="sig-card" style="border-color:{pen_color}33">
          <div class="sig-header">
            <span class="sig-code">S07</span>
            <span class="sig-label">Risk Gate Penalty</span>
            <span class="sig-pts" style="color:{pen_color}">-{pen:.0f}<span class="sig-max">/{MAX_SCORE}</span></span>
          </div>
        </div>"""

    # ── Score table ──────────────────────────────────────────────────────────
    score_table = f"""
      <div class="score-summary">
        <div class="score-row"><span>Raw Score</span><span>{raw:.1f} / {MAX_SCORE}</span></div>
        <div class="score-row"><span>S07 Penalty</span><span style="color:#ffab40">-{pen:.1f} pts</span></div>
        <div class="score-row bold"><span>Final Score</span><span style="color:{bar_color}">{final:.1f} / {MAX_SCORE}</span></div>
        <div class="score-row"><span>Normalized</span><span>{score_pct}%</span></div>
      </div>"""

    # ── Blocked banner ───────────────────────────────────────────────────────
    blocked_html = ""
    if "BLOCKED" in signal.upper():
        reasons = result.get("avoid_reasons", result.get("reason", []))
        if isinstance(reasons, list):
            reasons_str = " &bull; ".join(_esc(r) for r in reasons)
        else:
            reasons_str = _esc(str(reasons))
        blocked_html = f"""
      <div class="blocked-banner">
        🚫 <strong>TRADE BLOCKED BY SIGNAL 07 (AVOID)</strong><br>
        <small>{reasons_str}</small>
      </div>"""

    # ── Score guide ──────────────────────────────────────────────────────────
    guide_html = """
      <div class="guide-box">
        <div class="section-title">Score Guide (out of 95)</div>
        <div class="guide-row"><span class="dot" style="background:#00e676"></span><span>&ge;60 — STRONG BUY</span></div>
        <div class="guide-row"><span class="dot" style="background:#69f0ae"></span><span>&ge;45 — BUY</span></div>
        <div class="guide-row"><span class="dot" style="background:#ffd740"></span><span>&ge;30 — WATCH</span></div>
        <div class="guide-row"><span class="dot" style="background:#ffab40"></span><span>&ge;15 — WAIT</span></div>
        <div class="guide-row"><span class="dot" style="background:#ff5252"></span><span>&lt;15 — DO NOT TRADE</span></div>
        <div class="guide-row" style="margin-top:10px;padding-top:8px;border-top:1px solid #21262d">
          <span class="dot" style="background:#546e7a"></span>
          <span style="color:#8b949e;font-size:.8rem">Max: S01=15 S02=25 S03=5 S04=15 S05=10 S06=10 S09=10 S10=5 S12=8</span>
        </div>
      </div>"""

    # ── SVG gauge needle calculation ─────────────────────────────────────────
    angle_rad = math.radians(score_pct / 100 * 180)
    nx = round(100 + 70 * math.cos(math.radians(180) - angle_rad), 1)
    ny = round(100 - 70 * math.sin(angle_rad), 1)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gold Bot Dashboard — {_esc(ts[:10])}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0d1117;color:#e6edf3;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh;padding:20px}}
  a{{color:#ffd740}}

  /* ── Layout ── */
  .container{{max-width:960px;margin:0 auto}}
  .grid-2{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
  .grid-3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}}
  @media(max-width:700px){{.grid-2,.grid-3{{grid-template-columns:1fr}}}}

  /* ── Header ── */
  .header{{background:linear-gradient(135deg,#1a1f2e,#1e2a1a);border:1px solid #ffd74033;
           border-radius:12px;padding:24px 28px;margin-bottom:20px;
           display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px}}
  .header-left h1{{font-size:1.5rem;font-weight:700;color:#ffd740;letter-spacing:.5px}}
  .header-left .sub{{font-size:.85rem;color:#8b949e;margin-top:4px}}
  .etf-badge{{background:#ffd74022;border:1px solid #ffd74055;border-radius:8px;
              padding:8px 16px;font-size:.9rem;color:#ffd740;font-weight:600}}
  .ts{{font-size:.78rem;color:#8b949e;margin-top:4px;text-align:right}}

  /* ── Verdict card ── */
  .verdict-card{{background:{v_bg};border:2px solid {v_color}44;border-radius:12px;
                 padding:24px 28px;margin-bottom:20px;text-align:center}}
  .verdict-label{{font-size:.8rem;color:#8b949e;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px}}
  .verdict-signal{{font-size:2.4rem;font-weight:800;color:{v_color};letter-spacing:.5px;margin-bottom:8px}}
  .verdict-conf{{font-size:.9rem;color:#8b949e}}
  .verdict-action{{margin-top:16px;font-size:.95rem;color:#c9d1d9;line-height:1.6;
                   background:#ffffff08;border-radius:8px;padding:12px 16px;text-align:left}}

  /* ── Gauge ── */
  .gauge-card{{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:24px;margin-bottom:20px}}
  .section-title{{font-size:.82rem;text-transform:uppercase;letter-spacing:1px;color:#8b949e;margin-bottom:14px;font-weight:600}}
  .gauge-wrap{{position:relative;text-align:center;padding:10px 0 0}}
  .gauge-arc{{width:200px;height:105px;margin:0 auto;position:relative;overflow:hidden}}
  .gauge-arc svg{{width:100%;height:100%}}
  .gauge-number{{position:absolute;bottom:0;left:50%;transform:translateX(-50%);
                 font-size:2rem;font-weight:800;color:{bar_color}}}
  .gauge-max{{font-size:.9rem;color:#8b949e}}
  .zone-bar{{display:flex;height:10px;border-radius:6px;overflow:hidden;margin:16px 0 4px;gap:2px}}
  .zone-seg{{height:100%;border-radius:2px;transition:opacity .2s}}
  .thresh-row{{display:flex;justify-content:space-between;font-size:.72rem;color:#8b949e;text-align:center}}
  .score-summary{{margin-top:16px;border-top:1px solid #30363d;padding-top:14px}}
  .score-row{{display:flex;justify-content:space-between;font-size:.88rem;
              padding:5px 0;color:#c9d1d9;border-bottom:1px solid #21262d}}
  .score-row.bold{{font-weight:700;font-size:.95rem}}

  /* ── Signal cards ── */
  .signals-card{{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:24px;margin-bottom:20px}}
  .sig-card{{background:#0d1117;border:1px solid #21262d;border-radius:8px;
             padding:12px 14px;margin-bottom:10px}}
  .sig-header{{display:flex;align-items:center;gap:10px;margin-bottom:8px}}
  .sig-code{{font-size:.75rem;font-weight:700;background:#21262d;border-radius:4px;
             padding:2px 7px;color:#8b949e;letter-spacing:.5px}}
  .sig-label{{flex:1;font-size:.9rem;color:#c9d1d9}}
  .sig-pts{{font-size:1.1rem;font-weight:700}}
  .sig-max{{font-size:.75rem;color:#8b949e;font-weight:400}}
  .sig-sub{{font-size:.75rem;color:#8b949e;margin-bottom:6px;padding-left:2px}}
  .sig-bar-bg{{height:5px;background:#21262d;border-radius:3px;overflow:hidden}}
  .sig-bar-fill{{height:100%;border-radius:3px;transition:width .4s ease}}

  /* ── Trade box ── */
  .trade-box{{background:#0f1a0f;border:1px solid #00e67633;border-radius:12px;padding:20px;margin-bottom:16px}}
  .trade-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin:12px 0}}
  @media(max-width:500px){{.trade-grid{{grid-template-columns:1fr}}}}
  .trade-item{{background:#ffffff08;border-radius:8px;padding:12px;text-align:center}}
  .trade-item.green{{border:1px solid #00e67633}}
  .trade-item.red{{border:1px solid #ff525233}}
  .trade-lbl{{font-size:.75rem;color:#8b949e;margin-bottom:4px}}
  .trade-val{{font-size:1.2rem;font-weight:700;color:#e6edf3}}
  .trade-item.green .trade-val{{color:#00e676}}
  .trade-item.red .trade-val{{color:#ff5252}}
  .trade-note{{font-size:.78rem;color:#8b949e;margin-top:8px;text-align:center}}

  /* ── Trailing stop box ── */
  .trailing-box{{background:#0f1822;border:1px solid #ffd74033;border-radius:12px;padding:20px;margin-bottom:16px}}
  .ts-phase{{font-size:1rem;font-weight:700;margin-bottom:14px;letter-spacing:.3px}}
  .ts-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:12px}}
  @media(max-width:600px){{.ts-grid{{grid-template-columns:repeat(2,1fr)}}}}
  .ts-item{{background:#ffffff08;border-radius:8px;padding:10px;text-align:center}}
  .ts-lbl{{font-size:.72rem;color:#8b949e;margin-bottom:4px}}
  .ts-val{{font-size:1.05rem;font-weight:700;color:#e6edf3}}
  .ts-action{{font-size:.83rem;color:#c9d1d9;background:#ffffff06;border-radius:6px;
              padding:10px 12px;border-left:3px solid #ffd740;line-height:1.5}}

  /* ── Alert / blocked ── */
  .alert-box{{background:#3d1a0011;border:1px solid #ffab4044;border-radius:10px;
              padding:14px 16px;margin-bottom:16px;font-size:.9rem;color:#ffd740}}
  .blocked-banner{{background:#ff525211;border:1px solid #ff525244;border-radius:10px;
                   padding:16px;margin-bottom:16px;font-size:.9rem;color:#ff5252;line-height:1.6}}

  /* ── Guide box ── */
  .guide-box{{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:20px;margin-bottom:16px}}
  .guide-row{{display:flex;align-items:center;gap:10px;padding:5px 0;font-size:.87rem;color:#c9d1d9}}
  .dot{{width:10px;height:10px;border-radius:50%;flex-shrink:0}}

  /* ── Info card ── */
  .info-card{{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:20px;margin-bottom:16px}}
  .info-row{{display:flex;justify-content:space-between;padding:6px 0;
             font-size:.87rem;border-bottom:1px solid #21262d;color:#c9d1d9}}
  .info-row:last-child{{border-bottom:none}}
  .info-key{{color:#8b949e}}
  .info-val{{font-weight:600;text-align:right;max-width:60%}}

  /* ── Refresh btn ── */
  .refresh-bar{{text-align:center;margin:24px 0 8px}}
  .refresh-btn{{background:#ffd74022;border:1px solid #ffd74055;border-radius:8px;
                color:#ffd740;padding:10px 28px;font-size:.9rem;cursor:pointer;
                font-weight:600;text-decoration:none;display:inline-block}}
  .refresh-btn:hover{{background:#ffd74033}}

  /* ── Footer ── */
  .footer{{text-align:center;font-size:.78rem;color:#484f58;margin-top:24px;padding-bottom:8px}}

  /* ── Correlation monitor ── */
  .corr-card{{background:#161b22;border:1px solid #30363d;border-radius:12px;
              padding:20px 24px;margin-bottom:20px}}
  .corr-header,.corr-row{{display:grid;grid-template-columns:1.8fr .8fr .8fr 1.4fr 1.6fr;
                           gap:8px;align-items:center;padding:6px 0;
                           border-bottom:1px solid #21262d;font-size:.83rem}}
  .corr-header{{border-bottom:2px solid #30363d;padding-bottom:8px;margin-bottom:4px}}
  .corr-row:last-of-type{{border-bottom:none}}
  .corr-pair{{font-weight:600;color:#c9d1d9;font-size:.82rem}}
  .corr-val{{text-align:center;font-weight:700;font-size:.88rem;font-family:monospace}}
  .corr-val.dim{{color:#8b949e;font-weight:400}}
  .corr-band{{text-align:center;font-size:.75rem;color:#8b949e}}
  .corr-status{{font-size:.78rem;color:#c9d1d9}}
  .corr-section-title{{font-size:.72rem;text-transform:uppercase;letter-spacing:.8px;
                        color:#484f58;margin:12px 0 6px;padding-top:8px;
                        border-top:1px solid #21262d}}
  .break-row{{display:flex;gap:12px;padding:6px 0;border-bottom:1px solid #21262d;
              align-items:flex-start;font-size:.82rem}}
  .break-row:last-child{{border-bottom:none}}
  .break-pair{{font-weight:700;white-space:nowrap;min-width:90px;padding-top:1px}}
  .break-note{{color:#8b949e;line-height:1.4;flex:1}}
  .break-ok{{font-size:.84rem;color:#00e676;padding:6px 0}}
  .alert-badge{{display:flex;gap:12px;align-items:flex-start;padding:8px 12px;
                border:1px solid #30363d;border-radius:8px;margin-bottom:8px;
                background:#ffffff05}}
  .alert-badge:last-child{{margin-bottom:0}}
  @media(max-width:620px){{
    .corr-header,.corr-row{{grid-template-columns:1fr 1fr;}}
    .corr-band,.corr-val.dim{{display:none}}
  }}

  /* ── Scrollbar ── */
  ::-webkit-scrollbar{{width:6px}} ::-webkit-scrollbar-track{{background:#0d1117}}
  ::-webkit-scrollbar-thumb{{background:#30363d;border-radius:3px}}
</style>
</head>
<body>
<div class="container">

  <!-- HEADER -->
  <div class="header">
    <div class="header-left">
      <h1>🥇 Gold Bot Dashboard</h1>
      <div class="sub">Indian Gold ETF Trading Signal</div>
    </div>
    <div>
      <div class="etf-badge">{_esc(etf)}</div>
      <div class="ts">Last run: {_esc(ts)}</div>
    </div>
  </div>

  {blocked_html}
  {sell_html}

  <!-- VERDICT -->
  <div class="verdict-card">
    <div class="verdict-label">Final Verdict</div>
    <div class="verdict-signal">{_esc(signal)}</div>
    <div class="verdict-conf">Confidence: <strong style="color:#e6edf3">{_esc(conf)}</strong></div>
    {f'<div class="verdict-action">{_esc(action)}</div>' if action else ''}
  </div>

  <!-- TRADE PARAMS -->
  {trade_html}

  <!-- TRAILING STOP -->
  {ts_html}

  <!-- CORRELATION MONITOR (Signal 12) -->
  {corr_monitor_html}

  <div class="grid-2">
    <!-- LEFT: GAUGE + SCORE SUMMARY -->
    <div>
      <div class="gauge-card">
        <div class="section-title">📈 Composite Score</div>
        <div class="gauge-wrap">
          <div class="gauge-arc">
            <svg viewBox="0 0 200 105" xmlns="http://www.w3.org/2000/svg">
              <!-- background arc -->
              <path d="M10,100 A90,90 0 0,1 190,100" fill="none" stroke="#21262d" stroke-width="16" stroke-linecap="round"/>
              <!-- score arc -->
              <path d="M10,100 A90,90 0 0,1 190,100" fill="none" stroke="{bar_color}" stroke-width="16"
                    stroke-linecap="round"
                    stroke-dasharray="{round(score_pct/100*283,1)} 283"/>
              <!-- needle -->
              <line x1="100" y1="100" x2="{nx}" y2="{ny}"
                    stroke="#ffd740" stroke-width="2.5" stroke-linecap="round"/>
              <circle cx="100" cy="100" r="5" fill="#ffd740"/>
            </svg>
            <div class="gauge-number">{final:.0f}<span class="gauge-max">/{MAX_SCORE}</span></div>
          </div>
        </div>
        <div class="zone-bar">{zone_bars}</div>
        {thresholds}
        {score_table}
      </div>
      {guide_html}
    </div>

    <!-- RIGHT: SIGNAL BREAKDOWN -->
    <div>
      <div class="signals-card">
        <div class="section-title">🔍 Signal Breakdown</div>
        {cards_html}
        {pen_html}
      </div>
    </div>
  </div>

  <!-- BOT INFO -->
  <div class="info-card">
    <div class="section-title">⚙️ Bot Configuration</div>
    <div class="info-row"><span class="info-key">ETF</span><span class="info-val">{_esc(etf)}</span></div>
    <div class="info-row"><span class="info-key">Profit Target</span><span class="info-val" style="color:#00e676">+{cfg.get('profit_target_pct',3.0)}%</span></div>
    <div class="info-row"><span class="info-key">Stop Loss</span><span class="info-val" style="color:#ff5252">-{cfg.get('stop_loss_pct',1.0)}%</span></div>
    <div class="info-row"><span class="info-key">Hold Period</span><span class="info-val">1–5 trading days</span></div>
    <div class="info-row"><span class="info-key">Transaction Cost</span><span class="info-val">~0.755% round-trip</span></div>
    <div class="info-row"><span class="info-key">Max Score</span><span class="info-val">{MAX_SCORE} pts (9 signals + S12)</span></div>
    <div class="info-row"><span class="info-key">Run At</span><span class="info-val">{_esc(ts)}</span></div>
  </div>

  <!-- REFRESH -->
  <div class="refresh-bar">
    <span class="refresh-btn" onclick="location.reload()">🔄 Refresh Page</span>
  </div>

  <div class="footer">Gold Bot · Indian Gold ETF Strategy · {_esc(ts[:4])} · Run <code>python3 run_signal_08.py</code> to update</div>

</div>
</body>
</html>"""

    return html


# =============================================================================
# WRITE DASHBOARD FILE
# =============================================================================

def write_dashboard(result: dict, config: Optional[dict] = None,
                    output_path: Optional[str] = None) -> str:
    """
    Generate dashboard.html from Signal 08 result dict.
    Returns the path to the written file.
    """
    if output_path is None:
        output_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "dashboard.html"
        )

    html = build_html(result, config)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path
