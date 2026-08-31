import logging
from types import SimpleNamespace

from edward.services.research_evidence_logger_v087 import ResearchEvidenceLoggerV087


def _evidence(excess, win_rate, n=10):
    return SimpleNamespace(
        hypothesis="BREAKOUT_EXPANSION", regime="TREND_UP", volatility_bucket="High",
        direction="Positive", horizon=5, excess_return_pct=excess,
        win_rate_pct=win_rate, observations=n, sufficient_sample=n >= 8,
    )


def test_logger_builds_summary_without_recommendation(caplog):
    logger = logging.getLogger("test-research-evidence")
    with caplog.at_level(logging.WARNING, logger=logger.name):
        summary = ResearchEvidenceLoggerV087(logger).build_and_log(
            [_evidence(2.0, 70.0), _evidence(1.0, 60.0)],
            ticker="SBER",
        )
    assert summary.total_cells == 2
    assert "[V087 RESEARCH SUMMARY] ticker=SBER" in caplog.text
    assert "recommendation" not in caplog.text.lower()


def test_logger_emits_separate_magnitude_and_consistency_views(caplog):
    logger = logging.getLogger("test-research-evidence-views")
    with caplog.at_level(logging.WARNING, logger=logger.name):
        ResearchEvidenceLoggerV087(logger).build_and_log(
            [_evidence(5.0, 55.0), _evidence(1.0, 90.0)],
            ticker="SBER",
        )
    assert "[V087 RESEARCH MAGNITUDE]" in caplog.text
    assert "[V087 RESEARCH CONSISTENCY]" in caplog.text
