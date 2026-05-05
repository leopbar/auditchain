# ADR 003: Server-Sent Events (SSE) for Real-time Streaming

## Status
Accepted

## Context
The frontend needs to show real-time progress as agents work. We need a way to push data from the server to the client as events happen.

## Decision
We chose **Server-Sent Events (SSE)** instead of WebSockets.

## Consequences
- **Pros**:
    - **Simplicity**: SSE uses the standard HTTP protocol. No need for a custom handshake or managing complex "ping/pong" frames.
    - **Automatic Reconnection**: Browsers natively handle reconnections for SSE.
    - **Resource Efficiency**: SSE is lighter than a full-duplex WebSocket connection for a unidirectional data flow.
- **Cons**:
    - **Unidirectional**: SSE only flows from server to client. For AuditChain, this is sufficient. If we ever need to "chat" back to the agent in the middle of a run, we would need to supplement this with REST calls or migrate to WebSockets.
