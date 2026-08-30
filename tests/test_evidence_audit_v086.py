from types import SimpleNamespace

from edward.services.conditional_discovery_service_v086 import (
    ConditionalDiscoveryCell,
    ConditionalDiscoveryEvidence,
    ConditionalDiscoveryResult,
)
from edward.services.evidence_audit_v086 import EvidenceAuditServiceV086


def test_evidence_audit_calculates_dispersion_and_period_persistence():
    observations = tuple(
        SimpleNamespace(
            hypothesis="BREAKOUT_EXPANSION",
            regime="TREND_UP",
            volatility_bucket="High",
            direction="Positive",
            index=index,
            forward_return=lambda horizon, value=value: value,
        )
        for index, value in ((10, 1.0), (20, 3.0), (70, -1.0), (80, 2.0))
    )
    cell = ConditionalDiscoveryCell(
        "BREAKOUT_EXPANSION", "TREND_UP", "High", "Positive", 5,
        observations=4, mean_forward_return_pct=1.25,
        median_forward_return_pct=1.5, win_rate_pct=75.0,
        baseline_mean_return_pct=0.25, excess_return_pct=1.0,
        sufficient_sample=False,
    )
    result = ConditionalDiscoveryResult(
        version="0.8.6", candles=120, min_observations=8,
        evidence=(ConditionalDiscoveryEvidence("BREAKOUT_EXPANSION", 4, (cell,)),),
        observations=observations,
    )

    audit = EvidenceAuditServiceV086.audit(result)
    assert len(audit) == 1
    assert round(audit[0].dispersion_pct, 6) == round(1.4790199458, 6)
    assert audit[0].distinct_periods == 2
    assert audit[0].positive_periods == 2
    assert audit[0].negative_periods == 0
    assert audit[0].persistence_pct == 100.0
