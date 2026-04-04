# =============================================================================
# GOLD BOT — dashboard_writer.py
# Generates a self-contained HTML dashboard from Signal 08 result dict.
# Called automatically by run_signal_08.py after every run.
# Output: gold_bot/dashboard.html  (open directly in any browser)
# =============================================================================

import os
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
    if pct >= 80:  col = "#00e676"
    elif pct >= 50: col = "#ffd740"
    elif pct > 0:  col = "#ffab40"
    else:          col = "#546e7a"
    return col

def _esc(s) -> str:
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")


# =============================================================================
# HTML BUILDER
# =============================================================================

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

    score_pct   = round((final / 80) * 100, 1)
    v_color     = _verdict_color(signal)
    v_bg        = _verdict_bg(signal)
    bar_color   = _score_color(score_pct)

    # Signal score rows
    sig_rows = [
        ("S01", "Buy the Dip",     scores.get("s01", {}), 15),
        ("S02", "Macro Trigger",   scores.get("s02", {}), 25),
        ("S03", "Seasonality",     scores.get("s03", {}),  5),
        ("S04", "Bollinger Bands", scores.get("s04", {}), 15),
        ("S05", "2026 Outlook",    scores.get("s05", {}), 10),
        ("S06", "Weekly Routine",  scores.get("s06", {}), 10),
    ]

    def signal_card(code, label, sc, mx):
        pts   = sc.get("pts", 0)
        col   = _signal_badge(pts, mx)
        bar_w = round((pts / mx * 100) if mx else 0)
        return f"""
        <div class="sig-card">
          <div class="sig-header">
            <span class="sig-code">{_esc(code)}</span>
            <span class="sig-label">{_esc(label)}</span>
            <span class="sig-pts" style="color:{col}">{pts:.0f}<span class="sig-max">/{mx}</span></span>
          </div>
          <div class="sig-bar-bg">
            <div class="sig-bar-fill" style="width:{bar_w}%;background:{col}"></div>
          </div>
        </div>"""

    cards_html = "".join(signal_card(c, l, s, m) for c, l, s, m in sig_rows)

    # Trade parameters
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

    # Sell alert
    sell_html = ""
    if result.get("sell_alert"):
        sell_html = f"""
      <div class="alert-box">
        ⚡ <strong>EXIT ALERT:</strong> {_esc(result['sell_alert'])}
      </div>"""

    # Score gauge segments
    zones = [
        (15, "#ff5252", "No Trade"),
        (15, "#ffab40", "Wait"),
        (15, "#ffd740", "Watch"),
        (15, "#69f0ae", "Buy"),
        (20, "#00e676", "Strong Buy"),
    ]
    zone_bars = ""
    for width_pts, col, lbl in zones:
        w = round(width_pts / 80 * 100)
        zone_bars += f'<div class="zone-seg" style="width:{w}%;background:{col}" title="{lbl}"></div>'

    # Score thresholds row
    thresholds = """
      <div class="thresh-row">
        <span>0</span><span>15<br><small>WAIT</small></span>
        <span>30<br><small>WATCH</small></span>
        <span>45<br><small>BUY</small></span>
        <span>60<br><small>STR BUY</small></span>
        <span>80</span>
      </div>"""

    # S07 penalty row
    pen_color = "#ff5252" if pen >= 20 else ("#ffab40" if pen > 0 else "#546e7a")
    pen_html = f"""
        <div class="sig-card" style="border-color:{pen_color}33">
          <div class="sig-header">
            <span class="sig-code">S07</span>
            <span class="sig-label">Risk Gate Penalty</span>
            <span class="sig-pts" style="color:{pen_color}">-{pen:.0f}<span class="sig-max">/80</span></span>
          </div>
        </div>"""

    # Score table summary
    score_table = f"""
      <div class="score-summary">
        <div class="score-row"><span>Raw Score</span><span>{raw:.1f} / 80</span></div>
        <div class="score-row"><span>S07 Penalty</span><span style="color:#ffab40">-{pen:.1f} pts</span></div>
        <div class="score-row bold"><span>Final Score</span><span style="color:{bar_color}">{final:.1f} / 80</span></div>
        <div class="score-row"><span>Normalized</span><span>{score_pct}%</span></div>
      </div>"""

    # Blocked banner
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

    # Threshold guide
    guide_html = """
      <div class="guide-box">
        <div class="section-title">Score Guide</div>
        <div class="guide-row"><span class="dot" style="background:#00e676"></span><span>&ge;60 — STRONG BUY</span></div>
        <div class="guide-row"><span class="dot" style="background:#69f0ae"></span><span>&ge;45 — BUY</span></div>
        <div class="guide-row"><span class="dot" style="background:#ffd740"></span><span>&ge;30 — WATCH</span></div>
        <div class="guide-row"><span class="dot" style="background:#ffab40"></span><span>&ge;15 — WAIT</span></div>
        <div class="guide-row"><span class="dot" style="background:#ff5252"></span><span>&lt;15 — DO NOT TRADE</span></div>
      </div>"""

    needle_deg = round((final / 80) * 180 - 90)

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
              <line x1="100" y1="100"
                    x2="{round(100 + 70*__import__('math').cos(__import__('math').radians(180 - score_pct/100*180)),1)}"
                    y2="{round(100 - 70*__import__('math').sin(__import__('math').radians(score_pct/100*180)),1)}"
                    stroke="#ffd740" stroke-width="2.5" stroke-linecap="round"/>
              <circle cx="100" cy="100" r="5" fill="#ffd740"/>
            </svg>
            <div class="gauge-number">{final:.0f}<span class="gauge-max">/80</span></div>
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
