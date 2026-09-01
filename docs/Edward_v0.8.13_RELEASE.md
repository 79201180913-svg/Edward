# Edward v0.8.13 — Release Marker

## Release status

Version `0.8.13` is frozen and ready for release to `main`.

## Scope delivered

- Opportunity Service consumes canonical `TradingPathAnalysisV012` results;
- legacy opportunity recalculation removed from the canonical handoff;
- portfolio-scoped opportunity scan analyzes only portfolio instruments;
- completed live-scan results are streamed to the UI incrementally;
- canonical event observations are reused per instrument to avoid redundant work;
- bulk last-price retrieval is protected against transient T-Invest HTTP 504 failures;
- local adapter client disconnects such as Windows `10053`, broken pipe and reset connections are treated as non-fatal disconnects;
- regression coverage added for the new consumer, portfolio scope, incremental UI, transport resilience and adapter disconnect handling;
- full automated test suite verified green locally.

## Architectural boundary

`Decision` remains part of the canonical Trading Path analysis and is not changed in v0.8.13.

Portfolio state is used for selecting the scan universe only. It does not reinterpret or override canonical `BUY / WAIT / PASS` analysis decisions.

Position-aware actions such as `HOLD`, `REDUCE` or `SELL` derived from an existing holding are explicitly deferred to a future version.

## Version

`0.8.13`
