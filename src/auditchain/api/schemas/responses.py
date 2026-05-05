"""Pydantic schemas for API responses and requests.

Standardizes the data models for REST endpoints communicating with the frontend.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    cik: str
    ticker: Optional[str] = None
    name: str
    is_known_fraud: bool
    fraud_notes: Optional[str] = None
    filings_count: int
    has_text_indexed: bool

class CompanyListResponse(BaseModel):
    companies: List[CompanyResponse]
    total: int

class AuditRunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    run_id: str
    company_cik: str
    company_name: str
    company_ticker: Optional[str] = None
    status: str
    conclusion: Optional[str] = None
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    red_flags_count: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

class AuditRunListResponse(BaseModel):
    audits: List[AuditRunSummary]
    total: int

class AuditRunDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    run_id: str
    company_cik: str
    company_name: str
    company_ticker: Optional[str] = None
    status: str
    conclusion: Optional[str] = None
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    needs_human_review: bool
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_tokens: Optional[int] = None
    total_cost_usd: Optional[float] = None
    final_report: Optional[Dict[str, Any]] = None
    red_flags: List[Dict[str, Any]]
    agent_steps: List[Dict[str, Any]]

class CreateAuditRequest(BaseModel):
    cik: str = Field(min_length=10, max_length=10, pattern=r"^\d{10}$")
    model: str = Field(default="gpt-4o-mini")

class CreateAuditResponse(BaseModel):
    run_id: str
    status: str
    message: str
    stream_url: str  # URL for frontend to open EventSource

class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
