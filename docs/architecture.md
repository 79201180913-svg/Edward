# Edward v0.1 — Architecture

## Goals

Edward v0.1 is a Python trading application integrating with T-Invest API. The first implementation is backend-first: the UI is intentionally deferred, while the application/domain/API boundaries are established now.

## Layers

- `domain` — business entities and value objects; no T-Invest SDK dependency.
- `api` — adapter around the T-Invest Python SDK; no UI logic.
- `services` — application use cases and validation orchestration.
- `validation` — pre-trade safety and consistency checks.
- `storage` — local persistence, including `.xlsx` trade history.
- `config` — environment and secret configuration.

## Source of truth

T-Invest API is the source of truth for account, portfolio, balance, order and execution state. Local storage must never be used to decide whether an order was created or executed.

## Environments

The application supports two environments:

- `sandbox` — default and safe for development/testing.
- `production` — explicit opt-in for real trading.

The production trading gateway must not be selected implicitly.

## Token handling

The UI will accept the T-Invest API token. The application will persist it through the OS credential store using `keyring`, not in source code, Excel, logs, or plain-text configuration. The `.env` file is reserved for non-secret configuration such as environment selection.

## Trading flow

1. Load credentials and environment.
2. Connect through the API adapter.
3. Load accounts and select an active account.
4. Load instrument/trading status and market data.
5. Validate the order immediately before submission.
6. Submit with a unique idempotency identifier.
7. Persist the returned `order_id`.
8. Track order state until terminal state.
9. On execution, obtain factual execution/operation data.
10. Update local Excel history without ever resubmitting the order.

## Initial modules

```text
src/edward/
├── api/
├── config/
├── domain/
├── services/
├── storage/
└── validation/
```

The UI will depend on services, never directly on the T-Invest SDK.
