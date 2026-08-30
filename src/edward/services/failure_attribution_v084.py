from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class FailureAttributionV084:
    strategy: str
    passed: bool
    primary_reason: str
    supporting_reasons: tuple[str, ...] = ()
    details: Mapping[str, object] = None


class FailureAttributionServiceV084:
    """Explain why a strategy did not pass without changing selection or QG."""

    @staticmethod
    def evaluate(
        *,
        strategy: str,
        quality_gate_passed: bool,
        quality_gate_failure_reason: str | None,
        quality_gate_failed_checks: tuple[str, ...] = (),
        low_sample_pct: float = 0.0,
        oos_mean_return_pct: float = 0.0,
        oos_positive_pct: float = 0.0,
        stable_zone_pct: float = 0.0,
        viable_windows: int = 0,
    ) -> FailureAttributionV084:
        if quality_gate_passed:
            primary = "PASS"
        elif viable_windows == 0:
            primary = "NO_VIABLE_TRAIN"
        elif oos_mean_return_pct < 0:
            primary = "OOS_NEGATIVE"
        elif oos_positive_pct < 50.0:
            primary = "OOS_LOW_POSITIVE_RATE"
        elif low_sample_pct >= 50.0:
            primary = "LOW_SAMPLE"
        elif stable_zone_pct < 50.0:
            primary = "LOW_PARAMETER_STABILITY"
        elif quality_gate_failure_reason:
            primary = quality_gate_failure_reason
        else:
            primary = "QUALITY_GATE"

        supporting: list[str] = []
        if low_sample_pct >= 50.0 and primary != "LOW_SAMPLE": supporting.append("LOW_SAMPLE")
        if stable_zone_pct < 50.0 and primary != "LOW_PARAMETER_STABILITY": supporting.append("LOW_PARAMETER_STABILITY")
        supporting.extend(check for check in quality_gate_failed_checks if check not in supporting)
        return FailureAttributionV084(
            strategy=strategy,
            passed=quality_gate_passed,
            primary_reason=primary,
            supporting_reasons=tuple(dict.fromkeys(supporting)),
            details={
                "low_sample_pct": low_sample_pct,
                "oos_mean_return_pct": oos_mean_return_pct,
                "oos_positive_pct": oos_positive_pct,
                "stable_zone_pct": stable_zone_pct,
                "viable_windows": viable_windows,
            },
        )


__all__ = ["FailureAttributionV084", "FailureAttributionServiceV084"]
