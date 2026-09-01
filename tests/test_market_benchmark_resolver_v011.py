from edward.services.market_benchmark_resolver_v011 import MarketBenchmarkResolverV011


def test_moex_equity_resolves_from_tqbr_when_market_field_is_absent():
    result = MarketBenchmarkResolverV011.resolve(
        {
            "instrument_type": "SHARE",
            "class_code": "TQBR",
        }
    )

    assert result.supported is True
    assert result.benchmark_id == "IMOEX"
    assert result.market == "MOEX"
    assert result.benchmark_kind == "EQUITY_MARKET"


def test_non_russian_equity_is_not_silently_mapped():
    result = MarketBenchmarkResolverV011.resolve(
        {
            "instrument_type": "SHARE",
            "class_code": "NASDAQ",
        }
    )

    assert result.supported is False
    assert result.benchmark_id is None
