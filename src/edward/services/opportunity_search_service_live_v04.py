from __future__ import annotations

from typing import Any, Callable

import edward.services.opportunity_search_service as opportunity_search_module
from edward.services.opportunity_search_service import MARKET_SCOPE, ProgressCallback, OpportunitySearchResult, OpportunitySearchService
from edward.services.trading_path_opportunity_runtime_service_v013 import TradingPathOpportunityRuntimeServiceV013

ResultCallback = Callable[[OpportunitySearchResult, int, int], None]


class _ProvidedAnalysisService:
    """Backward-compatible test seam for a precomputed analysis result."""

    def __init__(self, result: Any):
        self.result = result

    def analyze(self, **_kwargs: Any) -> Any:
        return self.result


class LiveOpportunitySearchService(OpportunitySearchService):
    """Live Opportunity consumer backed exclusively by canonical v0.8.12 Trading Paths."""

    def __init__(self, client: Any, *, force_recompute: bool = False):
        self.force_recompute = force_recompute
        super().__init__(client, analysis_service=None)
        self.path_runtime = TradingPathOpportunityRuntimeServiceV013()

    @property
    def cache_info(self) -> dict[str, int]:
        return {}

    def _canonical_result(self, instrument: Any, opportunity: Any, quantity: float) -> OpportunitySearchResult:
        path = opportunity.best_path
        decision = getattr(opportunity.decision, "value", opportunity.decision)
        status = getattr(path.status, "value", path.status)
        state = getattr(opportunity.current_state, "value", opportunity.current_state)
        path_opportunity = path.opportunity
        reason = ""
        if decision == "pass":
            if status == "rejected": reason = "TRADING_PATH_REJECTED"
            elif not bool(path_opportunity.risk_gate): reason = "RISK_GATE_FAILED"
            elif path_opportunity.score is None: reason = "OPPORTUNITY_SCORE_UNAVAILABLE"
            else: reason = "NO_PROMOTED_TRADING_PATH"
        elif decision == "wait": reason = "TRADING_PATH_WAIT"
        elif decision == "buy": reason = "TRADING_PATH_BUY"
        explanation = f"Trading Path: {path.hypothesis}; regime={path.regime}; volatility={path.volatility_bucket}; direction={path.direction}; horizon={path.horizon}; status={status}; state={state}."
        return OpportunitySearchResult(
            instrument_uid=str(self._field(instrument, "uid", self._field(instrument, "instrument_uid", ""))),
            ticker=str(self._field(instrument, "ticker", "")),
            name=str(self._field(instrument, "name", "")),
            price=self._float_or_none(self._field(instrument, "last_price", None)),
            market_regime=path.regime,
            strategy_name=path.strategy_family,
            strategy_score=float(path_opportunity.score or 0.0),
            opportunity_score=float(path_opportunity.score or 0.0),
            decision=str(decision).upper() if decision is not None else None,
            status=str(status).upper(), reason=reason, explanation=explanation,
            quantity=quantity, risk_score=float(path_opportunity.risk_score or 0.0),
            execution_ready=False, canonical_opportunity=opportunity,
        )

    def scan(self, *, profile: str = "medium_term", instrument_kind: str = "SHARE", scope: str = MARKET_SCOPE, progress_callback: ProgressCallback | None = None, result_callback: ResultCallback | None = None, force_recompute: bool = False) -> list[OpportunitySearchResult]:
        scope = str(scope or MARKET_SCOPE).upper()
        if scope not in {"MARKET", "PORTFOLIO"}:
            raise ValueError(f"Unsupported opportunity scope: {scope}")
        self._notify(progress_callback, "Загрузка списка инструментов", 2.0, 0, 0)
        account_id = self._active_account(); positions = self.client.get_positions(account_id) if account_id else None
        instruments = self._build_universe(scope=scope, instrument_kind=instrument_kind, positions=positions); total = len(instruments)
        self._notify(progress_callback, f"Вселенная анализа: {total}", 8.0, 0, total)
        results: list[OpportunitySearchResult] = []; valid_index = 0
        for instrument in instruments:
            uid = str(self._field(instrument, "uid", self._field(instrument, "instrument_uid", "")))
            if not uid: continue
            valid_index += 1; progress_base = 15.0 + ((valid_index - 1) / max(1, total)) * 80.0; progress_span = 80.0 / max(1, total); ticker = str(self._field(instrument, "ticker", ""))
            self._notify(progress_callback, f"Market Data: {ticker}", progress_base, valid_index, total)
            try:
                candles = self._get_candles(uid)
                if len(candles) < 300:
                    result = self._unavailable(instrument, self._field(instrument, "last_price", None), 0.0, f"Недостаточно исторических данных: получено {len(candles)} свечей, требуется не менее 300.")
                else:
                    self._notify(progress_callback, f"Trading Path Analysis: {ticker}", progress_base + progress_span * 0.45, valid_index, total)
                    canonical = self.path_runtime.scan_instrument(instrument_uid=uid, ticker=ticker, candles=candles, profile=profile)
                    if canonical is None:
                        result = self._unavailable(instrument, self._field(instrument, "last_price", None), 0.0, "Нет сформированных Trading Path.")
                    else:
                        quantity = 0.0; raw_positions = self._field(positions, "securities", []) if positions is not None else []
                        for position in raw_positions or []:
                            if str(self._field(position, "instrument_uid", self._field(position, "uid", ""))) == uid:
                                quantity = float(self._field(position, "balance", self._field(position, "quantity", 0)) or 0); break
                        result = self._canonical_result(instrument, canonical, quantity)
            except Exception as exc:
                opportunity_search_module.logger.exception("[V013 OPPORTUNITY ERROR] uid=%s ticker=%s", uid, ticker); result = self._unavailable(instrument, self._field(instrument, "last_price", None), 0.0, f"Ошибка анализа: {exc}")
            results.append(result)
            if result_callback is not None:
                try: result_callback(result, valid_index, total)
                except Exception: opportunity_search_module.logger.exception("[V013 OPPORTUNITY CALLBACK] ticker=%s", ticker)
            self._notify(progress_callback, f"Обработано: {ticker}", progress_base + progress_span, valid_index, total)
        self._notify(progress_callback, "Ранжирование возможностей", 97.0, valid_index, total); results.sort(key=lambda item: (item.decision not in {"BUY", "WAIT"}, -item.opportunity_score)); self._notify(progress_callback, "Сканирование завершено", 100.0, valid_index, total)
        return results

    @staticmethod
    def _field(value: Any, name: str, default: Any = None) -> Any:
        return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)

    @staticmethod
    def _float_or_none(value: Any) -> float | None:
        try: return None if value in (None, "") else float(value)
        except Exception: return None

    @staticmethod
    def _unavailable(instrument: Any, price: float | None, quantity: float, reason: str) -> OpportunitySearchResult:
        return OpportunitySearchResult(str(LiveOpportunitySearchService._field(instrument, "uid", LiveOpportunitySearchService._field(instrument, "instrument_uid", ""))), str(LiveOpportunitySearchService._field(instrument, "ticker", "")), str(LiveOpportunitySearchService._field(instrument, "name", "")), price, None, None, 0.0, 0.0, None, "ANALYSIS_UNAVAILABLE", "ANALYSIS_UNAVAILABLE", reason, quantity, 0.0)


__all__ = ["_ProvidedAnalysisService", "LiveOpportunitySearchService"]
