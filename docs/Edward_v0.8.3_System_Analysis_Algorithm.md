# Edward v0.8.9 — фактически зафиксированный системный анализ

## Назначение

Документ фиксирует состояние системного анализа Edward на выпуске v0.8.9. Алгоритм анализа v0.8.8 не изменяется в рамках этой версии. v0.8.9 исправляет интеграцию сервиса поиска возможностей с результатами анализа.

## Архитектурная граница v0.8.9

```text
Market candles
  -> AnalysisPipelineServiceV08
  -> AnalysisServiceV08
  -> Robust Walk-Forward
  -> TRAIN viability
  -> parameter selection
  -> OOS validation
  -> robustness diagnostics
  -> Quality Gate
  -> canonical AnalysisPipelineV08Result
  -> Opportunity Search
  -> existing Opportunity / Decision logic
```

Ключевой принцип версии: Opportunity Search принимает уже рассчитанный результат анализа и не запускает анализ повторно в canonical production flow.

## Что НЕ менялось

В v0.8.9 не изменялись:

1. алгоритм Analysis v0.8.8;
2. Robust Walk-Forward;
3. TRAIN viability;
4. OOS/production separation;
5. Transfer Selection;
6. Robustness calculation;
7. Quality Gate thresholds;
8. смысл существующих Opportunity/Decision алгоритмов.

## Что исправлено

Исправлена передача результата нового анализа в сервис возможностей.

Результат анализа теперь проходит через compatibility boundary в существующий `OpportunityAnalysisViewV0821` с сохранением canonical `pipeline_result`.

Для `LiveOpportunitySearchService`:

```text
analysis calculated once
        -> canonical result
        -> provided analysis service
        -> OpportunitySearchService
```

Использованные для анализа candles также переиспользуются downstream, чтобы handoff не приводил к повторному запросу market data.

## Compatibility fixes

В процессе интеграции был обнаружен и исправлен compatibility defect: `confidence` нового `AnalysisPipelineV082Result` находится внутри `base`, тогда как legacy Opportunity adapter ожидал поле на верхнем уровне.

Compatibility layer теперь корректно принимает nested confidence, не изменяя источник расчёта.

## Regression protection

Зафиксированы тесты на:

- передачу canonical analysis result;
- сохранение `trading_path_research`;
- отсутствие повторного `analyze()`;
- lifecycle временного provided analysis service;
- переиспользование подготовленных candles;
- обработку ошибок одного инструмента без падения всего scan;
- совместимость callback flow.

Последний подтвержденный полный прогон:

```text
835 passed, 5 skipped
```

После добавления regression coverage количество тестов увеличилось; подтвержденный локальный прогон после исправления фикстур был зелёным.

## Runtime verification

Контрольный runtime-прогон подтвердил, что новый Analysis Pipeline реально доходит до результата pipeline и формирует `opportunity` и `confidence`.

### SBER

```text
recommendation = Momentum
evidence_strategy = Breakout
quality_gate = False
stability = 67.03
opportunity = 52.1400
confidence = 51.0450
```

### VSMO

```text
recommendation = None
score = 0.0000
evidence_strategy = Breakout
quality_gate = False
stability = 62.85
opportunity = 53.9400
confidence = 46.0733
```

Эти значения подтверждают, что после исправления результата analysis pipeline сервис больше не падает на отсутствии `confidence` и получает сформированный canonical result.

## Runtime findings, не входящие в scope исправления

Контрольный прогон также показал отдельную системную особенность: `Quality Gate=False` может сосуществовать с рассчитанными диагностическими `opportunity` и `confidence`.

Например, для SBER Breakout имеет `quality_gate=False`, но pipeline формирует `opportunity=52.1400` и `confidence=51.0450`. Для VSMO аналогично формируется opportunity при отсутствии торговой recommendation.

Это не изменяется в v0.8.9, поскольку текущая задача — исправление передачи результатов анализа в сервис возможностей. Семантическое изменение Opportunity/Decision после QG является отдельной задачей и отдельной версией.

## Итоговый статус v0.8.9

Дефект интеграции нового анализа с сервисом поиска возможностей исправлен.

Подтверждено:

1. canonical результат анализа доступен Opportunity Search;
2. повторный расчет анализа в canonical flow устранён;
3. candles переиспользуются;
4. compatibility с legacy Opportunity view сохранена;
5. nested confidence корректно принимается;
6. `trading_path_research` не теряется;
7. runtime формирует `opportunity` и `confidence`;
8. полный набор автотестов после исправлений проходит зелёным.

**v0.8.9 фиксируется как release с целью исправления сервиса поиска возможностей и интеграции результатов Analysis v0.8.8. Сам алгоритм Analysis v0.8.8 в этой версии не изменён.**

## Граница следующей работы

После выпуска v0.8.9 изменения Quality Gate semantics, Opportunity scoring, Decision semantics или самого Analysis Pipeline не входят в текущий release и должны рассматриваться отдельно.
