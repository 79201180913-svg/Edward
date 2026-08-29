# Edward v0.8.3 — системный анализ алгоритма

## 1. Назначение

Документ фиксирует фактическую архитектуру и алгоритм анализа Edward на состоянии ветки `version-0.8.3-active-window-audit` перед слиянием в `main`, а также определяет направление следующего изменения анализа.

Цель анализа — выбрать торговую стратегию и параметры без использования будущего OOS в процессе выбора, проверить устойчивость результата и передать результат в Quality Gate. OOS используется для проверки качества выбора, а не для подгонки решения.

## 2. Фактический pipeline

```text
Instrument
  -> market candles
  -> AnalysisPipelineServiceV08
  -> AnalysisServiceV08
  -> regime detection
  -> per-strategy Robust Walk-Forward
  -> parameter selection on TRAIN
  -> OOS evaluation
  -> WF transfer/shadow audit
  -> robustness diagnostics
  -> Quality Gate
  -> strategy/recommendation
```

В текущей реализации основной класс анализа называется `AnalysisServiceV08`; runtime показывает версию core analysis `0.8.0`. Версия 0.8.3 является надстройкой, добавляющей Walk-Forward, robust parameter selection, transfer audit, diagnostics и Quality Gate.

## 3. Входные данные

Для инструмента анализ получает:

- исторические свечи;
- профиль горизонта (`long_term`, `medium_term`, `speculative`);
- risk profile;
- horizon;
- доступные стратегии;
- parameter grid каждой стратегии.

Для SBER в проверенном запуске использовалось 1767 дневных свечей. Для `medium_term`: train = 240, test = 60, ожидается 25 WF-окон.

## 4. Определение режима рынка

Перед стратегическим анализом определяется рыночный regime и confidence. В проверенном запуске SBER получил:

```text
regime = TRANSITION
confidence = 57.09
```

Текущая реализация определяет режим, но пока не использует его как полноценный маршрутизатор стратегий. Все четыре стратегии продолжают конкурировать внутри общего анализа.

## 5. Стратегии

Текущий набор:

1. Trend Following
2. Momentum
3. Breakout
4. Mean Reversion

Для каждой стратегии выполняется Robust Walk-Forward.

## 6. Walk-Forward

Для каждого окна:

1. Берётся train-отрезок.
2. На train запускаются все кандидаты parameter grid.
3. Для каждого кандидата рассчитываются return, benchmark, excess return, Sharpe, Sortino, drawdown, trades, exposure, turnover и win rate.
4. Выбирается production parameter set.
5. Выбранный набор переносится на следующий OOS test-отрезок.
6. Все результаты окна сохраняются для последующей агрегации.

Ключевой принцип: OOS не должен участвовать в выборе production-параметров.

## 7. Robust parameter selection

В v0.8.3 введён выбор устойчивой области параметров вместо механического выбора максимального Train excess return.

Текущий composite score использует:

- excess return — 40%;
- Sharpe — 20%;
- Sortino — 15%;
- return/drawdown — 10%;
- neighborhood stability — 15%.

Neighborhood stability оценивает согласованность близких параметров.

### Проблема текущей реализации

Composite score может дать высокий результат кандидату, у которого Train excess return отрицателен, если его Sharpe/Sortino/drawdown/stability достаточно сильны. Для торгового решения это нежелательно: устойчивость должна уточнять экономически жизнеспособный кандидат, а не заменять его.

Следовательно, следующий этап должен ввести предварительный economic viability gate внутри выбора параметров:

```text
Train excess > 0
AND допустимый drawdown
AND минимальная активность
    -> кандидат допускается в robust ranking
```

Если ни один кандидат не проходит viability, стратегия не получает валидный production parameter set.

## 8. OOS и transfer

После выбора production parameters выполняется OOS.

Дополнительно система сравнивает:

- production/train-selected parameters;
- OOS winner;
- transfer/shadow-selected parameters.

Transfer сейчас используется как shadow/audit-механизм и не должен автоматически менять production решение без доказанной устойчивой пользы.

Это важно, потому что в наблюдавшемся SBER-прогоне transfer иногда выбирал другой набор, но изменение не гарантировало улучшения OOS.

## 9. Robustness

Robustness агрегирует несколько характеристик:

- return consistency;
- risk consistency;
- Sharpe consistency;
- parameter stability;
- performance consistency.

Для Breakout в проверенном SBER-прогоне итоговый robustness был около 58.77, при этом стратегия имела положительную OOS доходность около 1.00% и Sharpe около 0.44.

Для Momentum robustness был около 56.08 при OOS около 0.63% и 14 положительных из 25 окон.

Trend Following и Mean Reversion показали отрицательную OOS доходность.

## 10. Quality Gate

Quality Gate проверяет уже полученный результат стратегии. В `medium_term` текущие пороги включают минимальную стабильность 60% и максимальный drawdown 25%; конкретные проверки также включают WF windows, mean test return, mean test drawdown, mean test Sharpe, return consistency и robustness score.

Принципиально Quality Gate не должен использоваться для компенсации плохого parameter selection. Сначала должен быть корректно выбран экономически валидный набор параметров, затем проверяется его устойчивость.

## 11. Фактический результат SBER

По проверенному запуску:

| Стратегия | OOS return | Sharpe | Положительные окна | Robustness |
|---|---:|---:|---:|---:|
| Trend Following | ~ -0.78% | ~ -0.10 | 3/25 | ~39.18 |
| Momentum | ~ +0.63% | ~ +0.16 | 14/25 | ~56.08 |
| Breakout | ~ +1.00% | ~ +0.44 | 9/25 | ~58.77 |
| Mean Reversion | ~ -2.89% | ~0.00 | 5/25 | ~42.73 |

Вывод: Breakout имеет лучший абсолютный результат, но Momentum имеет более равномерное количество положительных OOS-окон. Ни одна стратегия не должна автоматически считаться пригодной к торговле только потому, что она лучшая среди четырёх.

## 12. Основные системные проблемы анализа

### P1. Parameter selection

Текущий robust score способен предпочесть статистически красивый, но экономически отрицательный Train candidate.

**Решение:** economic viability как обязательный первый фильтр.

### P2. Regime awareness

Regime определяется, но пока недостаточно влияет на выбор стратегии.

**Решение:** использовать regime как routing/prioritization layer:

```text
TRENDING    -> Trend Following / Breakout
MOMENTUM    -> Momentum
MEAN_REVERT -> Mean Reversion
TRANSITION  -> conservative selection / NO TRADE
```

Это не означает жёстко запрещать остальные стратегии; regime должен задавать приоритет и допустимость, а фактическое качество подтверждается WF и Quality Gate.

### P3. NO TRADE

Если ни одна стратегия не проходит Quality Gate, система должна явно выдавать `NO TRADE`, а не просто выбирать лучшую из непройденных стратегий как торговую возможность.

### P4. Separation of concerns

Необходимо сохранить разделение:

```text
parameter selection -> economic viability + robustness
OOS -> unbiased validation
transfer -> shadow evidence
Quality Gate -> trading admissibility
recommendation -> final decision
```

## 13. Целевой алгоритм следующей итерации

```text
1. Detect market regime

2. Determine strategy priority by regime

3. For every allowed/prioritized strategy:
   3.1 Run WF train candidates
   3.2 Apply economic viability filter
   3.3 Rank viable candidates by robust score
   3.4 Select production parameters
   3.5 Run OOS
   3.6 Record OOS result

4. Aggregate WF evidence

5. Apply Quality Gate

6. If at least one strategy passes:
      select best admissible strategy
   else:
      NO TRADE

7. Produce recommendation with:
      strategy
      parameters
      opportunity
      confidence
      risk
      evidence
```

## 14. Что не следует делать

Не следует:

- снижать Quality Gate только ради прохождения Breakout;
- использовать OOS winner для выбора production parameters;
- добавлять новые диагностические метрики без влияния на decision flow;
- считать высокий robustness достаточным при отрицательном Train excess;
- автоматически включать transfer в production без доказательства OOS improvement;
- выбирать стратегию только по максимальной доходности.

## 15. Критерий успеха следующей версии

Следующая версия анализа считается улучшением только если она показывает на независимом OOS:

- меньше selection gap;
- больше устойчивых положительных окон;
- не ухудшает drawdown/risk;
- не использует OOS для выбора;
- чаще корректно выдаёт `NO TRADE`, когда доказательств недостаточно;
- улучшает качество реального выбора стратегии, а не только диагностические показатели.

## 16. Итог

v0.8.3 уже содержит полноценный слой Robust Walk-Forward и Quality Gate. Главная следующая задача — не расширять диагностику, а превратить анализ в последовательную decision system:

**режим рынка → экономически жизнеспособные параметры → robust selection → OOS validation → Quality Gate → стратегия или NO TRADE.**

Именно эта последовательность является целевой архитектурой алгоритма анализа Edward.
