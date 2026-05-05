"""Text Ingestion Pipeline for SEC filings.

Extracts text from HTML filings, identifies key sections (MD&A, Risk Factors, etc.),
chunks the text, generates embeddings via OpenAI, and saves to the PostgreSQL database.
"""

import os
import re
from pathlib import Path
from typing import Any

import tiktoken
from bs4 import BeautifulSoup
from openai import OpenAI
from sqlalchemy import select, func

from auditchain.core.config import get_settings
from auditchain.core.logging import get_logger
from auditchain.data.database import get_session
from auditchain.data.models import FilingORM, DisclosureORM, CompanyORM

logger = get_logger(__name__)

# Constants
CHUNK_SIZE_TOKENS = 400
CHUNK_OVERLAP_TOKENS = 50
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536

# Regex patterns for identifying sections
# Note: These are simplified patterns; real-world SEC filings vary significantly.
SECTION_PATTERNS = {
    "mdna": [
        r"(?i)item\s*7[.\s].*management.{0,5}s discussion and analysis",
        r"(?i)management.{0,5}s discussion and analysis of financial condition",
    ],
    "risk_factors": [
        r"(?i)item\s*1a[.\s].*risk factors",
        r"(?i)risk factors",
    ],
    "notes_to_financials": [
        r"(?i)notes\s+to\s+(consolidated\s+)?financial\s+statements",
    ],
    "business": [
        r"(?i)item\s*1[.\s].*business",
        r"(?i)description\s+of\s+business",
    ],
    "legal_proceedings": [
        r"(?i)item\s*3[.\s].*legal proceedings",
        r"(?i)legal proceedings",
    ],
}


class TextIngestionPipeline:
    """Pipeline to process SEC HTML filings into embedded vector chunks."""

    def __init__(self):
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.openai_api_key.get_secret_value() if self.settings.openai_api_key else None)
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def extract_text_from_html(self, html_path: Path) -> str:
        """Reads HTML and returns cleaned plain text."""
        with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, "html.parser")
        
        # Remove script and style elements
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()

        # Get text with separator to preserve some structure
        text = soup.get_text(separator="\n")

        # Clean whitespace
        lines = (line.strip() for line in text.splitlines())
        # Break multi-headlines into a line each
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # Drop blank lines
        text = "\n".join(chunk for chunk in chunks if chunk)

        return text

    def identify_sections(self, text: str) -> dict[str, str]:
        """Identifies and extracts specific sections from the full text."""
        # Find start indices for all possible sections
        section_starts = []
        for section_name, patterns in SECTION_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    section_starts.append({
                        "name": section_name,
                        "start": match.start(),
                        "match_text": match.group()
                    })
                    break # Use first pattern match for this section

        # Sort by start position
        section_starts.sort(key=lambda x: x["start"])

        sections_found = {}
        for i in range(len(section_starts)):
            current = section_starts[i]
            # Content goes until the next section starts or end of text
            end = section_starts[i+1]["start"] if i + 1 < len(section_starts) else len(text)
            sections_found[current["name"]] = text[current["start"]:end].strip()

        return sections_found

    def chunk_text(self, text: str, section: str) -> list[dict]:
        """Splits section text into overlapping chunks based on token count."""
        tokens = self.tokenizer.encode(text)
        chunks = []
        
        step = CHUNK_SIZE_TOKENS - CHUNK_OVERLAP_TOKENS
        for i in range(0, len(tokens), step):
            chunk_tokens = tokens[i : i + CHUNK_SIZE_TOKENS]
            chunk_content = self.tokenizer.decode(chunk_tokens)
            
            chunks.append({
                "content": chunk_content,
                "section": section,
                "chunk_index": len(chunks),
                "token_count": len(chunk_tokens)
            })
            
            if i + CHUNK_SIZE_TOKENS >= len(tokens):
                break
                
        return chunks

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generates embeddings for a list of strings in batches."""
        all_embeddings = []
        batch_size = 100
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = self.client.embeddings.create(
                input=batch,
                model=EMBEDDING_MODEL,
                dimensions=EMBEDDING_DIMENSIONS
            )
            all_embeddings.extend([data.embedding for data in response.data])
            
        logger.info("embeddings_generated", count=len(texts))
        return all_embeddings

    def ingest_filing_text(self, filing_id: int, html_path: Path):
        """Processes a single filing: extract, chunk, embed, and save."""
        log = logger.bind(filing_id=filing_id, path=str(html_path))
        log.info("ingest_filing_text_started")

        # 1. Extract text
        text = self.extract_text_from_html(html_path)
        
        # 2. Identify sections
        sections = self.identify_sections(text)
        
        # 3. Chunk sections
        all_chunks = []
        for section_name, section_text in sections.items():
            chunks = self.chunk_text(section_text, section_name)
            all_chunks.extend(chunks)

        if not all_chunks:
            log.warning("no_text_chunks_found")
            return

        # 4. Generate embeddings
        chunk_texts = [c["content"] for c in all_chunks]
        embeddings = self.generate_embeddings(chunk_texts)
        
        # 5. Save to database
        with get_session() as session:
            # Clear existing disclosures for this filing if any (optional, but safer)
            # session.query(DisclosureORM).filter(DisclosureORM.filing_id == filing_id).delete()
            
            for i, chunk in enumerate(all_chunks):
                disclosure = DisclosureORM(
                    filing_id=filing_id,
                    section=chunk["section"],
                    chunk_index=chunk["chunk_index"],
                    content=chunk["content"],
                    token_count=chunk["token_count"],
                    embedding=embeddings[i]
                )
                session.add(disclosure)
            
            session.commit()
            
        log.info(
            "filing_text_ingested", 
            sections_found=list(sections.keys()), 
            total_chunks=len(all_chunks)
        )

    def ingest_all_for_company(self, cik: str):
        """Finds and ingests all SEC HTML filings for a given CIK."""
        base_dir = Path("data/raw/sec_edgar") / cik
        if not base_dir.exists():
            logger.error("cik_directory_not_found", cik=cik)
            return

        with get_session() as session:
            company = session.execute(select(CompanyORM).where(CompanyORM.cik == cik)).scalar_one_or_none()
            if not company:
                logger.error("company_not_in_db", cik=cik)
                return

            # Find all .htm files recursively
            html_files = list(base_dir.rglob("*.htm"))
            
            for html_path in html_files:
                # Path pattern: data/raw/sec_edgar/{cik}/{filing_type}/{filing_date}/*.htm
                # Example: data/raw/sec_edgar/0000320193/10-K/2023-11-03/0000320193-23-000106.htm
                parts = html_path.parts
                if len(parts) < 5: continue
                
                filing_type = parts[-3]
                filing_date_str = parts[-2] # e.g. "2023-11-03"
                
                # Match with FilingORM in DB
                filing = session.execute(
                    select(FilingORM)
                    .where(FilingORM.company_id == company.id)
                    .where(FilingORM.filing_type == filing_type)
                    .where(FilingORM.filing_date == filing_date_str)
                ).scalar_one_or_none()

                if not filing:
                    logger.warning("no_db_filing_match", path=str(html_path), date=filing_date_str)
                    continue

                # Check if already ingested
                exists = session.execute(
                    select(func.count(DisclosureORM.id)).where(DisclosureORM.filing_id == filing.id)
                ).scalar()
                
                if exists > 0:
                    logger.info("filing_already_ingested", filing_id=filing.id)
                    continue

                self.ingest_filing_text(filing.id, html_path)
