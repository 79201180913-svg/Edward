# Edward v0.8.13 — System Analysis

## 1. Purpose

v0.8.13 completes the integration of the canonical Trading Path Analysis into the Opportunity Service / live opportunity scan and its UI consumer.

The central rule for this version is:

> v0.8.13 integrates and exposes the existing canonical Trading Path Analysis. It does not change the analysis itself or the semantics of its Decision Engine.

The service of opportunities is a consumer of the canonical analysis, not a second analysis engine.

## 2. Canonical analysis boundary

The canonical analysis pipeline remains:

```text
Market Context
    ↓
Conditional Discovery
    ↓
Trading Path Candidates
    ↓
Trading Path Analysis
    ↓
OOS / Walk Forward validation
    ↓
Expected Value
    ↓
Risk
    ↓
Opportunity
    ↓
Decision
    ↓
TradingPathAnalysisV012
```

`Decision` is part of the canonical analysis. Its result (`BUY / WAIT / PASS`) must be preserved and exposed by consumers without reinterpretation.

The following are explicitly outside the v0.8.13 scope:

- changing Decision Engine thresholds or semantics;
- making Decision position-aware;
- converting `BUY` into `HOLD` merely because a position already exists;
- converting `PASS` into `SELL` / `REDUCE` based on portfolio state;
- introducing a separate `Final Action` that overrides the canonical Decision.

Position context may be used to define the scan universe (for example, the "My Portfolio" scope), but it must not modify the canonical analytical result.

## 3. Opportunity Service integration

The live Opportunity Service must consume the canonical Trading Path result directly.

Legacy opportunity recalculation must not run after the canonical result is available.

The consumer exposes the canonical result including, where available:

- Trading Path / strategy family;
- hypothesis;
- regime;
- volatility bucket;
- direction;
- horizon;
- validation status;
- expected value;
- risk score / risk gate;
- opportunity score;
- confidence;
- canonical Decision;
- canonical current state;
- canonical reasons.

The consumer may format or aggregate these fields for UI presentation, but must not recalculate or silently replace them.

## 4. Portfolio scan scope

A scan explicitly scoped to `Мой портфель` must build its universe from the current portfolio positions.

Required behavior:

```text
Portfolio positions
    ↓
portfolio instrument UIDs
    ↓
market data only for those instruments
    ↓
canonical Trading Path analysis
```

It must not first build the complete market universe and then discard instruments outside the portfolio.

This distinction is both a correctness and performance requirement.

For a market-wide scan, the existing market-universe behavior remains valid.

## 5. Incremental UI behavior

The live scan must publish a completed instrument result as soon as that instrument finishes canonical analysis.

Required flow:

```text
instrument analysis complete
        ↓
consumer result
        ↓
UI callback/update
        ↓
render completed row
        ↓
continue next instrument
```

Therefore, when progress reports `N / total`, completed instruments must already be visible in the table. The UI must not wait for the complete scan before rendering all results.

An error for one instrument must not prevent processing of the remaining instruments where the existing scan contract permits continuation.

## 6. Market-data transport resilience

Bulk `GetLastPrices` access was hardened because a large single REST request could produce T-Invest HTTP 504 responses (`code=4`).

The transport layer uses bounded batching and limited retry for transient 504 failures. This is transport resilience only; it does not alter Trading Path analysis or decision semantics.

The retry policy must remain limited to transient 504 behavior rather than retrying arbitrary API failures.

## 7. Performance correction

A major redundant computation was identified in the canonical runtime: expensive event observations could be rebuilt independently for every candidate/path during OOS validation and Expected Value calculation.

The runtime now builds the canonical event observation set once per instrument and reuses it across candidates.

Conceptually:

```text
candles
   ↓
EventObservationBuilder — once per instrument
   ↓
shared observations
   ├── OOS validation
   ├── Expected Value
   ├── Risk / downstream stages
   └── Decision
```

This optimization preserves analytical semantics because it removes repeated construction of the same canonical observations rather than changing the calculations performed on them.

## 8. UI interpretation rule

The UI must distinguish between:

1. the status of the selected / best Trading Path; and
2. the canonical Decision produced by the analysis.

For example, `status=REJECTED` and `decision=PASS` are not automatically contradictory: they belong to different semantic levels.

The UI should therefore label these fields clearly and avoid presenting a derived portfolio action as though it were the canonical Decision.

## 9. Acceptance criteria

v0.8.13 is accepted when all of the following are true:

- canonical Trading Path analysis is the single analytical source for the Opportunity Service;
- no legacy opportunity recalculation is performed for a canonical result;
- `Мой портфель` scans only portfolio instruments;
- completed instruments appear incrementally in the UI;
- bulk last-price retrieval is resilient to transient T-Invest 504 responses;
- shared event observations avoid redundant per-candidate construction;
- canonical Decision remains unchanged and is exposed to the consumer/UI;
- the complete automated test suite is green;
- real UI acceptance confirms the intended portfolio scope and incremental rendering.

## 10. Explicit non-goals

The following are deferred to a future version and must not be added implicitly to v0.8.13:

- position-aware trading actions;
- `BUY → HOLD` transformation based on existing holdings;
- `PASS → SELL/REDUCE` transformation;
- portfolio-action / execution decision engine;
- changes to Trading Path discovery, validation, Expected Value, Risk, Opportunity, Confidence, or Decision semantics.

A future position-aware action layer can consume the canonical analysis plus portfolio state, but it must remain a separate layer from the canonical analysis.

## 11. Version conclusion

v0.8.13 is an integration/consumer version, not an analysis-algorithm version.

Its architectural outcome is:

```text
Canonical Trading Path Analysis
            ↓
      Opportunity Service
            ↓
   portfolio-scoped live scan
            ↓
 incremental result delivery
            ↓
             UI
```

The canonical analysis remains authoritative. The Opportunity Service consumes it, and the UI presents it.
