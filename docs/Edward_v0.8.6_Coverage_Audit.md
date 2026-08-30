# Edward v0.8.6 — Conditional Discovery Coverage Audit

## Objective

Before promoting any conditional result to an event-strategy candidate, measure how the historical sample is distributed across the discovery dimensions.

## Required audit

For every hypothesis report:

- total event count;
- event count by canonical regime;
- event count by volatility bucket;
- event count by direction;
- event count by regime × volatility;
- event count by regime × direction;
- event count by volatility × direction;
- event count by full regime × volatility × direction condition;
- number and percentage of cells below `MIN_OBSERVATIONS`;
- number of sufficient cells;
- concentration of events in the largest conditions.

## Interpretation rules

Coverage is descriptive and must not be optimized against SBER or any other instrument.

Do not lower the minimum sample threshold to manufacture sufficient cells.
Do not select the strongest cell merely because it has the largest excess return.
Do not merge canonical regimes solely to increase sample size without an explicit research rationale and regression tests.

If the full Cartesian matrix is sparse, evaluate marginal conditional effects first (event × regime, event × volatility, event × direction), then only inspect higher-order interactions where sufficient sample exists.

## Promotion rule

A condition becomes a candidate for event-based backtest only when its sample is sufficient and its effect is supported across multiple observations/horizons rather than by a single maximum cell.
