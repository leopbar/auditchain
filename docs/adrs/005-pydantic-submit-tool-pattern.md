# ADR 005: Pydantic "Submit Tool" Pattern

## Status
Accepted

## Context
When an agent finishes its node in the graph, it must hand off its results to the next node. If we rely on the LLM's text output, we have to use regex or expensive "LLM-based parsing" to extract data.

## Decision
We implemented a **Submit Tool Pattern**. Every agent has a tool like `submit_collector_data` or `submit_reconciliation_report`. To exit a node, the agent MUST call this tool with arguments that match a Pydantic schema.

## Consequences
- **Pros**:
    - **Guaranteed Structure**: If the tool is called, the data is valid JSON that matches our internal types.
    - **Strict Validation**: Pydantic handles type checking, range validation, and default values.
    - **Explicit Handoff**: It makes the "completion" of an agent's task an explicit, traceable event.
- **Cons**:
    - **Token Usage**: Defining complex tool schemas in the system prompt consumes some input tokens.
    - **Retry Logic**: If the LLM misses a required field, the node must catch the `ValidationError` and tell the agent to try again (handled by LangChain/LangGraph logic).
