# Signal 12 — Correlation Break Alert
## Planning Document (No Code — Strategy Design Only)
### Version 1.0 | April 2026

---

## 1. PURPOSE AND ROLE IN THE BOT

Gold does not move in isolation. It has historically strong, **predictable relationships**
with a small set of global instruments. When these relationships break down,
it is one of the most powerful signals in existence — because correlation breaks
almost always precede large directional moves.

Signal 12 monitors four key correlations in real time and alerts when any of them
breaks its normal range. It is a **confirmation and warning system**, not a standalone buy signal.

> "If gold is rising while DXY is also rising, something unusual is happening.
> Either gold is right and DXY will fall, or gold is wrong and will reverse.
> Either way — PAY ATTENTION."

---

## 2. THE FOUR CORE CORRELATIONS

### Correlation 1: GOLDBEES ↔ COMEX Gold (GC=F)
**Normal state**: Strong positive correlation (+0.90 to +0.99 over 20 days)
GOLDBEES is 99% driven by COMEX. They move together almost perfectly.

**Break signal**: 20-day rolling correlation drops below +0.75
**What it means**:
- India-specific premium/discount events (festival demand surge, import duty change)
- Currency disruption (sharp INR move decoupled from gold price)
- Liquidity issue in GOLDBEES units (ETF redemption pressure or creation lag)

**Trading implication**:
- If GOLDBEES < COMEX fair value and correlation breaks → ARBITRAGE BUY opportunity
- If GOLDBEES > COMEX fair value and correlation breaks → Overpriced, DO NOT BUY
- Pair with S10 MCX Spread for confirmation

---

### Correlation 2: GOLDBEES ↔ DXY (DX-Y.NYB)
**Normal state**: Moderate negative correlation (-0.40 to -0.80 over 20 days)
Strong dollar = weak gold. This is the primary macro relationship for gold.

**Break signal**: 20-day rolling correlation rises above -0.20 (approaching zero or positive)
**What it means** (when DXY is strong but gold also rises):
- **Scenario A — Flight to Safety**: Both dollar AND gold bid simultaneously.
  Happens during extreme geopolitical stress (war, banking crisis, pandemic shock).
  Gold is acting as a crisis hedge, not a dollar hedge.
  → BULLISH for gold. Both assets reflect fear. S05 geopolitical score should be high.

- **Scenario B — Dollar Losing Reserve Status**: Rare but powerful.
  USD weakening in global confidence even as DXY index holds up.
  → VERY BULLISH for gold. Watch for central bank buying news.

- **Scenario C — False Break / Noise**: Happens in choppy, low-volatility markets.
  No geopolitical trigger, just random co-movement for a few days.
  → IGNORE. Check if S05 tension score is below 10.

**What it means** (when DXY is weak but gold also falls):
- **Scenario D — Risk-On Mode**: Both dollar AND gold sold as investors chase equities.
  → BEARISH for gold in short term. Not time to buy.
  Wait for risk appetite to cool.

---

### Correlation 3: GOLDBEES ↔ USDINR (USDINR=X)
**Normal state**: Moderate positive correlation (+0.30 to +0.70 over 20 days)
Weaker rupee (higher USDINR) = more expensive gold imports = higher GOLDBEES price in INR.

**Break signal**: 20-day rolling correlation drops below +0.10 (near zero or negative)
**What it means** (when rupee weakens but GOLDBEES doesn't rise):
- Import duty or tax policy change capping gold price in India
- RBI intervention suppressing the USDINR move
- GOLDBEES premium compression (ETF-specific, not gold price issue)
- → CAUTION: GOLDBEES may be artificially held down. Real gold still higher.
- → Opportunity: GOLDBEES could catch up to fair value = potential BUY

**What it means** (when rupee strengthens but GOLDBEES rises anyway):
- Strong global gold demand overriding favorable INR move
- COMEX rally is so strong it overwhelms the FX tailwind
- → BULLISH signal: Gold momentum is very strong globally

---

### Correlation 4: GOLDBEES ↔ Nifty 50 (^NSEI)
**Normal state**: Low to slightly negative correlation (-0.10 to -0.30 over 20 days)
Stocks and gold are mild hedges against each other in normal markets.

**Break signal**: Correlation becomes strongly positive (> +0.40) OR strongly negative (< -0.50)
**Strongly positive (both gold AND stocks up)**:
- Liquidity surge: Easy money lifting all assets simultaneously
- → CAUTION: This is not "true" gold demand. Gold rise may not be sustainable.
- Usually reverses when liquidity tightens. Wait for divergence.

**Strongly negative (gold up, stocks sharply down)**:
- Classic flight to safety. Gold acting as crisis hedge.
- → BULLISH for gold. Institutional money rotating from equity to gold.
- → HIGH CONVICTION buy if other signals also aligned.

**Strongly negative (gold down, stocks sharply up)**:
- Risk-on rally. Investors dumping safe havens.
- → BEARISH for gold. Wait for rotation back.

---

## 3. HOW CORRELATIONS ARE CALCULATED

### Rolling window
Use 20-day rolling Pearson correlation as the primary window.
Also compute 10-day rolling correlation as a short-term early warning.

### Data needed
| Instrument | yfinance ticker | Fields |
|-----------|----------------|--------|
| GOLDBEES | GOLDBEES.NS | Adj Close daily |
| COMEX Gold | GC=F | Adj Close daily |
| DXY | DX-Y.NYB | Adj Close daily |
| USDINR | USDINR=X | Adj Close daily |
| Nifty 50 | ^NSEI | Adj Close daily |

All fetched independently for the last 60 days (20-day correlation needs 20 days minimum;
60 days gives historical context).

### Daily return series
Correlation is computed on **daily percentage returns**, not raw prices.
Raw price correlation is misleading because of trends.
`return_t = (price_t - price_{t-1}) / price_{t-1}`

### Thresholds for "break" detection
Each correlation has a **normal band** (based on historical 2-year average) and a **break threshold**:

| Correlation Pair | Normal Band | Break Threshold | Alert Level |
|-----------------|-------------|-----------------|-------------|
| GOLDBEES ↔ COMEX | +0.85 to +0.99 | < +0.75 | HIGH |
| GOLDBEES ↔ DXY | -0.40 to -0.80 | > -0.20 | MEDIUM |
| GOLDBEES ↔ USDINR | +0.30 to +0.70 | < +0.10 | MEDIUM |
| GOLDBEES ↔ NIFTY | -0.10 to -0.30 | > +0.40 or < -0.50 | MEDIUM |

If 2+ correlations break simultaneously → **HIGH ALERT** (compound break)
If GOLDBEES-COMEX breaks → always HIGH regardless of others (most important)

---

## 4. SCORING LOGIC (INTEGRATION WITH SIGNAL 08)

Signal 12 contributes up to **8 points** to the composite score.
New max composite = 95 + 8 = **103 points**.

| Condition | Points | Interpretation |
|-----------|--------|----------------|
| No correlations breaking | +5 | Normal regime, signal relationships valid |
| 1 correlation breaking — bullish implication | +8 | Unusual alignment, EXTRA bullish |
| 1 correlation breaking — bearish implication | +0 | Caution, reduce confidence |
| 1 correlation breaking — ambiguous | +3 | Flag for human review |
| 2+ correlations breaking — bullish | +8 | Rare, very high confidence setup |
| 2+ correlations breaking — bearish | -5 | Penalty (overrides other bullish signals) |
| 2+ correlations breaking — mixed | +0 | Cannot interpret, DATA FLAG |
| DATA UNAVAILABLE (any fetch fails) | +0 | No score, no penalty |

Note: Signal 12 can issue a **penalty** (-5 pts) when multiple correlations break bearishly.
This is the only signal in the bot allowed to penalize (like S07) based on its reading.

---

## 5. COMPOUND ALERT CONDITIONS

Define pre-set alert combinations the bot watches for:

### Alert Type A — "Crisis Gold" (STRONG BUY addition)
- GOLDBEES-DXY correlation breaks positive (both up together)
- AND GOLDBEES-NIFTY correlation < -0.50 (gold up, stocks down)
- AND S05 geopolitical score ≥ 1 pt
- → Interpretation: Classic flight-to-safety. Institutional rotation into gold.
- → Dashboard alert: 🚨 CRISIS GOLD SETUP — Correlation break confirms panic buying

### Alert Type B — "Arbitrage Window" (STRONG BUY addition)
- GOLDBEES-COMEX correlation < +0.75 (unusual divergence)
- AND S10 MCX spread shows FAIR VALUE or DISCOUNT (GOLDBEES cheap vs COMEX)
- → Interpretation: GOLDBEES is lagging COMEX. Should catch up.
- → Dashboard alert: ⚡ ARBITRAGE WINDOW — GOLDBEES lagging COMEX by X%

### Alert Type C — "Liquidity Trap" (AVOID signal)
- GOLDBEES-NIFTY correlation > +0.40 (both rising together)
- AND composite score ≥ 45 (bot thinks it's a BUY)
- → Interpretation: Gold rising on liquidity, not fundamentals. Risky entry.
- → Dashboard alert: ⚠️ LIQUIDITY TRAP — Gold and stocks co-moving. Not true demand.

### Alert Type D — "Risk-On Dump" (WAIT signal)
- GOLDBEES-NIFTY correlation < -0.50 AND Nifty trending UP
- Gold falling while stocks rally
- → Interpretation: Risk-on environment. Gold being sold.
- → Dashboard alert: 🔴 RISK-ON MODE — Gold under selling pressure from equity rotation

### Alert Type E — "Silent Bull" (WATCH → BUY upgrade)
- GOLDBEES-USDINR correlation breaks negative (gold rising, rupee strengthening)
- This means COMEX rally is overwhelming FX tailwind
- AND COMEX 5d change > +1%
- → Interpretation: Global gold demand so strong it doesn't need INR weakness.
- → Dashboard alert: 📈 SILENT BULL — Gold rising despite strong rupee. COMEX-led.

---

## 6. HISTORICAL CALIBRATION

Before using fixed thresholds, the thresholds must be validated historically.

### Questions to answer via backtesting
1. What is the 2-year average and standard deviation of each correlation?
2. How often does each correlation break per year? (want: rare enough to be meaningful)
3. When GOLDBEES-COMEX correlation breaks, does GOLDBEES subsequently catch up within 5 days?
   (validating the Arbitrage Window logic)
4. When both correlations break bullishly (Alert Type A), what was the 5-day outcome?
5. What is the optimal break threshold for each pair?

### Calibration data period
Use 2020–2025 (5 years). Period includes:
- COVID crash (March 2020) — extreme correlation breaks
- Gold peak (August 2020) — correlation normalization
- Post-COVID reflation (2021) — risk-on, gold pressure
- Russia-Ukraine (2022) — flight to safety episode
- Fed hiking cycle (2022–2023) — dollar dominance
- Fed pivot / rate cut expectations (2024)
- 2025 current regime

Each major episode should show characteristic correlation breaks for validation.

---

## 7. NON-TRADING DAY BEHAVIOR

Same rule as all signals in this bot:
Friday and weekends → Signal 12 runs but issues no score contribution.
Correlations are still computed and displayed on dashboard for information.
Score contribution = 0 on non-trading days.

---

## 8. DATA FAILURE HANDLING

| Failure Scenario | Handling |
|-----------------|---------|
| yfinance fails for COMEX | GOLDBEES-COMEX correlation = DATA UNAVAILABLE, score = 0, no penalty |
| yfinance fails for DXY | That correlation skipped, others computed normally |
| Fewer than 15 days of data returned | Correlation unreliable, mark all as DATA UNAVAILABLE |
| Returns series has NaN gaps (missing days) | Drop NaN rows before computing correlation |
| Correlation exactly at boundary (e.g. -0.20) | Round to 2 decimal places, use strict inequality |
| All 4 correlations unavailable | Signal 12 = DATA UNAVAILABLE, contributes 0 pts to composite |
| Partial availability (2 of 4) | Compute score from available pairs only, flag partial in dashboard |

---

## 9. DASHBOARD DISPLAY

Signal 12 needs a dedicated dashboard section showing all four correlation values
with color coding:

```
📡 CORRELATION MONITOR
──────────────────────────────────────────────
GOLDBEES ↔ COMEX    +0.94   🟢 NORMAL
GOLDBEES ↔ DXY      -0.61   🟢 NORMAL
GOLDBEES ↔ USDINR   +0.45   🟢 NORMAL
GOLDBEES ↔ NIFTY    -0.08   🟢 NORMAL

Status: ALL CORRELATIONS NORMAL
Regime: Standard (signals reliable)
S12 Score: 5/8 pts
──────────────────────────────────────────────

(Example break scenario)
GOLDBEES ↔ DXY      +0.12   🔴 BREAK (expected: negative)
  → Gold rising WITH dollar — possible crisis signal
  → Cross-check S05 geopolitical score: 1.5/2 (HIGH TENSION)
  → ALERT TYPE A: CRISIS GOLD SETUP
S12 Score: 8/8 pts (EXTRA BULLISH)
```

Color coding:
- Green: Correlation within normal band
- Yellow: Correlation approaching break threshold (warning zone)
- Red: Correlation has broken threshold — interpret carefully
- Grey: DATA UNAVAILABLE

---

## 10. TELEGRAM ALERT INTEGRATION

Signal 12 sends Telegram alerts only for compound breaks (Alert Types A–E).
Single correlation breaks get dashboard display only (not Telegram, to avoid alert fatigue).

Telegram message format for Alert Type A:
```
🚨 GOLD BOT — CRISIS GOLD SETUP DETECTED

Signal 12 Correlation Break:
• Gold-DXY correlation: +0.12 (BROKEN — both rising)
• Gold-Nifty correlation: -0.52 (stocks falling, gold rising)
• Geopolitical tension: HIGH

Interpretation: Institutional flight-to-safety rotation into gold.
Action: Review full bot signal. If composite ≥ 45, HIGH CONFIDENCE BUY.

Composite Score: 71/103 → STRONG BUY
```

---

## 11. INTEGRATION WITH OTHER SIGNALS

### Works best when combined with:
- **S02 Macro Trigger**: GOLDBEES-DXY break + S02 bullish = very high confidence
- **S05 2026 Outlook**: GOLDBEES-DXY break + high geopolitical tension = Crisis Gold validated
- **S09 Volume**: GOLDBEES-COMEX break + high volume = real divergence (not noise)
- **S10 MCX Spread**: GOLDBEES-COMEX break + DISCOUNT spread = Arbitrage Window validated

### Conflicts to watch:
- If S12 gives +8 pts (correlation break bullish) but S07 blocks the trade → S07 wins. No entry.
- If S12 gives -5 pts penalty + S08 composite was exactly 45 → final score drops to 40. WATCH only.
- If S12 is DATA UNAVAILABLE → do not reduce confidence. Simply run without S12 contribution.

---

## 12. FILES NEEDED

| File | Purpose |
|------|---------|
| `signal_12_correlation_break.py` | Core engine — fetch 5 instruments, compute 4 correlations, score |
| `run_signal_12.py` | Standalone launcher for testing |
| `signal_08_verdict_score.py` | Add `_load_signal_12()` and `score_signal_12()` (same pattern as S09/S10) |
| `dashboard_writer.py` | Add Correlation Monitor section to HTML dashboard |

---

## 13. IMPLEMENTATION ORDER (FOR FUTURE CODING SESSION)

1. Build historical correlation calibration notebook (answer the 5 calibration questions)
2. Define final break thresholds based on calibration (confirm or adjust defaults above)
3. Build `signal_12_correlation_break.py` with all 4 correlations + scoring logic
4. Build all 5 Alert Type detections
5. Wire into Signal 08 via `_load_signal_12()` and `score_signal_12()`
6. Add correlation monitor section to `dashboard_writer.py`
7. Add Telegram compound break alerts
8. Build `run_signal_12.py` standalone launcher
9. Run live for 2 weeks in observation mode (no score contribution yet)
10. After 2 weeks of live data, validate thresholds match real-world behavior
11. Enable score contribution (set max_pts = 8 in config)

---

## 14. CONFIGURATION VALUES (in config.py)

```python
# Signal 12 — Correlation Break Alert
"s12_enabled": True,
"s12_lookback_days": 60,           # Days of data to fetch
"s12_rolling_window": 20,          # Days for rolling correlation
"s12_early_warning_window": 10,    # Short-window early warning

# Break thresholds (tunable after calibration)
"s12_comex_break_threshold": 0.75,
"s12_dxy_break_threshold": -0.20,
"s12_usdinr_break_threshold": 0.10,
"s12_nifty_positive_break": 0.40,
"s12_nifty_negative_break": -0.50,

# Scoring
"s12_max_pts": 8,
"s12_penalty_pts": -5,             # Applied for 2+ bearish breaks
```

---

## 15. EDGE CASES NOT COVERED BY OTHER SIGNALS

Signal 12 uniquely catches scenarios that S01–S10 cannot:

| Scenario | How S12 catches it | Other signals miss it because |
|----------|-------------------|------------------------------|
| India-specific ETF premium compression | GOLDBEES-COMEX break | S10 only looks at today's premium, not trend |
| Flight-to-safety institutional flow | DXY-GOLDBEES both up | S02 only looks at DXY direction, not gold-DXY relationship |
| Risk-on environment where gold sells off | NIFTY-GOLDBEES negative break | No other signal directly monitors equity-gold rotation |
| Rupee crisis where gold doesn't benefit | USDINR-GOLDBEES break | No other signal monitors FX-gold relationship |
| Liquidity-driven co-movement (false gold rally) | NIFTY-GOLDBEES positive break | Every other signal would look bullish in this scenario |

---

*End of Signal 12 Planning Document*
