"""Pydantic schemas for the company data ingestion pipeline.

These models define the request/response contracts and internal data structures
for the ingestion subsystem, which handles downloading SEC filings, parsing
XBRL data, and embedding textual disclosures for a given company.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator
import re


class IngestionStage(str, Enum):
    """Ordered stages of the ingestion pipeline."""

    VALIDATE = "validate"
    DOWNLOAD_FACTS = "download_facts"
    DOWNLOAD_FILINGS = "download_filings"
    PARSE_XBRL = "parse_xbrl"
    EMBED_TEXT = "embed_text"


class IngestionStatus(str, Enum):
    """Lifecycle status of an ingestion run."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestionRun(BaseModel):
    """Representation of an ingestion run record (mirrors ingestion_runs table)."""

    id: str
    cik: str
    status: IngestionStatus
    current_stage: Optional[IngestionStage] = None
    stages_completed: list[str] = Field(default_factory=list)
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    filings_count: Optional[int] = None
    chunks_generated: Optional[int] = None
    financial_items_extracted: Optional[int] = None
    is_update: bool = False

    class Config:
        from_attributes = True


class CreateIngestionRequest(BaseModel):
    """Request payload to start a new ingestion pipeline."""

    cik: str = Field(
        ...,
        description="SEC Central Index Key — exactly 10 digits, zero-padded.",
        examples=["0000320193"],
    )
    force_update: bool = Field(
        default=False,
        description="If True, allows re-ingestion for a company that already exists in the database.",
    )

    @field_validator("cik")
    @classmethod
    def validate_cik(cls, v: str) -> str:
        if not re.match(r"^\d{10}$", v):
            raise ValueError("CIK must be exactly 10 digits (zero-padded).")
        return v


class CreateIngestionResponse(BaseModel):
    """Response returned after successfully initiating an ingestion pipeline."""

    ingestion_id: str
    status: str
    message: str
    stream_url: str
