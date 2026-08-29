from __future__ import annotations

from types import SimpleNamespace


def test_analysis_ui_v081_runtime_is_bound_to_canonical_v082_pipeline() -> None:
    import edward.services.analysis_pipeline_service_v082 as canonical
    import edward.ui.analysis_ui_v081_runtime as runtime

    # The GUI launcher applies this binding before installing the v0.8.1
    # presentation wrapper. Importing the launcher must therefore leave the
    # wrapper pointing at the canonical v0.8.2 pipeline service.
    import edward.ui.gui_launcher  # noqa: F401

    assert runtime.AnalysisPipelineServiceV081 is canonical.AnalysisPipelineServiceV082


def test_canonical_v082_pipeline_keeps_v082_version_contract() -> None:
    from edward.services.analysis_pipeline_service_v082 import (
        ANALYSIS_PIPELINE_V082_VERSION,
        AnalysisPipelineServiceV082,
    )

    assert ANALYSIS_PIPELINE_V082_VERSION == "0.8.2"
    assert AnalysisPipelineServiceV082.__name__ == "AnalysisPipelineServiceV082"


def test_v082_result_preserves_v081_ui_contract() -> None:
    from edward.services.analysis_pipeline_service_v082 import AnalysisPipelineV082Result

    base = SimpleNamespace(
        multifactor=object(),
        overlay=object(),
        forecast_quality_score=81.0,
        regime_confidence=72.0,
        evidence_strategy="Trend Following",
        portfolio_context_available=True,
    )
    result = AnalysisPipelineV082Result(
        base=base,
        fundamental=object(),
        entry_quality=object(),
    )

    assert result.multifactor is base.multifactor
    assert result.overlay is base.overlay
    assert result.forecast_quality_score == base.forecast_quality_score
    assert result.regime_confidence == base.regime_confidence
    assert result.evidence_strategy == base.evidence_strategy
    assert result.portfolio_context_available is base.portfolio_context_available
