import pytest

from edward.services.multiple_testing_control_v088 import MultipleTestingControlV088


def test_multiple_testing_audit_exposes_search_space_and_expected_false_positives():
    result = MultipleTestingControlV088.assess((0.01, 0.02, 0.04, 0.2, 0.9))
    assert result.hypotheses_tested == 5
    assert result.positive_hypotheses == 3
    assert result.expected_false_positives_at_alpha == pytest.approx(0.25)
    assert result.false_discovery_rate_proxy_pct == pytest.approx(8.3333333333)


def test_multiple_testing_control_validates_alpha_and_p_values():
    with pytest.raises(ValueError):
        MultipleTestingControlV088.assess((0.1,), alpha=0)
    with pytest.raises(ValueError):
        MultipleTestingControlV088.assess((-0.1,))
    with pytest.raises(ValueError):
        MultipleTestingControlV088.assess((1.1,))


def test_multiple_testing_audit_does_not_invent_positive_results():
    result = MultipleTestingControlV088.assess((0.2, 0.4, 0.9))
    assert result.positive_hypotheses == 0
    assert result.false_discovery_rate_proxy_pct == 0.0
