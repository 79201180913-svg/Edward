# Edward v0.8.10 — System Analysis: Opportunity Consumer

## 1. Цель версии

Цель v0.8.10 — исправить архитектурный дефект сервиса поиска возможностей: Opportunity Search не должен повторно анализировать инструмент, самостоятельно рассчитывать opportunity/confidence или интерпретировать результаты анализа. Он должен принимать готовый канонический результат Analysis Pipeline и использовать его как источник истины.

## 2. Исходный дефект

В предыдущей реализации между новым анализом и сервисом возможностей существовал второй аналитический контур. Opportunity Search исторически имел собственную логику оценки инструмента, включая зависимости от Forecast / Opportunity Engine / Decision Engine и других execution-компонентов.

Это приводило к расхождению между результатом нового Analysis Pipeline и тем, что фактически показывал/использовал Opportunity Search.

Дополнительный runtime-дефект был обнаружен на границе типов: Analysis Pipeline фактически возвращал канонический `AnalysisPipelineV082Result`, тогда как consumer принимал только `AnalysisPipelineV08Result`. В результате корректно завершившийся анализ превращался в `ANALYSIS_UNAVAILABLE`.

## 3. Целевая архитектура

```text
Analysis Pipeline
        |
        | canonical Analysis Result
        v
Opportunity Analysis Consumer
        |
        | 1:1 consumption / mapping
        v
Opportunity Search Result
```

Opportunity Search не является вторым аналитическим движком.

Он не должен:

- запускать повторный Analysis;
- самостоятельно выбирать стратегию;
- пересчитывать opportunity;
- пересчитывать confidence;
- самостоятельно применять Quality Gate как новый смысловой decision rule;
- запускать Forecast для получения аналитического результата;
- вызывать Opportunity Engine;
- вызывать Decision Engine;
- строить Trade Plan или Position Sizing в рамках consumer path.

## 4. Что было исправлено

### 4.1 Canonical consumer

Добавлен/зафиксирован `OpportunityAnalysisConsumerV010`, который принимает канонический результат Analysis Pipeline и предоставляет Opportunity Search read-only представление результата.

Consumer поддерживает фактические канонические типы:

- `AnalysisPipelineV08Result`;
- `AnalysisPipelineV082Result`.

Нека нонические/произвольные объекты отклоняются через `TypeError`.

### 4.2 Исправление adapter contract

`OpportunityAnalysisPipelineV0821` должен сохранять свой legacy-shaped view для совместимости существующих вызовов, но внутри него `pipeline_result` должен оставаться исходным canonical Analysis result.

Live Opportunity Search передаёт именно `pipeline_result` в `OpportunityAnalysisConsumerV010`.

Таким образом adapter не подменяет canonical result произвольным wrapper-объектом на границе consumer.

### 4.3 Удаление legacy analytical dependency

Из live Opportunity Search удалена зависимость от `UnifiedOpportunityEngineV0821` и связанные legacy-вызовы, которые могли создавать второй источник opportunity.

Также добавлены архитектурные regression-тесты, защищающие consumer boundary от возврата старого аналитического контура.

### 4.4 Faithful mapping

В `_from_canonical_result()` устранена собственная интерпретация Quality Gate вида `quality_gate -> STRATEGY_QUALITY_FAIL`.

`opportunity_score` берётся непосредственно из canonical Analysis result.

Сервис возможностей не должен менять смысл результата Analysis.

## 5. Runtime-диагностика

Реальный запуск подтвердил следующую важную последовательность.

Для VSMO Analysis Pipeline завершает расчёт и формирует:

- `evidence_strategy=Breakout`;
- `opportunity=52.6900`;
- `confidence=44.1381`.

При этом Quality Gate для выбранной стратегии сообщает `FAIL`. Аналогично для ELMT Pipeline формирует `opportunity=59.6800`, `confidence=22.2432` при `quality_gate=False`.

Следовательно, наличие `FAIL` в Analysis и наличие числовых `opportunity/confidence` в canonical result — это два поля одного результата Analysis. Opportunity Service не должен самостоятельно преобразовывать их в другой decision.

## 6. Важный вывод по Quality Gate

В рамках v0.8.10 **Quality Gate не изменяется**.

Логика анализа, Walk Forward, Robustness и пороги Quality Gate не являются scope исправления Opportunity Service.

Если Analysis Pipeline сформировал canonical result, Opportunity Service должен его принять и передать дальше согласно контракту.

Например, в runtime для Momentum Quality Gate был `FAIL` из-за `return_consistency=40.0 < 60.0` и `robustness_score=52.73 < 60.0`, при этом Pipeline сформировал собственный итог. Это относится к семантике Analysis и не является основанием для добавления второй проверки в Opportunity Search.

## 7. Регрессионная защита

Зафиксированы тесты, проверяющие:

1. canonical result передаётся из Analysis в Opportunity;
2. анализ для инструмента рассчитывается один раз;
3. тот же результат используется Opportunity flow;
4. consumer отклоняет неканонический объект;
5. Opportunity Search не возвращает старый `UnifiedOpportunityEngineV0821` в live path;
6. Opportunity Search не вызывает старые Forecast / Decision / TradePlan / PositionSizing контуры;
7. canonical `opportunity` не заменяется локальным scoring;
8. существующие adapter contracts сохраняются.

## 8. Runtime-критерий готовности

Версия считается корректно интегрированной, когда реальный запуск показывает:

```text
Analysis completed
        -> canonical result
        -> Opportunity consumer
        -> Opportunity result
```

без перехода корректного результата в `ANALYSIS_UNAVAILABLE` из-за несовместимого типа или legacy analytical path.

При этом значения Analysis должны сохраняться без повторного расчёта.

## 9. Что НЕ входит в v0.8.10

Не изменяются:

- алгоритмы анализа;
- стратегии;
- Walk Forward;
- Robustness;
- Quality Gate thresholds;
- формулы opportunity в Analysis;
- формулы confidence в Analysis;
- качество торговых сигналов.

v0.8.10 исправляет **интеграцию и потребление результата**, а не сам Analysis.

## 10. Итоговый статус

Основной дефект интеграции исправлен и защищён regression-тестами.

Ключевой архитектурный принцип v0.8.10:

> **Analysis является единственным источником аналитического результата. Opportunity Search — consumer этого результата, а не второй аналитический движок.**

Последующая работа по улучшению качества стратегий или согласованию Quality Gate с opportunity/confidence должна выполняться отдельно от исправления consumer boundary и не должна возвращать собственную аналитику в сервис возможностей.
