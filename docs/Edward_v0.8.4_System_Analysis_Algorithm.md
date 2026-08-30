# Edward v0.8.4 — системный анализ алгоритма

## Назначение

v0.8.4 усиливает decision pipeline v0.8.3 без ослабления Quality Gate и без использования будущего OOS для выбора production-параметров.

Целевая цепочка:

```text
market regime
  -> strategy routing
  -> Train economic viability
  -> robust parameter selection
  -> OOS validation
  -> transfer/shadow audit
  -> generalization evidence
  -> Quality Gate
  -> strategy / NO TRADE
```

## Реализовано в текущем срезе

### Train Economic Viability

Перед robust ranking кандидат обязан пройти Train-only фильтр:

```text
Train excess return > 0
AND Train drawdown <= profile limit
AND Train trades >= configured minimum
```

Отрицательный Train excess больше не может быть компенсирован высоким Sharpe, Sortino или neighborhood stability.

Если ни один кандидат окна не проходит viability, production parameter selection этого окна прекращается, а стратегия помечается как invalid для текущего WF-прогона.

### Logging

Для последующего аудита расчётов введены:

```text
[V084 WF START]
[V084 WF VIABILITY FILTER]
[V084 WF VIABILITY]
[V084 WF CANDIDATE]
[V084 WF VIABILITY RESULT]
[V084 WF NO VIABLE PARAMETER]
[V084 WF VIABLE SELECTION]
[V084 WF RESULT]
[V084 WF INVALID STRATEGY]
[V084 ROBUSTNESS BREAKDOWN]
[V084 ROBUSTNESS ACTIVITY]
[V084 QG CHECK]
[V084 QG RESULT]
```

Логи должны позволять восстановить причину допуска/отбраковки каждого Train candidate.

## Не реализовано в первом срезе

Следующие части v0.8.4 выполняются после прохождения regression baseline:

1. Regime-aware strategy router.
2. Regime-conditioned OOS evidence.
3. Strategy archetypes: persistent / burst / mean-reversion.
4. Activity-aware admissibility.
5. Parameter zones.
6. Generalization diagnostics.
7. Исправление downstream semantics для failed evidence strategy.

## Ограничения

- OOS не используется для выбора production parameters.
- Transfer остаётся shadow/audit механизмом.
- Пороги Quality Gate v0.8.3 в первом срезе не изменяются.
- Торговые сигналы стратегий не переписываются.
- Execution/backtest model не меняется.

## Критерий успеха

Экономический viability gate считается корректно интегрированным, если:

- отрицательный Train excess candidate не выбирается при наличии viable candidate;
- excessive drawdown и insufficient activity блокируют candidate;
- отсутствие viable candidates приводит к invalid strategy, а не к выбору наименее плохого параметра;
- OOS/transfer остаются после Train selection;
- каждый decision path имеет диагностическое логирование.
