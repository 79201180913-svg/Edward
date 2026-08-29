from edward.services.wf_selection_audit_service_v083 import (
    WFSelectionAuditServiceV083,
    WFSelectionAuditWindow,
)


def window(i, baseline, transfer, oracle, b, t, o):
    return WFSelectionAuditWindow(
        window_index=i,
        baseline_parameters=baseline,
        transfer_parameters=transfer,
        baseline_oos_return_pct=b,
        transfer_oos_return_pct=t,
        oracle_parameters=oracle,
        oracle_oos_return_pct=o,
    )


def test_audit_distinguishes_transfer_wins_losses_and_ties():
    result = WFSelectionAuditServiceV083.evaluate(
        "Breakout",
        [
            window(0, {"lookback": 20}, {"lookback": 10}, {"lookback": 10}, 1.0, 2.0, 2.0),
            window(1, {"lookback": 20}, {"lookback": 40}, {"lookback": 10}, 2.0, 1.0, 3.0),
            window(2, {"lookback": 10}, {"lookback": 10}, {"lookback": 10}, 0.0, 0.0, 0.0),
        ],
    )
    assert result.windows == 3
    assert result.changed_windows == 2
    assert result.transfer_wins == 1
    assert result.transfer_losses == 1
    assert result.transfer_ties == 1
    assert result.transfer_win_rate_pct == 100 / 3
    assert result.mean_transfer_delta_pct == 0.0


def test_audit_compounds_baseline_transfer_and_oracle_returns():
    result = WFSelectionAuditServiceV083.evaluate(
        "Momentum",
        [
            window(0, {"lookback": 10}, {"lookback": 20}, {"lookback": 20}, 10.0, 20.0, 20.0),
            window(1, {"lookback": 10}, {"lookback": 20}, {"lookback": 20}, -5.0, 0.0, 5.0),
        ],
    )
    assert round(result.cumulative_baseline_return_pct, 6) == 4.5
    assert round(result.cumulative_transfer_return_pct, 6) == 20.0
    assert round(result.cumulative_oracle_return_pct, 6) == 26.0
    assert round(result.mean_baseline_oracle_gap_pct, 6) == 10.0
    assert round(result.mean_transfer_oracle_gap_pct, 6) == 2.5


def test_empty_audit_is_safe():
    result = WFSelectionAuditServiceV083.evaluate("Breakout", [])
    assert result.windows == 0
    assert result.mean_transfer_delta_pct == 0.0
