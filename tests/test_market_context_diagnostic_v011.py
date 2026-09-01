from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import Candle
from edward.services.market_context_diagnostic_v011 import MarketContextDiagnosticV011, _parse_args


def _candles(count: int):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return tuple(
        Candle(
            timestamp=start + timedelta(days=index),
            open=100.0 + index,
            high=101.0 + index,
            low=99.0 + index,
            close=100.0 + index,
            volume=1000.0,
        )
        for index in range(count)
    )


def test_cutoffs_keep_warmup_and_oos_tail_contract():
    assert MarketContextDiagnosticV011.cutoffs(360, 120) == ()
    assert MarketContextDiagnosticV011.cutoffs(361, 120) == (300,)
    assert MarketContextDiagnosticV011.cutoffs(500, 120) == (300, 420)


def test_cutoffs_reject_non_positive_step():
    try:
        MarketContextDiagnosticV011.cutoffs(1000, 0)
    except ValueError as exc:
        assert str(exc) == "cutoff step must be positive"
    else:
        raise AssertionError("ValueError was not raised")


def test_cli_parser_accepts_required_diagnostic_arguments(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "market_context_diagnostic_v011",
            "--instrument-uid",
            "uid-1",
            "--ticker",
            "RZSB",
            "--days",
            "2400",
            "--cutoff-step",
            "120",
        ],
    )
    args = _parse_args()
    assert args.instrument_uid == "uid-1"
    assert args.ticker == "RZSB"
    assert args.days == 2400
    assert args.cutoff_step == 120
    assert args.profile == "medium_term"
