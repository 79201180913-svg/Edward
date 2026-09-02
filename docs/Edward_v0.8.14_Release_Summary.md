# Edward v0.8.14 — Release Summary

## Статус

**v0.8.14 — Adaptive Discovery — завершена.**

Версия расширила canonical Trading Path Analysis адаптивным поиском торговых правил за пределами фиксированного набора гипотез.

## Реализовано

1. Adaptive Feature Space — point-in-time feature library.
2. Adaptive Rule Discovery — bounded deterministic discovery на TRAIN.
3. Unified Candidate Layer — Fixed + Adaptive в одном candidate contract.
4. Candidate Pruning — TRAIN-only pruning без использования OOS.
5. Statistical Integrity — temporal split, effective sample size, overlap, multiple-testing correction.
6. Leakage Protection — discovery и threshold selection изолированы от OOS.
7. Adaptive OOS Evaluation — immutable rules оцениваются внутри точного evaluation range.
8. Unified OOS Validation — Fixed и Adaptive используют общий downstream contract.
9. Canonical Runtime Integration — `AnalysisPathRuntimeServiceV012` стал production runtime для canonical analysis.
10. GUI / Observability — UI переведён на canonical v0.8.14 result.
11. Regression protection — тесты для discovery, leakage, OOS routing, domain contract, runtime и UI.

## Runtime verification

На фактическом запуске SBER:

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

Adaptive candidates реально прошли discovery и validation, а в OOS оценивались тем же downstream контуром. Отрицательные OOS результаты корректно снижали EV/risk/opportunity и не превращались в искусственный BUY.

## Leakage / boundary verification

TRAIN, VALIDATION и OOS являются disjoint temporal ranges.

Adaptive discovery выполняется только на TRAIN.

Forward targets не могут пересекать границу evaluation range.

Изменение только OOS candles не изменяет adaptive discovery result при неизменных TRAIN/VALIDATION.

## Fixed OOS verification

Нулевые fixed OOS observations в отдельных окнах подтверждены как отсутствие matching events, а не ошибка маршрутизации. Boundary exclusions диагностируются отдельно.

## Главный архитектурный результат

Adaptive Discovery расширяет пространство поиска кандидатов, но не создаёт второго downstream analysis pipeline.

Canonical chain:

```text
TRAIN
  ↓
Fixed + Adaptive Discovery
  ↓
Unified Candidate Layer
  ↓
Pruning / Statistical Integrity
  ↓
VALIDATION
  ↓
OOS
  ↓
EV / Risk / Opportunity / Decision
  ↓
TradingPathAnalysisV012
```

## Ограничение версии

На момент завершения v0.8.14 основной Analysis UI использует canonical runtime, однако Market Opportunities / Opportunity Search всё ещё используют legacy `OpportunityAnalysisPipelineV0821` поверх `AnalysisPipelineServiceV08/V081/V082`.

Это не является незавершённостью v0.8.14: интеграция Opportunity Consumer выделена в отдельную следующую версию.

## Следующая версия

**v0.8.15 — Opportunity Canonical Integration**.

Цель: перевести Market Opportunities на `AnalysisPathRuntimeServiceV012`, сохранив существующий Universe → Analysis → Decision → Opportunity → Ranking → Portfolio flow.
