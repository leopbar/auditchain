"""Minimal async client for SEC EDGAR with proper rate limiting.

Uses the SEC EDGAR full-text search API directly (not requiring sec-edgar-downloader)
to give us more control over what we fetch and to handle the User-Agent requirement
properly.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from auditchain.core.logging import get_logger
from auditchain.data.known_fraud_cases import FraudCase

logger = get_logger(__name__)

SEC_BASE = "https://www.sec.gov"
SEC_DATA = "https://data.sec.gov"
RATE_LIMIT_DELAY = 0.15


class SECClient:
    """Minimal async client for SEC EDGAR with proper rate limiting."""

    def __init__(self, user_agent: str) -> None:
        self.headers = {
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov",
        }
        self._client = httpx.AsyncClient(
            headers=self.headers,
            timeout=30.0,
            follow_redirects=True,
        )

    async def __aenter__(self) -> SECClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self._client.aclose()

    async def get_company_submissions(self, cik: str) -> dict:
        """Fetch the submissions index for a company.

        Returns a dict with 'filings.recent' containing filing metadata.
        """
        cik_padded = cik.zfill(10)
        url = f"{SEC_DATA}/submissions/CIK{cik_padded}.json"
        await asyncio.sleep(RATE_LIMIT_DELAY)
        response = await self._client.get(url)
        response.raise_for_status()
        return response.json()

    async def get_company_facts(self, cik: str) -> dict:
        """Fetch all XBRL company facts (structured financial data).

        This is the magic endpoint — returns every reported financial concept
        across all filings in one JSON.
        """
        cik_padded = cik.zfill(10)
        url = f"{SEC_DATA}/api/xbrl/companyfacts/CIK{cik_padded}.json"
        await asyncio.sleep(RATE_LIMIT_DELAY)
        response = await self._client.get(url)
        response.raise_for_status()
        return response.json()

    async def download_filing(self, accession_number: str, cik: str, primary_doc: str) -> bytes:
        """Download the primary document of a filing."""
        accession_clean = accession_number.replace("-", "")
        url = f"{SEC_BASE}/Archives/edgar/data/{int(cik)}/{accession_clean}/{primary_doc}"

        headers = {**self.headers, "Host": "www.sec.gov"}
        await asyncio.sleep(RATE_LIMIT_DELAY)
        response = await self._client.get(url, headers=headers)
        response.raise_for_status()
        return response.content


async def download_company(
    client: SECClient,
    case: FraudCase,
    output_dir: Path,
    filing_types: tuple[str, ...] = ("10-K",),
    max_filings: int = 5,
) -> None:
    """Download filings + facts for a single company."""
    log = logger.bind(cik=case.cik, ticker=case.ticker, name=case.name)
    log.info("downloading_company")

    company_dir = output_dir / case.cik
    company_dir.mkdir(parents=True, exist_ok=True)

    try:
        facts = await client.get_company_facts(case.cik)
        (company_dir / "company_facts.json").write_text(
            __import__("json").dumps(facts, indent=2)
        )
        log.info("company_facts_saved", size_kb=len(str(facts)) // 1024)
    except httpx.HTTPStatusError as exc:
        log.warning("company_facts_failed", status=exc.response.status_code)

    try:
        submissions = await client.get_company_submissions(case.cik)
    except httpx.HTTPStatusError as exc:
        log.error("submissions_failed", status=exc.response.status_code)
        return

    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    filing_dates = recent.get("filingDate", [])

    downloaded = 0
    for form, acc, doc, date in zip(forms, accessions, primary_docs, filing_dates):
        if downloaded >= max_filings:
            break
        if form not in filing_types:
            continue

        filing_dir = company_dir / form / date
        filing_dir.mkdir(parents=True, exist_ok=True)
        target = filing_dir / doc

        if target.exists():
            log.debug("filing_cached", form=form, date=date)
            downloaded += 1
            continue

        try:
            content = await client.download_filing(acc, case.cik, doc)
            target.write_bytes(content)
            log.info("filing_saved", form=form, date=date, size_kb=len(content) // 1024)
            downloaded += 1
        except httpx.HTTPStatusError as exc:
            log.warning("filing_failed", form=form, date=date, status=exc.response.status_code)
