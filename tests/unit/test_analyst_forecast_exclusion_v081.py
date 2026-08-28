from edward.services.analyst_forecast_exclusion_v081 import (
    ANALYST_FORECAST_AUTOMATIC_EVIDENCE_ENABLED,
    ANALYST_FORECAST_EXCLUSION_REASON,
)


def test_opaque_analyst_forecast_is_not_automatic_evidence():
    assert ANALYST_FORECAST_AUTOMATIC_EVIDENCE_ENABLED is False
    assert ANALYST_FORECAST_EXCLUSION_REASON == "EXTERNAL_FORECAST_METHOD_NOT_VALIDATED"
