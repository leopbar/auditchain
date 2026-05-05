"""Investigation tools for semantic search and textual audit analysis.

Enables the Investigator Agent to perform vector similarity searches 
on SEC filing disclosures using pgvector and OpenAI embeddings.
"""

from typing import Any, Optional
import json

from langchain_core.tools import tool
from sqlalchemy import text
from openai import OpenAI

from auditchain.core.config import get_settings
from auditchain.core.logging import get_logger
from auditchain.data.database import get_session

logger = get_logger(__name__)
settings = get_settings()

DEFAULT_TOP_K = 3
EMBEDDING_MODEL = "text-embedding-3-small"


import time

def _embed_query(query: str) -> list[float]:
    """Generates embedding for a search query using OpenAI."""
    # Small delay to avoid rate limiting bursts
    time.sleep(0.5)
    client = OpenAI(
        api_key=settings.openai_api_key.get_secret_value() if settings.openai_api_key else None,
        timeout=15.0
    )
    response = client.embeddings.create(
        input=query,
        model=EMBEDDING_MODEL,
        dimensions=1536
    )
    return response.data[0].embedding


def _search_by_embedding(
    filing_id: int, 
    query_embedding: list[float], 
    section: Optional[str] = None, 
    top_k: int = DEFAULT_TOP_K
) -> list[dict]:
    """Performs a vector similarity search in the database."""
    # Convert list to pgvector compatible string format "[0.1, 0.2, ...]"
    vec_str = "[" + ",".join(map(str, query_embedding)) + "]"
    
    sql = text("""
        SELECT content, section, chunk_index, 1 - (embedding <=> CAST(:query_vec AS vector)) as similarity
        FROM disclosures
        WHERE filing_id = :filing_id
        AND (:section IS NULL OR section = :section)
        ORDER BY embedding <=> CAST(:query_vec AS vector)
        LIMIT :top_k
    """)
    
    results = []
    with get_session() as session:
        cursor = session.execute(sql, {
            "filing_id": filing_id,
            "query_vec": vec_str,
            "section": section,
            "top_k": top_k
        })
        
        for row in cursor:
            results.append({
                "content": row.content,
                "section": row.section,
                "chunk_index": row.chunk_index,
                "similarity": float(row.similarity)
            })
            
    return results


def _format_search_results(results: list[dict]) -> str:
    """Formats search results into a readable string for the LLM."""
    if not results:
        return "No relevant disclosures found for this query."
    
    output = []
    for i, res in enumerate(results, 1):
        section_name = res["section"].upper()
        sim_pct = res["similarity"] * 100
        content = res["content"].strip()
        if len(content) > 300:
            content = content[:300] + "... [TRUNCATED]"
            
        output.append(
            f"--- Result {i} (Section: {section_name}, Similarity: {sim_pct:.1f}%) ---\n"
            f"{content}\n"
        )
    
    return "\n".join(output)


@tool
def search_disclosures(filing_id: int, query: str, section: Optional[str] = None, top_k: int = 3) -> str:
    """Search through a company's SEC filing disclosures using semantic similarity. 
    Returns the most relevant text chunks matching the query. 
    Optionally filter by section: 'mdna', 'risk_factors', 'notes_to_financials', 'business', 'legal_proceedings'. 
    Use this tool to investigate specific topics mentioned in the filing text.
    """
    try:
        logger.info("search_disclosures_called", filing_id=filing_id, query=query[:50], section=section)
        
        query_embedding = _embed_query(query)
        results = _search_by_embedding(filing_id, query_embedding, section, top_k)
        
        return _format_search_results(results)
    except Exception as e:
        logger.error("search_disclosures_failed", error=str(e))
        return f"Error performing semantic search: {str(e)}"


@tool
def find_related_parties(filing_id: int) -> str:
    """Search for mentions of related party transactions, affiliated entities, or dealings 
    with subsidiaries and associated companies in the filing. 
    This is a key fraud indicator — undisclosed related party transactions were central 
    to the Enron and Valeant/Philidor scandals.
    """
    try:
        query = "related party transactions, affiliated entities, subsidiaries, special purpose entities, variable interest entities"
        logger.info("find_related_parties_called", filing_id=filing_id)
        
        query_embedding = _embed_query(query)
        results = _search_by_embedding(filing_id, query_embedding, section=None, top_k=4)
        
        return _format_search_results(results)
    except Exception as e:
        logger.error("find_related_parties_failed", error=str(e))
        return f"Error investigating related parties: {str(e)}"


@tool
def detect_language_patterns(filing_id: int) -> str:
    """Search for potentially evasive, vague, or concerning language patterns in the filing. 
    Looks for hedging language, unusual disclaimers, abrupt changes in accounting policies, 
    and other linguistic red flags that may indicate management is obscuring information.
    """
    try:
        query = "change in accounting policy, restatement, material weakness, going concern, significant uncertainty, management override, off-balance sheet arrangements, non-GAAP adjustments"
        logger.info("detect_language_patterns_called", filing_id=filing_id)
        
        query_embedding = _embed_query(query)
        results = _search_by_embedding(filing_id, query_embedding, section=None, top_k=4)
        
        return _format_search_results(results)
    except Exception as e:
        logger.error("detect_language_patterns_failed", error=str(e))
        return f"Error detecting language patterns: {str(e)}"
