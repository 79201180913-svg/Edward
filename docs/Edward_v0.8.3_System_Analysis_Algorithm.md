# Edward v0.8.4 — фактически зафиксированный алгоритм системного анализа

## 1. Назначение

Документ фиксирует состояние системного анализа Edward, которое считаем базовой версией v0.8.4. Документ описывает фактический decision flow: определение режима рынка, Robust Walk-Forward, экономическую жизнеспособность TRAIN-кандидатов, OOS-проверку, диагностику устойчивости и Quality Gate.

В этой фиксации алгоритм не расширяется. Дальнейшая разработка и изменение порогов Quality Gate остановлены до отдельного решения.

## 2. Общий pipeline

```text
Instrument
  -> market candles
  -> AnalysisPipelineServiceV08
  -> AnalysisServiceV08
  -> market regime
  -> per-strategy Robust Walk-Forward
  -> TRAIN parameter candidates
  -> TRAIN viability filter
  -> robust parameter selection
  -> OOS evaluation
  -> WF activity / NO_TRADE diagnostics
  -> robustness diagnostics
  -> Quality Gate
  -> admissible strategy OR NO TRADE
```

Ключевой принцип: OOS не используется для выбора production-параметров. OOS является независимой проверкой результата выбора.

## 3. Входные данные

Анализ получает исторические свечи, профиль горизонта (`long_term`, `medium_term`, `speculative`), risk profile, horizon, набор стратегий и parameter grid каждой стратегии.

Для `medium_term`: TRAIN = 240 свечей, TEST/OOS = 60 свечей, max drawdown = 25%, minimum TRAIN trades = 1, minimum stability = 60%.

Для `long_term`: TRAIN 360 / TEST 90 / max DD 30% / stability 60%.

Для `speculative`: TRAIN 120 / TEST 30 / max DD 35% / stability 55%.

## 4. Market Regime

Перед стратегическим анализом определяется текущий рыночный режим и confidence.

В зафиксированном SBER-прогоне:

```text
regime = TRANSITION
confidence = 57.76
trend_score = -0.7669
volatility_pct = 1.0986
volatility_percentile = 32.21
```

В режиме `TRANSITION` стратегии остаются допустимыми для анализа, но получают консервативный evidence multiplier. Для SBER он составлял 0.425.

Режим является routing/prioritization evidence, а не заменой статистической проверки стратегии.

## 5. Набор стратегий

Текущий набор: Trend Following, Momentum, Breakout, Mean Reversion.

Для каждой стратегии выполняется отдельный Robust Walk-Forward.

## 6. Walk-Forward

Для каждого WF-окна:

1. Формируется TRAIN-отрезок.
2. На TRAIN тестируются все кандидаты parameter grid.
3. Рассчитываются return, benchmark/excess return, Sharpe, Sortino, drawdown, trades, exposure и другие диагностические показатели.
4. Кандидаты проходят TRAIN viability filter.
5. Среди viable-кандидатов выбирается устойчивый production parameter set.
6. Выбранные параметры переносятся на следующий OOS TEST-отрезок.
7. OOS-результат сохраняется для последующей агрегации.

Для SBER в `medium_term` ожидается 25 WF-окон.

## 7. TRAIN economic viability

До robust ranking применяется обязательный viability filter.

```text
TRAIN excess return >= 0
AND TRAIN drawdown <= profile max_drawdown
AND TRAIN trades >= minimum_train_trades
```

При отсутствии viable-кандидатов окно получает `NO_VIABLE_TRAIN` и не получает production parameter set.

Такое окно не является отрицательным OOS результатом: стратегия просто не получила разрешение на OOS-тест в этом окне.

## 8. NO_TRADE windows и denominator

`NO_TRADE` / `NO_VIABLE_TRAIN` окна не считаются отрицательными OOS-окнами и не включаются в denominator OOS-метрик.

Отдельно сохраняются:

- `windows` — все WF-окна;
- `evaluated_windows` — окна с валидным OOS evaluation;
- `active_windows` — окна с фактической торговой активностью;
- `inactive_windows` — evaluated окна без активности;
- `no_trade_windows` — окна без viable TRAIN candidate.

NO_TRADE coverage является самостоятельной диагностикой и не должна теряться.

## 9. Robust parameter selection

После viability filter viable-кандидаты ранжируются по composite robust score.

Составляющие:

- excess return — 40%;
- Sharpe — 20%;
- Sortino — 15%;
- return/drawdown — 10%;
- neighborhood stability — 15%.

Neighborhood stability оценивает согласованность близких параметров.

Устойчивость используется для выбора среди экономически допустимых кандидатов, а не для оправдания отрицательного TRAIN excess return.

## 10. OOS validation

Выбранные на TRAIN production parameters переносятся на TEST/OOS.

OOS используется только для проверки качества выбора. Для evaluated окна фиксируются OOS return, OOS excess return, OOS drawdown, OOS Sharpe, trades, TRAIN-selected parameters и диагностические признаки.

OOS winner не становится автоматически production parameter set.

## 11. Activity и NO_TRADE coverage — SBER

### Breakout

```text
WF windows       = 25
evaluated        = 12
active           = 9
inactive         = 3
active_pct       = 75.00%
NO_TRADE windows = 13
NO_TRADE pct     = 52.00%
robustness       = 71.71
mean OOS return  = +1.9376%
mean OOS DD      = 1.0578%
mean OOS Sharpe  = +0.9900
```

### Momentum

```text
WF windows       = 25
evaluated        = 14
active           = 13
inactive         = 1
active_pct       = 92.86%
NO_TRADE windows = 11
NO_TRADE pct     = 44.00%
robustness       = 53.21
mean OOS return  = +0.7474%
mean OOS DD      = 5.8888%
mean OOS Sharpe  = +0.1404
```

### Mean Reversion

```text
WF windows       = 25
evaluated        = 7
active           = 2
inactive         = 5
active_pct       = 28.57%
NO_TRADE windows = 18
NO_TRADE pct     = 72.00%
robustness       = 38.05
mean OOS return  = -0.3376%
mean OOS DD      = 0.4151%
mean OOS Sharpe  = -0.3761
```

## 12. Robustness diagnostics

Robustness агрегирует return consistency, risk consistency, Sharpe consistency, parameter stability и performance consistency.

Для Breakout diagnostic breakdown:

```text
return_score       = 58.33
risk_score         = 100.00
sharpe_score       = 58.33
stability_score    = 66.67
performance_score  = 75.97
```

Итоговый WF result показывает robustness 71.71. Это агрегированный WF result; diagnostic breakdown является детализацией компонентов и не должен смешиваться с ним.

Для Momentum robustness = 53.21. Для Mean Reversion robustness = 38.05.

## 13. Quality Gate

Quality Gate — финальный допуск стратегии к торговой рекомендации.

Для `medium_term` ключевые пороги:

- mean test return >= 0;
- mean test Sharpe >= 0;
- return consistency >= 60%;
- robustness score >= 60%;
- mean test drawdown <= 25%.

Quality Gate не выбирает параметры и не исправляет плохой TRAIN/OOS результат. Он определяет, достаточно ли доказательств для admissibility.

## 14. Зафиксированный SBER result

| Стратегия | Evaluated OOS | NO_TRADE | Mean OOS Return | Mean OOS Sharpe | Robustness | Основной QG blocker |
|---|---:|---:|---:|---:|---:|---|
| Trend Following | 25 | — | отрицательная | отрицательный | ~36 | OOS return / Sharpe / consistency / robustness |
| Momentum | 14 | 11 | +0.7474% | +0.1404 | 53.21 | consistency + robustness |
| Breakout | 12 | 13 | +1.9376% | +0.9900 | 71.71 | return consistency 58.33% < 60% |
| Mean Reversion | 7 | 18 | -0.3376% | -0.3761 | 38.05 | OOS return / Sharpe / consistency / robustness |

Failure attribution для SBER:

```text
OOS_NEGATIVE            = 2
LOW_PARAMETER_STABILITY = 2
total failed             = 4
dominant                 = OOS_NEGATIVE
```

## 15. Важный вывод по текущему состоянию

Quality Gate не является единственной причиной слабого результата всех стратегий.

Breakout — главный диагностический кандидат: 12 evaluated OOS windows, +1.9376% mean OOS return, +0.9900 mean OOS Sharpe, robustness 71.71, но return consistency 58.33% при требовании 60%. Поэтому Breakout формально остаётся `FAIL`.

Momentum имеет положительные OOS return и Sharpe, но недостаточную aggregate robustness.

Mean Reversion показывает слабое OOS качество.

## 16. Зафиксированные правила v0.8.4

1. TRAIN выбирает параметры.
2. TRAIN viability является обязательным предварительным фильтром.
3. OOS не участвует в выборе production parameters.
4. NO_TRADE окна не смешиваются с evaluated OOS denominator.
5. NO_TRADE coverage сохраняется отдельно.
6. Robustness оценивает устойчивость результата.
7. Quality Gate определяет торговую admissibility.
8. Если ни одна стратегия не проходит Quality Gate — итоговое решение `NO TRADE`.
9. Лучшая стратегия среди FAIL не становится торговой рекомендацией.
10. Quality Gate не ослабляется только ради прохождения конкретной стратегии.

## 17. Граница версии

v0.8.4 считается зафиксированной точкой для дальнейшего анализа. Дальнейшие изменения должны выполняться отдельной версией и не должны молча менять состав WF окон, правило исключения NO_TRADE из OOS denominator, TRAIN viability, OOS/production separation, Quality Gate thresholds или смысл robustness без отдельного решения и новой версии.
