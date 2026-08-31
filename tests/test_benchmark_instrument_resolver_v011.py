from types import SimpleNamespace

import pytest

from edward.services.benchmark_instrument_resolver_v011 import BenchmarkInstrumentResolverV011
from edward.services.market_benchmark_resolver_v011 import BenchmarkDefinition


def _benchmark():
    return BenchmarkDefinition(
        benchmark_id="IMOEX",
        benchmark_kind="EQUITY_MARKET",
        market="MOEX",
        supported=True,
        reason="",
    )


def test_resolves_imoex_from_indicatives():
    resolver = BenchmarkInstrumentResolverV011(
        lambda: {"instruments": [{"ticker": "IMOEX", "uid": "index-uid", "class_code": "SNDX"}]}
    )
    result = resolver.resolve(_benchmark())
    assert result.instrument_uid == "index-uid"
    assert result.source == "INDICATIVES"


def test_falls_back_to_find_instrument_for_sandbox_not_found():
    def indicatives():
        error = RuntimeError("not_found")
        error.status_code = 404
        error.error_code = "not_found"
        raise error

    calls = []

    def find(query, trade_available_only):
        calls.append((query, trade_available_only))
        return {"instruments": [{"ticker": "IMOEX", "uid": "index-uid", "instrument_kind": "INSTRUMENT_TYPE_INDEX"}]}

    resolver = BenchmarkInstrumentResolverV011(indicatives, find)
    result = resolver.resolve(_benchmark())
    assert result.instrument_uid == "index-uid"
    assert result.source == "FIND_INSTRUMENT_FALLBACK"
    assert calls == [("IMOEX", False)]


def test_fallback_rejects_same_ticker_when_not_index():
    def indicatives():
        error = RuntimeError("not_found")
        error.status_code = 404
        error.error_code = "not_found"
        raise error

    resolver = BenchmarkInstrumentResolverV011(
        indicatives,
        lambda query, trade: {"instruments": [{"ticker": "IMOEX", "uid": "share-uid", "instrument_kind": "INSTRUMENT_TYPE_SHARE"}]},
    )
    with pytest.raises(ValueError, match="Index benchmark not found"):
        resolver.resolve(_benchmark())


def test_non_not_found_error_is_not_hidden():
    def indicatives():
        raise RuntimeError("server unavailable")

    resolver = BenchmarkInstrumentResolverV011(indicatives, lambda *args: {})
    with pytest.raises(RuntimeError, match="server unavailable"):
        resolver.resolve(_benchmark())
