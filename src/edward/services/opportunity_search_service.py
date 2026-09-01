from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from edward.services.account_service import AccountService
from edward.services.analysis_service import AnalysisService, Candle, StrategyResult
from edward.services.decision_engine import (
    DecisionEngine,
    DecisionRequest,
    OpportunityContext,
    PortfolioContextData,
    PositionContextData,
    RiskContextData,
    Scenario,
    StrategyContextData,
)
from edward.services.forecast_model_selection_service import ForecastModelSelectionService
from edward.services.instrument_catalog_service import InstrumentCatalogService
from edward.services.instrument_decision_context_service import InstrumentDecisionContextService
from edward.services.market_decision_context_service import MarketDecisionContextService
from edward.services.opportunity_analysis_pipeline_v0821 import (
    OpportunityAnalysisPipelineV0821,
    UnifiedOpportunityEngineV0821,
)
from edward.services.portfolio_decision_context_service import PortfolioDecisionContextService
from edward.services.position_sizing_service import PositionSizingInput, PositionSizingService
from edward.services.trade_plan_service import TradePlanInput, TradePlanService

logger = logging.getLogger(__name__)
ProgressCallback = Callable[[str, float, int, int], None]
INSTRUMENT_KIND_ALL = "ALL"
MARKET_SCOPE = "MARKET"
PORTFOLIO_SCOPE = "PORTFOLIO"
SUPPORTED_SCOPES = (MARKET_SCOPE, PORTFOLIO_SCOPE)

@dataclass(frozen=True, slots=True)
class OpportunitySearchResult:
    instrument_uid: str
    ticker: str
    name: str
    price: float | None
    market_regime: str | None
    strategy_name: str | None
    strategy_score: float
    opportunity_score: float
    decision: str | None
    status: str
    reason: str
    explanation: str
    quantity: float
    risk_score: float = 0.0
    forecast_model: str | None = None
    forecast_confidence: str | None = None
    forecast_prices: tuple[tuple[int, float], ...] = ()
    forecast_probability_up: tuple[tuple[int, float], ...] = ()
    forecast_probability_down: tuple[tuple[int, float], ...] = ()
    forecast_downside: tuple[tuple[int, float], ...] = ()
    forecast_upside: tuple[tuple[int, float], ...] = ()
    trade_plan: Any | None = None
    recommended_quantity: int = 0
    recommended_value: float = 0.0
    recommended_weight_pct: float = 0.0
    execution_ready: bool = False
    canonical_opportunity: Any | None = None

class OpportunitySearchService:
    """Run opportunity search using the canonical v0.8.2.1 analysis pipeline."""
    def __init__(self, client: Any, analysis_service: AnalysisService | None = None):
        self.client = client
        self.analysis = analysis_service or OpportunityAnalysisPipelineV0821(client)
        self.opportunity_engine = UnifiedOpportunityEngineV0821()
        self.catalog = InstrumentCatalogService(client)
        self.instrument_context = InstrumentDecisionContextService()
        self.market_context = MarketDecisionContextService()
        self.portfolio_context = PortfolioDecisionContextService()

    @staticmethod
    def _notify(progress_callback: ProgressCallback | None, stage: str, percent: float, current: int, total: int) -> None:
        if progress_callback is None: return
        try: progress_callback(stage, round(max(0.0, min(100.0, percent)), 1), current, total)
        except Exception: pass

    def scan(self, *, profile: str = "medium_term", instrument_kind: str = "SHARE", scope: str = MARKET_SCOPE, progress_callback: ProgressCallback | None = None, result_callback: Callable[[OpportunitySearchResult, int, int], None] | None = None, force_recompute: bool = False) -> list[OpportunitySearchResult]:
        scope = str(scope or MARKET_SCOPE).upper()
        if scope not in SUPPORTED_SCOPES: raise ValueError(f"Unsupported opportunity scope: {scope}")
        if force_recompute and hasattr(self.analysis, "force_recompute"):
            try: self.analysis.force_recompute()
            except Exception: logger.exception("[OPPORTUNITY CACHE] failed to force recompute")
        self._notify(progress_callback, "Загрузка списка инструментов", 2.0, 0, 0)
        account_id = self._active_account()
        positions = self.client.get_positions(account_id) if account_id else None
        portfolio = self.client.get_portfolio(account_id) if account_id else None
        self._notify(progress_callback, "Portfolio Context загружен", 5.0, 0, 0)
        instruments = self._build_universe(scope=scope, instrument_kind=instrument_kind, positions=positions)
        total = len(instruments)
        scope_title = "торговых инструментов" if scope == MARKET_SCOPE else "позиций портфеля"
        self._notify(progress_callback, f"Вселенная анализа: {total} {scope_title}", 8.0, 0, total)
        results: list[OpportunitySearchResult] = []
        valid_index = 0
        for instrument in instruments:
            uid = str(_field(instrument, "uid", _field(instrument, "instrument_uid", "")))
            if not uid: continue
            valid_index += 1
            progress_base = 15.0 + ((valid_index - 1) / max(1, total)) * 80.0
            progress_span = 80.0 / max(1, total)
            ticker = str(_field(instrument, "ticker", ""))
            self._notify(progress_callback, f"Market Data: {ticker}", progress_base, valid_index, total)
            result = self._evaluate_instrument(instrument=instrument, profile=profile, positions=positions, portfolio=portfolio, progress_callback=progress_callback, progress_base=progress_base, progress_span=progress_span, current=valid_index, total=total)
            results.append(result)
            if result_callback is not None:
                try: result_callback(result, valid_index, total)
                except Exception: logger.exception("[OPPORTUNITY RESULT CALLBACK] ticker=%s", ticker)
            self._notify(progress_callback, f"Обработано: {ticker}", progress_base + progress_span, valid_index, total)
        self._notify(progress_callback, "Ранжирование возможностей", 97.0, valid_index, total)
        results = sorted(results, key=lambda item: (item.decision not in {"BUY", "WAIT", "HOLD", "ADD", "REDUCE", "SELL"}, item.decision not in {"BUY", "ADD", "REDUCE", "SELL", "HOLD"}, -item.opportunity_score))
        self._notify(progress_callback, "Сканирование завершено", 100.0, valid_index, total)
        return results

    def _build_universe(self, *, scope: str, instrument_kind: str, positions: Any) -> list[Any]:
        return self._market_universe(instrument_kind, positions) if scope == MARKET_SCOPE else self._portfolio_universe(instrument_kind, positions)

    def _market_universe(self, instrument_kind: str, positions: Any = None) -> list[Any]:
        held_uids = {_uid(item) for item in _held_positions(positions) if _uid(item)}
        result: list[Any] = []; seen: set[str] = set()
        for kind in self._kinds(instrument_kind):
            for instrument in self.catalog.list(kind, trade_available_only=True):
                uid = _uid(instrument)
                if not uid or uid in seen or uid in held_uids: continue
                if not _bool_field(instrument, "buy_available", False) or not _bool_field(instrument, "trading_available", False): continue
                seen.add(uid); result.append(instrument)
        return result

    def _portfolio_universe(self, instrument_kind: str, positions: Any) -> list[Any]:
        held = _held_positions(positions)
        if not held: return []
        held_uids = {_uid(item) for item in held if _uid(item)}; catalog_items: dict[str, Any] = {}
        for kind in self._kinds(instrument_kind):
            for instrument in self.catalog.list(kind, trade_available_only=False):
                uid = _uid(instrument)
                if uid in held_uids: catalog_items[uid] = instrument
        return [catalog_items.get(_uid(position), dict(position) if isinstance(position, dict) else position) for position in held]

    @staticmethod
    def _enforce_execution_readiness(result: Any, *, forecast_quality_pass: bool = False, forecast_quality_label: str = "НЕ ПРИМЕНИМ") -> Any:
        decision = str(getattr(result, "decision", "") or "").upper()
        quantity = float(getattr(result, "recommended_quantity", 0) or 0)
        actionable = decision in {"BUY", "SELL", "ADD", "REDUCE"}
        ready = bool(getattr(result, "execution_ready", False))
        reason = str(getattr(result, "reason", "") or "")
        if actionable and quantity <= 0:
            ready = False
            reason = f"{reason}; POSITION_SIZE_NOT_READY; Исполнение: НЕТ"
        elif actionable:
            ready = True
            if forecast_quality_pass:
                reason = f"{reason}; Контроль качества прогноза: {forecast_quality_label}; Исполнение: ДА"
            else:
                reason = f"{reason}; Исполнение: ДА"
        else:
            ready = False
            reason = f"{reason}; Исполнение: НЕТ"
        try:
            return result.__class__(**{**result.__dict__, "execution_ready": ready, "reason": reason})
        except Exception:
            try:
                result.execution_ready = ready
                result.reason = reason
            except Exception:
                pass
            return result

    # Remaining legacy evaluation implementation intentionally preserved below this point.
