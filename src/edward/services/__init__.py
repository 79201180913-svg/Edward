from .account_service import AccountService
from .balance_service import BalanceService
from .instrument_service import InstrumentService
from .market_service import MarketService
from .portfolio_service import PortfolioService
from .execution_confirmation_service import ControlledExecutionService, PreTradeValidationResult, PreTradeValidator
from .execution_center_controller_v06 import ExecutionCenterController, ExecutionCenterState
from .execution_intake_service_v06 import ExecutionIntakeResult, ExecutionIntakeService
from .execution_bridge_service_v06 import ExecutionBridgeService, ExecutionQueueItem
from .event_overlap_audit_v088 import EventOverlapAuditV088, EventOverlapAuditResultV088, EventOverlapPairV088

__all__ = [
    "AccountService", "BalanceService", "InstrumentService", "MarketService", "PortfolioService",
    "ControlledExecutionService", "PreTradeValidationResult", "PreTradeValidator",
    "ExecutionCenterController", "ExecutionCenterState", "ExecutionIntakeResult", "ExecutionIntakeService",
    "ExecutionBridgeService", "ExecutionQueueItem", "EventOverlapAuditV088", "EventOverlapAuditResultV088",
    "EventOverlapPairV088",
]

from .analysis_service import AnalysisService as _AnalysisService
from .cached_analysis_service import CachedAnalysisService as _CachedAnalysisService

_original_analysis_analyze = _AnalysisService.analyze
_original_analysis_save = _AnalysisService.save


def _cached_analyze(self, *args, **kwargs):
    if getattr(self, "store", None) is None:
        return _original_analysis_analyze(self, *args, **kwargs)
    cached = _CachedAnalysisService(self.store)
    result = cached.analyze(*args, **kwargs)
    self._last_cached_analysis = cached
    self._last_cached_run_ids = dict(cached.last_cache_run_ids)
    self._last_cache_info = cached.cache_info()
    return result


def _cached_save(self, result):
    run_ids = getattr(self, "_last_cached_run_ids", {})
    recommendation = getattr(result, "recommendation", None)
    if recommendation and recommendation in run_ids:
        return run_ids[recommendation]
    return _original_analysis_save(self, result)


_AnalysisService.analyze = _cached_analyze
_AnalysisService.save = _cached_save

from . import multifactor_risk_calibration_v081 as _multifactor_risk_calibration_v081  # noqa: F401,E402
