# Edward

Python trading platform for T-Invest.

Current stable version: **0.6.0**

## Platform overview

Edward is a desktop trading platform for T-Invest that combines manual trading, adaptive market analysis, portfolio-aware opportunity search and controlled order execution. The platform is built around an instrument-centric workflow and separates analytical decisions from the final execution confirmation.

## Core capabilities

- T-Invest Sandbox integration for accounts, portfolio, positions, balances and market data;
- instrument catalog with ticker, UID, identifiers, price and trading availability;
- market prices, close-price change and trading status;
- BUY/SELL availability and order-type availability;
- manual order entry and order lifecycle monitoring;
- order history and local persistence;
- portfolio value, available cash, position quantity and portfolio weight;
- position and P&L context for decision making;
- adaptive strategy analysis for different trading profiles;
- portfolio-aware opportunity search;
- controlled execution through an explicit user confirmation step.

## v0.4 Decision Engine baseline

Version 0.4 introduced the analysis-to-decision pipeline:

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

Edward evaluates multiple strategies and selects the best available candidate for the current trading profile:

- Trend Following;
- Momentum;
- Breakout;
- Mean Reversion.

Trading profiles are adaptive to the intended trading horizon:

- long-term;
- medium-term;
- speculative.

The Risk Engine evaluates drawdown, volatility, risk level, portfolio weight, cash, portfolio fit and critical-risk conditions. The Opportunity Score combines strategy quality, entry quality, market-regime compatibility, risk, portfolio fit and confidence.

## v0.5 Forecast and trading-readiness layer

Version 0.5 extended the decision pipeline with forward-looking price analysis and execution-readiness controls:

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

The forecasting layer supports 1-, 5-, 20- and 60-trading-day horizons, adaptive model selection, point-in-time validation, anti-leakage checks and versioned forecast caching.

Trade plans can contain entry range, target, stop, expected return, expected risk, Risk/Reward, holding horizon, confidence and recommended position size. Portfolio reductions and exits expose the recommended reduction quantity and expected remaining position.

Execution readiness combines strategy Quality Gate, forecast Quality Gate, risk conditions, portfolio availability, trading status, position sizing, entry/target/stop readiness, liquidity and Risk/Reward. The result is exposed as **Execution Ready: YES/NO**.

## v0.6 Controlled Execution

Version 0.6 turns execution from a UI placeholder into a controlled execution flow connected to the T-Invest Sandbox.

### Business flow

```text
Analysis decision
      ↓
Execution Ready
      ↓
Передать в исполнение
      ↓
Ожидает подтверждения
      ↓
Live pre-trade revalidation
      ↓
Подтвердить и отправить
      ↓
T-Invest /orders/create
      ↓
Submitted
```

### Execution Center

The Execution Center provides:

- a shared execution queue between opportunity analysis and execution UI;
- selection of the active execution request;
- readable Russian execution status and event text;
- a simplified confirmation UX without exposing the internal validation pipeline;
- explicit user confirmation immediately before broker submission;
- asynchronous submission so network operations do not block Tkinter;
- protection against duplicate active submissions;
- safe handling of stale UI callbacks and queue-selection recursion;
- execution event journal and submission status.

The UI intentionally hides technical checks such as Trading Status, position revalidation and cash/max-lots validation. These checks remain mandatory in the execution service.

### Live pre-trade validation

Immediately before submission Edward revalidates live broker/account conditions.

For BUY/ADD the validator checks account availability, live price, trading status, quantity, price step, cash and broker max-lots.

For REDUCE/SELL it checks account availability, live price, trading status, quantity, price step and the actual held position. Broker max-lots is not used for exits because the held position is the controlling quantity constraint.

The validator accepts both normalized Edward fields and the T-Invest contract fields such as `*_available_flag`.

### T-Invest order contract

Version 0.6 includes compatibility fixes for the Sandbox order boundary, including:

- quotation serialization for Decimal prices;
- UUID normalization for `request_id` / order id;
- preservation of the execution identity while satisfying the broker UUID contract;
- adapter handling for live trading-status flags.

A real Sandbox REDUCE execution has been verified end-to-end through `/orders/create` with a successful API response.

### Simplified confirmation UX

The user sees a small number of business states instead of the internal execution pipeline:

```text
Решение готово
    ↓
Передать в исполнение
    ↓
Заявка подготовлена / Ожидает подтверждения
    ↓
Подтвердить и отправить
    ↓
Заявка отправлена
```

Before submission the system performs the technical live checks automatically.

## Market data and T-Invest compatibility

Edward uses T-Invest contracts for historical candles, last prices, trading statuses and instrument availability. Historical daily data is normalized before entering the analysis pipeline, including protobuf-style timestamps and quotations.

Large market-data requests are processed in batches to avoid oversized API requests and isolate failures between batches.

## Testing

The v0.6 development line includes regression coverage for:

- Decision Engine scenarios and ranking;
- Risk Engine;
- Opportunity Engine;
- market and portfolio opportunity search;
- Walk Forward and forecast caches;
- forecast model selection and Walk Forward validation;
- point-in-time and anti-leakage validation;
- trade plan and position sizing;
- execution-readiness gates;
- execution queue and bridge behavior;
- Execution Center controller and UI behavior;
- asynchronous execution and UI-thread dispatch;
- stale Tk callback protection;
- live pre-trade validation;
- T-Invest trading-status compatibility;
- T-Invest order payload and UUID compatibility;
- Sandbox execution regression scenarios.

Run the full test suite with:

```bash
python -m pytest -q
```

## Version 0.6.0 status

Version **0.6.0** is the frozen baseline for the controlled execution layer on top of the v0.5 analysis and execution-readiness architecture.

Validated in the T-Invest Sandbox:

- execution request creation;
- user confirmation flow;
- live pre-trade revalidation;
- REDUCE order submission through `/orders/create`;
- T-Invest UUID contract compliance;
- successful Sandbox API acceptance of the submitted REDUCE order.

The next validation step is a complete BUY/ADD Sandbox execution scenario, followed by order monitoring, fill/reconciliation verification and final release hardening.
