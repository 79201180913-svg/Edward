from types import SimpleNamespace

from edward.services.decision_engine import PortfolioContextData, PositionContextData
from edward.services.trading_path_context_factory_v015 import TradingPathContextFactoryV015


def test_factory_merges_portfolio_and_position_context_without_dropping_instrument_sources():
    fundamentals = object()
    instrument = SimpleNamespace(
        uid="SBER",
        fundamentals=fundamentals,
        last_price=101.5,
        session_name="MAIN",
        session_execution_allowed=True,
    )
    portfolio = PortfolioContextData(
        portfolio_value=1_000_000.0,
        available_cash=300_000.0,
        current_weight_pct=12.5,
        max_position_weight_pct=20.0,
    )
    position = PositionContextData(
        quantity=10.0,
        current_price=101.0,
        portfolio_weight_pct=11.5,
    )

    context = TradingPathContextFactoryV015.build(
        instrument=instrument,
        portfolio=portfolio,
        position=position,
    )

    assert context is not None
    assert context.instrument_metadata is instrument
    assert context.fundamentals is fundamentals
    assert context.current_price == 101.5
    assert context.current_weight_pct == 12.5
    assert context.max_position_weight_pct == 20.0
    assert context.session_name == "MAIN"


def test_factory_uses_position_values_when_instrument_does_not_expose_them():
    instrument = SimpleNamespace(uid="SBER")
    position = PositionContextData(
        current_price=99.0,
        portfolio_weight_pct=7.25,
    )

    context = TradingPathContextFactoryV015.build(instrument=instrument, position=position)

    assert context is not None
    assert context.current_price == 99.0
    assert context.current_weight_pct == 7.25


def test_factory_returns_none_only_when_no_sources_exist():
    assert TradingPathContextFactoryV015.build() is None
