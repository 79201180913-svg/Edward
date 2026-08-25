from types import SimpleNamespace

from edward.services.quality_gate_diagnostics import quality_gate_reasons


def test_quality_gate_diagnostics_exposes_each_check():
    result = SimpleNamespace(
        wf_windows=7,
        return_consistency=71.0,
        stability=62.0,
        return_pct=2.12,
        max_drawdown_pct=4.30,
        sharpe=0.48,
    )
    checks = quality_gate_reasons(
        result,
        {"min_stability_pct": 60.0, "max_drawdown_pct": 25.0},
    )

    assert len(checks) == 6
    assert all(ok for ok, _ in checks)


def test_quality_gate_diagnostics_identifies_failed_components():
    result = SimpleNamespace(
        wf_windows=7,
        return_consistency=52.0,
        stability=52.0,
        return_pct=-1.0,
        max_drawdown_pct=30.0,
        sharpe=-0.04,
    )
    checks = quality_gate_reasons(
        result,
        {"min_stability_pct": 60.0, "max_drawdown_pct": 25.0},
    )

    failed = [text for ok, text in checks if not ok]
    assert any("Return consistency" in text for text in failed)
    assert any("Stability" in text for text in failed)
    assert any("Return:" in text for text in failed)
    assert any("Max DD" in text for text in failed)
    assert any("Sharpe" in text for text in failed)
