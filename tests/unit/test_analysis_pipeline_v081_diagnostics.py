from dataclasses import dataclass

from edward.services.analysis_pipeline_service_v081 import AnalysisPipelineV081Result


@dataclass(frozen=True)
class _Analysis:
    diagnostics: dict


def test_pipeline_v081_result_exposes_base_analysis_diagnostics():
    diagnostics = {
        "strategies": {
            "Trend Following": {"data_sufficient": True, "quality_gate": False, "failed_checks": ["mean_oos_return"]},
            "Momentum": {"data_sufficient": True, "quality_gate": False, "failed_checks": ["mean_oos_sharpe"]},
        }
    }
    result = AnalysisPipelineV081Result(
        base=type("Base", (), {"analysis": _Analysis(diagnostics),})(),
        multifactor=object(),
        overlay=object(),
    )

    assert result.diagnostics is diagnostics
    assert result.diagnostics["strategies"]["Trend Following"]["data_sufficient"] is True
    assert result.diagnostics["strategies"]["Trend Following"]["failed_checks"] == ["mean_oos_return"]
