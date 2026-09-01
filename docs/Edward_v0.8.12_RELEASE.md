# Edward v0.8.12 — Release Marker

## Status

**Released to `main`.**

## Scope

v0.8.12 establishes Trading Path analysis as the current canonical analytical model of Edward.

Included:

- `TradingPathAnalysisV012` canonical analysis contract;
- Trading Path discovery and candidate generation;
- deterministic path ranking;
- validation and OOS evidence;
- market-context integration;
- expected-value and risk analysis;
- Trading Path opportunity construction;
- Trading Path decision/state model;
- analysis runtime integration;
- frontend integration for the current Trading Path analysis;
- regression coverage for the new analysis/domain/runtime/UI components.

## Architectural boundary

The Opportunity Service is **not** considered migrated to the Trading Path model in this release. Its remaining legacy analytical paths are explicitly carried into the next version scope.

## Next version

The next version will make Opportunity Service a pure consumer of `TradingPathAnalysisV012` and redesign the Opportunities table around current Trading Path evidence.
