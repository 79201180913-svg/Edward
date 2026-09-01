from dataclasses import dataclass

from edward.services.market_benchmark_resolver_v011 import (
    MARKET_BENCHMARK_RESOLVER_VERSION,
    MarketBenchmarkResolverV011,
)


def test_russian_equity_resolves_to_imoex():
    result = MarketBenchmarkResolverV011.resolve(
        {"instrument_type": "STOCK", "market": "MOEX"}
    )

    assert result.benchmark_id == "IMOEX"
    assert result.benchmark_kind == "EQUITY_MARKET"
    assert result.market == "MOEX"
    assert result.supported is True
    assert result.version == MARKET_BENCHMARK_RESOLVER_VERSION


def test_russian_equity_accepts_object_metadata():
    @dataclass
    class Instrument:
        instrument_type: str = "EQUITY"
        exchange: str = "RU"

    result = MarketBenchmarkResolverV011.resolve(Instrument())

    assert result.benchmark_id == "IMOEX"
    assert result.supported is True


def test_non_russian_equity_does_not_fallback_to_imoex():
    result = MarketBenchmarkResolverV011.resolve(
        {"instrument_type": "STOCK", "market": "US"}
    )

    assert result.benchmark_id is None
    assert result.benchmark_kind == "EQUITY_MARKET"
    assert result.supported is False


def test_unsupported_instrument_type_is_explicit():
    result = MarketBenchmarkResolverV011.resolve(
        {"instrument_type": "OPTION", "market": "MOEX"}
    )

    assert result.benchmark_id is None
    assert result.benchmark_kind == "UNSUPPORTED"
    assert result.supported is False
    assert "OPTION" in result.reason


def test_missing_instrument_type_is_unknown():
    result = MarketBenchmarkResolverV011.resolve({"market": "MOEX"})

    assert result.benchmark_id is None
    assert result.benchmark_kind == "UNKNOWN"
    assert result.supported is False
    assert result.reason == "Instrument type is missing"
