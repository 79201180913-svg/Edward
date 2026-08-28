# Edward — System Analysis of Instrument Analysis v0.8.2

## 1. Purpose

This document fixes the system-level logic introduced by version 0.8.2 of Edward instrument analysis.

Version 0.8.2 adds a structured Fundamental Analysis layer on top of the existing v0.8/v0.8.1 instrument-analysis pipeline. The layer is evidence-aware, strategy-profile-aware and coverage-aware. It must not manufacture positive or negative evidence from missing data.

SBER may be used as a runtime/example instrument when validating the implementation, but the analysis is instrument-agnostic. No ticker, instrument UID, budget, or portfolio value is hardcoded into the analysis logic.

## 2. Position in the analysis pipeline

```text
T-Invest contract data
        |
        v
contract mapping
        |
        v
normalized instrument snapshot
        |
        +-----------------------------+
        |                             |
        v                             v
base v0.8 analysis             Fundamental Analysis v0.8.2
                                      |
                                      v
                              group scores + coverage
                                      |
                                      v
                              strategy-profile weights
                                      |
                                      v
                              weighted fundamental score
                                      |
                                      v
                         Fundamental factor for v0.8.1
                         multifactor evidence aggregation
```

The v0.8.2 Fundamental layer is additive. Existing v0.8/v0.8.1 analysis and decision contracts remain compatible.

## 3. Strategy profile dependency

Fundamental analysis is not interpreted independently of the intended trading horizon.

Supported profiles:

- `long_term` — higher weight on business quality, financial health and valuation;
- `medium_term` — balanced fundamental evidence with increased fundamental momentum weight;
- `speculative` — strongly emphasizes fundamental momentum while retaining risk and valuation context.

Accepted aliases are normalized to the canonical profiles. Unknown profiles fall back to `medium_term`.

The profile affects aggregation weights; it does not change the raw metric values or their individual scoring functions.

## 4. Fundamental groups

The Fundamental layer produces seven groups:

| Group | Main metrics |
|---|---|
| Business Quality | ROE, ROIC, ROA, net margin |
| Growth | 1Y/3Y/5Y revenue growth, 5Y revenue change, EPS growth, EBITDA growth |
| Cash Generation | free cash flow, FCF-to-price |
| Financial Health | current ratio, net debt/EBITDA, total debt/EBITDA, debt/equity |
| Valuation | P/E, P/S, P/B, P/FCF, EV/EBITDA, EV/sales |
| Shareholder Return | dividend yield, payout, dividend growth, regularity |
| Fundamental Momentum | 1Y/3Y/5Y revenue growth, EPS growth, EBITDA growth |

`revenue_change_5y` remains available as growth evidence but is excluded from the independent Growth score so that cumulative change is not double-counted alongside normalized growth rates.

## 5. Metric scoring

Each usable metric is converted into a 0–100 score by the v0.8.2 scoring engine according to its metric type:

```text
profitability -> profitability scoring
valuation     -> valuation scoring
leverage      -> leverage scoring
current ratio -> liquidity/current-ratio scoring
debt/equity   -> debt-to-equity scoring
cash flow     -> cash-flow scoring
FCF yield     -> FCF-yield scoring
growth        -> growth scoring
payout        -> payout scoring
regularity    -> clamped score
```

Metric direction is derived from the resulting score:

```text
score > 60 -> POSITIVE
score < 40 -> NEGATIVE
otherwise  -> NEUTRAL
```

Business Quality additionally applies the defined ROE/leverage quality adjustment when the required inputs are available.

## 6. Data availability semantics

The analysis explicitly distinguishes three states:

```text
AVAILABLE
    usable metric value exists

UNAVAILABLE
    metric is applicable, but no usable value exists

NOT_APPLICABLE
    metric is explicitly outside the instrument/context scope
```

These states are not interchangeable.

An unavailable metric contributes neither positive nor negative evidence. It reduces group coverage and therefore group confidence.

An explicitly not-applicable metric is excluded from the applicable denominator and does not reduce coverage for that group.

A mapping or contract failure remains a diagnostic/mapping problem and must not be silently converted into a valid numerical score.

## 7. Zero-value handling

Zero is not globally interpreted as missing.

A numeric zero is a valid observation for operating/fundamental metrics where zero has economic meaning. For example, `ROE = 0.0` remains an available metric when there is no explicit not-applicable context.

Valuation multiples have a special rule. A zero value for:

```text
P/E
P/S
P/B
P/FCF
EV/EBITDA
EV/sales
```

is treated as unavailable because it does not represent a usable valuation multiple in the analysis model.

This distinction must be preserved both in the mapped data and in the audit log. The audit log must retain the original raw value while recording the mapped availability state.

## 8. Contract mapping

The T-Invest fundamental contract is mapped into Edward's normalized metric names. Quotation-like values are converted to numeric values before scoring.

The mapper must preserve the difference between:

```text
raw API value
mapped numeric value
analysis availability state
```

For the v0.8.2 fundamental contract, API zero values that are defined as unusable source values are mapped to `None`; downstream analysis then records them as `UNAVAILABLE` rather than scoring them as zero.

## 9. Group coverage

Coverage is calculated over applicable scoring metrics:

```text
coverage = available applicable scoring metrics
           ----------------------------------- x 100
             total applicable scoring metrics
```

Evidence-only metrics that are intentionally excluded from a group's score remain visible in the metric list and are reported with the reason:

```text
EVIDENCE_METRICS_EXCLUDED_FROM_SCORE
```

This prevents double counting while retaining useful diagnostic evidence.

Group confidence is based on available metric confidence and coverage. Low or partial coverage is explicitly represented through reason codes such as:

```text
LOW_DATA_COVERAGE
PARTIAL_DATA_COVERAGE
GROUP_UNAVAILABLE
METRICS_NOT_APPLICABLE
```

## 10. Fundamental Momentum

Fundamental Momentum is calculated from the growth trajectory and supporting EPS/EBITDA growth inputs.

The calculation considers:

```text
5Y revenue growth
3Y revenue growth
1Y revenue growth
EPS growth
EBITDA growth
```

Growth acceleration is derived from the available horizon values and classified as an explicit reason/evidence component.

Unavailable inputs are omitted from usable evidence rather than converted into zero growth.

## 11. Weighted overall Fundamental Score

The overall Fundamental Score is calculated from usable groups according to the selected strategy profile.

Only groups satisfying both conditions participate directly in the weighted aggregate:

```text
coverage > 0
profile weight > 0
```

If some weighted groups are unavailable, their weights are renormalized across the usable weighted groups. This prevents missing data from automatically producing an artificial zero score.

If no usable weighted group exists, the overall Fundamental Score and confidence are zero and the result is unavailable/partial according to the result contract.

The normalized group weights remain observable in the result so that the reason for the final score can be audited.

## 12. Evidence and auditability

The v0.8.2 service exposes structured results for:

```text
metric
value
score
available
confidence
freshness
direction
reason_codes
```

Group results additionally expose:

```text
score
confidence
coverage
metrics
reason_codes
```

The service writes metric-level audit records containing the raw value, mapped value, availability state, score, direction and reason information.

A diagnostic consumer must be able to determine whether a value was:

1. absent at the source;
2. explicitly not applicable;
3. mapped to an unusable value;
4. successfully scored.

## 13. Fundamental factor integration

The structured Fundamental result is consumed by the v0.8.1 multifactor layer as a factor with:

```text
score
reliability/confidence
availability
reason
```

The Fundamental factor must not be inferred from ticker identity or a fixed example instrument.

## 14. UI requirements for v0.8.2

The Fundamental Analysis UI must show:

- overall Fundamental Score;
- overall Confidence;
- overall Coverage;
- selected strategy Profile;
- all seven group results;
- `N/A` for groups with no usable applicable scoring evidence;
- metric-level diagnostic details on demand.

A group with no usable data must not be displayed as a numerical `0.0` score when that zero would imply a negative or neutral economic assessment. It must be represented as `N/A` with coverage/confidence information.

## 15. Example validation behavior

A runtime run may use SBER as an example instrument. The expected interpretation is generic and must also apply to any other supported instrument:

```text
available fundamental data
        |
        v
structured groups
        |
        +--> unavailable groups remain N/A
        |
        +--> usable groups are scored
        |
        v
coverage-aware profile weighting
        |
        v
Fundamental Score + Confidence + Coverage
```

The example instrument does not define system constants.

## 16. Version acceptance criteria

Version 0.8.2 is accepted when:

1. Fundamental Analysis is structured into the defined groups.
2. Strategy profile changes aggregation weights without changing raw metric scoring.
3. Missing data is not converted into negative evidence.
4. Explicitly not-applicable metrics are excluded from applicable coverage.
5. Valid zero values remain available where zero has valid economic meaning.
6. Zero valuation multiples are treated as unavailable.
7. Evidence-only metrics remain visible but do not cause double scoring.
8. Group coverage and confidence are exposed.
9. Overall group weights are renormalized over usable weighted groups.
10. Fundamental results integrate with the existing multifactor layer without instrument-specific hardcoding.
11. The UI represents unavailable groups as `N/A` rather than misleading `0.0`.
12. Automated tests cover the availability, zero-value, audit-log and profile-weighting rules.

## 17. Relationship to previous specifications

This document is the v0.8.2 extension of the v0.8.1 system analysis specification. Existing v0.8.1 multifactor principles remain in force unless explicitly superseded here.

The key v0.8.2 change is the introduction of a structured, coverage-aware Fundamental Analysis layer with explicit metric availability semantics and strategy-dependent aggregation.
