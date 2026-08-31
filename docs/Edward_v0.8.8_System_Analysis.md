# Edward v0.8.8 — System Analysis and Scope

## 1. Purpose

Version 0.8.8 introduces a separate Trading Paths research layer on top of the existing Edward analysis stack. The purpose is not to weaken or bypass the existing v0.8.7 strategy Quality Gate, but to discover conditional trading paths when the legacy strategy layer cannot produce a trading recommendation.

The core business question is:

> Can Edward find a specific, condition-dependent trading path that has sufficient evidence to be considered for trading, instead of ending the analysis with `recommendation=None` solely because every predefined strategy failed its Quality Gate?

## 2. Architectural principle

The v0.8.8 layer is additive and backward-compatible.

Existing flow remains intact:

```text
Market Data
  -> AnalysisServiceV08
  -> legacy strategies
  -> Robust Walk-Forward / Quality Gate
  -> legacy recommendation
```

Trading Paths runs as an additional research path:

```text
Market Data
  -> existing AnalysisServiceV08
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
  -> PROMOTED / RESEARCH_ONLY / REJECTED
```

The legacy recommendation must remain unchanged by the research layer.

## 3. Scope delivered in v0.8.8

### 3.1 Discovery

- Reuse the existing Conditional Discovery capability from v0.8.6/v0.8.7.
- Discover conditional combinations of hypothesis, regime, volatility, direction and horizon.
- Preserve the existing event observations rather than creating a parallel market-data model.

### 3.2 Candidate generation

Implemented Trading Path candidate generation from discovered evidence.

Each candidate carries the relevant research conditions and sample information and starts in research status.

### 3.3 Ranking and deduplication

Implemented deterministic candidate ranking and deduplication.

The SBER runtime test demonstrated:

```text
candidates=28
ranked=28
```

### 3.4 Event backtest

Implemented event-driven path backtesting with explicit direction and horizon handling.

The backtest is based on the existing candle model and supports the Trading Path rule contract.

### 3.5 Economic validation

Validation includes the existing Trading Path trading-cost model, including commission and slippage inputs.

### 3.6 Statistical validation

Implemented statistical evidence including:

- trade count;
- mean return;
- median return;
- standard error;
- confidence interval;
- positive-mean checks.

### 3.7 Temporal evidence

Implemented temporal block evidence to distinguish a broadly persistent effect from one concentrated in a single part of the sample.

Temporal stability is intentionally conservative: all required temporal blocks must be positive for the evidence to be considered temporally stable.

### 3.8 Overlap Audit

Implemented explicit audit of dependency between paths:

- event overlap;
- holding-window overlap.

The audit is evidence, not a ranking shortcut.

### 3.9 Multiple Testing

Implemented family-level multiple-testing evidence for the candidate set, including adjusted confidence intervals and pass/fail status.

This is required because Discovery deliberately searches multiple conditional paths; the best observed path cannot be treated as an independent hypothesis test.

### 3.10 Promotion Gate

Implemented a conservative promotion gate with three states:

```text
PROMOTED
RESEARCH_ONLY
REJECTED
```

The gate evaluates the evidence assembled by the research pipeline rather than changing the legacy Quality Gate.

Typical blocking reasons include:

```text
LOW_SAMPLE
NON_POSITIVE_NET_RETURN
CI95_NOT_ABOVE_ZERO
TEMPORAL_EVIDENCE_REQUIRED
EVENT_OVERLAP_TOO_HIGH
HOLDING_OVERLAP_TOO_HIGH
MULTIPLE_TESTING_FAILED
```

### 3.11 Integration

The Trading Path research result is exposed by the analysis adapter and integrated into the existing analysis pipeline without replacing the legacy recommendation.

### 3.12 Observability and tests

The implementation includes detailed v0.8.8 runtime logging and regression coverage for candidate generation, backtest, validation, evidence, overlap, multiple testing, promotion and adapter integration.

The full local regression suite is green at the current scope checkpoint.

## 4. SBER end-to-end result

The first real runtime validation of the complete v0.8.8 path was performed on SBER.

The result was:

```text
candidates=28
ranked=28
validated=28
overlap_audited=28
promotion_evaluated=28
recommendation_unchanged=None
```

This proves that the complete research pipeline is operational end-to-end.

The research layer found multiple candidates with positive observed returns. Examples included Breakout Expansion and Impulse Continuation paths with positive mean returns and, for some candidates, conventional CI95 intervals above zero.

However, no candidate was promoted to production trading status in this run.

This is an outcome of the evidence gates, not a failure of the implementation.

## 5. Important SBER findings

The strongest observed candidates were not sufficient for promotion because several independent-evidence requirements failed simultaneously.

The runtime showed, among other cases:

- positive observed mean return;
- conventional CI95 above zero for some paths;
- insufficient temporal stability for some paths;
- event overlap of 1.0 for many paths;
- holding overlap of 1.0 for many paths;
- failure of the multiple-testing requirement after considering the full candidate family.

Therefore:

```text
profitable observed path
    !=
statistically independent and temporally stable path
    !=
production-ready trading path
```

This distinction is a deliberate design property of v0.8.8.

## 6. Relationship with legacy v0.8.7 analysis

The SBER runtime also confirmed that the legacy strategy Quality Gate continues to operate independently.

The existing strategies were blocked by their established requirements, including return consistency and robustness thresholds. The legacy result remained:

```text
recommendation=None
score=0
```

The v0.8.8 research layer does not override this result.

This preserves backward compatibility while allowing Edward to answer a broader research question: whether a conditional trading path exists even when the predefined strategy templates do not pass their Quality Gate.

## 7. Scope conclusion

The engineering scope defined for v0.8.8 Trading Paths is considered substantially complete at this checkpoint.

Completed capabilities:

- discovery;
- candidate generation;
- ranking;
- backtest;
- economics;
- statistics;
- temporal evidence;
- overlap audit;
- multiple testing;
- promotion gate;
- adapter/pipeline integration;
- logging;
- regression tests;
- real SBER end-to-end validation.

The fact that SBER produced zero `PROMOTED` paths does **not** mean the v0.8.8 engineering scope failed. It means the implemented evidence framework did not find a candidate that met its conservative production criteria on that dataset/run.

## 8. What remains outside the completed v0.8.8 scope

The following are research questions for a subsequent scope rather than reasons to weaken v0.8.8:

1. Determine why overlap is so frequently measured as 1.0 and verify that the audit measures the intended notion of independent trading episodes.
2. Improve temporal validation using genuinely independent out-of-sample time blocks.
3. Reassess the statistical family definition for multiple testing when candidate paths are strongly dependent.
4. Evaluate Trading Paths across a broader instrument universe and multiple market regimes.
5. Define the production hand-off contract for a path that passes all evidence gates.
6. Expand the UI to explain the path, evidence, promotion status and blocking reasons to the user.

These items must not be addressed by simply lowering CI, overlap, sample-size or multiple-testing requirements merely to obtain a `PROMOTED` result.

## 9. Final architectural conclusion

Version 0.8.8 changes Edward from a system that can effectively answer:

> "Did one of the predefined strategies pass the Quality Gate?"

into a system that can additionally answer:

> "Which conditional trading paths were observed, how profitable were they, how stable were they, how dependent were they, and is there enough evidence to promote one?"

The key success criterion for the current scope is therefore the existence of a complete, auditable, backward-compatible Trading Path research pipeline — not the artificial production promotion of a candidate.
