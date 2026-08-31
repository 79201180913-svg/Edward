# Edward v0.8.8 — Trading Paths

## Status

Version: **0.8.8**  
Base: **v0.8.7 frozen research/diagnostic architecture**  
Branch: `version-0.8.8-trading-paths`

## 1. Goal

v0.8.8 extends the existing v0.8.7 analysis pipeline so that conditional research discoveries can be promoted into explicitly testable **Candidate Trading Paths** and validated through the existing backtest, Walk Forward, robustness and Quality Gate infrastructure.

The objective is not to weaken the Quality Gate or make an existing fixed strategy pass. The objective is to determine whether a specific combination of market context and observed event can form a reproducible, economically meaningful and independently validated trading path.

## 2. Frozen v0.8.7 boundary

The following remain authoritative and are not replaced:

- market data acquisition and canonical candle model;
- canonical regime taxonomy and `RegimeEngine`;
- v0.8.5 discovery hypotheses;
- v0.8.6 conditional discovery dimensions and evidence;
- existing backtest infrastructure;
- Robust Walk Forward;
- robustness diagnostics;
- existing Quality Gate thresholds and blockers;
- production recommendation contract.

When the new Trading Path layer is disabled, the existing v0.8.7 analysis behavior must remain unchanged.

## 3. New v0.8.8 flow

```text
Market Data
  -> existing v0.8.7 analysis
  -> event discovery
  -> conditional evidence
  -> Candidate Trading Path promotion
  -> explicit trading rule
  -> event backtest
  -> independent validation / Walk Forward
  -> economic validation
  -> existing Quality Gate
  -> TRADE / RESEARCH / NO TRADE
```

## 4. Trading Path

A Trading Path is an explicit, reproducible trading scenario composed from existing research dimensions.

Minimum conceptual fields:

- instrument;
- event hypothesis;
- market regime;
- volatility bucket;
- event direction;
- entry rule;
- exit rule;
- maximum holding horizon;
- risk/execution assumptions;
- validation evidence.

A research cell is never itself a production trading rule.

## 5. Candidate promotion

Conditional discovery results may become candidates only when evidence requirements are satisfied.

Promotion must consider, at minimum:

- sufficient observations;
- horizon persistence;
- temporal coverage;
- regime/volatility coverage;
- event overlap and independence;
- effect magnitude;
- consistency;
- statistical evidence;
- multiple-testing exposure.

Maximum historical excess alone is not a valid promotion criterion.

## 6. Event independence

v0.8.8 introduces an audit of overlapping event occurrences so that multiple hypotheses describing the same market episode are not incorrectly treated as independent evidence.

Required diagnostics include unique events, overlapping events and cross-hypothesis overlap.

## 7. Temporal validation

Horizon persistence and temporal persistence are separate concepts.

A candidate must be evaluated across independent chronological blocks so that positive forward returns across multiple horizons are not mistaken for stability across time.

## 8. Statistical evidence

Candidate evidence must expose enough information to distinguish magnitude from reliability, including sample size, central tendency, dispersion, win rate, baseline/excess return and confidence information where supported.

The research layer must remain descriptive until a candidate is explicitly promoted to trading-rule validation.

## 9. Multiple-testing control

Because conditional discovery evaluates a large hypothesis matrix, v0.8.8 must record and account for the breadth of the search before treating a candidate as strong evidence.

The implementation must not silently promote a candidate merely because it is the best result among many tested cells.

## 10. Trading-rule validation

A promoted candidate must become an explicit deterministic rule and receive a dedicated event-based backtest with:

- entry;
- exit;
- holding period;
- position/P&L accounting;
- exposure;
- turnover;
- drawdown;
- commissions;
- slippage/cost assumptions where supported by the existing execution model.

## 11. Independent Walk Forward

Candidate validation must use the existing Walk Forward infrastructure without reusing future/OOS information for candidate definition or parameter selection.

The candidate must be frozen before its independent OOS validation.

## 12. Quality Gate

The existing Quality Gate is preserved unchanged.

It becomes the final admission layer for Candidate Trading Paths as well as existing strategies. No v0.8.8 feature may lower or bypass existing QG requirements.

## 13. Result states

The research-to-trading pipeline should distinguish:

- `NO_EDGE` — no sufficiently supported candidate;
- `RESEARCH` — interesting evidence, not ready for trading validation;
- `CANDIDATE` — promoted to explicit trading-rule validation;
- `VALIDATED` — independent validation completed successfully but production admission is still subject to QG;
- `TRADE` — validated path passes the existing Quality Gate.

## 14. Regression invariant

For an unchanged v0.8.7 input, disabling the Trading Path layer must preserve the v0.8.7 strategy, Walk Forward, robustness, Quality Gate and recommendation behavior.

## 15. Definition of Done

v0.8.8 is complete only when:

1. conditional discovery can produce candidate paths;
2. candidate promotion is sample- and evidence-aware;
3. event overlap is auditable;
4. temporal stability is measured separately from horizon persistence;
5. multiple-testing exposure is visible and controlled;
6. candidates become explicit deterministic trading rules;
7. event backtests include economic costs supported by the platform;
8. candidates receive independent Walk Forward validation;
9. existing Quality Gate rules remain unchanged;
10. results are reproducible and logged;
11. disabling the new layer preserves v0.8.7 behavior;
12. at least one end-to-end candidate path can be traced from discovery to final decision in tests.
