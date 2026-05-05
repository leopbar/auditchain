"""SQLAlchemy ORM models matching the schema in infra/sql/001_init.sql.

Naming convention:
- ORM classes end in 'ORM' (e.g. CompanyORM) to distinguish them from
  Pydantic models with similar names (e.g. CompanyFacts).
- This separation is intentional: Pydantic = data in flight, ORM = data at rest.
"""

from datetime import date, datetime
from decimal import Decimal
import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from auditchain.data.database import Base


class CompanyORM(Base):
    """A US-listed company tracked by AuditChain."""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    cik: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    ticker: Mapped[str | None] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    sic_code: Mapped[str | None] = mapped_column(String(4))
    industry: Mapped[str | None] = mapped_column(Text)
    fiscal_year_end: Mapped[str | None] = mapped_column(String(4))
    is_known_fraud: Mapped[bool] = mapped_column(Boolean, default=False)
    fraud_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    filings: Mapped[list["FilingORM"]] = relationship(back_populates="company", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Company cik={self.cik} ticker={self.ticker} name={self.name!r}>"


class FilingORM(Base):
    """A single SEC filing (10-K, 10-Q, etc) submitted by a company."""

    __tablename__ = "filings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    company_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("companies.id", ondelete="CASCADE"))
    filing_type: Mapped[str] = mapped_column(
        SQLEnum(
            "10-K",
            "10-Q",
            "8-K",
            "20-F",
            "40-F",
            "10-K/A",
            "10-Q/A",
            "8-K/A",
            "20-F/A",
            "40-F/A",
            name="filing_type",
        ),
        nullable=False,
    )
    accession_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_of_report: Mapped[date] = mapped_column(Date, nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_period: Mapped[str] = mapped_column(String(2), nullable=False)
    raw_url: Mapped[str | None] = mapped_column(Text)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    fraud_injected: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped[CompanyORM] = relationship(back_populates="filings")
    line_items: Mapped[list["FinancialLineItemORM"]] = relationship(
        back_populates="filing", cascade="all, delete-orphan"
    )
    disclosures: Mapped[list["DisclosureORM"]] = relationship(
        back_populates="filing", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Filing {self.filing_type} {self.period_of_report} accn={self.accession_number}>"


class FinancialLineItemORM(Base):
    """A single line item from a financial statement (e.g. Revenues = $100M for FY2024)."""

    __tablename__ = "financial_line_items"
    __table_args__ = (
        UniqueConstraint("filing_id", "statement", "concept", "period_end"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    filing_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("filings.id", ondelete="CASCADE"))
    statement: Mapped[str] = mapped_column(
        SQLEnum("income_statement", "balance_sheet", "cash_flow", name="statement_type"),
        nullable=False,
    )
    concept: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str | None] = mapped_column(Text)
    value: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    unit: Mapped[str] = mapped_column(String(20), default="USD")
    decimals: Mapped[int | None] = mapped_column(Integer)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    filing: Mapped[FilingORM] = relationship(back_populates="line_items")

    def __repr__(self) -> str:
        return f"<LineItem {self.concept}={self.value} period={self.period_end}>"


class AuditRunORM(Base):
    """Record of a multi-agent audit execution."""

    __tablename__ = "audit_runs"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    company_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("companies.id"), nullable=False)
    filing_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("filings.id"), nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    risk_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    risk_level: Mapped[str | None] = mapped_column(String(10))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    total_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    langgraph_thread_id: Mapped[str | None] = mapped_column(Text)
    final_report: Mapped[dict | None] = mapped_column(JSONB)

    company: Mapped[CompanyORM] = relationship()
    steps: Mapped[list["AgentStepORM"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    red_flags: Mapped[list["RedFlagORM"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class AgentStepORM(Base):
    """Detailed trace of an agent's reasoning and actions within a run."""

    __tablename__ = "agent_steps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("audit_runs.id", ondelete="CASCADE"))
    agent_name: Mapped[str] = mapped_column(String(50))
    step_index: Mapped[int] = mapped_column(Integer)
    input: Mapped[dict | None] = mapped_column(JSONB)
    output: Mapped[dict | None] = mapped_column(JSONB)
    tool_calls: Mapped[dict | None] = mapped_column(JSONB)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    tokens_input: Mapped[int | None] = mapped_column(Integer)
    tokens_output: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[AuditRunORM] = relationship(back_populates="steps")


class RedFlagORM(Base):
    """A suspicious finding or Red Flag detected during an audit."""

    __tablename__ = "red_flags"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("audit_runs.id", ondelete="CASCADE"))
    detected_by: Mapped[str] = mapped_column(String(50))
    category: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String)  # Using String to map to the DB enum
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict | None] = mapped_column(JSONB)
    rationale: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[AuditRunORM] = relationship(back_populates="red_flags")


class DisclosureORM(Base):
    """Textual disclosure from an SEC filing, chunked and embedded for RAG."""

    __tablename__ = "disclosures"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    filing_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("filings.id", ondelete="CASCADE"))
    section: Mapped[str] = mapped_column(
        SQLEnum(
            "mdna",
            "risk_factors",
            "notes_to_financials",
            "auditors_report",
            "controls_procedures",
            "business",
            "legal_proceedings",
            name="disclosure_section",
        ),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    filing: Mapped[FilingORM] = relationship(back_populates="disclosures")

    def __repr__(self) -> str:
        return f"<Disclosure {self.section} chunk={self.chunk_index} filing_id={self.filing_id}>"


class IngestionRunORM(Base):
    """Record of a company data ingestion pipeline execution."""

    __tablename__ = "ingestion_runs"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    cik: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    current_stage: Mapped[str | None] = mapped_column(String(30))
    stages_completed: Mapped[dict | None] = mapped_column(JSONB, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    filings_count: Mapped[int | None] = mapped_column(Integer)
    chunks_generated: Mapped[int | None] = mapped_column(Integer)
    financial_items_extracted: Mapped[int | None] = mapped_column(Integer)
    is_update: Mapped[bool] = mapped_column(Boolean, default=False)

    def __repr__(self) -> str:
        return f"<IngestionRun id={self.id} cik={self.cik} status={self.status}>"