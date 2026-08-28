# Edward v0.8.1 — Multi-Factor Evidence & Market Intelligence

## Goal
Extend the v0.8 analysis core with additional evidence from existing T-Invest contracts without changing downstream contracts or treating opaque external analyst consensus as a decision source.

## Included
- Fundamental quality, valuation, growth and fundamental momentum.
- Market microstructure: spread, depth, order-book imbalance, trade imbalance and liquidity quality.
- Candle buy/sell volume pressure.
- T-Invest Signals as an independently validated external technical evidence source.
- Corporate-report/event risk with point-in-time controls.
- Dividends and total-return context.
- Insider transactions and independently measured historical signal value.
- Trading-session context.
- Instrument margin/risk-rate context.
- Portfolio and operations intelligence using available holdings, weights, cash, PnL and transaction economics.
- Unified Evidence Layer with strength, direction, reliability, availability and freshness.
- Integration into v0.8 confidence/opportunity/decision flow.

## Explicitly excluded
- Analyst consensus, analyst target prices and external analyst Buy/Hold/Sell recommendations as automatic decision evidence.
- Breaking changes to AnalysisResult, StrategyResult, OpportunityResult, DecisionRequest, DecisionResult or execution contracts.
- Changes to execution, protection, verification, replanning and autonomous execution architecture.

## Integration rules
1. New factors are evidence, not unconditional BUY votes.
2. Missing optional data is represented as unavailable/N/A, never as zero evidence.
3. Every historical factor used for backtesting must respect point-in-time availability.
4. New factors may affect strategy selection, entry quality, risk adjustment, confidence and opportunity scoring, but compatibility outputs remain stable.
5. Conflicting evidence must reduce confidence or produce WAIT/PASS where appropriate.
6. T-Invest Signals must be historically calibrated before contributing meaningful reliability.
7. No single factor may independently authorize BUY.

## Delivery phases
### P0
Fundamentals, microstructure, volume pressure, T-Invest signals, event risk, point-in-time controls, unified evidence, decision integration.

### P1
Dividends, insider intelligence, trading sessions, margin/risk rates, portfolio operations.

### P2
Options/futures enrichment and advanced derivatives analytics.

## Acceptance
The same v0.8 downstream consumers must continue to work without contract changes. Each new factor has isolated unit tests, integration tests for evidence aggregation, and regression tests for decision behavior.
