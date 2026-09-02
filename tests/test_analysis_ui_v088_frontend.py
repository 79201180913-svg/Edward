from enum import Enum
from pathlib import Path

from edward.ui.analysis_ui_v088_frontend import _fmt_num, _fmt_pct, _value


class _Status(Enum):
    PROMOTED = "promoted"
    RESEARCH = "research_only"
    REJECTED = "rejected"


def test_frontend_status_value_is_user_facing():
    assert _value(_Status.PROMOTED) == "promoted"
    assert _value(_Status.RESEARCH) == "research_only"
    assert _value(_Status.REJECTED) == "rejected"


def test_frontend_formats_evidence_values():
    assert _fmt_pct(6.148) == "+6.15%"
    assert _fmt_pct(-0.343) == "-0.34%"
    assert _fmt_num(1.2345) == "1.23"
    assert _fmt_num(0.125, 3) == "0.125"


def test_frontend_contains_canonical_result_panel_and_runtime():
    source = Path("src/edward/ui/analysis_ui_v088_frontend.py").read_text(encoding="utf-8")
    assert "Финальный результат canonical runtime" in source
    assert "AnalysisPathRuntimeServiceV012" in source
