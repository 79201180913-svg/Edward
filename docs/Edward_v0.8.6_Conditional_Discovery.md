# Edward v0.8.6 — Conditional Research Discovery

## Purpose

v0.8.6 extends the v0.8.5 discovery layer with conditional evidence. The purpose is to identify where a predefined market event has historically behaved differently from the unconditional baseline.

The layer is research-only. It MUST NOT select production parameters, bypass Robust Walk-Forward, modify Quality Gate thresholds, or create a trading recommendation.

## Conditional dimensions

Each predefined event is evaluated across:

- canonical market regime from `RegimeEngine.REGIMES`;
- volatility bucket: `Low`, `Normal`, `High`;
- event direction: `Positive`, `Negative`;
- forward horizon: 1, 3, 5, 10, 20 candles.

The canonical regime taxonomy is reused without introducing a second regime vocabulary.

## Evidence

Every cell contains:

- observations;
- mean forward return;
- median forward return;
- win rate;
- unconditional baseline mean return for the same horizon;
- excess return versus baseline;
- `sufficient_sample` flag.

`MIN_OBSERVATIONS = 8` is an evidence-quality flag. Cells below the threshold remain visible for diagnostics but must not be interpreted as validated edge.

## Event set

The six v0.8.5 hypotheses are retained:

- `BREAKOUT_EXPANSION`
- `PULLBACK_RECLAIM`
- `IMPULSE_CONTINUATION`
- `SHOCK_REVERSAL`
- `GAP_REVERSAL`
- `RANGE_BREAK`

## Architectural boundary

```text
Candles
  -> v0.8.5 Discovery events
  -> v0.8.6 Conditional Discovery
       -> event × regime × volatility × direction × horizon
       -> descriptive evidence only
  -> Robust Walk-Forward
  -> Quality Gate
  -> recommendation / NO TRADE
```

The existing v0.8.5 production analysis path remains authoritative. v0.8.6 is an additive research capability until a later version explicitly defines event-to-strategy promotion and validates it through independent WF + existing QG.

## Next step

v0.8.7 may introduce event-based candidate strategies. Any promoted event hypothesis must be converted into an explicit trading rule and evaluated through an independent Walk-Forward before Quality Gate admission.
