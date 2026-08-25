# Edward

Python trading platform for T-Invest.

Current stable version: **0.4.0**

## Platform overview

Edward combines manual trading through T-Invest with an adaptive market-analysis and decision pipeline. The platform is designed around an instrument-centric workflow and supports both individual instrument analysis and portfolio-aware opportunity search.

## Trading and portfolio

- T-Invest Sandbox integration for accounts, portfolio, positions, balances and market data;
- instrument catalog with ticker, UID, identifiers, price and trading availability;
- current market price, close-price change and trading status;
- BUY/SELL availability and order-type availability;
- manual order entry and order lifecycle monitoring;
- order history and local persistence;
- portfolio value, available cash, position quantity and portfolio weight;
- position and P&L context for decision making;
- portfolio analysis limited to currently held positions.

## v0.4 Decision Engine

Version 0.4 introduces a complete analysis-to-decision pipeline:

```text
Market Data
    ↓
Strategy Analysis / Walk Forward
    ↓
Risk Engine
    ↓
Opportunity Score
    ↓
Decision Engine
    ↓
BUY / WAIT / HOLD / ADD / REDUCE / SELL / PASS
```

### Strategy analysis

Edward evaluates multiple strategies and selects the best available candidate for the current trading profile:

- Trend Following;
- Momentum;
- Breakout;
- Mean Reversion.

Trading profiles are adaptive to the intended trading horizon:

- long-term;
- medium-term;
- speculative.

Each strategy is evaluated using historical testing and Walk Forward validation with Quality Gate diagnostics.

### Risk Engine

The Risk Engine evaluates the strategy and portfolio context, including:

- maximum drawdown;
- volatility;
- risk score and risk level;
- current portfolio weight;
- target and maximum position weight;
- available cash;
- portfolio fit;
- critical-risk conditions.

Risk is evaluated even when a strategy fails the Quality Gate, so the final decision remains explainable.

### Opportunity Score

The Opportunity Score combines:

- strategy quality;
- entry quality;
- market-regime compatibility;
- risk;
- portfolio fit;
- analysis confidence.

The score is used to rank actionable opportunities rather than relying on Strategy Score alone.

### Decision Engine

Edward separates two decision scenarios:

**Market opportunity search**

Only instruments that are currently tradable and available for BUY are included. Existing portfolio positions are excluded from the new-entry universe.

Typical decisions:

- BUY;
- WAIT;
- PASS.

**Portfolio analysis**

Only currently held positions are analyzed.

Typical decisions:

- HOLD;
- ADD;
- REDUCE;
- SELL.

The Decision Engine also considers trading availability, portfolio limits, risk deterioration and strategy degradation.

## Opportunity search UI

The v0.4 UI provides:

- selectable analysis scope: **Market Opportunities** / **My Portfolio**;
- instrument-type filtering;
- trading-profile selection;
- decision filtering;
- staged progress reporting with the current processing stage and instrument count;
- incremental table population while the scan is running;
- immediate display of analyzed instruments without waiting for the full scan;
- Strategy Score, Risk Score, Opportunity Score, Decision and explanation columns;
- localized Russian UI and decision explanations;
- safe handling when the user changes pages while background analysis is running.

## Walk Forward cache

Walk Forward optimization results are persisted and reused between repeated analyses.

The cache supports:

- reuse of valid strategy optimization results;
- invalidation when analysis inputs/data change;
- forced Walk Forward recalculation;
- complete cache clearing;
- cache usage in both mass opportunity search and individual instrument analysis.

This avoids repeating expensive parameter searches when the analysis context has not changed.

## Market data and T-Invest contract compatibility

Edward uses the T-Invest market-data contracts for:

- historical candles;
- last prices;
- trading statuses;
- instrument availability.

Historical daily data is normalized before entering the analysis pipeline, including protobuf-style timestamps and quotations.

Large market-data requests are processed in batches to avoid oversized API requests and to isolate failures between batches.

## Testing

The v0.4 release includes unit and E2E coverage for:

- Decision Engine scenarios and ranking;
- Risk Engine;
- Opportunity Engine;
- portfolio and market opportunity search;
- Walk Forward cache;
- candle normalization;
- instrument and market decision context;
- UI progress and incremental result updates;
- T-Invest adapter compatibility;
- regression coverage for the v0.4 integration pipeline.

Run the full test suite with:

```bash
python -m pytest -q
```

## Version 0.4.0 status

Version 0.4.0 is the frozen release baseline for the adaptive analysis and Decision Engine layer.

The next development cycle can build on top of this baseline without changing the v0.4 architecture.
