# Edward v0.8.5 — Research Discovery

## 1. Цель версии

v0.8.5 расширяет анализ инструмента исследовательским слоем **Research Discovery**.

Цель версии — не добиться прохождения Quality Gate конкретной стратегии и не изменить торговый допуск. Цель — получить проверяемые доказательства того, что в историческом поведении инструмента существуют повторяемые рыночные структуры, на которых потенциально можно строить торговую гипотезу.

Quality Gate, Robust Walk-Forward, TRAIN viability, OOS/production separation и правило `NO TRADE` не изменяются.

## 2. Проблема v0.8.4

v0.8.4 проверяет четыре стратегии: Trend Following, Momentum, Breakout и Mean Reversion. SBER показал, что Breakout может иметь положительное OOS качество, но остаётся FAIL из-за return consistency 58.33% при пороге 60%. Это является основанием для дальнейшего исследования условий работы edge, а не для ослабления Quality Gate.

## 3. Новый исследовательский вопрос

Вместо вопроса «какая из четырёх стратегий проходит Gate?» добавляется вопрос:

> «Есть ли после заранее определённого рыночного события статистически отличимое от baseline поведение цены на горизонтах 1/3/5/10/20 свечей?»

Исследование является event study и не является торговой рекомендацией.

## 4. Гипотезы v0.8.5

1. `BREAKOUT_EXPANSION` — выход из сжатия с расширением диапазона.
2. `PULLBACK_RECLAIM` — откат внутри восходящей структуры и возврат выше fast average.
3. `IMPULSE_CONTINUATION` — сильный импульс с подтверждением продолжения.
4. `SHOCK_REVERSAL` — экстремальное отрицательное движение и последующая реакция.
5. `GAP_REVERSAL` — сильный отрицательный gap и последующая реакция.
6. `RANGE_BREAK` — выход из узкого диапазона.

Пороговые определения гипотез фиксированы в коде и не оптимизируются по конкретному инструменту.

## 5. Horizons

Каждое событие исследуется на горизонтах 1, 3, 5, 10 и 20 свечей.

Для каждого горизонта сохраняются:

- observations;
- mean forward return;
- median forward return;
- win rate;
- unconditional baseline mean return;
- excess return относительно baseline.

## 6. Запреты

v0.8.5 не:

- меняет Quality Gate;
- снижает пороги Quality Gate;
- выбирает production strategy;
- выбирает production parameters;
- использует OOS для подбора гипотез;
- превращает сильнейшую гипотезу в recommendation;
- подгоняет пороги событий под SBER.

## 7. Интеграция

`AnalysisServiceV08` запускает Research Discovery после определения режима рынка и до существующего Robust Walk-Forward. Результат сохраняется в `AnalysisV08Diagnostics.research_discovery`.

Основной `AnalysisResult` и торговая recommendation flow сохраняются совместимыми с v0.8.4.

## 8. Логирование

Обязательные маркеры:

- `[V085 DISCOVERY START]` — начало discovery;
- `[V085 DISCOVERY HYPOTHESIS]` — итог каждой гипотезы;
- `[V085 DISCOVERY HORIZON]` — детализация по горизонту;
- `[V085 DISCOVERY RESULT]` — завершение discovery;
- `[V085 DISCOVERY SUMMARY]` — интеграция результата в AnalysisService.

Логи должны позволять вручную проверить, сколько событий найдено, на каких горизонтах появился excess return и не было ли влияния discovery на Quality Gate.

## 9. Acceptance criteria

1. Все существующие v0.8.4 Quality Gate rules остаются неизменными.
2. При достаточной истории запускаются все шесть discovery hypotheses.
3. Для каждой гипотезы доступны пять горизонтов.
4. Baseline рассчитывается независимо от событий.
5. Недостаточная история не вызывает исключение discovery и явно логируется.
6. Discovery не создаёт recommendation и не меняет QG status.
7. Автотесты покрывают полный набор гипотез, horizons, gap detection, shock detection и insufficient-data path.
8. Полный анализ содержит discovery result в diagnostics.

## 10. Следующий этап

После проверки v0.8.5 на SBER и других инструментах отдельным этапом может быть добавлен второй слой: conditional event study (`event × regime × volatility × direction`) и затем event-based backtest с независимым WF/QG. Эти функции не входят в первую интеграцию v0.8.5.
