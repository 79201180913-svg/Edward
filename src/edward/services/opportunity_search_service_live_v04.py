from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

import edward.services.opportunity_search_service as opportunity_search_module
from edward.config.application_settings import ApplicationSettingsStore
from edward.services.execution_readiness_service import ExecutionReadinessInput, ExecutionReadinessService
from edward.services.forecast_quality_gate_service import ForecastQualityGateService
from edward.services.forecast_walk_forward_service import ForecastWalkForwardService
from edward.services.opportunity_analysis_pipeline_v0821 import (
    OpportunityAnalysisPipelineV0821,
    UnifiedOpportunityEngineV0821,
)
from edward.services.opportunity_search_service import (
    MARKET_SCOPE,
    ProgressCallback,
    OpportunitySearchResult,
    OpportunitySearchService,
)
from edward.storage.sqlite_store import SQLiteStore

ResultCallback = Callable[[OpportunitySearchResult, int, int], None]


class _ProvidedAnalysisService:
    """Return a previously calculated analysis result without recalculating it."""

    def __init__(self, result: Any):
        self.result = result

    def analyze(self, **_kwargs: Any) -> Any:
        return self.result


class LiveOpportunitySearchService(OpportunitySearchService):
    """Opportunity search that streams results through the canonical v0.8.2 analysis."""

    def __init__(self, client: Any, *, force_recompute: bool = False):
        settings = ApplicationSettingsStore().load()
        store = SQLiteStore(settings.storage_path)
        self.force_recompute = force_recompute
        self.analysis_pipeline = OpportunityAnalysisPipelineV0821(
            client,
            cache_store=store,
            force_recompute=force_recompute,
        )
        super().__init__(client, analysis_service=self.analysis_pipeline)
        self._provided_candles: dict[str, list[Any]] = {}
        # Keep the existing OpportunitySearchService call graph intact while
        # making its OpportunityEngine consume the canonical v0.8.2 result.
        # The bridge falls back to the legacy engine for non-v0.8.2 callers.
        opportunity_search_module.OpportunityEngine = UnifiedOpportunityEngineV0821

    @property
    def cache_info(self) -> dict[str, int]:
        return self.analysis_pipeline.cache_info()

    def _get_candles(self, instrument_uid: str) -> list[Any]:
        cached = self._provided_candles.get(str(instrument_uid))
        if cached is not None:
            return cached
        return super()._get_candles(instrument_uid)

    @staticmethod
    def _enforce_execution_readiness(
        result: OpportunitySearchResult,
        *,
        forecast_quality_pass: bool = False,
        forecast_quality_label: str = "НЕ ПРОВЕРЕН",
    ) -> OpportunitySearchResult:
        decision = str(result.decision or "").upper()
        if decision not in {"BUY", "ADD", "HOLD", "REDUCE", "SELL"}:
            return result

        plan = getattr(result, "trade_plan", None)
        risk_reward = getattr(plan, "risk_reward", None) if plan is not None else None
        strategy_quality_pass = str(result.reason or "") not in {"STRATEGY_QUALITY_FAIL", "RISK_FAIL", "CRITICAL_RISK"}
        risk_reward_ok = decision not in {"BUY", "ADD"} or (risk_reward is not None and risk_reward > 0)
        position_size_ready = decision not in {"REDUCE", "SELL"} or int(getattr(result, "recommended_quantity", 0) or 0) > 0
        plan_ready = plan is not None

        gate = ExecutionReadinessService.evaluate(
            ExecutionReadinessInput(
                decision=decision,
                forecast_quality_pass=forecast_quality_pass,
                risk_ok=str(result.reason or "") not in {"RISK_FAIL", "CRITICAL_RISK"},
                portfolio_available=True,
                trading_status_ok=True,
                position_size_ready=position_size_ready,
                entry_ready=plan_ready,
                target_ready=plan_ready,
                stop_ready=plan_ready,
                liquidity_ok=True,
                strategy_quality_pass=strategy_quality_pass,
                risk_reward_ok=risk_reward_ok,
            )
        )

        readiness_text = "Исполнение: ДА" if gate.execution_ready else "Исполнение: НЕТ"
        gate_reason_text = " | ".join(gate.reasons) if gate.reasons else ""
        execution_parts = [
            str(result.reason or ""),
            *([gate_reason_text] if gate_reason_text else []),
            f"Контроль качества прогноза: {forecast_quality_label}",
            readiness_text,
        ]
        execution_explanation = " | ".join(part for part in execution_parts if part)
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

    @classmethod
    def _forecast_quality_gate(cls, service: OpportunitySearchService, instrument_uid: str, profile: str) -> tuple[bool, str]:
        decision_horizon = service._forecast_horizon(profile)
        candles = service._get_candles(instrument_uid)
        if len(candles) < 150:
            return False, "НЕ ПРОВЕРЕН: недостаточно истории"
        wf = ForecastWalkForwardService.validate(candles=candles, horizon=decision_horizon)
        gate = ForecastQualityGateService.evaluate(wf)
        return gate.passed, ("PASS" if gate.passed else "FAIL")

    def scan(
        self,
        *,
        profile: str = "medium_term",
        instrument_kind: str = "SHARE",
        scope: str = MARKET_SCOPE,
        progress_callback: ProgressCallback | None = None,
        result_callback: ResultCallback | None = None,
        force_recompute: bool = False,
    ) -> list[OpportunitySearchResult]:
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
        scope_title = "торговых инструментов" if scope == "MARKET" else "позиций портфеля"
        self._notify(progress_callback, f"Вселенная анализа: {total} {scope_title}", 8.0, 0, total)
        self._notify(progress_callback, "Portfolio Context загружается", 11.0, 0, total)
        self._notify(progress_callback, "Portfolio Context загружен", 14.0, 0, total)

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

            # Calculate the canonical analysis exactly once, then hand that
            # result to the existing OpportunitySearch decision flow.
            candles = super()._get_candles(uid)
            self._provided_candles[uid] = candles
            self._notify(progress_callback, f"Анализ стратегий: {ticker}", progress_base + progress_span * 0.28, valid_index, total)
            analysis_result = self.analysis_pipeline.analyze(
                instrument_uid=uid,
                ticker=ticker,
                candles=candles,
                profile=profile,
                instrument=instrument,
            )
            previous_analysis = self.analysis
            self.analysis = _ProvidedAnalysisService(analysis_result)
            try:
                result = self._evaluate_instrument(
                    instrument=instrument,
                    profile=profile,
                    positions=positions,
                    portfolio=portfolio,
                    progress_callback=progress_callback,
                    progress_base=progress_base,
                    progress_span=progress_span,
                    current=valid_index,
                    total=total,
                )
            finally:
                self.analysis = previous_analysis

            forecast_quality_pass = False
            forecast_quality_label = "НЕ ПРИМЕНИМ"
            if result.decision in {"BUY", "ADD", "HOLD", "REDUCE", "SELL"}:
                forecast_quality_label = "НЕ ПРОВЕРЕН"
                try:
                    self._notify(progress_callback, f"Контроль качества прогноза: {ticker}", progress_base + progress_span * 0.91, valid_index, total)
                    forecast_quality_pass, forecast_quality_label = self._forecast_quality_gate(self, uid, profile)
                except Exception:
                    forecast_quality_pass = False
                    forecast_quality_label = "FAIL"

            result = self._enforce_execution_readiness(
                result,
                forecast_quality_pass=forecast_quality_pass,
                forecast_quality_label=forecast_quality_label,
            )
            results.append(result)
            if result_callback is not None:
                try:
                    result_callback(result, valid_index, total)
                except Exception:
                    pass
            self._notify(progress_callback, f"Обработано: {ticker}", progress_base + progress_span, valid_index, total)

        self._notify(progress_callback, "Ранжирование возможностей", 97.0, valid_index, total)
        results = sorted(
            results,
            key=lambda item: (
                item.decision not in {"BUY", "WAIT", "HOLD", "ADD", "REDUCE", "SELL"},
                item.decision not in {"BUY", "ADD", "REDUCE", "SELL", "HOLD"},
                -item.opportunity_score,
            ),
        )
        self._notify(progress_callback, "Сканирование завершено", 100.0, valid_index, total)
        self._provided_candles.clear()
        return results

    @staticmethod
    def _field(value: Any, name: str, default: Any = None) -> Any:
        if isinstance(value, dict):
            return value.get(name, default)
        return getattr(value, name, default)
