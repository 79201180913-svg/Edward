# Edward — Scope v0.5

## 1. Цель версии

Версия 0.5 переводит Edward от анализа текущего состояния инструмента к прогнозно-ориентированному торговому анализу, пригодному как основа для будущей автоматической торговли.

Ключевой результат v0.5:

**«Что делать сейчас, куда может прийти цена, с какой вероятностью, за какой срок, каким объёмом и при каком риске?»**

Реальное автоматическое исполнение ордеров в v0.5 не включается. Версия формирует execution-ready торговый план для последующего Execution Engine.

---

## 2. Архитектурный результат

```text
Market Data
    ↓
Feature Engine
    ↓
Strategy Analysis
    ↓
Forecast Engine
    ↓
Forecast Quality Gate
    ↓
Risk Engine
    ↓
Opportunity Engine
    ↓
Portfolio Context
    ↓
Trade Score
    ↓
Decision Engine
    ↓
Trade Plan
    ↓
Execution Ready
```

---

## 3. Scope задач

### 0.5.1 Forecast Engine

Добавить прогноз цены и направления движения.

Требования:
- прогнозировать не только точечную цену, но и диапазон;
- поддерживать сценарии Bear / Base / Bull;
- рассчитывать ожидаемую доходность;
- рассчитывать вероятность роста/снижения;
- рассчитывать ожидаемую волатильность;
- рассчитывать ожидаемую просадку;
- рассчитывать confidence;
- поддерживать несколько горизонтов.

Базовые горизонты:
- 1D;
- 5D;
- 20D;
- 60D.

Привязка к профилю:
- speculative — короткие горизонты;
- medium_term — 5–30 дней;
- long_term — 1–12 месяцев.

### 0.5.2 Forecast Model Selection

Создать адаптивный слой выбора модели прогноза.

Базовые классы моделей:
- Trend;
- Momentum;
- Breakout;
- Mean Reversion;
- Volatility;
- Regime-based;
- Ensemble.

Edward должен выбирать модель/комбинацию моделей для конкретного инструмента, профиля и горизонта на основании исторического качества.

### 0.5.3 Forecast Walk Forward

Расширить текущий Walk Forward.

WF должен оценивать:
- стратегию;
- модель прогноза;
- горизонт прогноза.

Кроме торговых метрик, оценивать MAE, RMSE, Directional Accuracy, Hit Rate, calibration, error of expected return и стабильность по окнам.

### 0.5.4 Forecast Quality Gate

Добавить отдельный Quality Gate для прогнозов.

При недостаточном качестве прогноз не должен использоваться для BUY/SELL как подтверждающий фактор.

### 0.5.5 Trade Score 2.0

Trade Score должен учитывать:
- Strategy Score;
- Forecast Score;
- Risk Score;
- Opportunity Score;
- Portfolio Fit;
- Confidence.

Trade Score становится основным рейтингом торговых возможностей.

### 0.5.6 Trade Plan

Ввести сущность `TradePlan`.

Должны формироваться Entry zone, Target, Stop, Expected Return, Expected Risk, Risk/Reward, Holding Horizon, Confidence, Recommended Position Size, Max Position и Execution Ready.

Для существующих позиций TradePlan должен уметь формировать план HOLD / ADD / REDUCE / SELL.

### 0.5.7 Position Sizing

Добавить расчёт рекомендуемого размера позиции с учётом риска на сделку, max position weight, текущей экспозиции, available cash, volatility, stop distance, portfolio exposure и ограничений инструмента.

Результат: количество, доля портфеля, денежный объём, риск в процентах портфеля.

### 0.5.8 Trading Costs

Добавить влияние commission, spread, slippage, liquidity, minimum lot и tick size.

```text
Gross Expected Return
        - Commission
        - Spread
        - Slippage
        = Net Expected Return
```

Net Expected Return должен участвовать в Decision Engine.

### 0.5.9 Execution Readiness

Добавить `EXECUTION_READY = true / false`.

Проверять стратегию, forecast, risk, portfolio, trading status, position size, entry, target, stop, liquidity и ограничения инструмента.

Само размещение ордера в v0.5 не выполняется.

### 0.5.10 Forecast & Trade Cache

Расширить существующий WF Cache.

Ключ кэша учитывает instrument, profile, risk profile, forecast model, horizon, data snapshot и algorithm version.

Добавить операции показать состояние кэша, принудительно пересчитать и очистить кэш.

### 0.5.11 Anti-Leakage / Point-in-Time Validation

Обязательный блок для всей прогнозной аналитики.

Запретить использование future candles, future close, future market regime, future portfolio state и future rankings.

Добавить regression tests на look-ahead bias.

### 0.5.12 UI

Расширить экран анализа. Показывать текущую цену, прогноз по горизонту, Bear / Base / Bull, вероятности, confidence, expected return, expected risk, target, stop, risk/reward, Trade Score, рекомендуемый размер позиции, горизонт удержания и Execution Ready.

Добавить отдельный блок **«Торговый план»**.

Сохранить staged progress и live result updates.

### 0.5.13 Test & Validation

Обязательные уровни:

1. Unit tests — Forecast Engine, Model Selection, Forecast Quality Gate, Trade Score, Trade Plan, Position Sizing, Costs, Execution Readiness, Cache.
2. Integration tests — Market → Forecast → Risk → Opportunity → Decision; Portfolio → Forecast → Risk → TradePlan; cache hit/miss/invalidation.
3. Walk Forward tests — отсутствие leakage, стабильность результатов, качество прогноза.
4. E2E / UI — рынок, портфель, прогноз, Trade Plan, live result updates.

---

## 4. KPI версии 0.5

- Directional Accuracy;
- Hit Rate;
- MAE / RMSE;
- Forecast Calibration;
- Walk Forward stability;
- Net Expected Return;
- Risk/Reward;
- Max Drawdown;
- качество Trade Decision после добавления Forecast;
- отсутствие look-ahead bias;
- воспроизводимость результата при повторном анализе.

Ключевой KPI — **качество торгового решения**, а не точность одной прогнозной цены.

---

## 5. Границы версии 0.5

Входит: прогноз, оценка качества прогноза, торговый план, sizing, затраты, execution readiness, подготовка данных для автоторговли.

Не входит: автоматическая отправка реальных ордеров, самостоятельное управление позициями в реальном времени, полный Order Execution Engine. Это scope для v0.6.

---

## 6. Целевой результат версии

```text
Instrument
    ↓
Forecast
    ↓
Probability / Range
    ↓
Risk
    ↓
Opportunity
    ↓
Trade Score
    ↓
Decision
    ↓
Trade Plan
    ↓
Execution Ready
```

Пример результата:

```text
UNAC

Current:             0.3505
Forecast 5D:         0.3650
Forecast 20D:        0.3910
Probability Up:      68%
Confidence:          HIGH
Expected Return:     +11.6%
Expected Risk:       -4.1%
Risk/Reward:         2.83
Strategy Score:      81
Forecast Score:      74
Risk Score:          62
Portfolio Fit:       88
Trade Score:         79
Decision:            BUY
Entry:               0.348–0.353
Target:              0.390
Stop:                0.337
Recommended Size:    6.0%
Execution Ready:     YES
```

---

## 7. Последовательность разработки

1. Forecast Engine
2. Feature / Model Selection
3. Forecast Walk Forward
4. Forecast Quality Gate
5. Trade Score 2.0
6. Trade Plan
7. Position Sizing
8. Trading Costs
9. Execution Readiness
10. Forecast/Trade Cache
11. Anti-Leakage Validation
12. UI
13. Full Test / E2E
14. Freeze v0.5.0

---

## 8. Definition of Done

Версия 0.5 считается завершённой, когда прогноз строится по нескольким горизонтам, имеет диапазон и вероятности, модель выбирается адаптивно, качество проверяется Walk Forward, Forecast Quality Gate работает, Trade Score 2.0 интегрирован, TradePlan формируется, Position Sizing работает, Net Expected Return учитывает торговые затраты, Execution Ready рассчитывается, кэш прогнозов работает, есть защита от look-ahead bias, полный unit/integration/E2E набор зелёный, UI показывает прогноз и торговый план, а автоматическое исполнение ордеров остаётся за scope v0.6.
