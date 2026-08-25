from edward.services.portfolio_decision_context_service import PortfolioDecisionContextService


def test_builds_portfolio_and_position_context():
    result = PortfolioDecisionContextService().build(
        positions={
            "money": [
                {"currency": "RUB", "available": {"units": "50000", "nano": 0}, "blocked": {"units": "1000", "nano": 0}}
            ],
            "securities": [
                {
                    "instrument_uid": "uid-1",
                    "balance": 10,
                    "average_position_price": {"units": "90", "nano": 0},
                    "current_price": {"units": "100", "nano": 0},
                    "expected_yield": {"units": "100", "nano": 0},
                }
            ]
        },
        portfolio={"total_amount_portfolio": {"units": "60000", "nano": 0}},
        instrument_uid="uid-1",
    )

    assert result.position.quantity == 10
    assert result.position.average_price == 90.0
    assert result.position.current_price == 100.0
    assert result.position.pnl == 100.0
    assert round(result.position.portfolio_weight_pct, 2) == round(1000 / 60000 * 100, 2)
    assert result.portfolio.available_cash == 50000.0
    assert result.portfolio.blocked_cash == 1000.0
    assert result.portfolio.portfolio_value == 60000.0


def test_portfolio_value_falls_back_to_balance_summary():
    result = PortfolioDecisionContextService().build(
        positions={
            "money": [
                {"currency": "RUB", "available": {"units": "50000", "nano": 0}, "blocked": {"units": "1000", "nano": 0}}
            ],
            "securities": [
                {
                    "instrument_uid": "uid-1",
                    "balance": 10,
                    "current_price": {"units": "100", "nano": 0},
                }
            ],
        },
        portfolio={"positions": []},
        instrument_uid="uid-1",
    )

    assert result.portfolio.portfolio_value == 52000.0
    assert round(result.position.portfolio_weight_pct, 2) == round(1000 / 52000 * 100, 2)


def test_no_matching_position_returns_empty_position():
    result = PortfolioDecisionContextService().build(
        positions={"money": [], "securities": []},
        portfolio={"total_amount_portfolio": {"units": "100000", "nano": 0}, "positions": []},
        instrument_uid="uid-missing",
    )

    assert result.position.quantity == 0.0
    assert result.position.is_open is False
    assert result.position.portfolio_weight_pct == 0.0
    assert result.portfolio.portfolio_value == 100000.0
