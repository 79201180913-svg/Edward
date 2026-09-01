# Edward v0.8.11 — Release Freeze

## Release status

Version `0.8.11` freezes and integrates the Market Context scope into the Edward platform.

## Included

- point-in-time market benchmark resolution;
- Market Context snapshot with market regime, relative strength and relative volatility;
- conditional discovery as research/evidence only;
- market-context shadow scoring and market-aware research ranking;
- point-in-time baseline vs context A/B diagnostic;
- runtime integration into the existing v0.8.8 analysis flow;
- graceful `UNAVAILABLE` behavior when benchmark data is unavailable;
- analysis progress UX and updated analysis UI;
- T-Invest candle/instrument adapter boundaries required by Market Context;
- regression coverage for runtime, point-in-time safety, benchmark resolution, shadow ranking and UI integration;
- frozen v0.8.11 system analysis in `docs/Edward_v0.8.11_System_Analysis_Market_Context.md`.

## Architectural invariants

The release is additive. The canonical v0.8.8 analysis remains the source of truth.

Market Context does not:

- replace the canonical Analysis result;
- bypass or weaken Walk Forward;
- change Quality Gate thresholds;
- turn conditional discovery into an automatic production decision;
- create a second analytical source for Opportunity Search.

## Evidence conclusion

The v0.8.11 runtime demonstrated that Market Context can alter research ranking, but the available RZSB A/B experiment does not establish a general performance improvement. Therefore Market Context remains an evidence/shadow layer and is not treated as a proven production alpha mechanism.

## Version

`0.8.11`
