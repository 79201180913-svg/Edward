from datetime import datetime, timezone

from edward.api.market_data import MarketDataApi
from edward.services.instrument_decision_context_service import InstrumentDecisionContextService
from edward.services.market_decision_context_service import MarketDecisionContextService


class FakeMarketData:
    def get_last_prices(self, instrument_id):
        return {"last_prices": []}

    def get_trading_status(self, instrument_id):
        return {"instrument_uid": instrument_id}

    def get_trading_statuses(self, instrument_id):
        return {"trading_statuses": []}


class FakeClient:
    def __init__(self):
        self.market_data = FakeMarketData()
        self.candle_requests = []

    def get_candles(self, **kwargs):
        self.candle_requests.append(kwargs)
        return {"candles": []}


def test_instrument_context_uses_tinvest_flags():
    context = InstrumentDecisionContextService().build(
        {
            "uid": "uid-sber",
            "ticker": "SBER",
            "buy_available_flag": True,
            "sell_available_flag": True,
        },
        {
            "instrument_uid": "uid-sber",
            "trading_status": "SECURITY_TRADING_STATUS_NORMAL_TRADING",
            "api_trade_available_flag": True,
        },
    )

    assert context.instrument_uid == "uid-sber"
    assert context.ticker == "SBER"
    assert context.buy_available is True
    assert context.sell_available is True
    assert context.available is True


def test_instrument_context_marks_not_available_when_api_trading_is_disabled():
    context = InstrumentDecisionContextService().build(
        {"uid": "uid-sber", "ticker": "SBER", "buy_available_flag": True, "sell_available_flag": True},
        {"trading_status": "SECURITY_TRADING_STATUS_NORMAL_TRADING", "api_trade_available_flag": False},
    )

    assert context.available is False
    assert context.buy_available is True


def test_instrument_context_marks_not_available_for_closed_trading_status():
    context = InstrumentDecisionContextService().build(
        {"uid": "uid-sber", "ticker": "SBER", "buy_available_flag": True, "sell_available_flag": True},
        {"trading_status": "SECURITY_TRADING_STATUS_NOT_AVAILABLE_FOR_TRADING", "api_trade_available_flag": True},
    )

    assert context.available is False


def test_market_context_converts_quotation_and_candles():
    service = MarketDecisionContextService()
    now = datetime(2026, 8, 25, tzinfo=timezone.utc)
    payload = {
        "candles": [
            {
                "open": {"units": 100, "nano": 100000000},
                "high": {"units": 101, "nano": 200000000},
                "low": {"units": 99, "nano": 500000000},
                "close": {"units": 100, "nano": 900000000},
                "volume": 125,
                "time": now,
            }
        ]
    }

    context = service.build(
        last_price={"units": 100, "nano": 900000000},
        close_price="99.50",
        candles=payload["candles"],
        market_regime="Trend",
        trend="UP",
        momentum="POSITIVE",
        volatility=0.02,
        entry_level=101.0,
        stop_level=95.0,
        target_level=115.0,
        regime_compatible=True,
        entry_ok=True,
    )
    candles = service.candles(payload)

    assert context.current_price == 100.9
    assert context.close_price == 99.5
    assert context.market_regime == "Trend"
    assert context.entry_ok is True
    assert context.available is True
    assert len(candles) == 1
    assert candles[0].close == 100.9
    assert candles[0].volume == 125.0


def test_market_context_is_unavailable_without_market_values():
    context = MarketDecisionContextService().build(last_price=None, close_price=None, candles=[])
    assert context.available is False


def test_market_data_api_exposes_candles_contract():
    client = FakeClient()
    api = MarketDataApi(client)

    api.get_candles("uid-sber", interval="CANDLE_INTERVAL_HOUR", days=120)

    assert client.candle_requests == [
        {
            "instrument_uid": "uid-sber",
            "interval": "CANDLE_INTERVAL_HOUR",
            "days": 120,
        }
    ]
