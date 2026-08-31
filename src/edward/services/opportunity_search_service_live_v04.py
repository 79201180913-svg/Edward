from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

import edward.services.opportunity_search_service as opportunity_search_module
from edward.config.application_settings import ApplicationSettingsStore
from edward.services.execution_readiness_service import ExecutionReadinessInput, ExecutionReadinessService
from edward.services.opportunity_analysis_pipeline_v0821 import OpportunityAnalysisPipelineV0821
from edward.services.opportunity_search_analysis_consumer_v010 import OpportunityAnalysisConsumerV010
from edward.services.opportunity_search_service import MARKET_SCOPE, ProgressCallback, OpportunitySearchResult, OpportunitySearchService
from edward.storage.sqlite_store import SQLiteStore

ResultCallback = Callable[[OpportunitySearchResult, int, int], None]


class _ProvidedAnalysisService:
    """Return a previously calculated analysis result without recalculating it."""
    def __init__(self, result: Any):
        self.result = result

    def analyze(self, **_kwargs: Any) -> Any:
        return self.result


class LiveOpportunitySearchService(OpportunitySearchService):
    """Opportunity search consuming the canonical analysis result."""

    def __init__(self, client: Any, *, force_recompute: bool = False):
        settings = ApplicationSettingsStore().load()
        store = SQLiteStore(settings.storage_path)
        self.force_recompute = force_recompute
        self.analysis_pipeline = OpportunityAnalysisPipelineV0821(client, cache_store=store, force_recompute=force_recompute)
        super().__init__(client, analysis_service=self.analysis_pipeline)
        self._provided_candles: dict[str, list[Any]] = {}

    @property
    def cache_info(self) -> dict[str, int]:
        return self.analysis_pipeline.cache_info()

    def _get_candles(self, instrument_uid: str) -> list[Any]:
        cached = self._provided_candles.get(str(instrument_uid))
        if cached is not None:
            return cached
        return super()._get_candles(instrument_uid)

    @staticmethod
    def _enforce_execution_readiness(result: OpportunitySearchResult, *, forecast_quality_pass: bool = False, forecast_quality_label: str = "НЕ ПРОВЕРЕН") -> OpportunitySearchResult:
        decision = str(result.decision or "").upper()
        if decision not in {"BUY", "ADD", "HOLD", "REDUCE", "SELL"}:
            return result
        plan = getattr(result, "trade_plan", None)
        risk_reward = getattr(plan, "risk_reward", None) if plan is not None else None
        strategy_quality_pass = str(result.reason or "") not in {"STRATEGY_QUALITY_FAIL", "RISK_FAIL", "CRITICAL_RISK"}
        risk_reward_ok = decision not in {"BUY", "ADD"} or (risk_reward is not None and risk_reward > 0)
        position_size_ready = decision not in {"REDUCE", "SELL"} or int(getattr(result, "recommended_quantity", 0) or 0) > 0
        plan_ready = plan is not None
        gate = ExecutionReadinessService.evaluate(ExecutionReadinessInput(decision=decision, forecast_quality_pass=forecast_quality_pass, risk_ok=str(result.reason or "") not in {"RISK_FAIL", "CRITICAL_RISK"}, portfolio_available=True, trading_status_ok=True, position_size_ready=position_size_ready, entry_ready=plan_ready, target_ready=plan_ready, stop_ready=plan_ready, liquidity_ok=True, strategy_quality_pass=strategy_quality_pass, risk_reward_ok=risk_reward_ok))
        readiness_text = "Исполнение: ДА" if gate.execution_ready else "Исполнение: НЕТ"
        gate_reason_text = " | ".join(gate.reasons) if gate.reasons else ""
        execution_explanation = " | ".join(part for part in [str(result.reason or ""), *([gate_reason_text] if gate_reason_text else []), f"Контроль качества прогноза: {forecast_quality_label}", readiness_text] if part)
        changes: dict[str, Any] = {"execution_ready": gate.execution_ready}
        if hasattr(result, "reason"):
            changes["reason"] = execution_explanation
        if gate.execution_ready == result.execution_ready and execution_explanation == str(getattr(result, "reason", "") or ""):
            return result
        try:
            return replace(result, **changes)
        except TypeError:
            try:
                result.execution_ready = gate.execution_ready
                if hasattr(result, "reason"):
                    result.reason = execution_explanation
            except Exception:
                return result
            return result

    @staticmethod
    def _analysis_value(value: Any, default: Any = None) -> Any:
        if value is None:
            return default
        return getattr(value, "value", value)

    @classmethod
    def _from_canonical_result(cls, instrument: Any, analysis_result: Any, quantity: float = 0.0) -> OpportunitySearchResult:
        consumed = OpportunityAnalysisConsumerV010.from_result(analysis_result)
        analysis = consumed.analysis
        strategy_name = consumed.evidence_strategy
        strategy_score = 0.0
        selected = None
        for item in getattr(analysis, "strategies", ()) or ():
            if getattr(item, "strategy", None) == strategy_name:
                selected = item
                break
        if selected is None and strategy_name is None:
            for item in getattr(analysis, "strategies", ()) or ():
                if getattr(item, "quality_gate", False):
                    selected = item
                    strategy_name = getattr(item, "strategy", None)
                    break
        if selected is not None:
            strategy_score = float(getattr(selected, "score", 0.0) or 0.0)
        recommendation = cls._analysis_value(getattr(analysis, "recommendation", None))
        score = float(getattr(analysis, "score", 0.0) or 0.0)
        opportunity_score = float(getattr(consumed.opportunity, "score", 0.0) or 0.0)
        qg = bool(getattr(selected, "quality_gate", False)) if selected is not None else False
        reason = "" if qg else "STRATEGY_QUALITY_FAIL" if selected is not None else "ANALYSIS_NO_STRATEGY"
        explanation = str(getattr(analysis, "explanation", None) or getattr(analysis, "reason", None) or "")
        return OpportunitySearchResult(
            instrument_uid=str(cls._field(instrument, "uid", cls._field(instrument, "instrument_uid", ""))),
            ticker=str(cls._field(instrument, "ticker", "")),
            name=str(cls._field(instrument, "name", "")),
            price=cls._float_or_none(cls._field(instrument, "last_price", None)),
            market_regime=getattr(analysis, "market_regime", None),
            strategy_name=strategy_name,
            strategy_score=strategy_score if selected is not None else score,
            opportunity_score=opportunity_score,
            decision=recommendation,
            status="ANALYSIS_READY",
            reason=reason,
            explanation=explanation,
            quantity=quantity,
            risk_score=0.0,
            forecast_model=None,
            forecast_confidence=None,
            forecast_prices=(),
            forecast_probability_up=(),
            forecast_probability_down=(),
            forecast_downside=(),
            forecast_upside=(),
            trade_plan=None,
            recommended_quantity=0,
            recommended_value=0.0,
            recommended_weight_pct=0.0,
            execution_ready=False,
        )

    def scan(self, *, profile: str = "medium_term", instrument_kind: str = "SHARE", scope: str = MARKET_SCOPE, progress_callback: ProgressCallback | None = None, result_callback: ResultCallback | None = None, force_recompute: bool = False) -> list[OpportunitySearchResult]:
        scope = str(scope or MARKET_SCOPE).upper()
        if scope not in {"MARKET", "PORTFOLIO"}:
            raise ValueError(f"Unsupported opportunity scope: {scope}")
        if force_recompute:
            self.analysis_pipeline.force_recompute()
        self._notify(progress_callback, "Загрузка списка инструментов", 2.0, 0, 0)
        account_id = self._active_account()
        positions = self.client.get_positions(account_id) if account_id else None
        portfolio = self.client.get_portfolio(account_id) if account_id else None
        instruments = self._build_universe(scope=scope, instrument_kind=instrument_kind, positions=positions)
        total = len(instruments)
        self._notify(progress_callback, f"Вселенная анализа: {total}", 8.0, 0, total)
        results: list[OpportunitySearchResult] = []
        valid_index = 0
        for instrument in instruments:
            uid = str(self._field(instrument, "uid", self._field(instrument, "instrument_uid", "")))
            if not uid:
                continue
            valid_index += 1
            progress_base = 15.0 + ((valid_index - 1) / max(1, total)) * 80.0
            progress_span = 80.0 / max(1, total)
            ticker = str(self._field(instrument, "ticker", ""))
            self._notify(progress_callback, f"Market Data: {ticker}", progress_base, valid_index, total)
            try:
                candles = super()._get_candles(uid)
                if len(candles) < 150:
                    result = self._unavailable(instrument, self._field(instrument, "last_price", None), 0.0, f"Недостаточно исторических данных: получено {len(candles)} свечей, требуется не менее 150.")
                else:
                    self._provided_candles[uid] = candles
                    self._notify(progress_callback, f"Анализ стратегий: {ticker}", progress_base + progress_span * 0.28, valid_index, total)
                    analysis_result = self.analysis_pipeline.analyze(instrument_uid=uid, ticker=ticker, candles=candles, profile=profile, instrument=instrument)
                    quantity = 0.0
                    raw_positions = self._field(positions, "securities", []) if positions is not None else []
                    for position in raw_positions or []:
                        if str(self._field(position, "instrument_uid", self._field(position, "uid", ""))) == uid:
                            quantity = float(self._field(position, "balance", self._field(position, "quantity", 0)) or 0)
                            break
                    result = self._from_canonical_result(instrument, analysis_result, quantity)
            except Exception as exc:
                opportunity_search_module.logger.exception("[OPPORTUNITY ANALYSIS ERROR] uid=%s ticker=%s", uid, ticker)
                result = self._unavailable(instrument, self._field(instrument, "last_price", None), 0.0, f"Ошибка анализа: {exc}")
            results.append(result)
            if result_callback is not None:
                try:
                    result_callback(result, valid_index, total)
                except Exception:
                    opportunity_search_module.logger.exception("[OPPORTUNITY RESULT CALLBACK] ticker=%s", ticker)
            self._notify(progress_callback, f"Обработано: {ticker}", progress_base + progress_span, valid_index, total)
        self._notify(progress_callback, "Ранжирование возможностей", 97.0, valid_index, total)
        results.sort(key=lambda item: (item.decision not in {"BUY", "WAIT", "HOLD", "ADD", "REDUCE", "SELL"}, -item.opportunity_score))
        self._notify(progress_callback, "Сканирование завершено", 100.0, valid_index, total)
        self._provided_candles.clear()
        return results

    @staticmethod
    def _field(value: Any, name: str, default: Any = None) -> Any:
        if isinstance(value, dict):
            return value.get(name, default)
        return getattr(value, name, default)

    @staticmethod
    def _float_or_none(value: Any) -> float | None:
        try:
            return None if value in (None, "") else float(value)
        except Exception:
            return None

    @staticmethod
    def _unavailable(instrument: Any, price: float | None, quantity: float, reason: str) -> OpportunitySearchResult:
        display_status = f"ANALYSIS_UNAVAILABLE: {reason}" if reason else "ANALYSIS_UNAVAILABLE"
        opportunity_search_module.logger.warning("[OPPORTUNITY UNAVAILABLE] ticker=%s price=%s status=%s reason=%s", LiveOpportunitySearchService._field(instrument, "ticker", ""), price, "ANALYSIS_UNAVAILABLE", reason)
        return OpportunitySearchResult(str(LiveOpportunitySearchService._field(instrument, "uid", LiveOpportunitySearchService._field(instrument, "instrument_uid", ""))), str(LiveOpportunitySearchService._field(instrument, "ticker", "")), str(LiveOpportunitySearchService._field(instrument, "name", "")), price, None, None, 0.0, 0.0, None, display_status, "ANALYSIS_UNAVAILABLE", reason, quantity, 0.0)
