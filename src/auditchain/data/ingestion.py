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

import httpx

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
from auditchain.data.ingestion_validator import validate_and_flag, MIN_ANNUAL_DAYS, MAX_ANNUAL_DAYS

# Fiscal period labels for quarterly values in SEC company_facts
_QUARTER_FPS = {"Q1", "Q2", "Q3", "Q4"}
_ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}

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
    "LiabilitiesNoncurrent": "balance_sheet",
    "LiabilitiesAndStockholdersEquity": "balance_sheet",
    # Equity — NCI-inclusive variant stored alongside the parent-only version.
    # The parser in tools/financial_data.py prefers the NCI-inclusive tag when
    # both exist, so the accounting equation can balance against total assets.
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest": "balance_sheet",
    "StockholdersEquity": "balance_sheet",
    # Noncontrolling interest (NCI / minority interest) — needed so the
    # composition derivation can compute total equity = parent + NCI.
    "MinorityInterest": "balance_sheet",
    "RedeemableNoncontrollingInterestEquityCarryingAmount": "balance_sheet",
    "RetainedEarningsAccumulatedDeficit": "balance_sheet",
    "PropertyPlantAndEquipmentNet": "balance_sheet",
    "LongTermDebt": "balance_sheet",
    "LongTermDebtNoncurrent": "balance_sheet",
    "CashAndCashEquivalentsAtCarryingValue": "balance_sheet",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents": "balance_sheet",
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

            sic_code, industry = self._fetch_sic(case.cik)
            company = company_repo.upsert(
                cik=case.cik,
                name=case.name,
                ticker=case.ticker,
                is_known_fraud=case.is_known_fraud,
                fraud_notes=case.description,
                sic_code=sic_code,
                industry=industry,
            )
            log.info("company_upserted", company_id=company.id)

            grouped = self._group_facts_by_filing(facts)
            log.info("filings_to_ingest", count=len(grouped))

            total_line_items = 0
            for accession, fact_triples in grouped.items():
                # fact_triples: list of (concept_name, FactValue, value_source)
                first_fact = fact_triples[0][1]
                latest_fact = max(fact_triples, key=lambda t: t[1].end)[1]

                filing = filing_repo.upsert(
                    company_id=company.id,
                    accession_number=accession,
                    filing_type=first_fact.form or "10-K",
                    filing_date=first_fact.filed or first_fact.end,
                    period_of_report=latest_fact.end,
                    fiscal_year=latest_fact.fy or latest_fact.end.year,
                    fiscal_period=latest_fact.fp or "FY",
                )

                # validate_and_flag still receives (concept, FactValue) pairs
                fact_values = [(c, f) for c, f, _src in fact_triples]
                prior_values = self._get_prior_values(
                    session, company.id, latest_fact.end
                )
                quality_flags = validate_and_flag(
                    fact_values, prior_values, CONCEPT_TO_STATEMENT
                )

                line_item_rows = self._build_line_item_rows(
                    filing.id, fact_triples, quality_flags
                )
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

    def _fetch_sic(self, cik: str) -> tuple[str | None, str | None]:
        """Fetch SIC code and industry description from the SEC submissions API.

        Returns ``(sic_code, industry)`` or ``(None, None)`` on any error.
        The call is best-effort — ingestion continues even if it fails.
        """
        try:
            cik_padded = cik.zfill(10)
            url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
            resp = httpx.get(
                url,
                headers={"User-Agent": self._settings.sec_user_agent},
                timeout=10.0,
                follow_redirects=True,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("sic"), data.get("sicDescription")
        except Exception as exc:
            logger.warning("sic_fetch_failed", cik=cik, error=str(exc))
            return None, None

    @staticmethod
    def _load_facts(path: Path) -> CompanyFacts:
        """Read and validate a company_facts.json file."""
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return CompanyFacts.model_validate(raw)

    @staticmethod
    def _group_facts_by_filing(
        facts: CompanyFacts,
    ) -> dict[str, list[tuple[str, FactValue, str]]]:
        """Group fact values by accession, adding quarterly aggregations where needed.

        Returns accession_number -> list of (concept_name, FactValue, value_source).

        For each concept all fp=FY values are kept (including comparative-year entries
        from later filings) so historical coverage is preserved.  Additionally, for
        flow-statement concepts that have no annual-duration fp=FY entry for a given
        fiscal year, a synthetic annual FactValue is constructed by summing Q1+Q2+Q3+Q4
        and attached to the corresponding 10-K accession with value_source="aggregated_4q".
        """
        grouped: dict[str, list[tuple[str, FactValue, str]]] = defaultdict(list)

        for concept_name in CONCEPT_TO_STATEMENT:
            concept = facts.get_concept(concept_name)
            if concept is None or concept.units.USD is None:
                continue

            statement = CONCEPT_TO_STATEMENT[concept_name]
            is_flow = statement in ("income_statement", "cash_flow")

            # ── pass 1: keep all fp=FY values in their own accession ─────────
            # Track which (fy, concept) pairs already have an annual-duration value
            # so we don't add a quarterly aggregate on top of a good annual.
            fy_has_annual: set[int] = set()
            for v in concept.units.USD:
                if v.fp != "FY":
                    continue
                source = "annual_direct"
                if is_flow and (
                    v.start is None
                    or not (MIN_ANNUAL_DAYS <= (v.end - v.start).days <= MAX_ANNUAL_DAYS)
                ):
                    source = "duration_fallback"
                else:
                    if v.fy is not None:
                        fy_has_annual.add(v.fy)
                grouped[v.accn].append((concept_name, v, source))

            # ── pass 2: quarterly aggregation for flow concepts ───────────────
            if not is_flow:
                continue

            by_fy: dict[int, list[FactValue]] = defaultdict(list)
            for v in concept.units.USD:
                if v.fy is not None:
                    by_fy[v.fy].append(v)

            for fy, fy_values in by_fy.items():
                if fy in fy_has_annual:
                    continue  # already have a clean annual — no aggregation needed

                ten_k_accn = _find_tenk_accession(fy_values, fy)
                if ten_k_accn is None:
                    continue

                quarters = _collect_quarters(fy_values, fy)
                if len(quarters) != 4:
                    continue

                synthetic = _aggregate_quarters(quarters, fy, ten_k_accn)
                grouped[ten_k_accn].append((concept_name, synthetic, "aggregated_4q"))

        return dict(grouped)

    @staticmethod
    def _get_prior_values(session, company_id: int, current_period_end) -> dict[str, float]:
        """Fetch concept values from the filing immediately prior to current_period_end.

        Used by the quality validator to detect implausible YoY jumps.
        Returns an empty dict if no prior filing exists or on any error.
        """
        from sqlalchemy import select
        from auditchain.data.models import FilingORM, FinancialLineItemORM
        try:
            prior_filing = session.execute(
                select(FilingORM)
                .where(FilingORM.company_id == company_id)
                .where(FilingORM.period_of_report < current_period_end)
                .order_by(FilingORM.period_of_report.desc())
                .limit(1)
            ).scalar_one_or_none()

            if prior_filing is None:
                return {}

            rows = session.execute(
                select(FinancialLineItemORM.concept, FinancialLineItemORM.value)
                .where(FinancialLineItemORM.filing_id == prior_filing.id)
                .where(FinancialLineItemORM.quality_flag == None)  # noqa: E711
                .where(FinancialLineItemORM.frame != "")
            ).all()

            # Fallback: if no framed values, take any clean value
            if not rows:
                rows = session.execute(
                    select(FinancialLineItemORM.concept, FinancialLineItemORM.value)
                    .where(FinancialLineItemORM.filing_id == prior_filing.id)
                    .where(FinancialLineItemORM.quality_flag == None)  # noqa: E711
                ).all()

            return {r.concept: float(r.value) for r in rows if r.value is not None}
        except Exception as exc:
            logger.warning("prior_values_fetch_failed", company_id=company_id, error=str(exc))
            return {}

    @staticmethod
    def _build_line_item_rows(
        filing_id: int,
        fact_triples: Iterable[tuple[str, FactValue, str]],
        quality_flags: dict[tuple, str | None] | None = None,
    ) -> list[dict]:
        """Build rows for bulk_upsert.

        ``fact_triples`` is a list of (concept_name, FactValue, value_source).
        ``quality_flags`` maps (concept_name, period_end, frame) → flag or None.
        Deduplicates by (filing_id, statement, concept, period_end, frame);
        last-write-wins within a filing.
        """
        # Source priority for deduplication: higher index = higher priority.
        _SOURCE_PRIORITY = {"duration_fallback": 0, "annual_direct": 1, "aggregated_4q": 2}

        deduplicated: dict[tuple, dict] = {}
        for concept_name, fact, value_source in fact_triples:
            statement = CONCEPT_TO_STATEMENT[concept_name]
            frame = fact.frame or ""
            key = (filing_id, statement, concept_name, fact.end, frame)
            validator_key = (concept_name, fact.end, frame)
            quality_flag = (quality_flags or {}).get(validator_key)

            incoming_priority = _SOURCE_PRIORITY.get(value_source, 0)
            existing = deduplicated.get(key)
            if existing is not None:
                existing_priority = _SOURCE_PRIORITY.get(existing["value_source"] or "", 0)
                if existing_priority >= incoming_priority:
                    continue  # keep the higher-quality value already stored

            # An annual_direct value can never have duration_mismatch — the flag
            # was produced by a duration_fallback that shares the same validator key
            # (same concept + period_end + frame).  Clear the false positive here.
            if value_source == "annual_direct" and quality_flag == "duration_mismatch":
                quality_flag = None

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
                "frame": frame,
                "quality_flag": quality_flag,
                "value_source": value_source,
            }
        return list(deduplicated.values())


# ── module-level helpers for _group_facts_by_filing ──────────────────────────

def _find_tenk_accession(values: list[FactValue], fy: int) -> str | None:
    """Return the 10-K accession for this fiscal year, or None if not found.

    Prefers an annual-form filing (10-K, 20-F, 40-F). Falls back to any fp=FY
    accession so we still attach data even when form metadata is missing.
    """
    # Prefer explicit annual forms
    for v in values:
        if v.fp == "FY" and v.fy == fy and v.form in _ANNUAL_FORMS:
            return v.accn
    # Fallback: any fp=FY for this fy
    for v in values:
        if v.fp == "FY" and v.fy == fy:
            return v.accn
    return None


def _collect_quarters(values: list[FactValue], fy: int) -> dict[str, FactValue]:
    """Return {fp: FactValue} for Q1–Q4 of the given fiscal year.

    Each quarter is the value with the latest `filed` date for that fp, so
    amended filings (10-Q/A) automatically supersede the originals.
    """
    quarters: dict[str, FactValue] = {}
    for v in values:
        if v.fp not in _QUARTER_FPS or v.fy != fy or v.start is None:
            continue
        existing = quarters.get(v.fp)
        if existing is None or (v.filed or v.end) > (existing.filed or existing.end):
            quarters[v.fp] = v
    return quarters


def _aggregate_quarters(quarters: dict[str, FactValue], fy: int, accn: str) -> FactValue:
    """Create a synthetic annual FactValue by summing the four quarters."""
    q1 = quarters["Q1"]
    q4 = quarters["Q4"]
    total = sum(q.val for q in quarters.values())
    return FactValue(
        start=q1.start,
        end=q4.end,
        val=total,
        accn=accn,
        fy=fy,
        fp="FY",
        form="10-K",
        filed=q4.filed,
        frame=f"CY{fy}",
    )