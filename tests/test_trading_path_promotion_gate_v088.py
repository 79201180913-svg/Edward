from types import SimpleNamespace

from edward.services.trading_path_promotion_gate_v088 import (
    TradingPathPromotionGateV088,
    TradingPathPromotionPolicyV088,
    TradingPathPromotionStatusV088,
)


def _result(*, trades=10, net=6.0, ci_low=0.2):
    return SimpleNamespace(
        trades=trades,
        net_return_pct=net,
        statistical_evidence=SimpleNamespace(ci95_low_pct=ci_low),
    )


def test_strong_validated_path_stays_research_only_until_remaining_evidence_exists():
    result = TradingPathPromotionGateV088.evaluate(_result())
    assert result.status is TradingPathPromotionStatusV088.RESEARCH_ONLY
    assert "TEMPORAL_EVIDENCE_REQUIRED" in result.reasons
    assert "OVERLAP_AUDIT_REQUIRED" in result.reasons
    assert "MULTIPLE_TESTING_AUDIT_REQUIRED" in result.reasons


def test_low_sample_path_is_rejected():
    result = TradingPathPromotionGateV088.evaluate(_result(trades=9))
    assert result.status is TradingPathPromotionStatusV088.REJECTED
    assert "LOW_SAMPLE" in result.reasons


def test_non_positive_net_path_is_rejected():
    result = TradingPathPromotionGateV088.evaluate(_result(net=0.0))
    assert result.status is TradingPathPromotionStatusV088.REJECTED
    assert "NON_POSITIVE_NET_RETURN" in result.reasons


def test_non_positive_ci_path_is_rejected():
    result = TradingPathPromotionGateV088.evaluate(_result(ci_low=-0.1))
    assert result.status is TradingPathPromotionStatusV088.REJECTED
    assert "CI95_NOT_ABOVE_ZERO" in result.reasons


def test_policy_can_disable_ci_requirement_for_a_research_experiment():
    result = TradingPathPromotionGateV088.evaluate(
        _result(ci_low=-0.1),
        TradingPathPromotionPolicyV088(require_ci95_above_zero=False),
    )
    assert result.status is TradingPathPromotionStatusV088.RESEARCH_ONLY
