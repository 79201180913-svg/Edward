from pathlib import Path


def test_v088_ui_wires_market_context_fetchers_explicitly():
    source = Path("src/edward/ui/analysis_ui_v088_frontend.py").read_text(encoding="utf-8")

    # The production code may format the constructor on one or multiple lines;
    # the contract is the explicit service and fetcher wiring, not whitespace.
    assert "market_service = MarketContextRuntimeServiceV011(" in source
    assert "fetcher=app.client.get_candles" in source
    assert "indicatives_fetcher=app.client.get_indicatives" in source
    assert "find_instrument_fetcher=app.client.find_instrument" in source
