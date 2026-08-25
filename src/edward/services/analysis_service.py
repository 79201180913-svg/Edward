from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from math import sqrt
from statistics import mean, pstdev
from typing import Any, Callable, Iterable

from edward.storage.sqlite_store import SQLiteStore


ANALYSIS_VERSION = "0.4.0"


@dataclass(frozen=True, slots=True)
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass(frozen=True, slots=True)
class StrategyResult:
    strategy: str
    parameters: dict[str, Any]
    return_pct: float
    max_drawdown_pct: float
    sharpe: float
    trades: int
    stability: float
    quality_gate: bool
    score: float
    train_score: float = 0.0
    test_score: float = 0.0


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    instrument_uid: str
    ticker: str
    profile: str
    risk_profile: str
    horizon: str
    market_regime: str
    recommendation: str | None
    confidence: str
    score: float
    strategies: list[StrategyResult]
    explanation: str
    created_at: str
    analysis_version: str = ANALYSIS_VERSION


class AnalysisService:
    """Beta stock-analysis engine.

    The service intentionally keeps the strategy layer replaceable. It uses only
    standard-library calculations so the first beta does not add numerical
    package dependencies to Edward.
    """

    STRATEGIES = ("Trend Following", "Momentum", "Breakout", "Mean Reversion")
    PROFILES = ("long_term", "medium_term", "speculative")

    PROFILE_PARAMS = {
        "long_term": {
            "train": 360,
            "test": 90,
            "min_trades": 4,
            "max_drawdown_pct": 30.0,
            "min_stability_pct": 60.0,
            "return_target_pct": 30.0,
        },
        "medium_term": {
            "train": 240,
            "test": 60,
            "min_trades": 5,
            "max_drawdown_pct": 25.0,
            "min_stability_pct": 60.0,
            "return_target_pct": 15.0,
        },
        "speculative": {
            "train": 120,
            "test": 30,
            "min_trades": 8,
            "max_drawdown_pct": 35.0,
            "min_stability_pct": 55.0,
            "return_target_pct": 8.0,
        },
    }

    def __init__(self, store: SQLiteStore | None = None):
        self.store = store

    @staticmethod
    def _close(c: Candle) -> float:
        return float(c.close)

    @staticmethod
    def _returns(candles: list[Candle]) -> list[float]:
        result: list[float] = []
        for previous, current in zip(candles, candles[1:]):
            if previous.close:
                result.append(current.close / previous.close - 1.0)
        return result

    @staticmethod
    def _max_drawdown(equity: list[float]) -> float:
        peak = equity[0] if equity else 1.0
        max_dd = 0.0
        for value in equity:
            peak = max(peak, value)
            if peak:
                max_dd = max(max_dd, (peak - value) / peak)
        return max_dd

    @staticmethod
    def _sharpe(returns: list[float]) -> float:
        if len(returns) < 2:
            return 0.0
        deviation = pstdev(returns)
        if deviation == 0:
            return 0.0
        return mean(returns) / deviation * sqrt(252.0)

    @staticmethod
    def _sma(values: list[float], period: int) -> float:
        if len(values) < period:
            return mean(values) if values else 0.0
        return mean(values[-period:])

    @classmethod
    def _profile_params(cls, profile: str) -> dict[str, Any]:
        if profile not in cls.PROFILE_PARAMS:
            raise ValueError(f"Unsupported profile: {profile}")
        return dict(cls.PROFILE_PARAMS[profile])

    @classmethod
    def market_regime(cls, candles: list[Candle]) -> str:
        if len(candles) < 30:
            return "Unclear"
        closes = [c.close for c in candles]
        fast = cls._sma(closes, 20)
        slow = cls._sma(closes, 50) if len(closes) >= 50 else cls._sma(closes, 30)
        recent = closes[-1]
        returns = cls._returns(candles[-30:])
        volatility = pstdev(returns) if len(returns) > 1 else 0.0
        if fast > slow * 1.005 and recent > fast:
            return "Trend"
        if volatility > 0.02 and abs(recent / slow - 1.0) < 0.03:
            return "Momentum"
        if abs(recent / slow - 1.0) < 0.015:
            return "Range"
        return "Unclear"

    @staticmethod
    def _signal(strategy: str, candles: list[Candle], parameters: dict[str, int], index: int) -> bool:
        closes = [c.close for c in candles[: index + 1]]
        if strategy == "Trend Following":
            fast = parameters["fast"]
            slow = parameters["slow"]
            return len(closes) >= slow and AnalysisService._sma(closes, fast) > AnalysisService._sma(closes, slow)
        if strategy == "Momentum":
            lookback = parameters["lookback"]
            return len(closes) > lookback and closes[-1] > closes[-1 - lookback]
        if strategy == "Breakout":
            lookback = parameters["lookback"]
            if len(closes) <= lookback:
                return False
            return closes[-1] >= max(closes[-1 - lookback:-1])
        if strategy == "Mean Reversion":
            lookback = parameters["lookback"]
            if len(closes) < lookback:
                return False
            avg = AnalysisService._sma(closes, lookback)
            return closes[-1] < avg * (1.0 - parameters["deviation"] / 100.0)
        return False

    @classmethod
    def backtest(cls, candles: list[Candle], strategy: str, parameters: dict[str, Any]) -> StrategyResult:
        if len(candles) < 10:
            return StrategyResult(strategy, parameters, 0.0, 0.0, 0.0, 0, 0.0, False, 0.0)
        equity = [1.0]
        trade_returns: list[float] = []
        in_position = False
        entry = 0.0
        for i in range(1, len(candles)):
            signal = cls._signal(strategy, candles, parameters, i - 1)
            if signal and not in_position:
                entry = candles[i].open
                in_position = True
            elif not signal and in_position:
                if entry:
                    trade_returns.append(candles[i].open / entry - 1.0)
                in_position = False
            daily = 0.0
            if in_position and candles[i - 1].close:
                daily = candles[i].close / candles[i - 1].close - 1.0
            equity.append(equity[-1] * (1.0 + daily))
        if in_position and entry:
            trade_returns.append(candles[-1].close / entry - 1.0)
        total_return = equity[-1] - 1.0
        market_returns = cls._returns(candles)
        strategy_returns = []
        for i in range(1, len(candles)):
            strategy_returns.append(market_returns[i - 1] if cls._signal(strategy, candles, parameters, i - 1) else 0.0)
        dd = cls._max_drawdown(equity)
        sharpe = cls._sharpe(strategy_returns)
        trades = len(trade_returns)
        positive = sum(1 for value in trade_returns if value > 0)
        stability = positive / trades if trades else 0.0
        quality = total_return > 0 and dd <= 0.35 and trades >= 3 and stability >= 0.45
        score = cls._score(total_return * 100.0, dd * 100.0, sharpe, trades, stability * 100.0)
        return StrategyResult(strategy, dict(parameters), total_return * 100, dd * 100, sharpe, trades, stability * 100, quality, score)

    @staticmethod
    def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
        return max(minimum, min(maximum, value))

    @classmethod
    def _score(
        cls,
        return_pct: float,
        drawdown_pct: float,
        sharpe: float,
        trades: int,
        stability_pct: float,
        *,
        return_target_pct: float = 15.0,
        drawdown_limit_pct: float = 25.0,
    ) -> float:
        """Score a strategy using normalized return, risk, Sharpe and stability."""
        return_score = cls._clamp(return_pct / return_target_pct * 100.0) if return_target_pct > 0 else 0.0
        sharpe_score = cls._clamp(sharpe / 2.0 * 100.0)
        drawdown_score = cls._clamp((1.0 - drawdown_pct / drawdown_limit_pct) * 100.0) if drawdown_limit_pct > 0 else 0.0
        stability_score = cls._clamp(stability_pct)

        return round(
            return_score * 0.30
            + sharpe_score * 0.25
            + drawdown_score * 0.25
            + stability_score * 0.20,
            2,
        )

    @classmethod
    def parameter_grid(cls, strategy: str, profile: str) -> list[dict[str, Any]]:
        if strategy == "Trend Following":
            return [{"fast": fast, "slow": slow} for fast, slow in ((10, 30), (20, 50), (30, 90))]
        if strategy == "Momentum":
            return [{"lookback": value} for value in ((10, 20, 40) if profile != "long_term" else (20, 40, 80))]
        if strategy == "Breakout":
            return [{"lookback": value} for value in ((10, 20, 40) if profile == "speculative" else (20, 40, 80))]
        return [{"lookback": value, "deviation": deviation} for value in (10, 20, 40) for deviation in (1.5, 2.0, 3.0)]

    @classmethod
    def walk_forward(cls, candles: list[Candle], strategy: str, profile: str) -> StrategyResult:
        cfg = cls._profile_params(profile)
        train_size = cfg["train"]
        test_size = cfg["test"]
        max_drawdown_pct = cfg["max_drawdown_pct"]
        min_stability_pct = cfg["min_stability_pct"]
        return_target_pct = cfg["return_target_pct"]
        windows: list[StrategyResult] = []
        start = 0

        while start + train_size + test_size <= len(candles):
            train = candles[start:start + train_size]
            test = candles[start + train_size:start + train_size + test_size]
            candidates = [cls.backtest(train, strategy, params) for params in cls.parameter_grid(strategy, profile)]
            best = max(candidates, key=lambda item: item.score)
            tested = cls.backtest(test, strategy, best.parameters)
            windows.append(
                StrategyResult(
                    strategy,
                    best.parameters,
                    tested.return_pct,
                    tested.max_drawdown_pct,
                    tested.sharpe,
                    tested.trades,
                    tested.stability,
                    tested.quality_gate,
                    tested.score,
                    best.score,
                    tested.score,
                )
            )
            start += test_size

        window_count = len(windows)
        if window_count < 5:
            return StrategyResult(
                strategy,
                cls.parameter_grid(strategy, profile)[0],
                mean(item.return_pct for item in windows) if windows else 0.0,
                mean(item.max_drawdown_pct for item in windows) if windows else 0.0,
                mean(item.sharpe for item in windows) if windows else 0.0,
                sum(item.trades for item in windows),
                0.0,
                False,
                0.0,
                mean(item.train_score for item in windows) if windows else 0.0,
                mean(item.test_score for item in windows) if windows else 0.0,
            )

        positive_return_windows = sum(1 for item in windows if item.return_pct > 0)
        risk_ok_windows = sum(1 for item in windows if item.max_drawdown_pct <= max_drawdown_pct)
        positive_sharpe_windows = sum(1 for item in windows if item.sharpe > 0)

        return_consistency = positive_return_windows / window_count * 100.0
        risk_consistency = risk_ok_windows / window_count * 100.0
        sharpe_consistency = positive_sharpe_windows / window_count * 100.0
        stability = round(
            return_consistency * 0.50
            + risk_consistency * 0.30
            + sharpe_consistency * 0.20,
            2,
        )

        avg_return = mean(item.return_pct for item in windows)
        avg_dd = mean(item.max_drawdown_pct for item in windows)
        avg_sharpe = mean(item.sharpe for item in windows)
        avg_trades = sum(item.trades for item in windows)
        avg_train_score = mean(item.train_score for item in windows)
        avg_test_score = mean(item.test_score for item in windows)
        score = cls._score(
            avg_return,
            avg_dd,
            avg_sharpe,
            avg_trades,
            stability,
            return_target_pct=return_target_pct,
            drawdown_limit_pct=max_drawdown_pct,
        )

        quality = (
            window_count >= 5
            and return_consistency >= 60.0
            and stability >= min_stability_pct
            and avg_return > 0.0
            and avg_dd <= max_drawdown_pct
            and avg_sharpe > 0.0
        )

        representative = max(windows, key=lambda item: item.test_score)
        return StrategyResult(
            strategy,
            representative.parameters,
            avg_return,
            avg_dd,
            avg_sharpe,
            avg_trades,
            stability,
            quality,
            score,
            avg_train_score,
            avg_test_score,
        )

    def analyze(
        self,
        *,
        instrument_uid: str,
        ticker: str,
        candles: Iterable[Candle],
        profile: str = "medium_term",
        risk_profile: str = "balanced",
        horizon: str = "medium",
    ) -> AnalysisResult:
        if profile not in self.PROFILES:
            raise ValueError(f"Unsupported profile: {profile}")
        ordered = sorted(list(candles), key=lambda item: item.timestamp)
        if len(ordered) < 150:
            raise ValueError("Для beta-анализа требуется не менее 150 исторических свечей")
        regime = self.market_regime(ordered)
        results = [self.walk_forward(ordered, strategy, profile) for strategy in self.STRATEGIES]
        passed = [item for item in results if item.quality_gate]
        winner = max(passed, key=lambda item: item.score) if passed else None
        confidence = "Low"
        if winner:
            confidence = "High" if winner.stability >= 80 and winner.score >= 75 else "Medium" if winner.stability >= 65 and winner.score >= 60 else "Low"
        explanation = (
            f"Рекомендована {winner.strategy}: Score {winner.score:.1f}, "
            f"Walk Forward stability {winner.stability:.0f}%, режим {regime}."
            if winner else "Ни одна стратегия не прошла Quality Gate; рекомендация не сформирована."
        )
        created_at = datetime.now(timezone.utc).isoformat()
        return AnalysisResult(
            instrument_uid,
            ticker,
            profile,
            risk_profile,
            horizon,
            regime,
            winner.strategy if winner else None,
            confidence,
            winner.score if winner else 0.0,
            results,
            explanation,
            created_at,
        )

    def save(self, result: AnalysisResult) -> int | None:
        if self.store is None:
            return None
        run_ids: dict[str, int] = {}
        for item in result.strategies:
            run_ids[item.strategy] = self.store.save_walk_forward(
                instrument_uid=result.instrument_uid,
                ticker=result.ticker,
                profile=result.profile,
                risk_profile=result.risk_profile,
                strategy=item.strategy,
                strategy_version=ANALYSIS_VERSION,
                status="ACCEPTED" if item.quality_gate else "REJECTED",
                created_at=result.created_at,
                parameters=item.parameters,
                metrics={
                    "return_pct": item.return_pct,
                    "max_drawdown_pct": item.max_drawdown_pct,
                    "sharpe": item.sharpe,
                    "trades": item.trades,
                    "stability": item.stability,
                    "score": item.score,
                    "train_score": item.train_score,
                    "test_score": item.test_score,
                },
                data_from=result.created_at,
                data_to=result.created_at,
                training_period=result.profile,
                validation_period=result.horizon,
                out_of_sample_period=result.horizon,
                market_regime=result.market_regime,
            )
        return run_ids.get(result.recommendation or "")
