# Edward v0.8.15 — System Specification: Opportunity Consumer Integration

## 1. Назначение версии

**v0.8.15 — Opportunity Consumer Integration**.

Цель версии — перевести production Market Opportunities / Opportunity Search на **canonical Trading Path Analysis v0.8.14**, не создавая второго аналитического контура и не изменяя бизнес-flow поиска возможностей.

Главный принцип версии:

> **Canonical Trading Path Analysis является единственным источником аналитического результата. Opportunity Search является consumer этого результата и отвечает за universe, portfolio context, ranking, allocation и presentation/execution preparation, но не заменяет canonical analysis собственной аналитикой.**

Версия продолжает архитектурный результат v0.8.13 и использует Adaptive Discovery из v0.8.14 как полноценный источник кандидатов и итоговых Opportunities.

---

## 2. Исходное состояние

До v0.8.15 существовало разделение между двумя контурами:

```text
Market Opportunities
        ↓
OpportunitySearchService
        ↓
legacy OpportunityAnalysisPipelineV0821
        ↓
old AnalysisPipelineService V08/V081/V082
```

Одновременно canonical Trading Path runtime уже был построен и включал:

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
Expected Value
  ↓
Risk
  ↓
Opportunity
  ↓
Decision
  ↓
TradingPathAnalysisV012
```

Проблема заключалась не в отсутствии canonical analysis, а в том, что Market Opportunities не использовал его как production source of truth.

Это создавало риск расхождения между:

- результатом Trading Path Analysis;
- Adaptive Discovery;
- Quality Gate;
- Opportunity Search;
- Decision;
- UI.

---

## 3. Целевая архитектура

Целевая архитектура v0.8.15:

```text
                    Market / Portfolio Universe
                              ↓
                       Market Data / Candles
                              ↓
               CanonicalOpportunityAnalysisV015
                              ↓
                 AnalysisPathRuntimeServiceV012
                              ↓
        ┌─────────────────────────────────────────┐
        │ TRAIN                                   │
        │ Fixed Discovery + Adaptive Discovery    │
        │            ↓                            │
        │ Unified Candidates                      │
        │            ↓                            │
        │ Pruning / Statistical Integrity         │
        │            ↓                            │
        │ Validation → OOS                        │
        │            ↓                            │
        │ EV → Risk → Opportunity → Decision     │
        └─────────────────────────────────────────┘
                              ↓
                  Canonical Trading Paths
                              ↓
                OpportunitySearch consumer
                              ↓
             Ranking / Portfolio / Allocation
                              ↓
                         UI / Execution
```

Canonical analysis должен рассчитываться один раз для конкретного instrument snapshot и передаваться дальше без смысловой подмены.

---

## 4. Scope версии

v0.8.15 состоит из восьми блоков.

### Block 1 — Canonical Analysis Adapter

Добавляется production adapter `CanonicalOpportunityAnalysisV015`.

Ответственность:

- принять instrument UID, ticker, candles и profile;
- вызвать `AnalysisPathRuntimeServiceV012`;
- получить `TradingPathAnalysisV012` results;
- определить best canonical path;
- предоставить canonical result Opportunity Search;
- поддерживать cache для одинакового snapshot;
- не выполнять собственную стратегическую аналитику.

Adapter не должен создавать альтернативный Analysis Pipeline.

Ключевой контракт:

```text
Opportunity Search
        ↓
CanonicalOpportunityAnalysisV015
        ↓
AnalysisPathRuntimeServiceV012
        ↓
TradingPathAnalysisV012
```

---

### Block 2 — Preserve Opportunity Business Flow

Существующий бизнес-flow Opportunity Search сохраняется.

```text
Account
  ↓
Universe
  ↓
Portfolio Context
  ↓
Market Data
  ↓
Canonical Analysis
  ↓
Opportunity result
  ↓
Decision / ranking
  ↓
Trade Plan / Position Sizing
  ↓
Allocation
  ↓
UI / execution preparation
```

В рамках версии не меняются бизнес-сценарии:

- поиск возможностей без предварительного выбора инструмента;
- фильтрация доступных для торговли инструментов;
- исключение уже удерживаемых позиций из market universe;
- отдельный portfolio scope;
- ранжирование возможностей;
- передача BUY-кандидатов дальше по существующему flow;
- обработка WAIT/HOLD;
- исключение PASS;
- подготовка allocation/execution.

Позиционный контекст используется для формирования universe и downstream portfolio constraints, но не должен изменять сам canonical Trading Path result.

---

### Block 3 — Canonical Result → Opportunity Contract

`OpportunitySearchResult` должен получать значения из canonical result, а не пересчитывать их.

Обязательные переносимые поля, где они доступны:

- instrument UID;
- ticker;
- Trading Path / strategy family;
- hypothesis;
- regime;
- volatility bucket;
- direction;
- horizon;
- validation status;
- statistical validity;
- overlap validity;
- multiple-testing validity;
- expected value;
- risk score;
- risk gate;
- opportunity score;
- confidence;
- canonical decision;
- current state;
- reason codes / explanation.

Допустимы только форматирование, агрегация и consumer-specific представление.

Недопустимо:

- пересчитывать opportunity score;
- пересчитывать confidence;
- выбирать другую стратегию вместо canonical best path;
- создавать новый Quality Gate;
- превращать PASS в SELL/REDUCE;
- превращать BUY в HOLD только из-за наличия позиции;
- подменять canonical Decision отдельным consumer decision.

---

## 5. Adaptive Discovery как источник Opportunities

Adaptive Discovery v0.8.14 становится полноценным источником Opportunities.

Adaptive candidate имеет тот же downstream lifecycle, что и fixed candidate:

```text
Adaptive Rule
      ↓
Unified Candidate
      ↓
Pruning
      ↓
Validation
      ↓
OOS
      ↓
EV
      ↓
Risk
      ↓
Opportunity
      ↓
Decision
```

Adaptive path не имеет отдельного scoring/decision pipeline.

Пример фактического runtime-поведения:

```text
CNRU
ADAPTIVE_RULE:
regime=TREND_DOWN AND
sma20_slope <= -0.010869897 AND
distance_to_low_50 <= 0.083793648

Validation: validated
OOS mean return: positive
EV: positive
Risk gate: true
Opportunity: 94.94
Decision: BUY
State: entry_ready
```

Таким образом Adaptive Discovery не является только внутренним экспериментом: его результат способен попасть в production Opportunity Search как canonical BUY opportunity.

При этом малое число OOS observations не должно интерпретироваться как высокая статистическая надёжность только из-за высокого числового confidence. Статистические ограничения v0.8.14 сохраняются.

---

## 6. Quality Gate и статистическая целостность

v0.8.15 не ослабляет Quality Gate.

Canonical path считается допустимым для Opportunity consumer только с сохранением ограничений v0.8.14.

В частности, production adapter обязан учитывать canonical validation:

```text
promotion_status
AND statistical_valid == true
AND explicit overlap failure == false
AND explicit multiple-testing failure == false
```

Quality Gate не может быть заменён consumer-specific упрощённым условием.

### Запрещено

Нельзя повышать количество BUY за счёт:

- удаления statistical gate;
- игнорирования OOS;
- игнорирования overlap;
- игнорирования multiple testing;
- замены canonical decision локальным score threshold;
- использования TRAIN/VALIDATION для имитации OOS.

### Обязательное правило

```text
Adaptive ≠ weaker gate
Adaptive = additional candidate source
```

---

## 7. Temporal / leakage requirements

Canonical runtime обязан сохранять защиту v0.8.14.

### Discovery

Adaptive Discovery использует только TRAIN.

### Threshold selection

Thresholds adaptive rules не должны вычисляться из OOS.

### Validation

Validation использует отдельный temporal range.

### OOS

OOS evaluation использует immutable rule и точный evaluation range.

Forward target не может пересекать границу evaluation range.

### Consumer

Opportunity Search не должен добавлять собственные признаки, рассчитанные из будущего относительно canonical snapshot.

---

## 8. Market-wide execution

Market Opportunities должен работать по полной допустимой торговой universe.

Для `MARKET` scope:

```text
Instrument Catalog
      ↓
trade_available_only=True
      ↓
buy_available=True
      ↓
trading_available=True
      ↓
exclude held positions
      ↓
canonical analysis
```

Поддерживаются instrument kinds:

- SHARE;
- BOND;
- ETF;
- CURRENCY;
- FUTURES;
- OPTION;
- ALL.

Для `PORTFOLIO` scope universe строится из текущих позиций.

Market-wide scan не должен анализировать только заранее выбранные пользователем инструменты.

---

## 9. Ranking

После получения canonical Opportunities сохраняется единый ranking flow.

Приоритет должен отдаваться допустимым торговым решениям:

1. BUY / ADD / REDUCE / SELL;
2. HOLD / WAIT;
3. остальные / недопустимые результаты.

Внутри группы используется `opportunity_score` canonical result.

Ranking не изменяет canonical score и Decision.

---

## 10. Performance и cache

Canonical analysis является вычислительно дорогим этапом.

v0.8.15 использует in-memory cache adapter для повторного обращения к одному и тому же snapshot.

Cache key должен учитывать как минимум:

- instrument UID;
- ticker;
- profile;
- содержимое candle snapshot.

Для идентичного snapshot результат должен быть повторно использован без повторного запуска canonical runtime.

Cache не является persistent analytical storage и не должен заменять versioning/history.

### Force recompute

Запрос `force_recompute` должен действительно обходить cache для соответствующего analysis run.

Это является отдельным regression requirement, поскольку scan-level force recompute не должен тихо возвращать старый cached result.

---

## 11. A/B diagnostics

v0.8.15 содержит диагностический A/B слой.

Он не является вторым production pipeline.

Задача A/B:

```text
Legacy result
      vs
Canonical result
```

на одинаковой выборке и snapshot.

Сравниваются:

- coverage;
- analyzed instruments;
- analysis unavailable;
- total paths;
- adaptive paths;
- fixed paths;
- BUY;
- WAIT;
- average opportunity score.

Основные метрики:

```text
coverage_delta
path_delta
adaptive_paths_added
buy_delta
```

A/B должен позволять ответить на два разных вопроса:

1. Увеличила ли Adaptive Discovery пространство найденных возможностей?
2. Не привело ли это к искусственному росту BUY?

A/B diagnostics не должен влиять на production Decision.

---

## 12. UI requirements

Market Opportunities UI продолжает использовать `OpportunitySearchResult` как внешний business contract.

Обязательные отображаемые поля текущего экрана сохраняются:

- Instrument;
- Decision;
- Best Trading Path;
- Status;
- Opportunity;
- Confidence;
- Expected Value;
- Risk;
- Regime;
- Validation;
- Market Context;
- Paths.

### Canonical source visibility

Для Adaptive path пользователь должен иметь возможность понять, что источник результата — Adaptive Discovery, а не fixed hypothesis.

Минимально это должно быть видно через Trading Path / hypothesis или source metadata.

### Market Context

В текущем UI выявлен отдельный minor gap: backend Market Context рассчитывается и используется downstream, но в таблице Market Opportunities соответствующее поле может оставаться пустым, потому что `OpportunitySearchResult` пока не экспортирует полный context object.

**Это не является блокером canonical integration и не входит в обязательный scope исправления v0.8.15.**

Исправление UI/consumer observability может быть вынесено в minor follow-up.

---

## 13. Error handling

Ошибки анализа конкретного инструмента не должны ломать весь market scan, если существующий scan contract позволяет продолжить обработку.

При невозможности получить корректный canonical analysis возвращается:

```text
ANALYSIS_UNAVAILABLE
```

или соответствующий ERROR status.

Это не является торговым решением.

`ANALYSIS_UNAVAILABLE` / `ERROR` не должны превращаться в BUY, WAIT или PASS только для заполнения таблицы.

---

## 14. Explicit non-goals

В v0.8.15 не входят:

- изменение Adaptive Discovery algorithm;
- изменение feature library;
- изменение fixed hypotheses;
- изменение TRAIN/VALIDATION/OOS split;
- изменение Quality Gate thresholds;
- изменение statistical correction;
- изменение Expected Value formula;
- изменение Risk formula;
- изменение Opportunity formula;
- изменение Decision Engine semantics;
- автоматическая отправка торговых заявок;
- position-aware reinterpretation `BUY → HOLD`;
- reinterpretation `PASS → SELL/REDUCE`;
- полноценное отображение полного Market Context в Market Opportunities UI.

v0.8.15 — **integration/consumer version**, а не новая версия аналитического алгоритма.

---

## 15. Definition of Done

Версия считается выполненной, если подтверждены все пункты:

### Architecture

- [ ] Market Opportunities использует `CanonicalOpportunityAnalysisV015`.
- [ ] Canonical runtime — `AnalysisPathRuntimeServiceV012`.
- [ ] Старый Analysis Pipeline не является production source of truth для Opportunity Search.
- [ ] Fixed и Adaptive используют один downstream pipeline.

### Business flow

- [ ] Market universe сохраняется.
- [ ] Portfolio universe сохраняется.
- [ ] Portfolio context сохраняется.
- [ ] Ranking сохраняется.
- [ ] Allocation flow сохраняется.
- [ ] Execution preparation сохраняется.

### Canonical integrity

- [ ] Canonical Trading Path не пересчитывается consumer-ом.
- [ ] Canonical Decision не переинтерпретируется.
- [ ] Opportunity / confidence не заменяются локальным scoring.
- [ ] Quality Gate не ослаблен.
- [ ] BUY не увеличивается искусственно.

### Adaptive

- [ ] Adaptive rules реально появляются в Opportunity Search.
- [ ] Adaptive BUY может пройти полный canonical chain.
- [ ] Adaptive discovery остаётся TRAIN-only.
- [ ] OOS остаётся leakage-safe.

### Performance

- [ ] Cache работает для одинакового snapshot.
- [ ] Force recompute действительно обходит cache.

### Diagnostics

- [ ] A/B metrics доступны.
- [ ] A/B не влияет на production result.
- [ ] Coverage/path/adaptive/BUY delta измеряются.

### Regression

- [ ] Canonical adapter tests green.
- [ ] Opportunity consumer tests green.
- [ ] Quality Gate tests green.
- [ ] Market-wide scan tests green.
- [ ] Cache tests green.
- [ ] A/B diagnostics tests green.
- [ ] Full regression suite green.

### UI

- [ ] Market Opportunities показывает canonical Decision.
- [ ] Adaptive Trading Path виден в результате.
- [ ] Ranking соответствует canonical opportunity score.
- [ ] Existing portfolio/allocation UI не ломается.
- [ ] Market Context gap зафиксирован как non-blocking minor issue.

---

## 16. Acceptance runtime

Минимальный runtime acceptance должен демонстрировать:

```text
Market Universe
      ↓
Instrument
      ↓
Canonical Analysis
      ↓
Fixed + Adaptive Paths
      ↓
Validation / OOS
      ↓
EV / Risk / Opportunity
      ↓
Canonical Decision
      ↓
Opportunity Search Result
      ↓
Ranking
      ↓
UI
```

На фактическом запуске уже подтверждён важный сценарий Adaptive BUY для CNRU:

```text
ADAPTIVE_RULE
        ↓
validation=validated
        ↓
EV=positive
        ↓
risk_gate=true
        ↓
opportunity=94.94
        ↓
decision=BUY
        ↓
state=entry_ready
```

Это подтверждает, что Adaptive Discovery в v0.8.15 действительно становится источником production Opportunity, а не только внутренним candidate generator.

---

## 17. Итоговая архитектурная граница

Финальная граница v0.8.15:

```text
              CANONICAL ANALYSIS

TRAIN
 ↓
Fixed + Adaptive Discovery
 ↓
Unified Candidates
 ↓
Pruning / Statistical Integrity
 ↓
Validation
 ↓
OOS
 ↓
EV
 ↓
Risk
 ↓
Opportunity
 ↓
Decision
 ↓
TradingPathAnalysisV012
              │
              │ canonical result
              ▼
       OPPORTUNITY CONSUMER
              │
       Universe / Portfolio
              │
       Ranking / Allocation
              │
              ▼
             UI
              │
              ▼
          Execution
```

**Canonical Analysis остаётся единственным источником аналитической истины.**

Opportunity Consumer может организовывать, ранжировать и подготавливать результат к дальнейшему использованию, но не должен создавать второй смысл аналитического результата.

---

## 18. Version conclusion

v0.8.15 закрывает архитектурный разрыв между canonical Trading Path Analysis v0.8.14 и Market Opportunities.

Главный результат версии:

> **Adaptive Discovery теперь может напрямую становиться реальной рыночной Opportunity через тот же canonical downstream pipeline, который используется Fixed hypotheses.**

При этом сохраняются temporal integrity, Quality Gate, ranking, portfolio flow и существующие бизнес-сценарии.

Следующий отдельный minor follow-up может закрыть observability gap с полным Market Context в таблице Market Opportunities, но этот gap не должен менять canonical analysis или торговую семантику.