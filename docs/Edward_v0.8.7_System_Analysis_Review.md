# Edward v0.8.7 — System Analysis Review

## Status

Version: **0.8.7**
Branch analyzed: `version-0.8.7-research-report`
Analysis date: **2026-08-31**
Instrument in backend run: **SBER**
Profile: **medium_term**
Candles: **1768**

This document freezes the backend findings from the v0.8.7 research run and records the architectural observations that should be used as the baseline for the next analysis iteration.

## 1. What was achieved in v0.8.7

Edward has moved beyond a simple comparison of four fixed strategies. The backend now combines:

- regime detection;
- conditional hypothesis discovery;
- event observation across multiple horizons;
- Walk Forward validation with 25 OOS windows;
- parameter-selection and transfer diagnostics;
- robustness scoring and component breakdown;
- explicit Quality Gate blockers;
- sample-size awareness and `LOW_SAMPLE` / `INTERESTING` research flags;
- research evidence logging and summary.

The implemented discovery hypotheses are:

1. `BREAKOUT_EXPANSION` — выход из сжатия с расширением диапазона;
2. `PULLBACK_RECLAIM` — откат внутри восходящей структуры и возврат выше fast average;
3. `IMPULSE_CONTINUATION` — сильный импульс с последующим подтверждением продолжения;
4. `SHOCK_REVERSAL` — экстремальное отрицательное движение и последующая реакция;
5. `GAP_REVERSAL` — сильный отрицательный gap и последующая реакция;
6. `RANGE_BREAK` — выход из узкого диапазона.

## 2. Key backend findings

### 2.1 Conditional discovery is producing meaningful candidates

For SBER, `BREAKOUT_EXPANSION` showed positive excess across all five tested horizons:

- events: 65;
- positive excess horizons: 5/5;
- persistence: 100%;
- strongest horizon: 20;
- strongest excess: +2.2231%.

This is evidence of a candidate conditional relationship, not proof of a tradable edge.

A particularly interesting cell was:

- strategy: `Trend Following`;
- hypothesis: `BREAKOUT_EXPANSION`;
- regime: `TREND_DOWN`;
- volatility: `High`;
- direction: `Positive`;
- horizon: 3;
- N: 10;
- win rate: 100%;
- WF persistence: 100%;
- flag: `INTERESTING`.

The sample is still small, therefore the correct system behavior is to classify it as interesting research evidence rather than automatically promote it to a trading recommendation.

### 2.2 Research layer correctly rejects insufficient samples

The research summary contained:

- 5040 analyzed cells;
- 92 `INTERESTING`;
- 4820 `LOW_SAMPLE`;
- 108 with no positive excess;
- 20 with low WF persistence.

This is a major improvement in statistical discipline: a large historical return from N=1 is not treated as a validated edge.

For example, `GAP_REVERSAL` produced excess of +22.403731 at horizon 20 for SBER, but N=1 and therefore `LOW_SAMPLE`.

### 2.3 Walk Forward is now a real diagnostic layer

The medium-term profile uses:

- train: 240 candles;
- test: 60 candles;
- 25 expected WF windows;
- maximum drawdown: 25%;
- minimum stability: 60%.

Each strategy is evaluated across the OOS windows with return, excess return, drawdown, Sharpe, Sortino, trades, exposure, turnover, parameter selection, transfer, stability and robustness diagnostics.

### 2.4 Quality Gate now explains why strategies fail

The current SBER run produced the following results.

#### Trend Following

- mean OOS return: **-0.3431%**;
- mean OOS drawdown: **2.4830%**;
- mean OOS Sharpe: **0.1436**;
- positive OOS windows: **20%**;
- robustness: **42.50**.

Failed checks:

- mean OOS return;
- positive OOS windows / return consistency;
- robustness score.

#### Momentum

- mean OOS return: **+0.7482%**;
- mean OOS drawdown: **4.9363%**;
- mean OOS Sharpe: **0.0902**;
- positive OOS windows: **52%**;
- robustness: **53.55**.

Failed checks:

- positive OOS windows / return consistency (52% < 60%);
- robustness score (53.55 < 60).

Interpretation: Momentum is not simply a failed strategy. It has positive average OOS performance and acceptable risk, but insufficient consistency and robustness for the current gate.

#### Breakout

- mean OOS return: **+0.9604%**;
- mean OOS drawdown: **0.7715%**;
- mean OOS Sharpe: **0.3940**;
- positive OOS windows: **36%**;
- robustness: **58.81**.

Failed checks:

- positive OOS windows / return consistency (36% < 60%);
- robustness score (58.81 < 60).

Breakout is particularly important: its robustness is only **1.19 points below** the current threshold. The failure therefore identifies insufficient stability rather than an obviously unprofitable strategy.

#### Mean Reversion

- mean OOS return: **-2.8281%**;
- mean OOS drawdown: **5.3247%**;
- mean OOS Sharpe: **-0.0128**;
- positive OOS windows: **20%**;
- robustness: **42.37**.

Failed checks:

- mean OOS return;
- mean OOS Sharpe;
- positive OOS windows / return consistency;
- robustness score.

Mean Reversion is currently the clearest strategy to reject for this configuration.

## 3. Parameter-selection and stability observations

Momentum used 25 WF windows:

- transfer matches: 7/25 (28%);
- excess-return criterion matches: 9/25 (36%);
- Sharpe criterion matches: 7/25 (28%);
- Sortino criterion matches: 6/25 (24%);
- return/DD criterion matches: 4/25 (16%);
- composite criterion matches: 6/25 (24%);
- mean selection confidence: 37.60.

The shadow transfer test changed only 1 of 25 windows (4%), with mean return delta +0.0303%.

This suggests that Momentum's current weakness is not explained solely by unstable parameter transfer.

## 4. Most important architectural observation

The research layer and the unconditional strategy Quality Gate are now measuring different questions.

The Quality Gate asks:

> Is the entire strategy sufficiently profitable and stable across all OOS windows?

The research layer asks:

> Does a specific market behavior work under a specific combination of regime, volatility, direction and horizon?

The backend log demonstrates that a strategy can fail the first question while containing a potentially useful answer to the second question.

The clearest example is:

`Breakout` → Quality Gate **FAIL**

while the conditional research layer finds:

`BREAKOUT_EXPANSION + TREND_DOWN + High volatility + horizon 3` → `INTERESTING`, N=10, 100% win rate, 100% WF persistence.

This must **not** be interpreted as proof that the conditional signal is profitable. It is evidence that the next architecture should be able to validate conditional edges separately from unconditional strategy performance.

## 5. Baseline conclusion for v0.8.7

v0.8.7 is considered technically complete as a research/diagnostic release when the implementation and tests on the release branch are preserved.

The version successfully establishes:

1. multi-factor input and evidence aggregation;
2. regime-aware research;
3. conditional hypothesis discovery;
4. event-level evidence;
5. multi-horizon analysis;
6. 25-window Walk Forward diagnostics;
7. parameter-transfer audit;
8. robustness decomposition;
9. explicit Quality Gate blockers;
10. sample-size-aware research classification.

The system **does not yet establish a proven profitable strategy**. That is an intentional and correct conclusion from the current evidence.

## 6. Direction for the next iteration

The next research step should focus on promotion of conditional discoveries into explicitly testable conditional strategies, with their own:

- minimum sample requirements;
- regime/volatility coverage requirements;
- OOS validation;
- consistency thresholds;
- robustness scoring;
- economic significance checks;
- anti-overfitting controls;
- promotion/demotion rules.

The existing unconditional Quality Gate should remain intact. Conditional discovery should provide additional candidates for validation rather than weaken the gate.

## 7. Release decision

**v0.8.7: FREEZE.**

No claim of a production-ready profitable strategy is made by this document. The release freezes the research and diagnostic architecture and the evidence obtained from the backend run so that v0.8.8 can build on a reproducible baseline.
