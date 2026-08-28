from types import SimpleNamespace

from edward.ui.analysis_ui_v081_runtime import _fundamental_display_score


def test_fundamental_ui_uses_v082_overall_score() -> None:
    detail = SimpleNamespace(
        status="OK",
        overall_score=69.6,
        business_quality=SimpleNamespace(score=47.1),
    )

    assert _fundamental_display_score(detail) == 69.6


def test_fundamental_ui_returns_none_when_unavailable() -> None:
    detail = SimpleNamespace(status="UNAVAILABLE", overall_score=69.6)

    assert _fundamental_display_score(detail) is None


def test_fundamental_ui_handles_missing_detail() -> None:
    assert _fundamental_display_score(None) is None
