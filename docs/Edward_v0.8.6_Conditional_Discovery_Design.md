# Edward v0.8.6 — Conditional Research Discovery

## Purpose

Extend v0.8.5 event study with conditional evidence without changing the existing trading decision pipeline.

## Analysis dimensions

For each of the six v0.8.5 hypotheses evaluate canonical market regime, volatility bucket, event direction, and forward horizons 1, 3, 5, 10 and 20 candles.

## Metrics

Each condition cell reports observations, mean forward return, median forward return, win rate, unconditional baseline, excess return versus baseline, and a sufficient-sample flag.

Cells below the minimum observation threshold remain visible for auditability but are not treated as evidence of an edge.

## Non-goals

Conditional Discovery must not modify strategy parameters, Walk-Forward windows, Quality Gate thresholds, recommendation, or NO TRADE behavior.

## Next stage

A condition becomes an event-strategy candidate only after statistical review and an independent event-based backtest. The candidate then uses the existing Walk-Forward and Quality Gate path.
