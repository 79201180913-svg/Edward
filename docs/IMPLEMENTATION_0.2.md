# Edward 0.2 implementation scope

## Goal
Bring the trading core into alignment with the T-Invest contracts and SR-001..SR-115.

## Completed baseline in this branch
- OrdersService contract model: LIMIT, MARKET, BESTPRICE.
- Separate domain boundary for stop orders.
- API response normalization for dict/protobuf order state.
- Partial/full execution state handling.
- CI tracks main and version-0.2.

## 0.2 delivery scope
1. Contract compliance: OrdersService and StopOrdersService, request/response DTOs, errors.
2. Instrument availability: buy/sell flags, trading status, schedule and user restrictions where exposed by API.
3. Balance and portfolio: available/blocked, multi-currency RUB/USD display, valuation and refresh.
4. Order engine: buy/sell, order types, quantity/price validation, idempotency and final preflight.
5. Order state machine: NEW, ACTIVE, PARTIALLY_FILLED, FILLED, CANCELLED, REJECTED, ERROR.
6. Execution processing: actual fills, price, amount, commission and remaining quantity.
7. Commission: pre-trade estimate where supported and actual commission after execution.
8. Restart recovery: accounts, active orders, portfolio and balance followed by monitoring.
9. History: actual executions to XLSX, deduplication and separate cancelled/rejected records.
10. Error handling: normalized categories and retry policy.
11. UI notifications for lifecycle events.
12. Unit, integration, sandbox and negative regression tests.

## Non-goals
Telegram, automated trading, strategy engine, mobile UI, cloud synchronization and advanced analytics.

## Completion rule
Do not merge this branch to main until the P0/P1 items above have tests and the trading path is contract-compatible end to end.
