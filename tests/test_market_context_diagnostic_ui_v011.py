from types import SimpleNamespace

import edward.ui.market_context_diagnostic_ui_v011 as diagnostic_ui
from edward.services.analysis_trading_path_adapter_v088 import AnalysisTradingPathAdapterV088
from edward.services.market_context_runtime_service_v011 import MarketContextRuntimeServiceV011


class _DiagnosticResult:
    rank_change_rate_pct = 25.0
    baseline_top1 = SimpleNamespace(mean_oos_return_pct=1.0, win_rate_pct=50.0, positive_windows=1)
    context_top1 = SimpleNamespace(mean_oos_return_pct=2.0, win_rate_pct=60.0, positive_windows=2)
    baseline_top3 = SimpleNamespace(mean_oos_return_pct=0.5, positive_windows=1)
    context_top3 = SimpleNamespace(mean_oos_return_pct=0.9, positive_windows=2)
    window_results = ()


def test_install_runs_diagnostic_after_common_analysis(monkeypatch):
    calls = []

    def original(self, **kwargs):
        calls.append(("analysis", kwargs["ticker"]))
        return SimpleNamespace(ok=True)

    def diagnostic_run(self, **kwargs):
        calls.append(("diagnostic", kwargs["ticker"], kwargs["cutoff_step"]))
        return _DiagnosticResult()

    monkeypatch.setattr(AnalysisTradingPathAdapterV088, "analyze", original)
    monkeypatch.setattr(diagnostic_ui, "_INSTALLED", False)
    monkeypatch.setattr(diagnostic_ui, "_RUNNING", False)
    monkeypatch.setattr(diagnostic_ui.MarketContextDiagnosticV011, "run", diagnostic_run)
    monkeypatch.setattr(
        MarketContextRuntimeServiceV011,
        "last_built_snapshot",
        SimpleNamespace(instrument_id="uid-1", context_status="FULL"),
    )
    monkeypatch.setattr(
        MarketContextRuntimeServiceV011,
        "last_built_market_candles",
        (SimpleNamespace(timestamp=1),),
    )

    diagnostic_ui.install()
    adapter = AnalysisTradingPathAdapterV088()
    result = adapter.analyze(
        instrument_uid="uid-1",
        ticker="RZSB",
        candles=(SimpleNamespace(timestamp=1),),
        profile="medium_term",
    )

    assert result.ok is True
    assert calls == [("analysis", "RZSB"), ("diagnostic", "RZSB", 120)]


def test_diagnostic_skips_without_full_runtime_context(monkeypatch):
    calls = []

    def original(self, **kwargs):
        return SimpleNamespace(ok=True)

    def diagnostic_run(self, **kwargs):
        calls.append(True)
        return _DiagnosticResult()

    monkeypatch.setattr(AnalysisTradingPathAdapterV088, "analyze", original)
    monkeypatch.setattr(diagnostic_ui, "_INSTALLED", False)
    monkeypatch.setattr(diagnostic_ui, "_RUNNING", False)
    monkeypatch.setattr(diagnostic_ui.MarketContextDiagnosticV011, "run", diagnostic_run)
    monkeypatch.setattr(
        MarketContextRuntimeServiceV011,
        "last_built_snapshot",
        SimpleNamespace(instrument_id="other", context_status="FULL"),
    )
    monkeypatch.setattr(MarketContextRuntimeServiceV011, "last_built_market_candles", (SimpleNamespace(),))

    diagnostic_ui.install()
    AnalysisTradingPathAdapterV088().analyze(
        instrument_uid="uid-1",
        ticker="RZSB",
        candles=(SimpleNamespace(timestamp=1),),
    )

    assert calls == []
