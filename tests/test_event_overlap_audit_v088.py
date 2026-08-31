from datetime import datetime, timezone

from edward.services.event_observation_v086 import EventObservationV086
from edward.services.event_overlap_audit_v088 import EventOverlapAuditV088


def _obs(hypothesis: str, index: int) -> EventObservationV086:
    return EventObservationV086(
        hypothesis=hypothesis,
        index=index,
        timestamp=datetime(2025, 1, index + 1, tzinfo=timezone.utc),
        regime="TREND_UP",
        volatility_bucket="Normal",
        direction="Positive",
        forward_returns_pct=((1, 1.0), (3, 2.0), (5, 3.0), (10, 4.0), (20, 5.0)),
    )


def test_overlap_audit_counts_duplicate_event_identity():
    result = EventOverlapAuditV088.run((_obs("A", 20), _obs("B", 20), _obs("A", 21)))
    assert result.total_observations == 3
    assert result.unique_event_indices == 2
    assert result.overlap_count == 1


def test_overlap_audit_reports_pairwise_hypothesis_overlap():
    result = EventOverlapAuditV088.run((_obs("A", 20), _obs("B", 20), _obs("B", 21)))
    assert result.pairwise_overlaps == (type(result.pairwise_overlaps[0])("A", "B", 1),)


def test_overlap_audit_is_empty_for_disjoint_events():
    result = EventOverlapAuditV088.run((_obs("A", 20), _obs("B", 21)))
    assert result.overlap_count == 0
    assert result.pairwise_overlaps == ()
