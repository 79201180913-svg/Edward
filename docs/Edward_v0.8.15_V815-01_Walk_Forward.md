# Edward v0.8.15 — V815-01 Walk-Forward

## Purpose

Introduce a sequential walk-forward contract in which each validation block is unseen at the time the corresponding TRAIN block is used for research.

## Fold layout

For `train_size=60`, `validation_size=30`, `windows=4` over 180 candles:

```text
WF1: TRAIN  [0:60)    -> VALIDATION [60:90)
WF2: TRAIN  [0:90)    -> VALIDATION [90:120)
WF3: TRAIN  [0:120)   -> VALIDATION [120:150)
WF4: TRAIN  [0:150)   -> VALIDATION [150:180)
```

TRAIN is expanding and validation is always the immediately following unseen block.

## Current implementation

`TradingPathWalkForwardServiceV015` provides:

- deterministic chronological fold construction;
- independent evaluation of every validation window;
- per-window observations, return, baseline, excess return and win rate;
- persistence percentage;
- mean and median excess return;
- worst-window excess return;
- dispersion and sign consistency;
- minimum sample sufficiency;
- a conservative pass rule requiring at least 75% positive windows and a strictly positive worst window.

The service intentionally does not alter an existing candidate or use validation data to modify its thresholds.

## Important integration boundary

The current commit establishes and tests the fold/evidence contract. Canonical runtime integration and rerunning discovery independently inside every TRAIN fold remain the next integration step. Until that integration is complete, this service must not be described as full nested WFO in production output.

## Acceptance criteria

- No validation candle is visible to discovery for the same fold.
- Fold ranges are deterministic and contiguous.
- A negative worst window cannot be hidden by a positive mean.
- Insufficient observations in any fold prevent the WF gate from passing.
- Existing v0.8.14 behavior remains unchanged until runtime integration is explicitly enabled.
