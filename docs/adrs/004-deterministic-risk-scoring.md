# ADR 004: Deterministic Risk Scoring Formula

## Status
Accepted

## Context
We need to assign a numerical "Risk Score" to each audit. Asking an LLM to generate this number results in "vibe-based" metrics that vary wildly between runs.

## Decision
We implemented a **deterministic scoring formula** based on red flags:
- **CRITICAL**: 25 points
- **HIGH**: 15 points
- **MEDIUM**: 8 points
- **LOW**: 3 points
- **INFO**: 1 point

The final score is `sum(flag_points)` capped at 100.

## Consequences
- **Pros**:
    - **Reproducibility**: The same set of findings will always result in the same score.
    - **Auditability**: You can show the user exactly why the score is 48/100 (e.g., "3 High flags and 1 Medium flag").
    - **No Hallucination**: The LLM doesn't "hallucinate" the score; it only detects the evidence.
- **Cons**:
    - **Rigidity**: A company with 10 "Low" flags might get a higher score than a company with 2 "High" flags, even if the latter is riskier in context. This is a trade-off for consistency.
