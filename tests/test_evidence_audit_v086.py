from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from edward.services.analysis_service import Candle
from edward.services.conditional_discovery_service_v086 import (
    ConditionalDiscoveryCell,
    ConditionalDiscoveryEvidence,
    ConditionalDiscoveryResult,
)
from edward.services.evidence_audit_service_v086 import EvidenceAuditServiceV086


def test_evidence_audit_calculates_dispersion_and_period_persistence():
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    observations = tuple(
        SimpleNamespace(
            hypothesis="BREAKOUT_EXPANSION", regime="TREND_UP",
            volatility_bucket="High", direction="Positive", index=index,
            timestamp=start + timedelta(hours=index),
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
    assert audit[0].periods == 2
    assert audit[0].positive_periods == 2
    assert audit[0].negative_periods == 0
    assert audit[0].persistence_pct == 100.0


def test_evidence_audit_wf_persistence_uses_actual_test_windows():
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    candles = [
        Candle(start + timedelta(hours=index), 100.0, 101.0, 99.0, 100.0, 1000.0)
        for index in range(100)
    ]
    observations = (
        SimpleNamespace(
            hypothesis="BREAKOUT_EXPANSION", regime="TREND_UP",
            volatility_bucket="High", direction="Positive", index=20,
            forward_return=lambda horizon: 1.0,
            timestamp=candles[20].timestamp,
        ),
        SimpleNamespace(
            hypothesis="BREAKOUT_EXPANSION", regime="TREND_UP",
            volatility_bucket="High", direction="Positive", index=50,
            forward_return=lambda horizon: -1.0,
            timestamp=candles[50].timestamp,
        ),
    )
    cell = ConditionalDiscoveryCell(
        "BREAKOUT_EXPANSION", "TREND_UP", "High", "Positive", 5,
        observations=2, mean_forward_return_pct=0.0,
        median_forward_return_pct=0.0, win_rate_pct=50.0,
        baseline_mean_return_pct=0.0, excess_return_pct=0.0,
        sufficient_sample=False,
    )
    result = ConditionalDiscoveryResult(
        version="0.8.6", candles=len(candles), min_observations=8,
        evidence=(ConditionalDiscoveryEvidence("BREAKOUT_EXPANSION", 2, (cell,)),),
        observations=observations,
    )
    wf_result = SimpleNamespace(windows=(
        SimpleNamespace(test_start=candles[10].timestamp, test_end=candles[40].timestamp),
        SimpleNamespace(test_start=candles[41].timestamp, test_end=candles[70].timestamp),
    ))

    audit = EvidenceAuditServiceV086.audit_wf(result, wf_result, candles)
    assert len(audit) == 1
    assert audit[0].wf_windows == 2
    assert audit[0].positive_wf_windows == 1
    assert audit[0].negative_wf_windows == 1
    assert audit[0].wf_persistence_pct == 50.0
    assert audit[0].observations == 2


def test_evidence_audit_wf_excludes_forward_return_crossing_test_boundary():
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    candles = [
        Candle(start + timedelta(hours=index), 100.0, 101.0, 99.0, 100.0, 1000.0)
        for index in range(50)
    ]
    observations = (
        SimpleNamespace(
            hypothesis="BREAKOUT_EXPANSION", regime="TREND_UP",
            volatility_bucket="High", direction="Positive", index=38,
            forward_return=lambda horizon: 5.0,
            timestamp=candles[38].timestamp,
        ),
    )
    cell = ConditionalDiscoveryCell(
        "BREAKOUT_EXPANSION", "TREND_UP", "High", "Positive", 5,
        observations=1, mean_forward_return_pct=5.0,
        median_forward_return_pct=5.0, win_rate_pct=100.0,
        baseline_mean_return_pct=0.0, excess_return_pct=5.0,
        sufficient_sample=False,
    )
    result = ConditionalDiscoveryResult(
        version="0.8.6", candles=len(candles), min_observations=8,
        evidence=(ConditionalDiscoveryEvidence("BREAKOUT_EXPANSION", 1, (cell,)),),
        observations=observations,
    )
    wf_result = SimpleNamespace(windows=(
        SimpleNamespace(test_start=candles[30].timestamp, test_end=candles[40].timestamp),
    ))

    audit = EvidenceAuditServiceV086.audit_wf(result, wf_result, candles)
    assert audit[0].wf_windows == 0
    assert audit[0].observations == 0
