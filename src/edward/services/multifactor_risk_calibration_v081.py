from __future__ import annotations

from logging import getLogger
from typing import Any

from edward.services.multifactor_analysis_service_v081 import (
    Evidence,
    InstrumentRiskFactor,
    MultiFactorAnalysisServiceV081,
    _clamp,
    _num,
    _value,
)

logger = getLogger(__name__)


def calibrated_instrument_risk(cls: type[MultiFactorAnalysisServiceV081], risk_data: Any = None) -> InstrumentRiskFactor:
    """Calibrate v0.8.1 instrument risk from required margin.

    The existing pipeline normalizes fractional contract values to percentages.
    The effective margin is the long requirement unless short selling is enabled,
    in which case the stricter of long/short requirements is used.
    """
    if risk_data is None:
        return InstrumentRiskFactor(
            None,
            None,
            False,
            0,
            0,
            Evidence("instrument_risk", "UNAVAILABLE", 0, 0, available=False, reason="NO_RISK_RATE_DATA"),
        )

    dlong = _num(risk_data, "dlong", "dlong_client")
    dshort = _num(risk_data, "dshort", "dshort_client")
    short_enabled = bool(_value(risk_data, "short_enabled_flag", "short_enabled", default=False))

    candidates = []
    if dlong is not None:
        candidates.append(dlong)
    if short_enabled and dshort is not None:
        candidates.append(dshort)

    if not candidates:
        return InstrumentRiskFactor(
            dlong,
            dshort,
            short_enabled,
            0,
            0,
            Evidence("instrument_risk", "UNAVAILABLE", 0, 0, available=False, reason="INCOMPLETE_RISK_RATE_DATA"),
        )

    effective_margin_pct = _clamp(max(candidates))
    capital_efficiency = _clamp(100.0 - effective_margin_pct)
    risk_score = effective_margin_pct
    direction = "NEGATIVE" if risk_score >= 65.0 else "NEUTRAL"

    logger.info(
        "[V081 RISK CALIBRATION] dlong=%r dshort=%r short_enabled=%r "
        "effective_margin_pct=%.2f capital_efficiency_score=%.2f risk_score=%.2f direction=%s",
        dlong,
        dshort,
        short_enabled,
        effective_margin_pct,
        capital_efficiency,
        risk_score,
        direction,
    )

    return InstrumentRiskFactor(
        dlong,
        dshort,
        short_enabled,
        capital_efficiency,
        risk_score,
        Evidence("instrument_risk", direction, risk_score, 90.0),
    )


# Install the calibrated method only for v0.8.1 runtime usage.
MultiFactorAnalysisServiceV081.instrument_risk = classmethod(calibrated_instrument_risk)

__all__ = ["calibrated_instrument_risk"]
