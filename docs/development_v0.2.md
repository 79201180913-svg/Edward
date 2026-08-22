# Edward 0.2 Development Scope

## Baseline

- `main` is the frozen Edward 0.1 baseline.
- `version-0.2` is the active development branch.

## Completed increment 0.2.1 — Contract Compliance Foundation

- [x] Ordinary `OrdersService` order types aligned to `LIMIT`, `MARKET`, `BESTPRICE`.
- [x] `BESTPRICE` added to the application order request model.
- [x] Ordinary order requests reject price for `MARKET` and `BESTPRICE`.
- [x] Ordinary order requests require price for `LIMIT`.
- [x] Stop-order fields are rejected by the ordinary order model.
- [x] `OrdersApi` prevents stop-order types from being sent through `OrdersService`.
- [x] Runtime adapter supports mapping `BESTPRICE` to the installed T-Invest SDK enum when available.
- [x] Order monitor accepts both protobuf-like objects and REST dictionaries.
- [x] Partial-fill and full-fill status normalization covered by regression tests.
- [x] CI updated to run for `main` and `version-0.2`.

## Next 0.2 increments

### 0.2.2 — StopOrdersService

- [ ] Dedicated stop-order domain/request model.
- [ ] `StopOrdersService` adapter.
- [ ] Stop-order create/get/cancel operations according to the T-Invest contract.
- [ ] Stop-order UI availability and validation.

### 0.2.3 — Instrument availability

- [ ] buy/sell availability flags.
- [ ] trading status.
- [ ] trading schedule.
- [ ] user/instrument restrictions.
- [ ] final pre-submit availability check.

### 0.2.4 — Balance and portfolio

- [ ] available/blocked cash.
- [ ] multi-currency positions.
- [ ] RUB/USD display conversion.
- [ ] portfolio valuation and yield.

### 0.2.5 — Order lifecycle

- [ ] canonical order DTO.
- [ ] state machine.
- [ ] partial executions.
- [ ] cancellation.
- [ ] replacement.
- [ ] idempotency enforcement.

### 0.2.6 — Commission and execution

- [ ] preliminary order price/commission.
- [ ] actual execution price.
- [ ] actual commission.
- [ ] execution-to-history pipeline.

### 0.2.7 — Recovery and errors

- [ ] restart recovery.
- [ ] error classification.
- [ ] retry policy.
- [ ] active-order resynchronization.

### 0.2.8 — QA

- [ ] unit tests.
- [ ] adapter contract tests.
- [ ] sandbox integration tests.
- [ ] negative tests.
- [ ] regression suite.
