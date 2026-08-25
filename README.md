# Edward

Python trading platform for T-Invest.

Current development version: **0.3.0**

## Version 0.2

Version 0.2 is the frozen baseline for manual trading and Sandbox integration.

It includes the ordinary order path aligned with the T-Invest `OrdersService` contract:

- `LIMIT`
- `MARKET`
- `BESTPRICE`

The 0.2 baseline also includes Sandbox read-only and trading E2E coverage, portfolio/balance handling, instrument catalog, order monitoring, history, and the GUI launcher/runtime integration.

## Version 0.3

Version 0.3 focuses on making the instrument the central object of the manual trading workflow.

First increment:

- dedicated instrument detail screen;
- current price and close-price change;
- trading status and order-type availability;
- instrument identifiers and contract metadata;
- current position information when available;
- quick BUY/SELL order entry from the instrument screen;
- `MARKET`, `LIMIT`, and `BESTPRICE` quick-order types;
- pre-trade validation and confirmation before submission.

Planned next increments:

- Stop Loss and Take Profit through the dedicated StopOrdersService flow;
- richer order ticket and order lifecycle controls;
- expanded position/P&L presentation;
- production safety and reliability improvements;
- UI/E2E coverage for the new trading workflow.
