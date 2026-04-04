# Signal 11 — ML Backtester
## Planning Document (No Code — Strategy Design Only)
### Version 1.0 | April 2026

---

## 1. PURPOSE AND ROLE IN THE BOT

The ML Backtester is not a real-time trading signal.
It is a **retrospective evaluation engine** that runs periodically (weekly or monthly)
to answer one core question:

> "Which combination of our signals has actually predicted profitable trades in the past,
> and what thresholds give the best win rate at the lowest risk?"

Its output feeds back into Signal 08 as **dynamic weight adjustments** —
so the bot becomes smarter over time instead of using fixed weights forever.

---

## 2. WHAT PROBLEM IT SOLVES

### Current limitation
All signals S01–S10 have fixed point allocations decided by human judgment.
S02 (Macro Trigger) gets 25 pts. S03 (Seasonality) gets 5 pts.
These weights are educated guesses, not data-validated.

### What the backtester tells us
- Which signals actually predict +2% moves within 5 days on GOLDBEES
- Which signals are noise (high score but no outcome correlation)
- What composite score threshold gives the best win rate
- How many false positives we get per quarter
- Whether some signals work better in certain months/regimes

---

## 3. DATA REQUIREMENTS

### 3A. Historical GOLDBEES price data
- **Source**: yfinance (`GOLDBEES.NS`)
- **Period**: Minimum 3 years, ideally 5 years (2020–2025)
- **Fields needed**: Date, Open, High, Low, Close, Volume, Adjusted Close
- **Frequency**: Daily (1d interval)
- **Edge case**: Missing days = Indian market holidays. Must handle gaps without filling.
- **Edge case**: Stock splits/adjustments. Use Adjusted Close only for return calculation.
- **Edge case**: Pre-2020 data may be sparse or unreliable for GOLDBEES. Set hard floor at Jan 2020.

### 3B. Historical signal scores (reconstructed)
Since we cannot go back in time and run the bot on past dates,
we must **reconstruct** each signal's score for every historical date.

| Signal | How to Reconstruct Historically |
|--------|----------------------------------|
| S01 Buy the Dip | Re-run Bollinger/RSI/dip logic on historical OHLCV |
| S02 Macro Trigger | Pull historical FRED data (FEDFUNDS, DXY) for each date |
| S03 Seasonality | Pure calendar logic — trivial, exact same code |
| S04 Bollinger Bands | Re-run on historical OHLCV window |
| S05 2026 Outlook | Macro regime classification — manually label 3–4 regimes |
| S06 Weekly Routine | Calendar logic + historical COMEX weekly changes |
| S07 Risk Gate | Re-run COMEX/VIX/spread checks on historical data |
| S08 Composite | Compute from reconstructed S01–S07 |
| S09 Volume | Re-run on historical volume data (available via yfinance) |
| S10 MCX Spread | Re-run with historical COMEX + USDINR + GOLDBEES prices |

**Important**: Each signal must be reconstructed using only data available *at that point in time*,
not future data. This is the look-ahead bias rule.

### 3C. Outcome labels
For each date D, the label is:
- **WIN**: Max High in D+1 to D+5 ≥ entry price × (1 + profit_target_pct)
- **STOP**: Min Low in D+1 to D+5 ≤ entry price × (1 - stop_loss_pct) [hit before target]
- **TIMEOUT**: Neither target nor stop hit in 5 days. Mark as neutral/loss depending on final close.

Entry price = Close on day D (bot signal day). This assumes next-day open is close, conservative.
Better: Entry price = Open of day D+1 (more realistic — you act on next morning open).

---

## 4. MACHINE LEARNING APPROACH OPTIONS

### Option A — Logistic Regression (Recommended for v1)
**What**: Binary classifier. Input = [S01_pts, S02_pts, ..., S10_pts, day_of_week, month].
Output = probability of WIN.

**Why**: Transparent. Each coefficient shows which signal matters most.
Fast to train. No overfitting risk on small dataset (~750 trading days in 3 years).
Threshold tunable (e.g., only trade if P(win) > 0.65).

**Limitations**: Assumes linear relationships between signals and outcome.
Cannot capture interactions (e.g., S03 only matters when S02 is high).

### Option B — Gradient Boosting (XGBoost / LightGBM)
**What**: Tree-based ensemble. Handles non-linear relationships and feature interactions.

**Why**: Better accuracy than logistic regression on tabular financial data.
Naturally finds that "S03 high AND S02 high = better than either alone."
Feature importance ranking built-in.

**Limitations**: Needs more data to generalize. With 750 rows, risk of overfitting.
Less interpretable. Must use cross-validation carefully.

### Option C — Rule-Based Threshold Optimizer (Non-ML, but data-driven)
**What**: No model. Instead, grid-search the composite score threshold.
Test every threshold from 30 to 70 (step 1). For each, compute win rate, trade count, avg return.
Pick the threshold with best Sharpe ratio.

**Why**: Fully transparent. No model to explain to yourself. Very robust on small data.
Also doubles as a sanity check for any ML model.

**Recommendation**: Run Option C first (always). Then Option A. Compare. If Option A beats Option C
by >5% win rate with same trade count, adopt it.

---

## 5. FEATURE ENGINEERING

Beyond raw signal scores, add derived features:

| Feature | Formula | Reason |
|---------|---------|--------|
| composite_score | Sum of all signal pts | Core predictor |
| score_percentile | Rank of today's score vs last 90 days | Context-adjusted |
| s01_s04_combo | S01_pts + S04_pts | Technical convergence |
| s02_s05_combo | S02_pts + S05_pts | Macro convergence |
| s09_positive | 1 if S09 ≥ 5 else 0 | Volume confirmation binary |
| s10_fair_value | 1 if S10 = 5 else 0 | Spread is fair (not overpriced) |
| month_num | 1–12 | Seasonal regime |
| day_of_week | 0=Mon to 3=Thu | Entry day affects outcome (Mon better) |
| prior_trade_result | WIN/STOP/TIMEOUT of previous trade | Regime momentum |
| goldbees_5d_momentum | (Close - Close_5d_ago) / Close_5d_ago | Is gold already trending? |
| volume_5d_avg_ratio | Today volume / 5d avg | Not same as S09, broader check |

---

## 6. VALIDATION METHODOLOGY

### 6A. Walk-Forward Validation (mandatory)
Do NOT use a random train/test split. Financial data is time-ordered.

Split into rolling windows:
- Window 1: Train on Jan 2020 – Dec 2021 → Test on Jan–Jun 2022
- Window 2: Train on Jan 2020 – Jun 2022 → Test on Jul–Dec 2022
- Window 3: Train on Jan 2020 – Dec 2022 → Test on 2023
- Window 4: Train on Jan 2020 – Dec 2023 → Test on 2024
- Window 5: Train on Jan 2020 – Dec 2024 → Test on Jan–Apr 2025

Average win rate across all test windows = true out-of-sample win rate.

### 6B. Metrics to track per window

| Metric | Formula | Target |
|--------|---------|--------|
| Win Rate | Wins / Total trades | >60% |
| Trade Count | Trades triggered per quarter | >5 (need enough signal) |
| Avg Win Return | Mean gain on wins | >2.5% net after 0.755% cost |
| Avg Loss Return | Mean loss on stops | < -1.5% |
| Profit Factor | Gross wins / Gross losses | >1.5 |
| Max Drawdown | Worst consecutive losing streak | <4 trades |
| Sharpe (weekly) | Avg weekly return / Std dev | >0.8 |
| False Positive Rate | Trades that hit stop / Total | <30% |

### 6C. Benchmark comparison
Always compare ML model results vs two baselines:
1. **Buy and Hold GOLDBEES** over the same period
2. **Fixed threshold bot** (current strategy, threshold = 45/95)

If ML model does not beat baseline 2 by ≥5% win rate, do not switch to ML weights.

---

## 7. REGIME DETECTION (CRITICAL COMPONENT)

The single biggest insight in gold trading is that signals mean different things in different regimes.
S02 (Macro) matters more in a hiking-rate environment than a cutting-rate environment.
S03 (Seasonality) matters more in normal years than during geopolitical crises.

### Regime classification

| Regime | Definition | Detection Method |
|--------|-----------|-----------------|
| RATE_HIKE_CYCLE | Fed hiking, DXY strong, gold under pressure | FEDFUNDS 6M change > +0.5% |
| RATE_CUT_CYCLE | Fed cutting, DXY weak, gold tailwind | FEDFUNDS 6M change < -0.5% |
| RATE_PAUSE | Fed on hold, mixed signals | Neither above condition |
| GEOPOLITICAL_STRESS | News tension score chronically high | S05 O1 tension > 30 for 30+ days |
| NORMAL | None of above | Default |

### How regime affects ML model
Train **separate models per regime**, or add regime as a one-hot feature.
In RATE_CUT_CYCLE, S02 weight should be higher. In GEOPOLITICAL_STRESS, S05 should dominate.
In RATE_PAUSE (like Q1 2026), composite score and volume matter more than macro.

---

## 8. OUTPUT: WEIGHT ADJUSTMENT RECOMMENDATIONS

The backtester does not automatically change weights. It produces a report:

```
=== ML BACKTESTER REPORT — April 2026 ===

BEST THRESHOLD (data-driven): 52/95 pts
  → Win rate at 52+: 67.3%  (vs 58.1% at current 45)
  → Trade frequency: 18 trades per quarter (vs 24 at 45)
  → False positive rate: 28.4%

SIGNAL IMPORTANCE RANKING:
  1. S02 Macro Trigger      — coefficient +0.42  [weight justified]
  2. S09 Volume Confirm     — coefficient +0.38  [UNDERWEIGHTED — consider +3pts]
  3. S04 Bollinger Bands    — coefficient +0.31  [weight justified]
  4. S01 Buy the Dip        — coefficient +0.27  [weight justified]
  5. S10 MCX Spread         — coefficient +0.21  [slightly underweighted]
  6. S03 Seasonality        — coefficient +0.18  [weight justified]
  7. S05 2026 Outlook       — coefficient +0.12  [weight OK, regime-dependent]
  8. S06 Weekly Routine     — coefficient +0.08  [OVERWEIGHTED — may reduce]

REGIME: RATE_PAUSE
  → In this regime, S09 Volume is strongest predictor.
  → Suggestion: Increase S09 max from 10 to 13 in config.

RECOMMENDATION: Raise threshold to 50/95. Monitor for 30 days.
```

Human reviews the report and manually adjusts `config.py` if they agree.
The bot never self-modifies weights automatically — human stays in the loop.

---

## 9. WHEN TO RUN

| Trigger | Frequency | Action |
|---------|----------|--------|
| Scheduled | Monthly, last Saturday | Full walk-forward backtest + report |
| Manual | Any time | Run via `python3 run_signal_11.py` |
| After 10 new trades | Event-based | Re-evaluate if recent win rate drops below 50% |

---

## 10. FILES NEEDED

| File | Purpose |
|------|---------|
| `signal_11_ml_backtester.py` | Core engine — data fetch, reconstruction, training, evaluation |
| `run_signal_11.py` | Launcher — runs backtest, prints report, saves to file |
| `backtest_results/` | Folder — saves dated HTML reports (backtest_2026_04.html) |
| `signal_weights_history.json` | Tracks weight adjustments over time with rationale notes |

---

## 11. EDGE CASES AND FAILURE MODES

| Scenario | Handling |
|----------|---------|
| yfinance returns incomplete historical data | Abort with clear error — never backtest on partial data |
| Fewer than 50 trade signals in historical period | Warn: "Insufficient sample size — results not reliable" |
| Model overfits (train accuracy >> test accuracy) | Fall back to Option C (threshold optimizer only) |
| Win rate < current baseline after ML | Keep current weights, log reason in report |
| Regime changes mid-backtest window | Split window at regime boundary, train separately |
| GOLDBEES data has gaps (holidays, halts) | Skip gap dates, do not impute prices |
| Adjusted Close differs from Close | Always use Adjusted Close for returns; always use raw Close for price display |
| NFP/FOMC dates missing from reconstruction | Use heuristic (first Friday, FOMC dates) — same as S06 |

---

## 12. DATA STORAGE DESIGN

All historical reconstructed signal scores + outcomes stored in:
`backtest_data/goldbees_signal_history.csv`

Columns:
```
date | open | high | low | close | volume | adj_close
| s01_pts | s02_pts | s03_pts | s04_pts | s05_pts | s06_pts | s09_pts | s10_pts
| composite_raw | s07_penalty | composite_final
| outcome | outcome_days | outcome_return_pct
| regime
```

This file grows by ~250 rows per year. After 5 years: ~1250 rows.
Rebuild from scratch if data corrupted. Never store derived ML features — recompute each run.

---

## 13. IMPLEMENTATION ORDER (FOR FUTURE CODING SESSION)

1. Build historical GOLDBEES OHLCV fetcher with holiday gap handling
2. Build S01/S04/S09/S10 historical reconstructors (yfinance-based signals — straightforward)
3. Build S03/S06 historical reconstructors (calendar logic — trivial)
4. Build S02/S05 historical reconstructors (FRED data — need FRED historical timeseries)
5. Build outcome labeler (WIN/STOP/TIMEOUT)
6. Build threshold optimizer (Option C — non-ML first)
7. Build logistic regression model (Option A)
8. Build walk-forward validation harness
9. Build report generator (text + HTML)
10. Build run_signal_11.py launcher
11. Test on 2020–2025 data, validate results make intuitive sense

---

*End of Signal 11 Planning Document*
