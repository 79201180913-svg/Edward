# Edward v0.8 — Expected Value & Portfolio Intelligence

**Версия:** 0.8
**Статус:** разработка в ветке `version-0.8-analysis`
**Базовая версия:** v0.7

## 1. Цель

v0.8 усиливает только аналитическое ядро Edward. Внешние контракты и downstream-интеграции v0.7 должны сохранять обратную совместимость.

Главная цель: перейти от эвристической оценки качества стратегии и opportunity к оценке подтвержденного торгового преимущества, ожидаемой доходности, ожидаемого убытка, неопределенности и влияния операции на текущий портфель.

## 2. Основной принцип

`Strategy Edge -> Forecast Edge -> Expected Value -> Risk -> Portfolio Impact -> Opportunity -> Decision`

Ни один отдельный показатель (`strategy_score`, `forecast`, `risk_score`, `opportunity_score`) не является самостоятельным основанием для BUY.

## 3. Границы

В v0.8 входят:

- research-grade backtest;
- transaction costs, spread и slippage в исследовании;
- единая модель исполнения backtest;
- расширенные метрики стратегии;
- robust walk-forward;
- стабильность параметров и performance dispersion;
- regime-aware strategy evaluation;
- forecast quality и calibration;
- Expected Value Engine;
- uncertainty/distribution;
- portfolio impact и marginal risk;
- Opportunity Score 2.0 как внутреннее улучшение при сохранении существующего внешнего результата;
- Confidence 2.0;
- point-in-time integrity;
- reproducibility и research snapshots;
- тесты и UI-представление новых аналитических результатов.

Не входят изменения execution, broker adapter, preflight, verification, protection, replanning, dynamic budget, slots и других автономных механизмов v0.7.

## 4. Contract Compatibility

### V08-CONTRACT-001
Публичные контракты v0.7 сохраняются.

### V08-CONTRACT-002
Без отдельного согласования запрещены удаление, переименование или изменение типа существующих output fields и enum values.

### V08-CONTRACT-003
Существующие потребители `AnalysisResult`, `StrategyResult`, `OpportunityResult` и `DecisionRequest` должны продолжать работать без обязательной адаптации.

### V08-CONTRACT-004
Новые аналитические показатели добавляются аддитивно. Внутренняя аналитика может быть значительно расширена при сохранении существующих выходных полей.

### V08-CONTRACT-005
Интеграции с T-Invest используют контрактные идентификаторы и типы без подмены семантики API.

## 5. External Contract Baseline

Для v0.8 учитываются предоставленные контракты `invest-contracts-master`. Существенные доступные источники T-Invest, которые могут использоваться аналитическим контуром:

- candles / market data;
- instrument metadata;
- trading status, liquidity и API availability;
- asset fundamentals;
- issuer reports;
- consensus forecasts;
- analyst forecasts;
- risk rates;
- insider deals;
- news;
- technical signals и стратегии Signals API.

Использование этих источников в аналитике не должно изменять внешние контракты Edward.

## 6. Phase 1 — Research Foundation

### A. Research-grade Backtest

- единая временная модель signal -> execution -> position -> equity;
- корректный gap handling;
- комиссия;
- spread;
- slippage;
- net return;
- benchmark / buy-and-hold comparison;
- CAGR, Sharpe, Sortino, Calmar, win rate, profit factor, payoff ratio, turnover, exposure.

### B. Robust Walk-Forward

- rolling windows;
- out-of-sample evaluation;
- parameter stability;
- performance dispersion;
- best/worst/median windows;
- stress windows;
- robustness score.

### C. Regime Engine

Минимальная таксономия:

- `TREND_UP`;
- `TREND_DOWN`;
- `RANGE`;
- `HIGH_VOLATILITY`;
- `LOW_VOLATILITY`;
- `TRANSITION`;
- `UNKNOWN`.

Для каждой стратегии рассчитывается историческая эффективность по режимам и `regime_compatibility`.

### D. Point-in-Time Integrity

Исторический расчет не должен использовать данные, опубликованные после момента принятия решения.

## 7. Phase 2 — Predictive Layer

### E. Forecast Quality

- horizon-specific backtest;
- directional accuracy;
- MAE/MAPE;
- downside/upside error;
- calibration;
- horizon-specific confidence.

### F. Expected Value

Базовая концепция:

`EV = P(win) × AvgWin - P(loss) × AvgLoss - Costs`

Дополнительно:

- expected return;
- expected loss;
- probability of profit;
- risk-adjusted EV;
- minimum edge threshold.

### G. Uncertainty

Для прогноза/EV хранить распределение результата, включая expected/median/downside/upside и ширину неопределенности.

### H. Confidence 2.0

Разделить confidence на strategy, forecast, regime, portfolio и overall confidence. Confidence не должна определяться только количеством наблюдений.

## 8. Phase 3 — Portfolio Intelligence

### I. Portfolio Impact

- asset/portfolio correlation;
- diversification benefit;
- sector/factor concentration;
- portfolio risk before/after;
- marginal risk contribution;
- portfolio expected return impact.

### J. Opportunity Score 2.0

Внутренне объединяет Strategy Edge, Forecast Edge, EV, Risk, Portfolio Impact, Regime Compatibility и Confidence. Существующий `opportunity_score` остается внешне совместимым.

### K. REPLACE 2.0

Замена оценивается через преимущество новой позиции относительно текущей по EV, risk и portfolio impact. Existing `REPLACE` contract remains unchanged.

### L. Decision Engine Integration

`DecisionEngine` получает более качественные значения существующих context fields. Сигнатура и значения существующих публичных enum/decision остаются совместимыми.

## 9. Phase 4 — Reproducibility, Tests, UI

- versioned research snapshots;
- reproducible analysis runs;
- contract compatibility tests;
- v0.8 unit/integration tests;
- UI details for EV, risk, forecast, portfolio impact and rationale.

## 10. T-Invest Contract Usage Rules

- `instrument_uid` является основным идентификатором внутри Edward;
- contract fields `lot`, `min_price_increment`, `buy_available_flag`, `sell_available_flag`, `api_trade_available_flag`, `liquidity_flag` и trading status не переопределяются локальной логикой;
- финансовые значения с контрактными `Quotation`/`MoneyValue` должны нормализоваться без потери точности;
- timestamps из API считаются UTC и приводятся к единой временной модели;
- consensus/analyst forecasts, fundamentals, risk rates, insider deals, news и Signals API трактуются как внешние источники данных, а не как безусловные торговые сигналы.

## 11. Definition of Done

v0.8 считается готовой, когда для инструмента Edward способен воспроизводимо показать:

1. устойчивость стратегии out-of-sample;
2. совместимость стратегии с текущим рыночным режимом;
3. историческое качество прогноза на выбранном горизонте;
4. expected return и expected loss;
5. probability of profit;
6. Expected Value после издержек;
7. uncertainty;
8. individual и marginal portfolio risk;
9. portfolio impact;
10. calibrated confidence;
11. финальный `BUY/WAIT/PASS/HOLD/ADD/REDUCE/SELL` через существующий Decision Engine контракт.

## 12. Compatibility Acceptance

После изменений существующие downstream-потребители должны продолжать успешно работать без обязательной миграции. Regression tests v0.7 должны оставаться зелеными, кроме тестов, которые явно фиксировали заменяемую внутреннюю математическую реализацию и были обновлены осознанно в рамках v0.8.
