from edward.services.analysis_service_v08 import AnalysisV08Diagnostics
from edward.services.train_sample_diagnostics_v084 import TrainSampleDiagnosticsV084


def test_analysis_diagnostics_exposes_train_sample_by_strategy() -> None:
    diagnostics = AnalysisV08Diagnostics(
        regime_confidence=80.0,
        regime="TREND",
        robustness_by_strategy={},
        quality_gate_by_strategy={},
        train_sample_by_strategy={
            "Breakout": TrainSampleDiagnosticsV084(
                windows=4,
                no_trades_windows=0,
                low_sample_windows=3,
                adequate_sample_windows=1,
                mean_selected_train_trades=3.5,
                min_selected_train_trades=1,
                max_selected_train_trades=8,
                low_sample_pct=75.0,
            )
        },
    )
    sample = diagnostics.train_sample_by_strategy["Breakout"]
    assert sample.windows == 4
    assert sample.low_sample_pct == 75.0
    assert sample.adequate_sample_windows == 1
