"""High-level service that ingests SEC filings into the database.

Pipeline for each company:
  1. Load company_facts.json from disk
  2. Validate structure with the CompanyFacts Pydantic model
  3. Upsert the company row
  4. For every fact value, upsert a synthetic 'filing' row (one per accession number)
     and a financial_line_items row.

The Pydantic model lives in `data/sec_models.py` and represents data 'in flight';
the SQLAlchemy ORM models in `data/models.py` represent data 'at rest'. This
service is the bridge between the two worlds.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from pathlib import Path

from auditchain.core.config import get_settings
from auditchain.core.logging import get_logger
from auditchain.data.database import get_session
from auditchain.data.known_fraud_cases import FraudCase, get_benchmark_companies
from auditchain.data.repositories import (
    CompanyRepository,
    FilingRepository,
    FinancialLineItemRepository,
)
from auditchain.data.sec_models import CompanyFacts, FactValue

logger = get_logger(__name__)


# Concepts we care about, mapped to which financial statement they belong to.
# This is intentionally small for the MVP — we focus on income statement and
# balance sheet basics. The full taxonomy has hundreds of concepts.
CONCEPT_TO_STATEMENT: dict[str, str] = {
    # Income statement
    "Revenues": "income_statement",
    "RevenueFromContractWithCustomerExcludingAssessedTax": "income_statement",
    "CostOfRevenue": "income_statement",
    "CostOfGoodsAndServicesSold": "income_statement",
    "GrossProfit": "income_statement",
    "OperatingIncomeLoss": "income_statement",
    "NetIncomeLoss": "income_statement",
    "OperatingExpenses": "income_statement",
    "ResearchAndDevelopmentExpense": "income_statement",
    "SellingGeneralAndAdministrativeExpense": "income_statement",
    "DepreciationAndAmortization": "income_statement",
    "DepreciationDepletionAndAmortization": "income_statement",
    # Balance sheet
    "Assets": "balance_sheet",
    "AssetsCurrent": "balance_sheet",
    "Liabilities": "balance_sheet",
    "LiabilitiesCurrent": "balance_sheet",
    "StockholdersEquity": "balance_sheet",
    "RetainedEarningsAccumulatedDeficit": "balance_sheet",
    "PropertyPlantAndEquipmentNet": "balance_sheet",
    "LongTermDebt": "balance_sheet",
    "LongTermDebtNoncurrent": "balance_sheet",
    "CashAndCashEquivalentsAtCarryingValue": "balance_sheet",
    "AccountsReceivableNetCurrent": "balance_sheet",
    "InventoryNet": "balance_sheet",
    # Cash flow
    "NetCashProvidedByUsedInOperatingActivities": "cash_flow",
    "NetCashProvidedByUsedInInvestingActivities": "cash_flow",
    "NetCashProvidedByUsedInFinancingActivities": "cash_flow",
}


class FilingIngestionService:
    """Ingests one company's facts into the database."""

    def __init__(self) -> None:
        self._settings = get_settings()

    def ingest_company(self, case: FraudCase) -> dict[str, int]:
        """Ingest a single company's company_facts.json.

        Returns a small report with counts for logging.
        """
        log = logger.bind(cik=case.cik, ticker=case.ticker, name=case.name)

        facts_path = (
            self._settings.raw_data_dir / "sec_edgar" / case.cik / "company_facts.json"
        )
        if not facts_path.exists():
            log.warning("facts_file_missing", path=str(facts_path))
            return {"company": 0, "filings": 0, "line_items": 0}

        log.info("ingesting_company")
        facts = self._load_facts(facts_path)

        with get_session() as session:
            company_repo = CompanyRepository(session)
            filing_repo = FilingRepository(session)
            line_item_repo = FinancialLineItemRepository(session)

            company = company_repo.upsert(
                cik=case.cik,
                name=case.name,
                ticker=case.ticker,
                is_known_fraud=case.is_known_fraud,
                fraud_notes=case.description,
            )
            log.info("company_upserted", company_id=company.id)

            grouped = self._group_facts_by_filing(facts)
            log.info("filings_to_ingest", count=len(grouped))

            total_line_items = 0
            for accession, fact_values in grouped.items():
                first_value = fact_values[0][1]
                filing = filing_repo.upsert(
                    company_id=company.id,
                    accession_number=accession,
                    filing_type=first_value.form or "10-K",
                    filing_date=first_value.filed or first_value.end,
                    period_of_report=first_value.end,
                    fiscal_year=first_value.fy or first_value.end.year,
                    fiscal_period=first_value.fp or "FY",
                )

                line_item_rows = self._build_line_item_rows(filing.id, fact_values)
                count = line_item_repo.bulk_upsert(line_item_rows)
                total_line_items += count

            log.info(
                "company_ingested",
                company_id=company.id,
                filings=len(grouped),
                line_items=total_line_items,
            )
            return {
                "company": 1,
                "filings": len(grouped),
                "line_items": total_line_items,
            }

    def ingest_all(self) -> dict[str, int]:
        """Ingest every company in the benchmark catalog."""
        totals = {"company": 0, "filings": 0, "line_items": 0}
        for case in get_benchmark_companies():
            result = self.ingest_company(case)
            for key, value in result.items():
                totals[key] += value
        logger.info("ingestion_complete", **totals)
        return totals

    @staticmethod
    def _load_facts(path: Path) -> CompanyFacts:
        """Read and validate a company_facts.json file."""
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return CompanyFacts.model_validate(raw)

    @staticmethod
    def _group_facts_by_filing(
        facts: CompanyFacts,
    ) -> dict[str, list[tuple[str, FactValue]]]:
        """Group fact values by their accession number.

        Returns a dict mapping accession_number -> list of (concept_name, FactValue).
        Only concepts in CONCEPT_TO_STATEMENT are kept; only USD annual values.
        """
        grouped: dict[str, list[tuple[str, FactValue]]] = defaultdict(list)

        for concept_name in CONCEPT_TO_STATEMENT:
            concept = facts.get_concept(concept_name)
            if concept is None or concept.units.USD is None:
                continue

            for value in concept.units.USD:
                if value.fp != "FY":
                    continue
                grouped[value.accn].append((concept_name, value))

        return dict(grouped)

    @staticmethod
    def _build_line_item_rows(
        filing_id: int,
        fact_values: Iterable[tuple[str, FactValue]],
    ) -> list[dict]:
        """Build the list of rows ready for bulk_upsert into financial_line_items.

        This method deduplicates rows before returning. SEC filings sometimes report
        the same concept multiple times for the same period (e.g., in different tables
        or as restatements). Since the database has a unique constraint on
        (filing_id, statement, concept, period_end), we keep only the last value
        encountered ('last-write-wins') to avoid CardinalityViolation during bulk UPSERT.
        """
        deduplicated: dict[tuple, dict] = {}
        for concept_name, fact in fact_values:
            statement = CONCEPT_TO_STATEMENT[concept_name]
            key = (filing_id, statement, concept_name, fact.end)
            deduplicated[key] = {
                "filing_id": filing_id,
                "statement": statement,
                "concept": concept_name,
                "label": concept_name,
                "value": fact.val,
                "currency": "USD",
                "unit": "USD",
                "decimals": None,
                "period_start": fact.start,
                "period_end": fact.end,
            }
        return list(deduplicated.values())