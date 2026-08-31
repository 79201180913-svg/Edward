from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import Candle
from edward.services.conditional_discovery_coverage_v086 import ConditionalDiscoveryCoverageV086
from edward.services.conditional_discovery_service_v086 import ConditionalDiscoveryServiceV086


def _candles(count: int = 220) -> list[Candle]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    price = 100.0
    result = []
    for i in range(count):
        previous = price
        if i % 37 == 0 and i > 25:
            price *= 1.035
        elif i % 43 == 0 and i > 25:
            price *= 0.965
        else:
            price *= 1.0015 if (i // 12) % 2 == 0 else 0.999
        result.append(Candle(start + timedelta(hours=i), previous, max(previous, price) * 1.002, min(previous, price) * 0.998, price, 1000.0))
    return result


def test_coverage_audit_accounts_for_all_hypotheses():
    audits = ConditionalDiscoveryCoverageV086.run(_candles())
    assert len(audits) == len(ConditionalDiscoveryServiceV086.HYPOTHESES)
    assert {item.hypothesis for item in audits} == set(ConditionalDiscoveryServiceV086.HYPOTHESES)


def test_coverage_audit_exposes_marginal_and_full_distributions():
    audits = ConditionalDiscoveryCoverageV086.run(_candles())
    for audit in audits:
        assert audit.events == sum(audit.by_regime.values())
        assert audit.events == sum(audit.by_volatility.values())
        assert audit.events == sum(audit.by_direction.values())
        assert audit.events == sum(audit.by_full_condition.values())
        assert 0.0 <= audit.sparsity_pct <= 100.0
        assert 0.0 <= audit.largest_condition_share_pct <= 100.0


def test_coverage_audit_does_not_change_conditional_result():
    candles = _candles()
    before = ConditionalDiscoveryServiceV086.run(candles)
    ConditionalDiscoveryCoverageV086.run(candles)
    after = ConditionalDiscoveryServiceV086.run(candles)
    assert before == after
