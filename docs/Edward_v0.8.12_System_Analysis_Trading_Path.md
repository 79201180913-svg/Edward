# Edward v0.8.12 — System Analysis and Release Scope

## 1. Version purpose

Version 0.8.12 introduces the Trading Path analysis layer as the current canonical analytical model of Edward.

The central architectural change is that a Trading Path becomes the primary unit of analysis. A strategy family is treated as a hypothesis family, not as a trading recommendation by itself.

The version keeps the existing market-context work and the established validation controls, while exposing a structured result that can be consumed by downstream product services.

## 2. Canonical analysis flow

The intended v0.8.12 analytical flow is:

```text
Market Data
  -> AnalysisServiceV08
  -> Conditional Discovery
  -> Trading Path Candidates
  -> Path Ranking
  -> Path Validation / OOS evidence
  -> Market Context
  -> Expected Value
  -> Risk
  -> Path Opportunity
  -> Path Decision
  -> TradingPathAnalysisV012
```

The canonical result is represented by `TradingPathAnalysisV012`.

A Trading Path contains:

- instrument;
- strategy family;
- hypothesis;
- regime;
- volatility bucket;
- direction;
- horizon;
- evidence;
- validation summary;
- market-context snapshot;
- opportunity metrics;
- current state;
- decision;
- analysis status;
- rank.

## 3. Validation model

The analysis exposes validation evidence instead of reducing the result to a single legacy strategy score.

The validation summary includes:

- Walk-Forward persistence;
- robustness score;
- positive OOS windows;
- statistical validity;
- overlap validity;
- multiple-testing validity;
- promotion status.

Promotion remains evidence-driven. The analysis must distinguish an observed profitable path from a path that has sufficient independent and temporally stable evidence for promotion.

## 4. Market context

Market context is part of the path analysis result and is used for ranking/contextual interpretation.

The exposed context includes:

- benchmark;
- baseline rank;
- context-adjusted rank;
- rank delta;
- baseline score;
- context-adjusted score;
- score delta;
- regime compatibility;
- relative-strength component;
- volatility component.

The market-context layer must not silently replace or mutate the underlying validation evidence.

## 5. Decision model

The canonical Trading Path decision is deliberately small:

```text
BUY
WAIT
PASS
```

Current state is represented separately:

```text
ENTRY_READY
WAIT
INVALID
```

This separation prevents analytical evidence, current market state and final decision from being conflated.

## 6. Relationship to legacy analysis

The v0.8.12 Trading Path layer is additive to the existing analysis stack.

Legacy strategy analysis remains available for compatibility, but Trading Path analysis is the canonical representation for the new analysis result.

The system must not infer that a strategy family is itself a recommendation. The selected path and its evidence are the objects that downstream consumers should use.

## 7. Current product integration checkpoint

The analysis/frontend integration has been updated to expose the Trading Path model and market-context information.

The separate Opportunity Service integration is intentionally identified as the next scope rather than being treated as complete in v0.8.12.

At the current checkpoint, the Opportunity Service still contains legacy v0.8.2.1-oriented calculation paths, including legacy opportunity/decision/trade-plan/forecast handling. Therefore its existing table must not be treated as a faithful presentation of the complete Trading Path analysis.

This is a known integration boundary, not a reason to weaken or alter the Trading Path evidence model.

## 8. Release acceptance criteria

The v0.8.12 checkpoint is considered complete for the Trading Path analysis scope when:

1. `TradingPathAnalysisV012` is the stable domain representation.
2. Trading Path discovery, ranking, validation, market context, opportunity, risk and decision services are wired into the analysis runtime.
3. Legacy analysis remains backward-compatible.
4. Analysis UI exposes the current Trading Path result rather than presenting obsolete strategy-only information.
5. Regression coverage exists for the new domain/services/runtime/UI wiring.
6. No production promotion is manufactured by lowering evidence requirements.

## 9. Known next-scope item

The next version must address the Opportunity Service as a pure consumer of the canonical Trading Path analysis.

Target architecture:

```text
Canonical Analysis
      |
      v
TradingPathAnalysisV012
      |
      v
Opportunity Consumer
      |
      v
Instrument-level Opportunity View
      |
      v
UI
```

The Opportunity Service must not independently recalculate:

- strategy selection;
- forecast;
- opportunity score;
- decision;
- risk;
- trade plan.

The next scope should also replace the obsolete Opportunity table with an instrument-level view backed by current Trading Path evidence, while allowing detailed path evidence to be inspected for the selected instrument.

## 10. Version conclusion

v0.8.12 establishes Trading Path analysis as the current analytical model and makes its evidence, market context, opportunity and decision data explicit.

The next architectural priority is not another independent analysis engine. It is completing the consumer boundary so that the Opportunity Service and its UI present exactly the same canonical analysis result.
