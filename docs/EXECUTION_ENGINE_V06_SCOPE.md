# Edward v0.6 — Execution Engine Scope

## Purpose

Version 0.6 introduces a separate Execution Engine service responsible for controlled execution of an already-approved trading decision.

The Execution Engine does not make investment decisions. Decision Engine and Execution Readiness remain the source of the trading decision and its approval status.

## Architecture

```text
Market Data
    ↓
Analysis
    ↓
Forecast
    ↓
Risk Engine
    ↓
Opportunity Engine
    ↓
Decision Engine
    ↓
Execution Readiness
    ↓
Execution Engine
    ↓
Pre-trade validation
    ↓
User confirmation
    ↓
T-Invest
    ↓
Order monitoring
    ↓
Reconciliation
```

## Core service

The new service is named `Execution Engine`.

Its responsibilities are:

1. Accept an immutable `ExecutionRequest` produced by the decision pipeline.
2. Validate that the request is technically and operationally executable.
3. Build the execution plan and order parameters.
4. Revalidate the market and account state immediately before submission.
5. Submit the order through a broker-specific execution adapter.
6. Monitor order state, including partial fills, fills, cancellation, timeout and rejection.
7. Reconcile broker state with Edward's local state.
8. Persist every execution attempt in an execution journal.
9. Recover safely after application restart without creating duplicate orders.
10. Expose execution state and events to the UI.

## Contract boundary

Execution Engine receives an immutable `ExecutionRequest` containing at least:

- execution_id;
- account_id;
- instrument_uid;
- ticker;
- decision;
- side;
- quantity;
- order_type;
- entry_price;
- stop_price;
- strategy;
- strategy_score;
- opportunity_score;
- risk_score;
- forecast_quality;
- execution_ready;
- portfolio_weight;
- target_weight;
- maximum_position_weight;
- analysis_snapshot;
- created_at.

Execution Engine must not rerun investment analysis as part of order submission.

## Execution state machine

```text
CREATED
  ↓
VALIDATING
  ↓
READY
  ↓
WAITING_CONFIRMATION
  ↓
SUBMITTING
  ↓
SUBMITTED
  ↓
PARTIALLY_FILLED
  ↓
FILLED
  ↓
RECONCILED
```

Error and terminal states include:

- BLOCKED;
- REJECTED;
- CANCELLED;
- TIMEOUT;
- FAILED;
- RECONCILIATION_ERROR.

## Pre-trade revalidation

Immediately before order submission the service must re-check:

- trading status;
- order availability;
- current market price;
- account balance / available cash;
- current position and quantity;
- position and risk limits;
- execution readiness;
- price and lot constraints;
- required order parameters.

If revalidation fails, the order is not submitted.

## Idempotency and recovery

Execution must be idempotent.

Every execution attempt has a persistent `execution_id` and broker/client order identifier where supported.

After restart or ambiguous network failure the service must reconcile the broker state before submitting another order. It must never blindly resubmit an order because local state is incomplete.

## Persistent execution journal

The journal stores at least:

- execution_id;
- account_id;
- instrument_uid;
- decision;
- side;
- order_type;
- requested_quantity;
- requested_price;
- stop_price;
- execution_ready;
- pretrade_status;
- broker_order_id;
- filled_quantity;
- average_fill_price;
- commission;
- lifecycle status;
- timestamps;
- error code;
- error message.

## Broker integration

Execution Engine must use a broker-specific adapter boundary.

```text
Execution Engine
      ↓
TInvestExecutionAdapter
      ↓
T-Invest
```

The core execution service must not depend directly on T-Invest REST/SDK details.

## UI

A separate button `Исполнение` is added to the main Edward navigation.

The button opens a dedicated `Центр исполнения` window.

The window must show:

### Service header

- active account;
- SANDBOX / execution mode;
- service status;
- start / stop controls;
- emergency stop.

### Execution mode

For v0.6 the supported modes are:

- analysis only;
- prepare orders;
- user confirmation required.

Fully automatic unattended execution is intentionally excluded from v0.6.

### Execution queue

The window displays:

- instrument;
- decision;
- quantity;
- price;
- execution readiness;
- current execution status.

### Current operation

The window displays the active execution with step-by-step progress, for example:

```text
✓ Decision received
✓ Execution Readiness
✓ Trading status
✓ Position check
✓ Cash check
✓ Quantity calculation
✓ Price / lot validation
→ Pre-trade revalidation
→ User confirmation
→ Order submission
→ Order monitoring
→ Position reconciliation
```

### Journal

The window contains a live execution log with timestamps and execution events.

## Scope by implementation stage

### 0.6.1 — Execution Domain

Create the execution contracts and lifecycle model:

- `ExecutionRequest`;
- `ExecutionResult`;
- `ExecutionStatus`;
- `ExecutionEvent`;
- `ExecutionJournal`.

### 0.6.2 — Execution Engine

Implement:

- `validate()`;
- `plan()`;
- `submit()`;
- `monitor()`;
- `reconcile()`;
- `cancel()`;
- restart recovery;
- idempotency.

### 0.6.3 — T-Invest Execution Adapter

Create the broker adapter and map Edward execution contracts to T-Invest order APIs.

### 0.6.4 — Execution Center UI

Create the separate execution window, queue, active operation panel, event journal and controls.

### 0.6.5 — Confirmation Mode

Implement the first end-to-end controlled flow:

```text
Decision
  ↓
Execution Readiness PASS
  ↓
Execution Engine
  ↓
Pre-trade revalidation
  ↓
User confirmation
  ↓
T-Invest order
```

### 0.6.6 — Recovery / Reconciliation

Cover:

- restart;
- timeout;
- partial fill;
- cancellation;
- rejection;
- ambiguous execution state;
- duplicate protection.

### 0.6.7 — Paper Execution

Provide an execution simulator using real market data without sending broker orders.

### 0.6.8 — Auto Execution Preparation

Prepare the architecture for automated execution, but do not enable unattended live execution as part of the v0.6 baseline.

## Explicit exclusions from v0.6 baseline

- unattended automatic live trading;
- replacing Decision Engine logic;
- changing the investment analysis methodology;
- direct UI-to-broker order submission;
- bypassing Execution Readiness;
- blind order retries.

## Evolution policy

The v0.6 scope is the baseline architecture. Improvements discovered during real use may be added in v0.7+ without treating the initial architecture as immutable.