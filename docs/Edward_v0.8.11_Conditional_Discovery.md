# Edward v0.8.11 — Conditional Discovery

## Purpose

v0.8.11 adds a research-only conditional discovery layer on top of the point-in-time market context introduced in the release branch.

The layer answers whether a historical future-return effect is observable under a named condition. It does not make trading decisions.

## Inputs

Each observation contains:

- `as_of` — observation timestamp;
- `condition` — the exact point-in-time condition label;
- `future_return_pct` — the future outcome associated with that observation.

Conditions can represent combinations such as market regime, relative strength, volatility context, or other explicitly constructed evidence states.

## Outputs

For each requested condition the engine calculates:

- observation count;
- mean future return;
- median future return;
- positive-return rate;
- minimum and maximum future return;
- simple 95% normal-approximation confidence interval.

The result status is:

- `SUFFICIENT` — sample meets the configured minimum;
- `INSUFFICIENT_SAMPLE` — effect is observed but the sample is too small;
- `UNAVAILABLE` — no observations for the condition.

## Guardrail

Conditional discovery is explicitly research/evidence only. It must not:

- select a live strategy;
- modify strategy score;
- modify confidence;
- bypass Walk Forward;
- bypass Quality Gate;
- turn a small-sample observation into a trading recommendation.

## Integration sequence

The intended v0.8.11 flow is:

`point-in-time market context → conditional discovery → evidence → existing strategy/WF/QG pipeline`

The current implementation establishes the discovery contract without changing the canonical v0.8.2 scoring or Quality Gate behavior.
