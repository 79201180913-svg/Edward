import pytest

from scripts.run_market_context_ab_v011 import build_cutoff_indices


def test_build_cutoff_indices_requires_point_in_time_warmup_and_oos_tail():
    assert build_cutoff_indices(360, 120) == ()
    assert build_cutoff_indices(361, 120) == (300,)
    assert build_cutoff_indices(500, 120) == (300, 420)


def test_build_cutoff_indices_uses_fixed_step():
    assert build_cutoff_indices(900, 120) == (300, 420, 540, 660, 780)


def test_build_cutoff_indices_rejects_non_positive_step():
    with pytest.raises(ValueError, match="cutoff step must be positive"):
        build_cutoff_indices(900, 0)
