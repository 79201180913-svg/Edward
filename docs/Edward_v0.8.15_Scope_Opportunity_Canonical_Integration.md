# Edward v0.8.15 — Scope: Opportunity Search Canonical Integration

## 1. Цель версии

v0.8.15 должна перевести бизнес-сценарий поиска возможностей на тот же canonical Analysis Runtime, который используется основным анализом и GUI в v0.8.14.

Главная цель:

> **Opportunity Search должен потреблять результат v0.8.14 canonical analysis, а не запускать собственный legacy analysis pipeline.**

Версия не должна создавать новый аналитический движок.

## 2. Почему нужен отдельный scope

В v0.8.14 canonical runtime был доведён до рабочего состояния и подключён к GUI.

При проверке Opportunity Consumer обнаружено, что фактический `OpportunityAnalysisPipelineV0821` всё ещё строит анализ через старую цепочку:

```text
AnalysisPipelineServiceV08
        -> AnalysisPipelineServiceV081
        -> AnalysisPipelineServiceV082
```

вместо:

```text
AnalysisPathRuntimeServiceV012
        -> v0.8.14 Adaptive Discovery
        -> Unified Candidate Layer
        -> Validation
        -> OOS
        -> EV
        -> Risk
        -> Opportunity
        -> Decision
```

Следовательно, бизнес-сценарий Opportunity Search пока не получает результаты v0.8.14.

## 3. Source of Truth

Единственным источником аналитического результата должен стать canonical `TradingPathAnalysisV012`, сформированный `AnalysisPathRuntimeServiceV012`.

Opportunity Search должен быть consumer этого результата.

Он не должен:

- повторно запускать Analysis;
- самостоятельно выбирать стратегию;
- самостоятельно строить adaptive/fixed candidates;
- пересчитывать opportunity;
- пересчитывать confidence;
- повторно применять Quality Gate как отдельный смысловой rule;
- вызывать Forecast для получения аналитического результата;
- запускать legacy Opportunity Engine;
- создавать собственный Decision Engine path;
- выполнять Trade Plan или Position Sizing в consumer path.

## 4. Целевой бизнес flow

Согласно бизнес-сценарию:

```text
Account State
     |
     v
Market Universe
     |
     v
Instrument Availability Filter
     |
     v
Canonical v0.8.14 Analysis
     |
     v
Decision / Opportunity Result
     |
     v
Opportunity Consumer
     |
     v
Opportunity Ranking
     |
     v
Market Opportunities UI
```

На текущем этапе реальных ордеров нет.

## 5. Block 1 — Audit current Opportunity flow

Перед изменением production code необходимо зафиксировать фактический runtime call chain.

Проверить:

- entrypoint Market Opportunities;
- кнопку запуска анализа рынка;
- Universe Scan;
- Instrument filtering;
- Opportunity Search;
- Opportunity Analysis Consumer;
- ranking;
- UI state;
- logging.

Найти все вызовы:

- `AnalysisService`;
- `AnalysisPipelineServiceV08*`;
- `AnalysisTradingPathAdapterV088`;
- `AnalysisPathRuntimeServiceV012`;
- `OpportunityEngine`;
- `DecisionEngine`;
- Forecast/TradePlan/PositionSizing.

Результат блока — документированный фактический call graph.

## 6. Block 2 — Canonical Analysis Adapter

Перевести Opportunity Search на вызов:

`AnalysisPathRuntimeServiceV012.analyze_paths(...)`

или на тонкий adapter, который вызывает исключительно этот canonical runtime.

Adapter может преобразовывать техническую форму данных, но не должен изменять смысл результата.

Обязательное правило:

```text
canonical result in
        ==
result consumed by Opportunity Search
```

Никакого второго анализа.

## 7. Block 3 — Opportunity Consumer

Проверить и при необходимости доработать `OpportunityAnalysisConsumer` так, чтобы он принимал canonical v0.8.14 result.

Consumer должен:

- принимать `TradingPathAnalysisV012`;
- сохранять source/path/rank/evidence;
- передавать opportunity/decision/risk/validation без reinterpretation;
- корректно обрабатывать отсутствие результата;
- отличать analysis unavailable/error от торгового решения;
- не создавать собственный scoring.

Legacy compatibility допустима только как технический boundary, но live path не должен возвращаться к старому analysis engine.

## 8. Block 4 — Opportunity Ranking

Проверить ranking после перехода на canonical result.

Ranking должен использовать фактические поля canonical analysis и не создавать вторую формулу качества.

Проверить отдельно:

- BUY;
- WAIT;
- PASS;
- confidence;
- opportunity;
- risk;
- validation/Quality Gate;
- отсутствие результата.

Особенно важно не превращать PASS/WAIT в BUY через consumer-side scoring.

## 9. Block 5 — Adaptive Discovery propagation

Проверить, что adaptive paths из v0.8.14 проходят весь Opportunity flow без потери происхождения.

В Opportunity result должны быть доступны как минимум:

- source = adaptive/fixed;
- adaptive rule, если применимо;
- TRAIN evidence;
- statistical integrity;
- validation status;
- OOS evidence;
- EV;
- risk;
- opportunity;
- decision.

Adaptive candidate не должен становиться generic opportunity без traceability.

## 10. Block 6 — Runtime and observability

Сохранить и расширить диагностику бизнес-сценария.

Обязательные события:

- `AUTONOMOUS_CYCLE_STARTED`;
- `ACCOUNT_SNAPSHOT`;
- `UNIVERSE_SCAN_STARTED`;
- `INSTRUMENT_FILTERED`;
- `ANALYSIS_STARTED`;
- `ANALYSIS_COMPLETED`;
- `DECISION`;
- `OPPORTUNITY`;
- `AUTONOMOUS_CYCLE_COMPLETED`.

Для analysis/opportunity событий должны быть доступны:

- instrument;
- analysis version;
- source;
- decision;
- opportunity;
- confidence;
- risk;
- validation status;
- reason codes.

Логи должны позволять доказать, что один instrument анализируется один раз canonical runtime и тот же результат используется consumer.

## 11. Block 7 — Regression protection

Добавить/обновить тесты:

1. Opportunity flow вызывает v0.8.14 canonical runtime.
2. Legacy `AnalysisPipelineServiceV08*` не вызывается в live Opportunity path.
3. `AnalysisTradingPathAdapterV088` не используется как analysis engine.
4. Один instrument анализируется один раз.
5. Canonical result передаётся без изменения смысла.
6. Adaptive candidate доходит до Opportunity Consumer.
7. Fixed candidate доходит до Opportunity Consumer.
8. Opportunity не пересчитывается consumer-side.
9. Confidence не пересчитывается consumer-side.
10. Quality Gate не заменяется новой consumer-side логикой.
11. PASS/WAIT не превращаются в BUY искусственно.
12. Analysis unavailable/error не интерпретируется как торговое решение.
13. Existing adapter contracts не ломаются без необходимости.
14. Полный regression suite остаётся green.

## 12. Block 8 — Runtime acceptance

На реальном запуске необходимо подтвердить цепочку:

```text
Market Universe
      -> instrument
      -> v0.8.14 canonical analysis
      -> TradingPathAnalysisV012
      -> Opportunity Consumer
      -> Opportunity Result
      -> Ranking
      -> UI
```

Для одного и того же instrument должны совпадать ключевые значения между canonical analysis и Opportunity result.

Минимальный acceptance set:

- instrument analyzed once;
- analysis version = 0.8.14;
- adaptive/fixed source preserved;
- opportunity preserved;
- confidence preserved;
- validation preserved;
- risk preserved;
- decision preserved;
- no legacy analysis call;
- no consumer-side scoring;
- no artificial BUY increase.

## 13. Что НЕ входит в v0.8.15

Не входит:

- новый алгоритм Adaptive Discovery;
- изменение feature library;
- изменение Statistical Integrity methodology;
- изменение OOS methodology;
- изменение Quality Gate thresholds;
- изменение Risk formulas;
- изменение Opportunity formulas в canonical Analysis;
- изменение Decision semantics;
- реальная отправка ордеров;
- новая стратегия;
- новый execution engine.

v0.8.15 — интеграционная версия.

## 14. Definition of Done

v0.8.15 считается выполненной, когда:

1. Market Opportunities использует v0.8.14 canonical Analysis Runtime.
2. Legacy analysis pipeline отсутствует в live Opportunity path.
3. Analysis выполняется один раз на instrument.
4. Opportunity Search является consumer, а не вторым аналитическим движком.
5. Adaptive и Fixed результаты одинаково проходят consumer boundary.
6. Canonical opportunity/confidence/risk/decision не пересчитываются.
7. Quality Gate не изменён.
8. BUY не увеличивается искусственно.
9. Runtime logs подтверждают canonical chain.
10. Regression suite green.
11. Реальный Market Opportunities запуск подтверждает совпадение canonical Analysis и consumer result.

## 15. Главный критерий версии

После v0.8.15 не должно существовать двух независимых аналитических результатов для одного instrument:

```text
WRONG

Analysis v0.8.14 ----> Result A
                         \
                          -> Opportunity Search -> Result B
                         /
Legacy Analysis --------/

CORRECT

Analysis v0.8.14
       |
       v
TradingPathAnalysisV012
       |
       +----> GUI
       |
       +----> Opportunity Consumer
       |
       +----> Ranking
```

Главный архитектурный принцип:

> **Один instrument → один canonical analysis → один source of truth → несколько read-only consumers.**
