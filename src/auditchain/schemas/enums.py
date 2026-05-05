"""Enums for the AuditChain multi-agent system.

This module contains all standard enumerations used to categorize risks,
findings, phases, and conclusions across the audit pipeline.
"""

from enum import Enum


class RiskLevel(str, Enum):
    """The overall risk assessment level for a company or audit area."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FlagSeverity(str, Enum):
    """The severity of a specific finding (Red Flag)."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditPhase(str, Enum):
    """The current phase of the multi-agent audit workflow."""

    PLANNING = "planning"
    COLLECTION = "collection"
    RECONCILIATION = "reconciliation"
    QUANT_ANALYSIS = "quant_analysis"
    INVESTIGATION = "investigation"
    SUPERVISION = "supervision"
    COMPLETED = "completed"
    FAILED = "failed"


class AuditConclusion(str, Enum):
    """Official audit opinion terminology."""

    CLEAN = "clean"  # unqualified opinion
    QUALIFIED = "qualified"  # qualified opinion
    ADVERSE = "adverse"  # adverse opinion
    DISCLAIMER = "disclaimer"  # disclaimer of opinion


class FlagCategory(str, Enum):
    """Categorization of audit findings for structured reporting and statistics."""

    ACCOUNTING_EQUATION = "accounting_equation"
    REVENUE_RECOGNITION = "revenue_recognition"
    EXPENSE_CAPITALIZATION = "expense_capitalization"
    RELATED_PARTY = "related_party"
    CASH_FLOW_INCONSISTENCY = "cash_flow_inconsistency"
    BENEISH_MSCORE = "beneish_mscore"
    ALTMAN_ZSCORE = "altman_zscore"
    QUALITATIVE_DISCLOSURE = "qualitative_disclosure"
    DATA_QUALITY = "data_quality"
