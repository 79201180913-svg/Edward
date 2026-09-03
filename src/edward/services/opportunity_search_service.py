from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from edward.services.account_service import AccountService
from edward.services.analysis_service import AnalysisService, Candle, StrategyResult
from edward.services.decision_engine import DecisionEngine, DecisionRequest, OpportunityContext, PortfolioContextData, PositionContextData, RiskContextData, Scenario, StrategyContextData
from edward.services.forecast_model_selection_service import ForecastModelSelectionService
from edward.services.instrument_catalog_service import InstrumentCatalogService
from edward.services.instrument_decision_context_service import InstrumentDecisionContextService
from edward.services.market_benchmark_resolver_v011 import MarketBenchmarkResolverV011
from edward.services.market_decision_context_service import MarketDecisionContextService
from edward.services.opportunity_canonical_analysis_adapter_v015 import CanonicalOpportunityAnalysisV015
from edward.services.opportunity_analysis_pipeline_v0821 import UnifiedOpportunityEngineV0821
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
    """Run Opportunity Search on the canonical v0.8.14 analysis runtime."""
    def __init__(self, client: Any, analysis_service: AnalysisService | None = None):
        self.client = client
        self.analysis = analysis_service or CanonicalOpportunityAnalysisV015
        self.opportunity_engine = UnifiedOpportunityEngineV0821()
        self.catalog = InstrumentCatalogService(client)
        self.instrument_context = InstrumentDecisionContextService()
        self.market_context = MarketDecisionContextService()
        self.portfolio_context = PortfolioDecisionContextService()
        self.market_context_runtime = self._build_market_context_runtime()

    def _build_market_context_runtime(self) -> Any | None:
        """Reuse the existing v0.11 benchmark/context runtime when supported by the client."""
        get_candles = getattr(self.client, "get_candles", None)
        get_indicatives = getattr(self.client, "get_indicatives", None)
        if not callable(get_candles) or not callable(get_indicatives):
            return None
        try:
            from edward.services.market_context_runtime_service_v011 import MarketContextRuntimeServiceV011
            return MarketContextRuntimeServiceV011(
                fetcher=get_candles,
                indicatives_fetcher=get_indicatives,
                find_instrument_fetcher=getattr(self.client, "find_instrument", None),
            )
        except Exception:
            logger.exception("[V015 MARKET CONTEXT] failed to initialize existing v0.11 runtime")
            return None

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
    def _kinds(instrument_kind: str) -> tuple[str, ...]:
        kind = str(instrument_kind or "SHARE").upper()
        return ("SHARE", "BOND", "ETF", "CURRENCY", "FUTURES", "OPTION") if kind == INSTRUMENT_KIND_ALL else (kind,)

    @staticmethod
    def _forecast_horizon(profile: str) -> int:
        return {"speculative": 5, "medium_term": 20, "long_term": 60}.get(str(profile), 20)

    @staticmethod
    def _forecast_maps(result: Any) -> tuple[tuple[tuple[int, float], ...], ...]:
        points = tuple(result.forecast.points)
        return (tuple((p.horizon_days, p.expected_price) for p in points), tuple((p.horizon_days, p.probability_up) for p in points), tuple((p.horizon_days, p.probability_down) for p in points), tuple((p.horizon_days, p.downside_price) for p in points), tuple((p.horizon_days, p.upside_price) for p in points))

    def _benchmark_context(self, instrument: Any, candles: list[Candle]) -> tuple[list[Candle] | None, str | None]:
        """Build the existing v0.11 point-in-time benchmark context and return its market candles."""
        # Some unit tests construct the service with __new__ and inject only the
        # collaborators needed for decision-branch testing. Benchmark context is
        # optional there, so a missing runtime must behave exactly like an
        # unsupported client rather than turning the analysis into an error.
        runtime = getattr(self, "market_context_runtime", None)
        if runtime is None:
            return None, None
        try:
            benchmark, snapshot = runtime.build(instrument_metadata=instrument, asset_candles=candles, as_of=max(item.timestamp for item in candles))
            benchmark_candles = tuple(getattr(runtime, "last_built_market_candles", ()) or ())
            benchmark_id = str(getattr(benchmark, "benchmark_id", None) or "") or None
            if not benchmark_candles:
                logger.info("[V015 MARKET CONTEXT] ticker=%s benchmark=%s status=%s candles=0", _field(instrument, "ticker", ""), benchmark_id, getattr(snapshot, "context_status", "UNAVAILABLE"))
                return None, benchmark_id
            logger.info("[V015 MARKET CONTEXT] ticker=%s benchmark=%s status=%s candles=%d", _field(instrument, "ticker", ""), benchmark_id, getattr(snapshot, "context_status", "UNAVAILABLE"), len(benchmark_candles))
            return list(benchmark_candles), benchmark_id
        except Exception:
            logger.exception("[V015 MARKET CONTEXT] ticker=%s failed", _field(instrument, "ticker", ""))
            return None, None

    def _evaluate_instrument(self, *, instrument: Any, profile: str, positions: Any, portfolio: Any, progress_callback: ProgressCallback | None = None, progress_base: float = 15.0, progress_span: float = 80.0, current: int = 0, total: int = 0) -> OpportunitySearchResult:
        uid = str(_field(instrument, "uid", _field(instrument, "instrument_uid", ""))); ticker = str(_field(instrument, "ticker", "")); name = str(_field(instrument, "name", "")); price = _float_or_none(_field(instrument, "last_price", None))
        position_context = self.portfolio_context.build(positions=positions, portfolio=portfolio, instrument_uid=uid) if positions is not None else _empty_portfolio()
        position_data = position_context.position; raw_portfolio = position_context.portfolio
        portfolio_data = PortfolioContextData(portfolio_value=raw_portfolio.portfolio_value, available_cash=raw_portfolio.available_cash, blocked_cash=raw_portfolio.blocked_cash, current_weight_pct=raw_portfolio.current_weight_pct, target_weight_pct=raw_portfolio.target_weight_pct, max_position_weight_pct=raw_portfolio.max_position_weight_pct, allows_buy=raw_portfolio.allows_buy and not position_data.is_open, allows_add=raw_portfolio.allows_add and position_data.is_open, available=raw_portfolio.available if account_id_or_none(positions, portfolio) else True)
        try:
            instrument_data = self.instrument_context.build(instrument, _field(instrument, "trading_status", None)); self._notify(progress_callback, f"Market Data: candles {ticker}", progress_base + progress_span * 0.08, current, total); candles = self._get_candles(uid)
            if len(candles) < 150: return self._unavailable(instrument, price, position_data.quantity, f"Недостаточно исторических данных: получено {len(candles)} свечей, требуется не менее 150.")
            benchmark_candles, benchmark_id = self._benchmark_context(instrument, candles)
            self._notify(progress_callback, f"Анализ стратегий: {ticker}", progress_base + progress_span * 0.28, current, total); analysis = self.analysis.analyze(instrument_uid=uid, ticker=ticker, candles=candles, profile=profile, instrument=instrument, benchmark_candles=benchmark_candles, benchmark_id=benchmark_id); selected = self._best_strategy(analysis.strategies); market = self.market_context.build(last_price=_field(instrument, "last_price", None), candles=candles, market_regime=analysis.market_regime)
            forecast = None; forecast_prices = forecast_up = forecast_down = forecast_low = forecast_high = (); self._notify(progress_callback, f"Прогноз цены: {ticker}", progress_base + progress_span * 0.44, current, total)
            if candles and all(isinstance(item, Candle) for item in candles):
                try:
                    selected_forecast = ForecastModelSelectionService.select_and_forecast(instrument_uid=uid, ticker=ticker, candles=candles); forecast = selected_forecast.forecast; forecast_prices, forecast_up, forecast_down, forecast_low, forecast_high = self._forecast_maps(selected_forecast)
                except Exception: logger.exception("[OPPORTUNITY FORECAST] uid=%s ticker=%s", uid, ticker)
            self._notify(progress_callback, f"Risk / Opportunity: {ticker}", progress_base + progress_span * 0.60, current, total)
            if selected is None:
                opportunity_context = OpportunityContext(0.0, False, False, False, False, True); strategy_context = StrategyContextData(strategy_name=None, strategy_score=0.0, quality_gate=False, available=True); risk_score = 0.0
            else:
                estimated_trade_value = max(0.0, portfolio_data.available_cash * 0.10) if not position_data.is_open and portfolio_data.available_cash is not None and price is not None else None; opportunity_engine = getattr(self, "opportunity_engine", None) or UnifiedOpportunityEngineV0821(); opportunity = opportunity_engine.evaluate(analysis, candles, selected, position_weight_pct=position_data.portfolio_weight_pct or portfolio_data.current_weight_pct, target_weight_pct=position_data.target_weight_pct or portfolio_data.target_weight_pct, max_position_weight_pct=portfolio_data.max_position_weight_pct, portfolio_available=portfolio_data.available, available_cash=portfolio_data.available_cash, estimated_trade_value=estimated_trade_value); opportunity_context = opportunity.context; risk = getattr(opportunity, "risk", None); risk_score = float(getattr(risk, "score", 0.0) or 0.0); strategy_context = StrategyContextData(strategy_name=selected.strategy, strategy_score=selected.score, walk_forward_score=selected.test_score, stability_score=selected.stability, confidence=analysis.confidence, quality_gate=selected.quality_gate, entry_signal=bool(selected.quality_gate and opportunity_context.entry_ok), quality_degraded=not selected.quality_gate, available=True)
            risk_context = RiskContextData(risk_gate=opportunity_context.risk_ok, critical_risk=opportunity_context.critical_risk, risk_score=risk_score, max_drawdown_pct=selected.max_drawdown_pct if selected else None, available=True); self._notify(progress_callback, f"Decision Engine: {ticker}", progress_base + progress_span * 0.72, current, total)
            scenario = Scenario.SINGLE_INSTRUMENT if position_data.is_open else Scenario.OPPORTUNITY_SEARCH
            request = DecisionRequest(scenario=scenario, instrument=instrument_data, strategy=strategy_context, market=market, position=PositionContextData(quantity=position_data.quantity, average_price=position_data.average_price, current_value=position_data.current_value, unrealized_pnl=position_data.unrealized_pnl, portfolio_weight_pct=position_data.portfolio_weight_pct, target_weight_pct=position_data.target_weight_pct, is_open=position_data.is_open), risk=risk_context, opportunity=opportunity_context, portfolio=portfolio_data)
            decision_result = DecisionEngine.evaluate(request)
            quantity = position_data.quantity
            if decision_result.decision in {Decision.BUY, Decision.ADD}: quantity = self._recommended_quantity(price, portfolio_data.available_cash, position_data)
            trade_plan = self._trade_plan(instrument, decision_result, quantity, price, position_data)
            recommended_quantity, recommended_value, recommended_weight_pct = self._position_size(price, portfolio_data, position_data, decision_result)
            return OpportunitySearchResult(instrument_uid=uid, ticker=ticker, name=name, price=price, market_regime=analysis.market_regime, strategy_name=getattr(selected, "strategy", None), strategy_score=float(getattr(selected, "score", 0.0) or 0.0), opportunity_score=float(getattr(opportunity_context, "opportunity_score", 0.0) or 0.0), decision=getattr(decision_result.decision, "value", decision_result.decision), status=getattr(decision_result.status, "value", decision_result.status), reason=",".join(getattr(code, "value", str(code)) for code in decision_result.reason_codes), explanation=str(getattr(decision_result, "explanation", "")), quantity=quantity, risk_score=risk_score, forecast_model=getattr(forecast, "model_name", None) if forecast else None, forecast_confidence=getattr(forecast, "confidence", None) if forecast else None, forecast_prices=forecast_prices, forecast_probability_up=forecast_up, forecast_probability_down=forecast_down, forecast_downside=forecast_low, forecast_upside=forecast_high, trade_plan=trade_plan, recommended_quantity=recommended_quantity, recommended_value=recommended_value, recommended_weight_pct=recommended_weight_pct, execution_ready=bool(getattr(decision_result, "execution_ready", False)), canonical_opportunity=getattr(analysis, "best_analysis", None))
        except Exception as exc:
            logger.exception("[OPPORTUNITY ANALYSIS ERROR] uid=%s ticker=%s", uid, ticker)
            return self._unavailable(instrument, price, position_data.quantity, f"Ошибка анализа: {exc}")

    def _get_candles(self, uid: str) -> list[Candle]:
        start = datetime(2000, 1, 1, tzinfo=timezone.utc); end = datetime.now(timezone.utc)
        try: return list(self.client.get_candles(uid, start, end, interval="CANDLE_INTERVAL_DAY", limit=2400) or [])
        except TypeError: return list(self.client.get_candles(uid, interval="CANDLE_INTERVAL_DAY", limit=2400) or [])

    def _active_account(self) -> str | None:
        try: return AccountService(self.client).get_active_account_id()
        except Exception: return None

    @staticmethod
    def _best_strategy(strategies: list[StrategyResult]) -> StrategyResult | None:
        return max(strategies, key=lambda item: (item.quality_gate, item.score)) if strategies else None

    @staticmethod
    def _recommended_quantity(price: float | None, available_cash: float | None, position: Any) -> float:
        if price is None or price <= 0 or available_cash is None or available_cash <= 0: return 0.0
        if getattr(position, "is_open", False): return float(getattr(position, "quantity", 0.0) or 0.0)
        return float(int((available_cash * 0.10) / price))

    def _position_size(self, price: float | None, portfolio: PortfolioContextData, position: Any, decision_result: Any) -> tuple[int, float, float]:
        if price is None or price <= 0 or not getattr(decision_result, "decision", None) in {Decision.BUY, Decision.ADD}: return 0, 0.0, float(getattr(position, "portfolio_weight_pct", 0.0) or 0.0)
        sizing = PositionSizingService().calculate(PositionSizingInput(available_cash=portfolio.available_cash or 0.0, price=price, target_weight_pct=portfolio.target_weight_pct, max_position_weight_pct=portfolio.max_position_weight_pct, current_weight_pct=getattr(position, "portfolio_weight_pct", 0.0) or 0.0, side="BUY"))
        return sizing.recommended_quantity, sizing.recommended_value, sizing.recommended_weight_pct

    def _trade_plan(self, instrument: Any, decision_result: Any, quantity: float, price: float | None, position: Any) -> Any | None:
        if decision_result.decision not in {Decision.BUY, Decision.ADD, Decision.REDUCE, Decision.SELL}: return None
        try: return TradePlanService().build(TradePlanInput(instrument_uid=_field(instrument, "uid", _field(instrument, "instrument_uid", "")), ticker=_field(instrument, "ticker", ""), side=decision_result.decision.value, quantity=quantity, price=price, reason=str(getattr(decision_result, "explanation", ""))))
        except Exception: logger.exception("[TRADE PLAN] failed"); return None

    @staticmethod
    def _unavailable(instrument: Any, price: float | None, quantity: float, reason: str) -> OpportunitySearchResult:
        return OpportunitySearchResult(instrument_uid=str(_field(instrument, "uid", _field(instrument, "instrument_uid", ""))), ticker=str(_field(instrument, "ticker", "")), name=str(_field(instrument, "name", "")), price=price, market_regime=None, strategy_name=None, strategy_score=0.0, opportunity_score=0.0, decision=None, status="ANALYSIS_UNAVAILABLE", reason=reason, explanation=reason, quantity=quantity)

def _field(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict): return obj.get(name, default)
    return getattr(obj, name, default)

def _bool_field(obj: Any, name: str, default: bool = False) -> bool:
    value = _field(obj, name, default); return bool(value)

def _float_or_none(value: Any) -> float | None:
    try: return None if value is None else float(value)
    except (TypeError, ValueError): return None

def _uid(item: Any) -> str:
    return str(_field(item, "uid", _field(item, "instrument_uid", _field(item, "figi", ""))) or "")

def _held_positions(positions: Any) -> list[Any]:
    if positions is None: return []
    if isinstance(positions, dict): return list(positions.get("securities") or positions.get("positions") or [])
    return list(getattr(positions, "securities", None) or getattr(positions, "positions", None) or [])

def _empty_portfolio() -> Any:
    return type("EmptyPortfolio", (), {"portfolio": PortfolioContextData(portfolio_value=None, available_cash=None, blocked_cash=None, current_weight_pct=0.0, target_weight_pct=None, max_position_weight_pct=None, allows_buy=True, allows_add=False, available=True), "position": PositionContextData(quantity=0.0, average_price=None, current_value=0.0, unrealized_pnl=0.0, portfolio_weight_pct=0.0, target_weight_pct=None, is_open=False)})()

def account_id_or_none(positions: Any, portfolio: Any) -> bool:
    return positions is not None or portfolio is not None
