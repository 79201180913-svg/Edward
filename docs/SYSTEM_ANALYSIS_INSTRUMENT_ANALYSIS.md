# Edward — System Analysis of Instrument Analysis

## 1. Purpose

This document fixes the current system-level design of Edward instrument analysis as the baseline for version 0.8.1.

The goal of the analysis is to transform an instrument snapshot and market history into a structured, evidence-aware assessment that can be consumed by the existing opportunity and decision pipeline without changing the external v0.8 output contract.

The analysis is instrument-centric and additive: v0.8.1 extends the stable v0.8 pipeline rather than replacing it.

## 2. High-level flow

```text
T-Invest / market data / portfolio context
                  |
                  v
        Contract data collection
                  |
                  v
          Contract mapping
                  |
                  v
       Evidence normalization
                  |
                  v
       Multifactor analysis
                  |
        +---------+---------+
        |                   |
        v                   v
  factor evidence      cross-factor
                        conflicts
        |                   |
        +---------+---------+
                  v
          Evidence aggregate
                  |
                  v
         v0.8 base pipeline
                  |
                  v
        Multifactor overlay
                  |
                  v
       Existing decision output
```

`AnalysisPipelineServiceV081` is an additive facade over the stable v0.8 pipeline. It runs the existing base analysis first, then enriches it with the v0.8.1 multifactor layer, normalizes the resulting evidence, applies the overlay and returns the v0.8.1 result object. The base result remains available through the result facade.

## 3. Input domains

The current analysis uses the following contract-backed input domains:

| Domain | Main purpose | Primary data |
|---|---|---|
| Historical candles | trend, volatility, returns, volume context | candles |
| Fundamentals | business quality, growth, valuation, balance sheet and cash flow | asset statistics / fundamentals |
| Order book | spread, depth and imbalance | bids / asks |
| Last trades | executed-flow imbalance and liquidity context | trade direction and quantity |
| Signals | current and historical strategy evidence | current signal + historical signals |
| Reports / events | event and gap risk | asset reports |
| News | current information flow and news risk | news items |
| Dividends | shareholder return evidence | dividend data |
| Insider activity | management/investor transaction evidence | insider deals |
| Trading session | execution context | trading schedules |
| Risk rates | broker margin/risk information when available | RiskRates response |
| Instrument metadata | client-specific margin and short availability | Instrument response |
| Portfolio context | concentration, marginal risk and diversification | portfolio weights/returns |

Not all domains are mandatory. Optional contract sources are represented as unavailable evidence rather than as artificial zero values.

## 4. Contract-source separation

A critical design rule is that different T-Invest contract sources must not be merged into one raw structure when they represent different semantics.

### Risk Rates

`GetRiskRates` is the source for the risk-rate response and contains `long_risk_rate`, `short_risk_rate`, `long_risk_rates[]`, `short_risk_rates[]` and a possible error result.

### Instrument metadata

`GetInstrumentBy` is the source for instrument metadata such as `dlong_client`, `dshort_client` and `short_enabled_flag`.

These sources are kept separate in the analysis data model:

```text
risk_data
instrument_risk_metadata
```

The instrument metadata is the preferred source for the Instrument Risk factor when it is available. Risk rates remain available as a fallback for callers that do not provide instrument metadata directly.

This separation prevents one source from silently overwriting values from another source.

## 5. Evidence model

Each factor produces an `Evidence` object with:

```text
name
direction
strength
reliability
freshness
available
reason
```

Evidence quality is derived from strength, reliability and freshness. An unavailable factor contributes zero evidence quality rather than being interpreted as a negative signal.

The system therefore distinguishes:

```text
AVAILABLE
    valid source + usable data

UNAVAILABLE
    source is valid, but usable data is absent

MAPPING / FAILURE
    source was returned, but Edward could not interpret it correctly
```

This distinction is important for both diagnostics and decision quality.

## 6. Fundamental analysis

The Fundamental factor evaluates several dimensions rather than a single ratio:

```text
Profitability
Growth
Balance sheet
Cash flow
Valuation
Shareholder return
Momentum context
```

Current supported inputs include, where provided:

- ROE / return on equity;
- ROIC / return on invested capital;
- net margin;
- one-, three- and five-year revenue growth;
- EPS growth;
- EBITDA growth;
- debt-to-EBITDA;
- current ratio;
- free cash flow;
- P/E, P/S, P/B and P/FCF;
- dividend yield and payout.

Contract-backed additional fields are reserved for further quality improvement where appropriate, including ROA, debt-to-equity, FCF-to-price, EV/EBITDA and EV/sales.

The factor produces component scores for quality, growth, valuation, balance sheet, cash flow, shareholder return and momentum, followed by an overall evidence direction.

The system must not interpret a missing fundamental metric as zero. Missing optional metrics reduce coverage/reliability instead.

## 7. Market microstructure

Microstructure combines order-book and trade information.

Primary calculations:

```text
Best bid / best ask
Spread percentage
Bid/ask depth
Order imbalance
Executed trade imbalance
Liquidity score
Entry quality score
```

The intent is to answer a different question from fundamental analysis:

> Is the instrument currently easy and efficient to enter, and does actual market flow support that entry?

Microstructure therefore complements, rather than duplicates, the strategic and fundamental layers.

## 8. Volume pressure

The current v0.8.1 Volume Pressure factor is based on buy and sell volume fields available on the candle representation:

```text
volume_buy
volume_sell
```

It calculates:

```text
Buy pressure %
Sell pressure %
Net pressure %
Accumulation score
Distribution score
```

If no usable buy/sell volume exists, the result is explicitly unavailable:

```text
reason = NO_BUY_SELL_VOLUME
```

The presence of `last_trades` provides a potential future evidence source for executed buy/sell pressure. That is intentionally separate from the current factor contract and should only be introduced as a defined enhancement, not as an implicit fallback.

## 9. Signal analysis

Signal evidence uses:

- current signal direction;
- historical signal outcomes;
- hit rate;
- average historical return;
- derived signal reliability.

Historical outcomes use point-in-time entry/close information where available. The purpose is to measure whether the current signal family has demonstrated useful behavior on the instrument rather than blindly treating the current signal as truth.

## 10. Event risk

Event analysis evaluates the distance to an event and historical behavior around events, including:

```text
days to event
historical gap
historical post-event volatility
```

The result expresses event risk as a factor that can weaken the opportunity even when other factors are positive.

## 11. News risk

News analysis is a separate intelligence layer.

Current processing includes:

```text
lookback window
instrument relevance
published timestamp
priority
explicit sentiment when available
title/content relevance
positive / negative / neutral classification
```

News older than the configured lookback is excluded. When an item is linked to a different instrument, it is excluded from instrument-specific analysis.

If a news item does not provide explicit sentiment, the current model may classify it as neutral rather than inventing a sentiment value.

The result exposes both parsed evidence and an aggregate news-risk score.

No opaque external consensus/forecast is used in this v0.8.1 analysis design.

## 12. Dividend and insider evidence

Dividend evidence evaluates available yield and payout information together with growth/stability context.

Insider evidence evaluates the direction and activity of insider transactions and can incorporate historical follow-through when available.

Both are supplementary factors. Neither is allowed to replace the base strategy analysis on its own.

## 13. Session factor

The Session factor contextualizes whether the current market session is suitable for execution.

The analysis distinguishes sessions such as:

```text
PREMARKET
OPENING_AUCTION
REGULAR
CLOSING_AUCTION
EVENING
CLEARING
```

Session quality is part of execution context rather than a standalone prediction of price direction.

## 14. Instrument Risk factor

Instrument Risk answers:

> How expensive or restrictive is the broker-defined position/risk profile for this instrument?

The factor uses:

```text
dlong_client
dshort_client
short_enabled
```

when instrument metadata is available.

Risk-rate data from `GetRiskRates` remains a fallback source when direct instrument metadata is absent.

Current normalization converts fractional rates to percentages when values are in `[0, 1]`.

Effective risk is based on the relevant available client margin rate, respecting whether short is enabled. High margin requirements reduce capital efficiency and increase the risk score.

An instrument with no usable margin data remains `UNAVAILABLE`; the system must not fabricate a numerical risk value merely because the source request succeeded.

## 15. Portfolio factor

Portfolio context is intentionally separated from instrument-only analysis.

The Portfolio factor can use:

```text
current weight
concentration penalty
marginal risk
 diversification benefit
expected return impact
maximum position weight
```

Its role is to answer:

> Is this instrument attractive for the current portfolio, not merely attractive in isolation?

This is required for correct ADD/REDUCE decisions and for reallocation decisions when better opportunities appear while available slots are occupied.

## 16. Multifactor aggregation

The multifactor result contains the individual factor results plus aggregate evidence and reliability measures.

The system also tracks factor conflicts.

Example:

```text
Fundamentals       POSITIVE
Microstructure     POSITIVE
Signal             POSITIVE
Instrument Risk    NEGATIVE
News Risk          HIGH
```

The correct behavior is not to hide the conflict by producing a single opaque number. The overlay should preserve the factor evidence and apply explicit adjustments/penalties.

## 17. Overlay and decision interaction

The v0.8.1 overlay operates on top of the existing v0.8 opportunity/confidence result.

Conceptually:

```text
v0.8 opportunity
        +
multifactor evidence
        +
reliability
        +
conflict penalties
        +
execution/session constraints
        ↓
adjusted opportunity / confidence
```

The public result remains compatible with the existing v0.8 consumer model. The new multifactor fields are additive.

## 18. Decision principles

The analysis must follow these principles:

1. **Evidence before score.** A score without identifiable source evidence is not trusted.
2. **Missing data is not negative data.** A valid but empty source becomes unavailable evidence.
3. **Contract semantics must be preserved.** Separate API sources must not silently overwrite each other.
4. **Risk can veto opportunity.** Strong opportunity does not justify ignoring critical execution or instrument-risk conditions.
5. **Portfolio context matters.** A good instrument may still be a poor portfolio action.
6. **Conflicts remain visible.** Disagreement between factors is information, not noise.
7. **The v0.8 public output remains stable.** Existing integrations must not require a breaking change.
8. **No opaque external forecast.** v0.8.1 does not depend on an unexplained external consensus forecast.

## 19. Diagnostics and observability

The analysis pipeline uses targeted diagnostics to distinguish data availability from mapping and calculation issues.

Important diagnostic stages include:

```text
RAW source
MAPPED source
NORMALIZED input
FACTOR result
OVERLAY result
```

A production diagnostic should make it possible to answer for every factor:

```text
Did the API respond?
Did the source contain data?
Did mapping succeed?
What exact data entered the factor?
What score was produced?
Was the factor available?
Why was it unavailable?
```

## 20. Current known behavior at the frozen 0.8.1 baseline

The frozen baseline intentionally preserves the successful v0.8.1 multifactor implementation and diagnostic commits.

Known semantic examples:

- a valid empty `RiskRates` result may produce `Instrument Risk = UNAVAILABLE`;
- empty fundamentals/news/insider/event collections are not automatically treated as mapping failures;
- instrument metadata and risk-rate payloads remain separate inputs;
- floating-point score assertions use approximate comparison in tests;
- the public v0.8 analysis contract remains unchanged.

These behaviors are part of the baseline and should not be changed implicitly during subsequent enhancements.

## 21. Evolution path after 0.8.1

Potential future improvements should be implemented as explicit tasks, with regression tests and without breaking the v0.8 public contract.

Candidate areas include:

```text
1. Improve Fundamental coverage using additional contract statistics.
2. Define a formal trade-based Volume Pressure evidence source.
3. Improve News relevance and sentiment quality using only explainable inputs.
4. Add stronger cross-factor conflict explanations.
5. Improve portfolio-aware reallocation reasoning.
6. Calibrate evidence reliability using observed historical coverage.
7. Expand end-to-end validation of the complete analysis-to-decision chain.
```

## 22. Compatibility requirement

All changes to this analysis must preserve the existing external parameters and integration-facing result fields unless a versioned contract change is explicitly approved.

The preferred extension pattern is:

```text
existing v0.8 input/output
        +
optional v0.8.1 evidence
        +
optional v0.8.1 factor metadata
```

rather than changing or renaming existing v0.8 fields.

## 23. Baseline

This document is frozen against the `version-0.8.1-multifactor` branch baseline at commit:

```text
4d0a4eb987c98a48af16f5a46e275682cc89728b
```

That commit is the current control point for the v0.8.1 analysis branch after the subsequent experimental runtime changes were discarded.
