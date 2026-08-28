# Edward v0.8.2 — Fundamental Analysis

## Status

**Release:** v0.8.2  
**Scope:** Structured Fundamental Analysis layer  
**Baseline:** v0.8.1 Multifactor Analysis

## What is fixed

- Added structured Fundamental Analysis with seven analytical groups.
- Added strategy-profile-aware aggregation for `long_term`, `medium_term` and `speculative` profiles.
- Added explicit metric states: `AVAILABLE`, `UNAVAILABLE`, `NOT_APPLICABLE`.
- Missing fundamental data no longer becomes artificial negative evidence.
- Valid zero values remain valid for metrics where zero has economic meaning.
- Zero valuation multiples are treated as unusable and therefore unavailable.
- Added coverage- and confidence-aware group scoring.
- Added weight renormalization across usable weighted groups.
- Kept evidence-only metrics visible without double-counting them in group scores.
- Added metric/group audit diagnostics with raw value, mapped value, status and reason codes.
- Added Fundamental Analysis details to the UI, including `N/A` for groups without usable evidence.
- Kept the implementation instrument-agnostic; SBER is only a validation/example instrument and is not a system constant.

## Fundamental groups

1. Business Quality
2. Growth
3. Cash Generation
4. Financial Health
5. Valuation
6. Shareholder Return
7. Fundamental Momentum

## Important behavior

Unavailable data reduces coverage/reliability instead of being interpreted as a zero score. Explicitly not-applicable metrics are excluded from the applicable denominator. Overall Fundamental Score uses only usable groups with a positive profile weight and renormalizes their weights.

## Validation

The v0.8.2 implementation was validated against the automated test suite during development. The release is intended to be merged into `main` as the fixed v0.8.2 baseline.
