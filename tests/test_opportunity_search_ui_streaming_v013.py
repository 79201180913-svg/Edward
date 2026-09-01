from pathlib import Path


def test_opportunity_ui_streams_completed_results_during_scan():
    source = Path("src/edward/ui/opportunity_search_ui_v04.py").read_text(encoding="utf-8")

    assert "def publish_result(result,current,total):" in source
    assert "result_callback=lambda result,c,t:self.after(0,lambda:publish_result(result,c,t))" in source
    assert "state[\"results\"].append(result)" in source
    assert "render()" in source
