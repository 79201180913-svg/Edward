# Edward v0.8.11 — System Analysis: Market Context

## 1. Назначение версии

v0.8.11 добавляет к существующему аналитическому контуру Edward point-in-time Market Context и использует его как дополнительное evidence для приоритизации Trading Paths.

Цель версии — не заменить существующий Analysis/WF/Quality Gate и не искусственно получить `PROMOTED`, а проверить, помогает ли знание состояния рынка выбирать более подходящий условный Trading Path.

Ключевой принцип:

```text
Market Context = дополнительное evidence
Market Context != второй Analysis Engine
Market Context != обход Quality Gate
```

Существующий canonical analysis остаётся источником статистического результата и Quality Gate.

## 2. Архитектурная база

v0.8.8 уже предоставляет research-контур Trading Paths:

```text
Market Data
  -> AnalysisServiceV08
  -> Conditional Discovery
  -> Trading Path Candidates
  -> Ranking / Deduplication
  -> Event Backtest
  -> Economic Validation
  -> Statistical Validation
  -> Temporal Evidence
  -> Overlap Audit
  -> Multiple Testing
  -> Promotion Gate
```

v0.8.11 добавляет market-context слой поверх этого контура:

```text
Market Data
  |
  +--> canonical instrument analysis
  |
  +--> benchmark market data
          |
          +--> Market Regime
          +--> Relative Strength
          +--> Relative Volatility
                  |
                  v
          immutable Market Context Snapshot
                  |
                  v
          Shadow Market-Context Scoring
                  |
                  v
          Market-aware Trading Path order
```

При этом validation, statistical evidence и Quality Gate не пересчитываются по другой формуле и не ослабляются из-за Market Context.

## 3. Benchmark resolution

Для российских акций v0.8.11 использует `IMOEX` как логический benchmark.

Определение benchmark выполняется по metadata инструмента:

- `STOCK` / `EQUITY` / `SHARE`;
- российский market/exchange либо `class_code=TQBR`.

После определения логического benchmark `IMOEX` он разрешается в реальный T-Invest instrument UID.

Основной путь разрешения — `InstrumentsService.Indicatives`.

Fallback использует `InstrumentsService.FindInstrument` с явным `INSTRUMENT_TYPE_INDEX`, чтобы одноимённая акция не могла быть принята за индекс.

Таким образом логический benchmark не хранится как придуманная свечная серия: данные загружаются у реального инструмента T-Invest через существующий adapter boundary.

## 4. Market Context Snapshot

`MarketContextSnapshotV011` — immutable point-in-time объект, содержащий:

- `instrument_id`;
- `as_of`;
- `benchmark_id`;
- `benchmark_supported`;
- market regime;
- relative strength;
- volatility;
- `context_status`;
- version.

Поддерживаются статусы:

```text
FULL
PARTIAL
UNAVAILABLE
```

Snapshot проверяет, что вложенные context-компоненты не используют timestamp позже собственного `as_of`.

### 4.1 Market Regime

`MarketRegimeContextBuilderV011` не создаёт второй классификатор рынка. Он использует canonical `MarketRegimeEngineV08` и ограничивает вход point-in-time свечами.

### 4.2 Relative Strength

`RelativeStrengthAnalyzerV011` сравнивает доходность инструмента и benchmark на заданном point-in-time горизонте.

Результат классифицируется как:

```text
OUTPERFORMING
UNDERPERFORMING
INLINE
```

и содержит `excess_return_pct`.

### 4.3 Relative Volatility

`MarketVolatilityContextAnalyzerV011` сравнивает реализованную close-to-close волатильность инструмента и benchmark.

Классификация:

```text
HIGHER_THAN_MARKET
LOWER_THAN_MARKET
INLINE_WITH_MARKET
```

содержится также `relative_volatility`.

## 5. Market Context Shadow Scoring

`MarketContextShadowScoringServiceV011` рассчитывает гипотетическую поправку к существующему Trading Path score.

Сопоставление гипотез с legacy strategy family:

```text
BREAKOUT_EXPANSION / RANGE_BREAK -> Breakout
PULLBACK_RECLAIM / SHOCK_REVERSAL / GAP_REVERSAL -> Mean Reversion
IMPULSE_CONTINUATION -> Momentum
```

Компоненты поправки:

1. совместимость hypothesis/strategy с текущим market regime;
2. relative strength;
3. relative volatility;
4. confidence hint.

В текущей версии поправка является shadow/research механизмом. Она не переписывает исходный statistical score и не изменяет canonical recommendation напрямую.

При построении market-aware ranking сначала рассчитывается shadow, затем Trading Path bundle переставляется по `context_rank`.

Важно: вместе с кандидатом переставляются его `validation_results`, `overlap_evidence`, `multiple_testing_evidence` и `promotion_results`. Это предотвращает рассинхронизацию строки кандидата и доказательств.

## 6. Runtime integration

Market Context встроен в существующий GUI/runtime Edward.

Используется один существующий T-Invest adapter и тот же набор загруженных данных. При успешном построении snapshot runtime временно хранит:

- `last_built_snapshot`;
- `last_built_market_candles`.

Это compatibility/research bridge, не persisted state.

Если benchmark недоступен, Market Context переходит в `UNAVAILABLE`, а основной анализ сохраняется. Это принципиально: отсутствие benchmark не должно превращать корректный canonical analysis в ошибку.

## 7. Point-in-Time A/B diagnostic

Для проверки ценности Market Context реализован `MarketContextABBacktestServiceV011` и фасад `MarketContextDiagnosticV011`.

### Правила

- warm-up: `300` свечей;
- OOS хвост: минимум `60` свечей;
- стандартный шаг cutoff: `120` свечей;
- каждое решение строится только на данных `<= cutoff`;
- будущие observations используются только как OOS labels;
- market context строится только на benchmark данных `<= as_of`.

Сравниваются два выбора:

```text
Baseline Top-1 / Top-3
vs
Market-aware Top-1 / Top-3
```

Метрики:

- mean OOS return;
- median OOS return;
- win rate;
- total trades;
- number of positive windows;
- rank change rate.

A/B является diagnostic/research этапом. Он не подменяет production Quality Gate.

## 8. Реальный RZSB runtime result

Первый полный point-in-time diagnostic для RZSB дал 12 окон.

Итог:

```text
rank_change_rate        = 25.00%
baseline_top1_mean      = 0.385342
context_top1_mean       = 0.450328
delta_top1              = +0.064986
baseline_top1_win       = 45.19%
context_top1_win        = 47.27%

baseline_top3_mean      = 0.305521
context_top3_mean       = 0.025421
delta_top3              = -0.280100

baseline_top3_positive  = 6 windows
context_top3_positive   = 5 windows
```

### Интерпретация

Результат неоднозначный.

Top-1 показывает небольшой положительный эффект:

```text
+0.064986 п.п. средней OOS доходности
+2.08 п.п. win rate
```

Но Top-3 ухудшается на текущем наборе окон. Следовательно, Market Context уже влияет на выбор, однако текущая формула ещё не доказала устойчивого улучшения всего ranking.

Нельзя делать вывод о готовности текущих коэффициентов к усилению только на основании Top-1.

## 9. Примеры point-in-time окон

### 2023-09-27

Baseline:

```text
BREAKOUT_EXPANSION / H20
OOS = -0.327832%
```

Market-aware:

```text
IMPULSE_CONTINUATION / H10
OOS = -2.263971%
```

Delta:

```text
-1.936139 п.п.
```

### 2024-03-19

Baseline:

```text
BREAKOUT_EXPANSION / H20
OOS = -0.216547%
```

Market-aware:

```text
IMPULSE_CONTINUATION / H10
OOS = -2.263971%
```

Delta:

```text
-2.047423 п.п.
```

### 2025-02-25

Baseline:

```text
PULLBACK_RECLAIM / H20
OOS = -4.763818%
win rate = 23.08%
```

Market-aware:

```text
BREAKOUT_EXPANSION / H20
OOS = -0.000425%
win rate = 66.67%
```

Delta:

```text
+4.763393 п.п.
```

Это подтверждает, что эффект Market Context реальный и может быть как положительным, так и отрицательным в зависимости от исторического режима.

## 10. Quality Gate invariant

v0.8.11 не меняет legacy Quality Gate.

Market Context не может:

- отменить WF failure;
- снизить QG thresholds;
- заменить robustness;
- заменить return consistency;
- преобразовать `RESEARCH_ONLY` в `PROMOTED`;
- превратить малую выборку в торговую рекомендацию.

Финальный RZSB runtime сохраняет эту инвариантность:

```text
Trading Paths = 30
Validated     = 30
Promoted     = 0
Research Only = 7
Rejected      = 23
Legacy QG     = 0/4 PASS
```

То есть Market Context меняет research priority, но не снимает существующие evidence blockers.

## 11. Runtime observability

В анализ добавлены явные runtime-сигналы:

```text
[V011 MARKET CONTEXT]
[V011 MARKET SHADOW SUMMARY]
[V011 MARKET SHADOW RANK]
[V011 MARKET-AWARE RANKING]
[V088 TRADING PATH RANKED]
[V011 MARKET DIAGNOSTIC RESULT]
[V011 MARKET DIAGNOSTIC WINDOW]
```

Это позволяет проверить весь путь от benchmark/context до фактического порядка Trading Paths и последующего A/B результата.

Для GUI также добавлен отдельный progress overlay с четырьмя этапами:

```text
1. Загрузка / подготовка истории
2. Market Context
3. Trading Paths / validation / QG
4. Формирование итогового результата
```

Текущий основной экран анализа сознательно оставлен без дальнейшего UX-redesign; более глубокая переработка фронта не входит в текущий scope.

## 12. Regression protection

Для v0.8.11 зафиксированы проверки на:

- benchmark resolution;
- INDEX fallback через FindInstrument;
- нормализацию market candles;
- point-in-time snapshot;
- relative strength;
- relative volatility;
- shadow scoring;
- отсутствие мутаций baseline ranking;
- синхронную перестановку research evidence bundle;
- cutoff warm-up/OOS contract;
- строгое исключение будущих observations;
- Market Context diagnostic facade;
- запуск diagnostic в общем анализе;
- progress UI installer.

Полный regression запускается стандартно через:

```bash
python -m pytest -q
```

## 13. Known limitations

На текущем checkpoint остаются исследовательские ограничения.

### 13.1 Market-aware ranking пока не доказал общего улучшения

RZSB показывает положительный Top-1 delta, но отрицательный Top-3 delta. Это означает, что текущая calibration может быть слишком агрессивной при перестановке части кандидатов.

### 13.2 Shadow coefficients не считаются финально откалиброванными

Коэффициенты выбраны как умеренные research-level adjustments и требуют проверки на большем числе независимых окон и инструментов.

### 13.3 Current production ranking и A/B objective различаются

Production ranking использует все существующие validation/evidence результаты, а A/B диагностирует последующее OOS поведение выбранного Top-1/Top-3. Поэтому положительный один metric не является сам по себе доказательством общей эффективности системы.

### 13.4 Overlap remains an important blocker

В RZSB многие сильные-looking paths имеют высокий event/holding overlap. Это ограничивает интерпретацию независимости наблюдений и остаётся частью Promotion Gate.

## 14. Current scope conclusion

Инженерная интеграция v0.8.11 работает end-to-end:

```text
T-Invest adapter
   -> benchmark resolution
   -> point-in-time Market Context
   -> Shadow scoring
   -> market-aware Trading Path ranking
   -> existing validation/evidence/QG
   -> point-in-time A/B diagnostic
   -> runtime/UI observability
```

При этом версия **не считается доказавшей**, что Market Context уже улучшает торговые результаты в целом.

Текущий доказанный результат точнее формулировать так:

> Market Context успешно встроен в Edward, реально меняет приоритет Trading Paths и на первом полном RZSB point-in-time A/B показывает небольшой положительный эффект по Top-1, но нестабильный эффект по всему ranking и отрицательный результат по Top-3.

Следующая исследовательская задача — не ослаблять QG и не усиливать коэффициенты вслепую, а найти условия, при которых Market Context имеет право существенно менять Top-1, и проверить это на более широком наборе независимых point-in-time окон и инструментов.
