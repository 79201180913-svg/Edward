# Edward

Python trading platform for T-Invest.

Current stable version: **0.5.0**

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

## v0.4 Decision Engine baseline

Version 0.4 introduced a complete analysis-to-decision pipeline:

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

## v0.5 Forecast and trading-readiness layer

Version 0.5 extends the v0.4 decision pipeline with forward-looking price analysis and pre-trade controls:

```text
Strategy / Risk / Portfolio Context
              ↓
       Forecast Model Selection
              ↓
      Point-in-Time Forecast
              ↓
       Forecast Walk Forward
              ↓
       Forecast Quality Gate
              ↓
          Trade Plan
              ↓
       Position Sizing
              ↓
    Execution Readiness Gate
```

### Price forecast

The platform produces multi-horizon forecasts for:

- 1 trading day;
- 5 trading days;
- 20 trading days;
- 60 trading days.

The forecast includes expected price, expected return, probability of upward/downward movement, downside/upside levels and confidence.

Forecast model selection is adaptive and uses historical validation rather than relying on one permanently fixed model.

### Point-in-time and anti-leakage validation

The v0.5 forecasting pipeline contains explicit point-in-time validation. Forecast, model-selection and Walk Forward results are checked at a fixed historical origin so that adding candles after that origin cannot change the historical result.

The validation is designed to reject future-data leakage rather than merely checking the order of an input list.

### Forecast cache

Forecast and trade-analysis results can be reused through a versioned cache. Cache identity includes the instrument, trading profile, risk context, forecast model, horizon, data snapshot and algorithm version.

The cache supports hit/miss handling, invalidation, clearing and statistics. The UI exposes cache state and controlled Walk Forward recalculation.

### Trade Plan

For an actionable decision Edward can build a trade plan containing:

- entry range;
- target price;
- stop price;
- expected return;
- expected risk;
- Risk/Reward;
- holding horizon;
- confidence;
- recommended position size.

For portfolio reductions and exits the UI shows the recommended reduction/closure quantity and the expected remaining position.

### Execution Readiness

Before a decision is considered ready for future automated execution, v0.5 evaluates a dedicated execution gate covering:

- strategy Quality Gate;
- forecast Quality Gate;
- risk conditions;
- portfolio availability;
- trading status;
- position sizing;
- entry/target/stop readiness;
- liquidity readiness;
- Risk/Reward.

The result is explicitly exposed as **Execution Ready: YES/NO**. Blocked decisions retain a readable reason instead of presenting a tradable-looking plan.

## v0.5 Opportunity Search UI

The v0.5 UI provides:

- selectable analysis scope: **Торгуемые инструменты** / **Мой портфель**;
- trading-profile selection;
- instrument-type selection;
- decision filtering;
- staged progress reporting with the current processing stage and instrument count;
- incremental table population while the scan is running;
- forecast columns for 5-day price and probability of growth;
- strategy score, risk score and opportunity score;
- separate **Готовность** status in the results table;
- localized Russian UI and decision explanations;
- detailed forecast and trade-plan panel for the selected instrument;
- explicit execution readiness and reduction sizing;
- safe handling when the user changes pages while background analysis is running.

## Walk Forward cache controls

The UI exposes persistent Walk Forward cache controls:

- current cache size;
- reuse of valid optimization results;
- forced Walk Forward recalculation;
- complete cache clearing;
- cache usage across repeated market and portfolio analyses.

This reduces repeated parameter-search work when the underlying analysis context has not changed.

## Market data and T-Invest contract compatibility

Edward uses the T-Invest market-data contracts for:

- historical candles;
- last prices;
- trading statuses;
- instrument availability.

Historical daily data is normalized before entering the analysis pipeline, including protobuf-style timestamps and quotations.

Large market-data requests are processed in batches to avoid oversized API requests and to isolate failures between batches.

## Testing

The v0.5 development line includes regression coverage for:

- Decision Engine scenarios and ranking;
- Risk Engine;
- Opportunity Engine;
- portfolio and market opportunity search;
- Walk Forward and forecast caches;
- forecast model selection;
- forecast Walk Forward validation;
- point-in-time and anti-leakage validation;
- trade plan and position sizing;
- execution-readiness gates;
- UI forecast/trade-plan formatting;
- UI readiness and blocked-plan behavior;
- staged progress and incremental result updates;
- T-Invest adapter compatibility;
- regression coverage for the v0.4/v0.5 integration pipeline.

Run the full test suite with:

```bash
python -m pytest -q
```

## Version 0.5.0 status

Version 0.5.0 is the frozen baseline for the forecast, trade-plan, position-sizing and execution-readiness layers on top of the v0.4 Decision Engine.

The next development cycle can build on this baseline without changing the v0.5 architecture. The next priority is improving decision quality and preparing a controlled Execution Engine for future automated trading.
