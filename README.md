# Edward

Python trading platform for T-Invest.

Current development version: **0.2.0**

## Version 0.2

Development is based on the frozen 0.1 baseline in `main`.

The first 0.2 increment aligns the ordinary order path with the T-Invest `OrdersService` contract:

- `LIMIT`
- `MARKET`
- `BESTPRICE`

Stop orders are intentionally kept out of the ordinary order model and will be implemented through the dedicated T-Invest StopOrdersService flow.

The 0.2 baseline also normalizes REST/dict order responses in the order monitor and adds regression tests for order-contract behavior.
