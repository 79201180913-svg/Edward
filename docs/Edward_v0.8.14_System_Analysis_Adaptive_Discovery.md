# Edward v0.8.14 — System Analysis: Adaptive Discovery

## 1. Цель версии

Цель v0.8.14 — расширить существующий анализ торговых путей адаптивным поиском условий, не ограниченных заранее заданным набором fixed hypotheses, при сохранении единого downstream pipeline и действующих Quality Gate.

Главная задача версии — увеличить покрытие качественных торговых путей, а не искусственно увеличить количество BUY.

## 2. Исходная проблема

До v0.8.14 анализ использовал фиксированный набор гипотез:

- `BREAKOUT_EXPANSION`;
- `PULLBACK_RECLAIM`;
- `IMPULSE_CONTINUATION`;
- `SHOCK_REVERSAL`;
- `GAP_REVERSAL`;
- `RANGE_BREAK`.

Такой подход ограничивал пространство поиска заранее известными паттернами. Система могла не находить устойчивые условия, которые не совпадают ни с одной fixed hypothesis.

Дополнительная проблема заключалась в том, что adaptive discovery нельзя было подключать отдельным аналитическим контуром: adaptive и fixed кандидаты должны проходить один и тот же downstream pipeline.

## 3. Целевая архитектура

```text
Historical Candles
       |
       v
Temporal Split
       |
       +---------------- TRAIN ----------------+
       |                                       |
       |       Fixed Discovery                 |
       |              |                        |
       |       Adaptive Discovery              |
       |              |                        |
       |              +-----------+------------+
       |                          |
       |                   Unified Candidate
       |                       Layer
       |                          |
       |                   Candidate Pruning
       |                          |
       |                Statistical Integrity
       |                          |
       +--------------------------+
                                  |
                              VALIDATION
                                  |
                              OOS Validation
                                  |
                         Expected Value / Risk
                                  |
                         Opportunity / Decision
                                  |
                         Final Analysis Result
```

Adaptive discovery является дополнительным источником кандидатов, а не альтернативным runtime.

## 4. Adaptive Feature Space

Добавлена детерминированная point-in-time библиотека признаков `TradingPathFeatureServiceV014`.

Используются, в частности:

- доходности на горизонтах 5/10/20/50;
- расстояния до high/low;
- расстояния до SMA;
- realized volatility;
- range percentage;
- SMA spread и slope;
- body/wick ratios;
- close position;
- gap percentage;
- ATR percentage.

Признаки рассчитываются только из данных, доступных на соответствующем timestamp. Будущие forward returns не входят в feature space.

## 5. Adaptive Rule Discovery

`TradingPathAdaptiveDiscoveryServiceV014` ищет компактные правила на TRAIN.

Основные ограничения:

- regimes определяются point-in-time;
- горизонты: `1, 3, 5, 10, 20`;
- threshold percentiles: `20, 40, 60, 80`;
- минимальное количество наблюдений — 12;
- правило содержит от 1 до 3 условий;
- поддерживаются `>=` и `<=`;
- поиск ограничен детерминированным bounded expansion;
- максимум single seeds — 12;
- максимум результатов — 50;
- сохраняются только кандидаты с положительным excess effect.

Forward return является target и не используется для построения признаков.

## 6. Unified Candidate Layer

Добавлен `TradingPathCandidateServiceV014`.

Он приводит fixed и adaptive discovery к единому `TradingPathCandidate`.

Для fixed кандидатов сохраняется источник:

`fixed:0.8.6`

Для adaptive:

`0.8.14`

Adaptive expression сохраняется в hypothesis с префиксом:

`ADAPTIVE_RULE:`

Добавлена отдельная `StrategyFamily.ADAPTIVE_DISCOVERY`.

После unified layer downstream код не должен иметь отдельного аналитического pipeline для adaptive.

## 7. Candidate Pruning

Добавлен `TradingPathCandidatePruningServiceV014`.

Pruning выполняется до дорогой OOS-проверки и использует только discovery/TRAIN evidence.

Правила pruning:

- фиксированные кандидаты сохраняются;
- adaptive кандидаты должны иметь достаточное количество наблюдений;
- применяется минимальный excess effect;
- максимальная сложность — 3 условия;
- эквивалентные adaptive rules deduplicate;
- ограничивается число adaptive кандидатов в одном контексте;
- retained candidates ранжируются детерминированно;
- статистический gate не ослабляется.

OOS данные в pruning не используются.

## 8. Statistical Integrity

Добавлен `TradingPathStatisticalIntegrityServiceV014`.

Введено строгое временное разбиение:

- TRAIN;
- VALIDATION;
- OOS.

Минимумы:

- TRAIN >= 60;
- VALIDATION >= 20;
- OOS >= 20.

Temporal split является contiguous и disjoint.

Статистическая оценка включает:

- observations;
- effective sample size;
- overlap ratio;
- mean return;
- baseline return;
- excess return;
- standard error;
- z-score;
- one-sided p-value;
- hypotheses tested;
- adjusted p-value;
- validity flags.

Для множественного тестирования используется Holm correction с сохранением FWER-контроля.

Overlap/effective sample size рассчитываются по фактическим event intervals, если event indices доступны; при отсутствии индексов используется консервативный fallback.

Критически важно: статистическая оценка adaptive discovery не имеет доступа к OOS.

## 9. Leakage Protection

Adaptive discovery запускается только на TRAIN.

Threshold selection выполняется до OOS и не использует OOS observations.

Adaptive rule после discovery считается immutable для последующих evaluation windows.

Forward return для validation/OOS считается только если весь target находится внутри соответствующей evaluation range. Target не может пересекать границу окна.

Аналогичная boundary protection применяется к fixed candidate targets и baseline.

Regression-тест зафиксировал инвариант: изменение только OOS candles не меняет adaptive discovery result, если TRAIN и VALIDATION остаются неизменными.

## 10. Unified OOS Validation

Добавлен `TradingPathAdaptiveOOSServiceV014`.

Он:

- парсит immutable `ADAPTIVE_RULE`;
- строит point-in-time features;
- проверяет regime;
- проверяет все условия rule;
- вычисляет forward returns только внутри evaluation range.

`TradingPathOOSValidationServiceV012` маршрутизирует:

- fixed candidates через существующий EventObservation path;
- adaptive candidates через adaptive OOS evaluator.

При этом оба типа используют один контракт `TradingPathOOSWindowV012` и один downstream validation path.

## 11. Canonical Runtime Integration

Канонический runtime —

`src/edward/services/analysis_path_runtime_service_v012.py`

Он теперь выполняет:

1. сортировку candles;
2. TRAIN/VALIDATION/OOS split;
3. fixed discovery на TRAIN;
4. adaptive discovery на TRAIN;
5. unified candidate layer;
6. adaptive statistical integrity;
7. candidate pruning;
8. validation;
9. выбор validated candidates;
10. OOS validation;
11. Expected Value;
12. Risk;
13. Opportunity;
14. Decision;
15. формирование `TradingPathAnalysisV012`.

Adaptive и fixed кандидаты используют общий downstream pipeline.

Quality Gate не заменён adaptive-логикой и не ослаблен.

## 12. Frontend / Observability

GUI переведён на canonical v0.8.14 runtime.

Frontend теперь показывает фактические результаты canonical analysis, включая:

- source fixed/adaptive;
- adaptive rule;
- TRAIN observations и excess;
- Statistical Integrity;
- Validation;
- OOS EV;
- Risk;
- Decision.

Progress wrapper больше не запускает legacy v0.8.8 analysis adapter и не подменяет canonical runtime.

Runtime diagnostics позволяют различать отсутствие matching events и исключение event из-за boundary protection.

## 13. Runtime verification

Для реального запуска SBER зафиксирован следующий runtime:

```text
candles=1768
train=1060
validation=353
oos=355
discovered=70
selected=8
final=8
buy=0
wait=1
pass=7
```

Adaptive discovery сформировал 50 кандидатов. После pruning осталось 26 кандидатов, из которых 20 были отклонены statistical gate, 21 — по complexity в исходном совокупном pruning счёте, при этом итоговый retained набор составил 26 кандидатов.

В validation прошли 8 кандидатов.

В финальном OOS adaptive candidates реально оценивались через adaptive OOS evaluator. В отдельных случаях OOS имел отрицательный результат, что корректно отражалось в EV/risk/opportunity/decision и не приводило к искусственному BUY.

Runtime завершился:

`buy=0 wait=1 pass=7`

что подтверждает отсутствие искусственного увеличения BUY.

## 14. Fixed OOS verification

В ходе runtime diagnostics были проверены случаи нулевого количества fixed OOS observations.

Проверка показала, что это не ошибка маршрутизации. Для ряда fixed hypotheses в конкретных OOS windows действительно отсутствовали matching events.

При этом validation range содержит реальные fixed events, а boundary exclusions фиксируются отдельно.

Следовательно:

- fixed OOS routing работает;
- boundary protection работает;
- отсутствие событий не подменяется synthetic observation.

## 15. GUI / Canonical boundary

GUI и progress wrapper больше не должны использовать старые `AnalysisService`, `AnalysisTradingPathAdapterV088` или legacy market-context monkeypatches для основного анализа.

Основной источник результата GUI:

`AnalysisPathRuntimeServiceV012.analyze_paths(...)`

Market Context остаётся отдельным point-in-time контекстом и не заменяет canonical path analysis.

## 16. Regression protection

Добавлены/обновлены тесты для:

1. feature library;
2. adaptive discovery;
3. unified candidate layer;
4. candidate pruning;
5. statistical integrity;
6. leakage isolation;
7. adaptive OOS;
8. fixed/adaptive OOS routing;
9. domain Statistical Integrity snapshot;
10. canonical runtime;
11. frontend canonical helpers/UI;
12. progress wrapper.

Полный regression suite на момент фиксации версии проходит.

## 17. Definition of Done

Версия v0.8.14 считается выполненной относительно согласованного scope, если:

1. Adaptive находит правила, отсутствующие среди fixed hypotheses.
2. Discovery не видит OOS.
3. Threshold selection не видит OOS.
4. Multiple testing учитывается.
5. Overlap учитывается.
6. Adaptive и Fixed используют один downstream pipeline.
7. Quality Gate не ослабляется.
8. BUY не увеличивается искусственно.
9. Canonical результаты доступны в GUI.
10. OOS adaptive rules оцениваются point-in-time.
11. Boundary crossing исключён.
12. Fixed OOS routing диагностически подтверждён.
13. Full regression остаётся green.

## 18. Что НЕ входит в v0.8.14

Не входит в эту версию:

- изменение Quality Gate thresholds;
- создание нового execution/trading engine;
- автоматическая отправка ордеров;
- изменение Risk/Opportunity/Decision семантики;
- отдельный adaptive decision engine;
- интеграция Opportunity Search с v0.8.14 — это следующий scope;
- A/B бизнес-оценка uplift adaptive discovery — это следующий scope.

## 19. Итоговый вывод

v0.8.14 сформировал adaptive discovery layer поверх canonical Trading Path Runtime.

Главное архитектурное достижение версии:

> **Adaptive Discovery расширяет пространство поиска кандидатов, но не создаёт второй аналитический pipeline.**

На момент фиксации версии canonical analysis и GUI используют v0.8.14. Следующий этап должен проверить и перевести потребителей анализа, прежде всего Opportunity Search, на этот же canonical runtime.
