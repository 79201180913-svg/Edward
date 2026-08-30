from edward.services.failure_attribution_summary_v084 import FailureAttributionSummaryServiceV084
from edward.services.failure_attribution_v084 import FailureAttributionV084


def test_summary_counts_failed_primary_reasons_and_dominant_reason() -> None:
    result = FailureAttributionSummaryServiceV084.evaluate([
        FailureAttributionV084("Trend Following", False, "OOS_NEGATIVE"),
        FailureAttributionV084("Momentum", False, "LOW_SAMPLE"),
        FailureAttributionV084("Breakout", False, "OOS_NEGATIVE"),
        FailureAttributionV084("Mean Reversion", True, "PASS"),
    ])
    assert result.total_strategies == 4
    assert result.passed_strategies == 1
    assert result.failed_strategies == 3
    assert result.primary_reason_counts == {"OOS_NEGATIVE": 2, "LOW_SAMPLE": 1}
    assert result.dominant_failure_reason == "OOS_NEGATIVE"
