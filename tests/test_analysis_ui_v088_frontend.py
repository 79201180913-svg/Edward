from enum import Enum
from pathlib import Path

from edward.ui.analysis_ui_v088_frontend import _fmt_pct, _fmt_ratio, _status_text


class _Status(Enum):
    PROMOTED = "promoted"
    RESEARCH = "research_only"
    REJECTED = "rejected"


def test_frontend_status_labels_are_user_facing():
    assert _status_text(_Status.PROMOTED) == "PROMOTED"
    assert _status_text(_Status.RESEARCH) == "RESEARCH ONLY"
    assert _status_text(_Status.REJECTED) == "REJECTED"


def test_frontend_formats_evidence_values():
    assert _fmt_pct(6.148) == "+6.15%"
    assert _fmt_pct(-0.343) == "-0.34%"
    assert _fmt_ratio(1.0) == "100%"
    assert _fmt_ratio(0.125) == "12%"


def test_frontend_contains_final_instrument_decision_panel_and_engine():
    source = Path("src/edward/ui/analysis_ui_v088_frontend.py").read_text(encoding="utf-8")
    assert "Финальное торговое решение по инструменту" in source
    assert "DecisionEngine.evaluate(request)" in source
    assert "[V012 UI DECISION]" in source
