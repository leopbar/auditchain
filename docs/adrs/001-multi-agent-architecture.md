# ADR 001: Multi-Agent Architecture via LangGraph

## Status
Accepted

## Context
Traditional LLM applications often use a single prompt (monolithic) or a simple chain to perform tasks. For forensic auditing, the reasoning required is too broad for a single prompt: it requires mathematical precision (reconciliation), quantitative modeling (Beneish/Altman), and qualitative search (RAG).

## Decision
We decided to implement a multi-agent architecture using **LangGraph**. The system is split into 5 specialized agents:
1. **Collector**: Data retrieval.
2. **Reconciler**: Math/consistency.
3. **Quant Analyst**: Financial models.
4. **Investigator**: RAG/Disclosures.
5. **Supervisor**: Executive consolidation.

## Consequences
- **Pros**:
    - **Specialization**: Each agent has a focused system prompt and a specific set of tools.
    - **Observability**: We can see exactly which agent failed or found a specific red flag.
    - **Cost Control**: Tool-heavy agents use `gpt-4o-mini`, while only the critical thinking node uses `gpt-4o`.
    - **Debugging**: It is much easier to tune the "Reconciler" prompt without affecting the "Investigator" logic.
- **Cons**:
    - **Latency**: Sequential execution of 5 nodes takes more time (~2 minutes).
    - **Complexity**: Managing state and communication between nodes adds overhead to the codebase.
