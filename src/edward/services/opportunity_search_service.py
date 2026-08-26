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
from edward.services.opportunity_engine import OpportunityEngine
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


class OpportunitySearchService:
    """Run the v0.4/v0.5 decision pipeline over a deliberately bounded instrument universe."""

    def __init__(self, client: Any, analysis_service: AnalysisService | None = None):
        self.client = client
        self.analysis = analysis_service or AnalysisService()
        self.catalog = InstrumentCatalogService(client)
        self.instrument_context = InstrumentDecisionContextService()
        self.market_context = MarketDecisionContextService()
        self.portfolio_context = PortfolioDecisionContextService()

    @staticmethod
    def _notify(progress_callback: ProgressCallback | None, stage: str, percent: float, current: int, total: int) -> None:
        if progress_callback is None:
            return
        try:
            progress_callback(stage, round(max(0.0, min(100.0, percent)), 1), current, total)
        except Exception:
            pass

    def scan(self, *, profile: str = "medium_term", instrument_kind: str = "SHARE", scope: str = MARKET_SCOPE, progress_callback: ProgressCallback | None = None, result_callback: Callable[[OpportunitySearchResult, int, int], None] | None = None, force_recompute: bool = False) -> list[OpportunitySearchResult]:
        scope = str(scope or MARKET_SCOPE).upper()
        if scope not in SUPPORTED_SCOPES:
            raise ValueError(f"Unsupported opportunity scope: {scope}")
        self._notify(progress_callback, "Загрузка списка инструментов", 2.0, 0, 0)
        account_id = self._active_account()
        positions = self.client.get_positions(account_id) if account_id else None
        portfolio = self.client.get_portfolio(account_id) if account_id else None
        instruments = self._build_universe(scope=scope, instrument_kind=instrument_kind, positions=positions)
        total = len(instruments)
        scope_title = "торговых инструментов" if scope == MARKET_SCOPE else "позиций портфеля"
        self._notify(progress_callback, f"Вселенная анализа: {total} {scope_title}", 8.0, 0, total)
        self._notify(progress_callback, "Portfolio Context загружается", 11.0, 0, total)
        self._notify(progress_callback, "Portfolio Context загружен", 14.0, 0, total)
        results: list[OpportunitySearchResult] = []
        valid_index = 0
        for instrument in instruments:
            uid = str(_field(instrument, "uid", _field(instrument, "instrument_uid", "")))
            if not uid:
                continue
            valid_index += 1
            progress_base = 15.0 + ((valid_index - 1) / max(1, total)) * 80.0
            progress_span = 80.0 / max(1, total)
            ticker = str(_field(instrument, "ticker", ""))
            self._notify(progress_callback, f"Market Data: {ticker}", progress_base, valid_index, total)
            result = self._evaluate_instrument(instrument=instrument, profile=profile, positions=positions, portfolio=portfolio, progress_callback=progress_callback, progress_base=progress_base, progress_span=progress_span, current=valid_index, total=total)
            results.append(result)
            if result_callback is not None:
                try:
                    result_callback(result, valid_index, total)
                except Exception:
                    logger.exception("[OPPORTUNITY RESULT CALLBACK] ticker=%s", ticker)
            self._notify(progress_callback, f"Обработано: {ticker}", progress_base + progress_span, valid_index, total)
        self._notify(progress_callback, "Ранжирование возможностей", 97.0, valid_index, total)
        results = sorted(results, key=lambda item: (item.decision not in {"BUY", "WAIT", "HOLD", "ADD", "REDUCE", "SELL"}, item.decision not in {"BUY", "ADD", "REDUCE", "SELL", "HOLD"}, -item.opportunity_score))
        self._notify(progress_callback, "Сканирование завершено", 100.0, valid_index, total)
        return results

    def _build_universe(self, *, scope: str, instrument_kind: str, positions: Any) -> list[Any]:
        return self._market_universe(instrument_kind, positions) if scope == MARKET_SCOPE else self._portfolio_universe(instrument_kind, positions)

    def _market_universe(self, instrument_kind: str, positions: Any = None) -> list[Any]:
        held_uids = {_uid(item) for item in _held_positions(positions) if _uid(item)}
        result: list[Any] = []
        seen: set[str] = set()
        for kind in self._kinds(instrument_kind):
            for instrument in self.catalog.list(kind, trade_available_only=True):
                uid = _uid(instrument)
                if not uid or uid in seen or uid in held_uids:
                    continue
                if not _bool_field(instrument, "buy_available", False) or not _bool_field(instrument, "trading_available", False):
                    continue
                seen.add(uid)
                result.append(instrument)
        return result

    def _portfolio_universe(self, instrument_kind: str, positions: Any) -> list[Any]:
        held = _held_positions(positions)
        if not held:
            return []
        held_uids = {_uid(item) for item in held if _uid(item)}
        catalog_items: dict[str, Any] = {}
        for kind in self._kinds(instrument_kind):
            for instrument in self.catalog.list(kind, trade_available_only=False):
                uid = _uid(instrument)
                if uid in held_uids:
                    catalog_items[uid] = instrument
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
        return (
            tuple((p.horizon_days, p.expected_price) for p in points),
            tuple((p.horizon_days, p.probability_up) for p in points),
            tuple((p.horizon_days, p.probability_down) for p in points),
            tuple((p.horizon_days, p.downside_price) for p in points),
            tuple((p.horizon_days, p.upside_price) for p in points),
        )

    def _evaluate_instrument(self, *, instrument: Any, profile: str, positions: Any, portfolio: Any, progress_callback: ProgressCallback | None = None, progress_base: float = 15.0, progress_span: float = 80.0, current: int = 0, total: int = 0) -> OpportunitySearchResult:
        uid = str(_field(instrument, "uid", _field(instrument, "instrument_uid", "")))
        ticker = str(_field(instrument, "ticker", ""))
        name = str(_field(instrument, "name", ""))
        price = _float_or_none(_field(instrument, "last_price", None))
        position_context = self.portfolio_context.build(positions=positions, portfolio=portfolio, instrument_uid=uid) if positions is not None else _empty_portfolio()
        position_data = position_context.position
        raw_portfolio = position_context.portfolio
        portfolio_data = PortfolioContextData(
            portfolio_value=raw_portfolio.portfolio_value,
            available_cash=raw_portfolio.available_cash,
            blocked_cash=raw_portfolio.blocked_cash,
            current_weight_pct=raw_portfolio.current_weight_pct,
            target_weight_pct=raw_portfolio.target_weight_pct,
            max_position_weight_pct=raw_portfolio.max_position_weight_pct,
            allows_buy=raw_portfolio.allows_buy and not position_data.is_open,
            allows_add=raw_portfolio.allows_add and position_data.is_open,
            available=raw_portfolio.available if account_id_or_none(positions, portfolio) else True,
        )
        try:
            instrument_data = self.instrument_context.build(instrument, _field(instrument, "trading_status", None))
            self._notify(progress_callback, f"Market Data: candles {ticker}", progress_base + progress_span * 0.08, current, total)
            candles = self._get_candles(uid)
            if len(candles) < 150:
                reason = f"Недостаточно исторических данных: получено {len(candles)} свечей, требуется не менее 150."
                logger.warning("[OPPORTUNITY CANDLES] uid=%s ticker=%s count=%d", uid, ticker, len(candles))
                return self._unavailable(instrument, price, position_data.quantity, reason)

            self._notify(progress_callback, f"Анализ стратегий: {ticker}", progress_base + progress_span * 0.28, current, total)
            analysis = self.analysis.analyze(instrument_uid=uid, ticker=ticker, candles=candles, profile=profile)
            selected = self._best_strategy(analysis.strategies)
            market = self.market_context.build(last_price=_field(instrument, "last_price", None), candles=candles, market_regime=analysis.market_regime)

            forecast = None
            forecast_prices = forecast_up = forecast_down = forecast_low = forecast_high = ()
            self._notify(progress_callback, f"Прогноз цены: {ticker}", progress_base + progress_span * 0.44, current, total)
            if candles and all(isinstance(item, Candle) for item in candles):
                try:
                    selected_forecast = ForecastModelSelectionService.select_and_forecast(instrument_uid=uid, ticker=ticker, candles=candles)
                    forecast = selected_forecast.forecast
                    forecast_prices, forecast_up, forecast_down, forecast_low, forecast_high = self._forecast_maps(selected_forecast)
                except Exception:
                    logger.exception("[OPPORTUNITY FORECAST] uid=%s ticker=%s", uid, ticker)
            else:
                logger.debug("[OPPORTUNITY FORECAST] skipped incompatible candle objects uid=%s ticker=%s", uid, ticker)

            self._notify(progress_callback, f"Risk / Opportunity: {ticker}", progress_base + progress_span * 0.60, current, total)
            if selected is None:
                opportunity_context = OpportunityContext(0.0, False, False, False, False, True)
                strategy_context = StrategyContextData(strategy_name=None, strategy_score=0.0, quality_gate=False, available=True)
                risk_score = 0.0
            else:
                estimated_trade_value = None
                if not position_data.is_open and portfolio_data.available_cash is not None and price is not None:
                    estimated_trade_value = max(0.0, portfolio_data.available_cash * 0.10)
                opportunity = OpportunityEngine.evaluate(analysis, candles, selected, position_weight_pct=position_data.portfolio_weight_pct or portfolio_data.current_weight_pct, target_weight_pct=position_data.target_weight_pct or portfolio_data.target_weight_pct, max_position_weight_pct=portfolio_data.max_position_weight_pct, portfolio_available=portfolio_data.available, available_cash=portfolio_data.available_cash, estimated_trade_value=estimated_trade_value)
                opportunity_context = opportunity.context
                risk = getattr(opportunity, "risk", None)
                risk_score = float(getattr(risk, "score", 0.0) or 0.0)
                strategy_context = StrategyContextData(strategy_name=selected.strategy, strategy_score=selected.score, walk_forward_score=selected.test_score, stability_score=selected.stability, confidence=analysis.confidence, quality_gate=selected.quality_gate, entry_signal=bool(selected.quality_gate and opportunity_context.entry_ok), quality_degraded=not selected.quality_gate, available=True)
            risk_context = RiskContextData(risk_gate=opportunity_context.risk_ok, critical_risk=opportunity_context.critical_risk, risk_score=risk_score, max_drawdown_pct=selected.max_drawdown_pct if selected else None, available=True)
            self._notify(progress_callback, f"Decision Engine: {ticker}", progress_base + progress_span * 0.78, current, total)
            request = DecisionRequest(
                scenario=Scenario.SINGLE_INSTRUMENT if position_data.is_open else Scenario.OPPORTUNITY_SEARCH,
                instrument=instrument_data,
                market=market,
                strategy=strategy_context,
                risk=risk_context,
                position=position_data,
                portfolio=portfolio_data,
                opportunity=opportunity_context,
                portfolio_allows_buy=portfolio_data.allows_buy,
                portfolio_allows_add=portfolio_data.allows_add,
                market_data_available=market.available,
                strategy_analysis_available=True,
                risk_analysis_available=True,
                portfolio_context_available=(not position_data.is_open) or portfolio_data.available,
                instrument_available=instrument_data.available,
                profile=profile,
            )
            decision = DecisionEngine.evaluate(request)
            decision_value = decision.decision.value if decision.decision else None

            trade_plan = None
            recommended_quantity = 0
            recommended_value = 0.0
            recommended_weight_pct = 0.0
            execution_ready = False
            horizon = self._forecast_horizon(profile)
            if forecast is not None:
                try:
                    plan_action = decision_value if decision_value in {"BUY", "ADD", "HOLD", "REDUCE", "SELL"} else "HOLD"
                    fp = forecast.point(horizon)
                    trade_plan = TradePlanService.build(TradePlanInput(action=plan_action, forecast=fp, confidence=fp.confidence, holding_horizon_days=horizon, entry_price=market.current_price or price, position_weight_pct=position_data.portfolio_weight_pct, target_weight_pct=position_data.target_weight_pct, max_position_weight_pct=portfolio_data.max_position_weight_pct or 10.0))
                    if portfolio_data.portfolio_value and (market.current_price or price) and trade_plan.stop_price:
                        sizing = PositionSizingService.calculate(PositionSizingInput(action=plan_action, portfolio_value=float(portfolio_data.portfolio_value), current_price=float(market.current_price or price), stop_price=float(trade_plan.stop_price), risk_per_trade_pct=1.0, max_position_weight_pct=float(portfolio_data.max_position_weight_pct or 10.0), available_cash=float(portfolio_data.available_cash or 0.0), current_quantity=int(position_data.quantity or 0), current_weight_pct=float(position_data.portfolio_weight_pct or 0.0), lot_size=1))
                        recommended_quantity = sizing.recommended_quantity
                        recommended_value = sizing.recommended_value
                        recommended_weight_pct = sizing.recommended_weight_pct
                    execution_ready = bool(decision_value in {"BUY", "ADD", "HOLD", "REDUCE", "SELL"} and trade_plan is not None and (decision.status.value == "VALID" if hasattr(decision.status, "value") else True))
                except Exception:
                    logger.exception("[OPPORTUNITY TRADE PLAN] uid=%s ticker=%s", uid, ticker)

            reason = decision.reason_codes[0] if decision.reason_codes else ""
            return OpportunitySearchResult(uid, ticker, name, market.current_price if market.current_price is not None else price, analysis.market_regime, decision.strategy_name, decision.strategy_score, decision.opportunity_score, decision_value, decision.status.value, reason, decision.explanation, position_data.quantity, risk_score, forecast.model if forecast is not None else None, forecast.confidence if forecast is not None else None, forecast_prices, forecast_up, forecast_down, forecast_low, forecast_high, trade_plan, recommended_quantity, recommended_value, recommended_weight_pct, execution_ready)
        except Exception as exc:
            logger.exception("[OPPORTUNITY ANALYSIS ERROR] uid=%s ticker=%s", uid, ticker)
            return self._unavailable(instrument, price, position_data.quantity, f"Ошибка анализа: {exc}")

    @staticmethod
    def _best_strategy(strategies: list[StrategyResult]) -> StrategyResult | None:
        if not strategies:
            return None
        passing = [item for item in strategies if item.quality_gate]
        return max(passing or strategies, key=lambda item: item.score)

    def _get_candles(self, instrument_uid: str) -> list[Candle]:
        payload: Any = None
        try:
            payload = self.client.get_candles(instrument_uid, interval="CANDLE_INTERVAL_DAY", limit=2400)
        except TypeError:
            payload = self.client.get_candles(instrument_uid, interval="CANDLE_INTERVAL_DAY", days=2400)

        def extract_items(value: Any) -> list[Any]:
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                items = value.get("candles")
                if items is None:
                    items = value.get("data")
                if isinstance(items, dict):
                    items = items.get("candles", [])
                return items if isinstance(items, list) else []
            items = getattr(value, "candles", None)
            if items is None:
                items = getattr(value, "data", None)
            if isinstance(items, dict):
                items = items.get("candles", [])
            return list(items) if items is not None and not isinstance(items, (str, bytes)) else []

        items = extract_items(payload)
        logger.info("[OPPORTUNITY CANDLES] uid=%s response_type=%s initial_count=%d", instrument_uid, type(payload).__name__, len(items))
        if len(items) < 150:
            logger.info("[OPPORTUNITY CANDLES] uid=%s initial_count=%d; retrying with explicit limit", instrument_uid, len(items))
            try:
                retry = self.client.get_candles(instrument_uid, interval="CANDLE_INTERVAL_DAY", limit=2400, days=2400)
                retry_items = extract_items(retry)
                if len(retry_items) > len(items):
                    items = retry_items
            except TypeError:
                pass

        result: list[Candle] = []
        for item in items:
            timestamp = _field(item, "time", _field(item, "timestamp", None))
            if timestamp is None:
                continue
            try:
                result.append(Candle(timestamp=_parse_timestamp(timestamp), open=_number(_field(item, "open", 0)), high=_number(_field(item, "high", 0)), low=_number(_field(item, "low", 0)), close=_number(_field(item, "close", 0)), volume=_number(_field(item, "volume", 0))))
            except (TypeError, ValueError, OverflowError):
                continue
        logger.info("[OPPORTUNITY CANDLES] uid=%s final_count=%d", instrument_uid, len(result))
        return result

    def _active_account(self) -> str | None:
        try:
            accounts = self.client.get_accounts()
            items = accounts if isinstance(accounts, list) else _field(accounts, "accounts", []) or []
            active = next((item for item in items if AccountService.is_open(item)), None)
            return str(_field(active, "id", "")) if active else None
        except Exception:
            return None

    @staticmethod
    def _unavailable(instrument: Any, price: float | None, quantity: float, reason: str) -> OpportunitySearchResult:
        return OpportunitySearchResult(str(_field(instrument, "uid", _field(instrument, "instrument_uid", ""))), str(_field(instrument, "ticker", "")), str(_field(instrument, "name", "")), price, None, None, 0.0, 0.0, None, "ANALYSIS_UNAVAILABLE", "ANALYSIS_UNAVAILABLE", reason, quantity, 0.0)


def _held_positions(positions: Any) -> list[Any]:
    raw = _field(positions, "securities", []) if positions is not None else []
    return [item for item in (raw or []) if abs(_number(_field(item, "balance", _field(item, "quantity", 0)))) > 0]


def _empty_portfolio():
    from edward.services.portfolio_decision_context_service import PortfolioDecisionContext
    return PortfolioDecisionContext(portfolio=PortfolioContextData(available=False), position=PositionContextData())


def account_id_or_none(positions: Any, portfolio: Any) -> bool:
    return positions is not None and portfolio is not None


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _uid(value: Any) -> str:
    return str(_field(value, "uid", _field(value, "instrument_uid", "")))


def _bool_field(value: Any, name: str, default: bool = False) -> bool:
    raw = _field(value, name, default)
    if isinstance(raw, str):
        return raw.strip().casefold() in {"true", "1", "yes", "да"}
    return bool(raw)


def _number(value: Any) -> float:
    if isinstance(value, dict):
        return float(value.get("units", 0)) + float(value.get("nano", value.get("nanos", 0))) / 1_000_000_000
    units = getattr(value, "units", None)
    nano = getattr(value, "nano", getattr(value, "nanos", None))
    if units is not None or nano is not None:
        return float(units or 0) + float(nano or 0) / 1_000_000_000
    try:
        return float(value)
    except Exception:
        return 0.0


def _float_or_none(value: Any) -> float | None:
    try:
        return None if value in (None, "") else _number(value)
    except Exception:
        return None


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, dict):
        seconds = int(value.get("seconds", 0) or 0)
        nanos = int(value.get("nanos", value.get("nano", 0)) or 0)
        return datetime.fromtimestamp(seconds + nanos / 1_000_000_000, tz=timezone.utc)
    seconds = getattr(value, "seconds", None)
    nanos = getattr(value, "nanos", getattr(value, "nano", None))
    if seconds is not None or nanos is not None:
        return datetime.fromtimestamp(float(seconds or 0) + float(nanos or 0) / 1_000_000_000, tz=timezone.utc)
    text = str(value or "")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
