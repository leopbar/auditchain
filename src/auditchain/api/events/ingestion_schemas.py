"""Schemas for Server-Sent Events (SSE) during company data ingestion.

Defines the structure of real-time events streamed from the ingestion pipeline
to the frontend while downloading, parsing, and embedding data for a company.
Follows the same patterns as the audit SSE schemas in schemas.py.
"""

from datetime import datetime
from typing import Any, Optional, Union, Literal
from pydantic import BaseModel, Field


class IngestionEventBase(BaseModel):
    event_type: str
    ingestion_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    elapsed_seconds: float  # time since ingestion start


class IngestionStartedEvent(IngestionEventBase):
    event_type: Literal["ingestion_started"] = "ingestion_started"
    cik: str
    company_name: Optional[str] = None  # populated after validate stage
    is_update: bool = False


class StageStartedEvent(IngestionEventBase):
    event_type: Literal["stage_started"] = "stage_started"
    stage: str  # validate, download_facts, download_filings, parse_xbrl, embed_text
    description: str  # human-friendly description, e.g. "Downloading SEC filings..."


class StageProgressEvent(IngestionEventBase):
    event_type: Literal["stage_progress"] = "stage_progress"
    stage: str
    current: int
    total: int
    message: str  # e.g. "Downloading filing 3 of 5"


class StageCompletedEvent(IngestionEventBase):
    event_type: Literal["stage_completed"] = "stage_completed"
    stage: str
    duration_seconds: float
    summary: dict[str, Any]  # stage-specific results


class IngestionCompletedEvent(IngestionEventBase):
    event_type: Literal["ingestion_completed"] = "ingestion_completed"
    cik: str
    company_name: str
    ticker: Optional[str] = None
    filings_count: int
    chunks_generated: int
    financial_items_extracted: int
    total_duration_seconds: float


class IngestionFailedEvent(IngestionEventBase):
    event_type: Literal["ingestion_failed"] = "ingestion_failed"
    failed_stage: str
    error_message: str


# Type alias for any ingestion event
IngestionEvent = Union[
    IngestionStartedEvent,
    StageStartedEvent,
    StageProgressEvent,
    StageCompletedEvent,
    IngestionCompletedEvent,
    IngestionFailedEvent,
]


def ingestion_event_to_sse(event: IngestionEventBase) -> str:
    """Convert ingestion event to SSE format string ready for browser consumption."""
    return f"event: {event.event_type}\ndata: {event.model_dump_json()}\n\n"
