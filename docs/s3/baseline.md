# S3 baseline: how far the committee's outputs are from their own source data (T2)

Audit of the **77 committee runs stored so far** (2026-09-18 to 2026-09-25), with **no new model calls**. This is the 'before' number every later S3 task is measured against. Reproduce it with `python -m app.scripts.baseline_discrepancy` (see that file's docstring for the exact rules and limits).

## The headline numbers

| Measure | Result | What it means |
|---|---|---|
| **A. Context fidelity**: numbers the committee is told, recomputed from raw prices | **1.1% differ** (12 of 1050 checks); **0.2% by more than rounding** (2) | The deterministic code that writes the analysts' briefing |
| **B. Headline**: CEO vote-weight % vs the stored consensus | **4.0% differ** (3 of 75); 0 by more than 1 point | The deterministic summary line |
| **C. AI prose**: numbers analysts wrote that trace to nothing in their briefing | **2.3% unsupported** (69 of 2948 numbers, 534 analyst write-ups) | The gap the A6 gate exists to close |
| Figures this audit could NOT recompute (Sharpe, win rate, beta, correlations, percentiles) | 401 occurrences | Reported as unchecked, never counted as passed |

## A. Context fidelity, by check

| Check | verified | mismatch | not recomputable / not found |
|---|---:|---:|---:|
| 1-day move % | 73 | 2 | 2 |
| 20-day move % | 75 | 0 | 2 |
| 20-day volatility % | 74 | 1 | 2 |
| 5-day move % | 73 | 2 | 2 |
| RSI | 74 | 1 | 2 |
| Sharpe (not independently checked) | 0 | 0 | 75 |
| above/below 200-day average | 75 | 0 | 0 |
| beta (not independently checked) | 0 | 0 | 75 |
| correlation (not independently checked) | 0 | 0 | 75 |
| distance from 252-day high % | 72 | 3 | 2 |
| distance from 60-day high % | 75 | 0 | 2 |
| engine confidence % | 75 | 0 | 2 |
| engine signal | 75 | 0 | 2 |
| last price | 73 | 2 | 2 |
| macro line (verbatim) | 75 | 0 | 2 |
| percentile (not independently checked) | 0 | 0 | 75 |
| risk level | 75 | 0 | 2 |
| risk score | 74 | 1 | 2 |
| win rate (not independently checked) | 0 | 0 | 75 |

First mismatches (claimed vs recomputed):

| Date | Symbol | Check | Claimed | Recomputed |
|---|---|---|---:|---:|
| 2026-09-21 | META | last price | 741.24 | 741.25 |
| 2026-09-21 | META | 1-day move % | 11.3 | 11.428458 |
| 2026-09-21 | META | 5-day move % | 11.4 | 11.453573 |
| 2026-09-21 | META | risk score | 45.0 | 45.6 |
| 2026-09-21 | QQQ | 1-day move % | 2.8 | 2.882054 |
| 2026-09-21 | QQQ | 5-day move % | 4.6 | 4.662091 |
| 2026-09-21 | QQQ | 20-day volatility % | 16.0 | 16.667722 |
| 2026-09-21 | QQQ | RSI | 65.7 | 65.587719 |
| 2026-09-22 | AAPL | headline vote-weight % | 85.0 | 84.0 |
| 2026-09-22 | META | last price | 736.59 | 736.599976 |
| 2026-09-22 | META | distance from 252-day high % | -3.6 | -3.654039 |
| 2026-09-23 | IWM | distance from 252-day high % | -7.3 | -7.353136 |
| 2026-09-23 | SPY | distance from 252-day high % | -1.1 | -1.049443 |
| 2026-09-25 | IWM | headline vote-weight % | 87.0 | 88.0 |
| 2026-09-25 | NVDA | headline vote-weight % | 87.0 | 88.0 |

## By day (read this before trusting any single rate)

| Day | A: checks | A: differ | C: numbers | C: unsupported | C rate |
|---|---:|---:|---:|---:|---:|
| 2026-09-18 | 0 | 0 | 63 | 63 | 100.0% |
| 2026-09-21 | 210 | 8 | 585 | 0 | 0.0% |
| 2026-09-22 | 210 | 2 | 572 | 0 | 0.0% |
| 2026-09-23 | 210 | 2 | 546 | 0 | 0.0% |
| 2026-09-24 | 210 | 0 | 570 | 1 | 0.2% |
| 2026-09-25 | 210 | 0 | 612 | 5 | 0.8% |

## C. AI prose, by analyst and by model (all days)

| Analyst | numbers written | unsupported | rate |
|---|---:|---:|---:|
| Behavioral Coach | 413 | 8 | 1.9% |
| Global Macro | 375 | 12 | 3.2% |
| Personal Context | 408 | 10 | 2.5% |
| Quantitative Strategist | 494 | 12 | 2.4% |
| Risk Manager | 448 | 5 | 1.1% |
| Technological Innovator | 399 | 8 | 2.0% |
| Value Investor | 411 | 14 | 3.4% |

| Model that answered | numbers written | unsupported | rate |
|---|---:|---:|---:|
| gemini-3.1-flash-lite | 1945 | 9 | 0.5% |
| gemini-3.5-flash | 190 | 0 | 0.0% |
| gemini-3.6-flash | 318 | 32 | 10.1% |
| gemini-3.7-flash | 189 | 18 | 9.5% |
| gemini-3.8-flash | 62 | 1 | 1.6% |
| gemini-flash-latest | 183 | 9 | 4.9% |
| nvidia/nemotron-3-ultra-550b-a55b:free | 1 | 0 | 0.0% |
| openrouter/free | 60 | 0 | 0.0% |

First unsupported numbers (an analyst wrote a figure that is not in its briefing):

| Date | Symbol | Analyst | Number |
|---|---|---|---|
| 2026-09-18 | GOOGL | Behavioral Coach | `60` |
| 2026-09-18 | GOOGL | Behavioral Coach | `+0.0%` |
| 2026-09-18 | GOOGL | Behavioral Coach | `1.87x` |
| 2026-09-18 | GOOGL | Behavioral Coach | `62.9` |
| 2026-09-18 | GOOGL | Global Macro | `60` |
| 2026-09-18 | GOOGL | Global Macro | `349.54` |
| 2026-09-18 | GOOGL | Global Macro | `3.3%` |
| 2026-09-18 | GOOGL | Global Macro | `1.87x` |
| 2026-09-18 | GOOGL | Global Macro | `62.9` |
| 2026-09-18 | GOOGL | Global Macro | `50%` |
| 2026-09-18 | GOOGL | Value Investor | `50%` |
| 2026-09-18 | GOOGL | Value Investor | `-0.46` |
| 2026-09-18 | GOOGL | Value Investor | `19%` |
| 2026-09-18 | GOOGL | Value Investor | `60` |
| 2026-09-18 | GOOGL | Technological Innovator | `60` |
| 2026-09-18 | GOOGL | Technological Innovator | `349.54` |
| 2026-09-18 | GOOGL | Technological Innovator | `1.87x` |
| 2026-09-18 | GOOGL | Technological Innovator | `62.9` |
| 2026-09-18 | GOOGL | Technological Innovator | `50%` |
| 2026-09-18 | GOOGL | Risk Manager | `-0.46` |

## How to read this honestly

- **Unsupported does not always mean invented.** An analyst may add two figures from its briefing, or quote a note it received that is not stored. What matters for S3 is that a reader cannot trace the figure, which is exactly what the A6 gate will require.
- Whole numbers up to 10 and years are treated as wording, not claims. A fabricated small number would be missed.
- A. can only prove what it can recompute; the rest is listed as not independently checked.
- The sample is small (77 runs over 6 trading days) and all of it is live, forward-recorded data. Treat the rates as a starting point, not a stable estimate.
- The full per-number results are in `docs/s3/baseline.csv`.

## What this run shows

*Written by hand on 2026-09-26. Everything above this heading is generated by the script and can be regenerated; this section is interpretation and will need updating when the numbers change.*

1. **The deterministic parts are already very faithful.** 98.9% of context checks agree with the raw prices, and only 2 of 1,050 differ by more than rounding. Both are on **2026-09-21, the day the price history was repaired and backfilled**: those runs were briefed with data that was corrected afterwards. That is exactly the failure the point-in-time snapshot store (T10) exists to make visible and provable.
2. **The headline percentage is off by one point in 3 of 75 runs** (for example 85% vs 84%). It is cosmetic, but it is a real inconsistency between two deterministic computations, so it belongs on the fix list.
3. **AI prose, since the first day: 6 unsupported numbers out of 2,885 (0.2%).** All six are dollar figures, position-sizing arithmetic by the Personal Context, Value Investor, Global Macro and Risk Manager analysts (for example `$967.6`, `$62.4`). They are derived or hypothetical amounts, not source data, and one is even malformed (`$9,230,44`).
4. **The first day (2026-09-18) is 63 of 63 unsupported**, and it must not be averaged away. That day's stored context is a shorter, older format with no signal, risk or macro lines, yet the analysts quoted those figures. Either the analysts saw more than what was stored, or they supplied the figures themselves; the record cannot say which. **The lesson for S3: the stored context has to be exactly what the analyst was given**, or no later check can prove anything.
5. **Gemini model versions differ a lot on the first day** (see the by-model table), but that table is confounded by the first-day effect. Do not read it as a model ranking.

### What this means for the plan
- On numeric traceability alone, the plan's 98% A6 target is **already roughly met** for the routine daily runs. So A6's value is less "catch invented numbers" and more: **prove it for every output** with source pointers (T3/T4), **catch stale or revised data** (finding 1), and **cover the channels this audit did not** (the assistant and user-triggered reports write free-form prose).
- **Not measured here:** whether a claim is *true* or its reasoning *sound* (only whether its numbers trace to the briefing), qualitative claims such as "bullish cross", whole numbers of 10 or less, and figures the audit cannot recompute (Sharpe, win rate, beta, correlations, percentiles: 401 occurrences, listed as unchecked).
- **Small sample:** 6 trading days, one committee configuration. Do not quote these rates as the product's accuracy.

