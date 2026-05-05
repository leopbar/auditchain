"""Pydantic models for parsing SEC EDGAR company_facts.json structure.

The SEC publishes a structured JSON for every public company containing
all reported financial concepts (XBRL tags) across all filings. These
models validate that structure and give us type-safe access.

Example file: data/raw/sec_edgar/0000320193/company_facts.json
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class FactValue(BaseModel):
    """A single reported value of a financial concept in a specific period.

    Example:
        {"end": "2024-09-28", "val": 391035000000, "fy": 2024, "fp": "FY",
         "form": "10-K", "filed": "2024-11-01", "accn": "0000320193-24-000123"}
    """

    model_config = ConfigDict(extra="ignore")

    start: date | None = None
    end: date
    val: float
    accn: str = Field(description="SEC accession number of the filing")
    fy: int | None = Field(default=None, description="Fiscal year")
    fp: str | None = Field(default=None, description="Fiscal period: FY, Q1, Q2, Q3")
    form: str | None = Field(default=None, description="Filing form type")
    filed: date | None = None
    frame: str | None = None


class ConceptUnits(BaseModel):
    """A financial concept's values grouped by currency unit (USD, EUR, etc)."""

    model_config = ConfigDict(extra="allow")

    USD: list[FactValue] | None = None


class Concept(BaseModel):
    """A single XBRL concept (e.g. Revenues, NetIncomeLoss, Assets).

    Each concept has a label, description, and values across all reported periods.
    """

    model_config = ConfigDict(extra="ignore")

    label: str | None = None
    description: str | None = None
    units: ConceptUnits


class Facts(BaseModel):
    """Container for all concepts grouped by taxonomy.

    Most relevant taxonomy is 'us-gaap' (US Generally Accepted Accounting Principles).
    'dei' is metadata (Document and Entity Information).
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    us_gaap: dict[str, Concept] = Field(default_factory=dict, alias="us-gaap")
    dei: dict[str, Concept] = Field(default_factory=dict)


class CompanyFacts(BaseModel):
    """Top-level structure of a company_facts.json file."""

    model_config = ConfigDict(extra="ignore")

    cik: int
    entityName: str
    facts: Facts

    def get_concept(self, name: str) -> Concept | None:
        """Look up a US GAAP concept by name. Returns None if not reported."""
        return self.facts.us_gaap.get(name)

    def get_annual_values(self, concept_name: str) -> list[FactValue]:
        """Return only fiscal-year (FY) values of a concept, sorted by date."""
        concept = self.get_concept(concept_name)
        if concept is None or concept.units.USD is None:
            return []
        return sorted(
            (v for v in concept.units.USD if v.fp == "FY"),
            key=lambda v: v.end,
        )