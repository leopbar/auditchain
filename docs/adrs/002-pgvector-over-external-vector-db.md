# ADR 002: Use pgvector inside PostgreSQL

## Status
Accepted

## Context
The **Investigator Agent** requires vector search capabilities to perform RAG over 10-K disclosures. We needed to choose between a dedicated vector database (Pinecone, Weaviate) or an extension of our existing relational database.

## Decision
We chose **PostgreSQL with the pgvector extension**.

## Consequences
- **Pros**:
    - **Single Source of Truth**: All data (companies, filings, audit history, and embeddings) lives in one database. No need to manage cross-DB consistency.
    - **Transactional Integrity**: We can perform standard SQL joins between metadata and vectors in a single query.
    - **Operational Simplicity**: No extra service to manage, back up, or pay for during the portfolio phase.
    - **HNSW Support**: Performance is sufficient for the ~10,000-100,000 chunks expected in this scope.
- **Cons**:
    - **Scalability**: While HNSW in pgvector is fast, dedicated engines like Pinecone are specialized for billion-scale vectors. We can migrate later if we hit that scale.
