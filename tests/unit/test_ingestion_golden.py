"""Unit tests: reconcile ingestion output against golden values.

No database required — these tests parse company_facts.json directly
and run the ingestion logic up to _build_line_item_rows, then compare
the extracted values against the manually verified golden values.

They also serve as a regression guard for the A2 fix: if the frame
filter is ever removed, test_tsla_consolidated_not_segment will catch
the segment revenue leaking back as the consolidated total.

Run with:
    make test-unit
    pytest -m unit tests/unit/test_ingestion_golden.py -v
"""

import pytest
from pathlib import Path

from auditchain.data.ingestion import FilingIngestionService
from auditchain.core.config import get_settings
from tests.fixtures.golden_values import AAPL_GOLDEN, TSLA_GOLDEN

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_facts(cik: str):
    settings = get_settings()
    path = settings.raw_data_dir / "sec_edgar" / cik / "company_facts.json"
    if not path.exists():
        pytest.skip(f"company_facts.json not found for CIK {cik} — run download-filings first")
    return FilingIngestionService._load_facts(path)


def _get_framed_values(cik: str, concept: str, frame: str) -> list[float]:
    """Return all values for a concept/frame pair across all filings."""
    facts = _load_facts(cik)
    concept_obj = facts.get_concept(concept)
    if concept_obj is None or concept_obj.units.USD is None:
        return []
    return [
        v.val
        for v in concept_obj.units.USD
        if v.fp == "FY" and v.frame == frame
    ]


def _get_unframed_annual_values(cik: str, concept: str, period_end) -> list[float]:
    """Return all FY values without a frame for a specific period_end date."""
    facts = _load_facts(cik)
    concept_obj = facts.get_concept(concept)
    if concept_obj is None or concept_obj.units.USD is None:
        return []
    return [
        v.val
        for v in concept_obj.units.USD
        if v.fp == "FY" and not v.frame and v.end == period_end
    ]


# ---------------------------------------------------------------------------
# Tesla tests — consolidated values via frame tag
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestTeslaGoldenValues:

    def test_revenue_cy2024_matches_golden(self):
        """Tesla CY2024 revenue matches the consolidated golden value."""
        values = _get_framed_values(
            TSLA_GOLDEN["cik"],
            TSLA_GOLDEN["revenue_concept"],
            "CY2024",
        )
        assert values, "No CY2024 revenue found for Tesla"
        assert TSLA_GOLDEN["periods"]["CY2024"]["revenue"] in values

    def test_revenue_cy2023_matches_golden(self):
        values = _get_framed_values(
            TSLA_GOLDEN["cik"],
            TSLA_GOLDEN["revenue_concept"],
            "CY2023",
        )
        assert values
        assert TSLA_GOLDEN["periods"]["CY2023"]["revenue"] in values

    def test_net_income_cy2024_matches_golden(self):
        values = _get_framed_values(
            TSLA_GOLDEN["cik"],
            TSLA_GOLDEN["net_income_concept"],
            "CY2024",
        )
        assert values
        assert TSLA_GOLDEN["periods"]["CY2024"]["net_income"] in values

    def test_consolidated_not_segment(self):
        """Regression for A2: consolidated revenue must be the company total,
        not a segment sub-total. Tesla segments (Automotive, Energy, Services)
        each report Revenues without a frame — those values are always smaller
        than the consolidated total which carries a CY frame."""
        facts = _load_facts(TSLA_GOLDEN["cik"])
        revenue_concept = facts.get_concept(TSLA_GOLDEN["revenue_concept"])
        assert revenue_concept is not None

        usd_values = revenue_concept.units.USD or []

        # Collect all FY segment values (no frame) and all consolidated (with frame)
        segment_values = {
            v.val for v in usd_values if v.fp == "FY" and not v.frame
        }
        consolidated_cy2024 = TSLA_GOLDEN["periods"]["CY2024"]["revenue"]

        # Every segment value must be strictly less than the consolidated total
        # (or equal if a company happens to have a single segment — but Tesla
        # explicitly has multiple segments so they must all be smaller)
        for seg_val in segment_values:
            assert seg_val <= consolidated_cy2024, (
                f"Segment value {seg_val:,.0f} >= consolidated total "
                f"{consolidated_cy2024:,.0f} — possible A2 regression"
            )

    def test_group_facts_contains_framed_revenue(self):
        """_group_facts_by_filing must preserve the framed (consolidated) entry."""
        facts = _load_facts(TSLA_GOLDEN["cik"])
        grouped = FilingIngestionService._group_facts_by_filing(facts)

        # Find any filing that contains a revenue entry with CY2024 frame
        found = False
        for accn, fact_values in grouped.items():
            for concept_name, fv in fact_values:
                if (
                    concept_name == TSLA_GOLDEN["revenue_concept"]
                    and fv.frame == "CY2024"
                    and fv.val == TSLA_GOLDEN["periods"]["CY2024"]["revenue"]
                ):
                    found = True
                    break
        assert found, "Consolidated CY2024 revenue not found after _group_facts_by_filing"

    def test_build_line_item_rows_includes_frame(self):
        """_build_line_item_rows must store the frame field — required by A2 fix."""
        facts = _load_facts(TSLA_GOLDEN["cik"])
        grouped = FilingIngestionService._group_facts_by_filing(facts)

        # Take any filing that has revenue data
        for accn, fact_values in grouped.items():
            rows = FilingIngestionService._build_line_item_rows(1, fact_values)
            revenue_rows = [r for r in rows if r["concept"] == TSLA_GOLDEN["revenue_concept"]]
            if revenue_rows:
                for row in revenue_rows:
                    assert "frame" in row, "frame field missing from line item row"
                return
        pytest.fail("No revenue rows found in any Tesla filing")


# ---------------------------------------------------------------------------
# Apple tests — non-calendar FY, fallback path (frame='')
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestAppleGoldenValues:

    def test_revenue_fy2024_matches_golden(self):
        """Apple FY2024 revenue (no frame) matches the golden value."""
        period_end = AAPL_GOLDEN["periods"]["FY2024"]["period_end"]
        values = _get_unframed_annual_values(
            AAPL_GOLDEN["cik"],
            AAPL_GOLDEN["revenue_concept"],
            period_end,
        )
        assert values, f"No FY2024 revenue (frame='') found for Apple at {period_end}"
        assert AAPL_GOLDEN["periods"]["FY2024"]["revenue"] in values

    def test_revenue_fy2023_matches_golden(self):
        period_end = AAPL_GOLDEN["periods"]["FY2023"]["period_end"]
        values = _get_unframed_annual_values(
            AAPL_GOLDEN["cik"],
            AAPL_GOLDEN["revenue_concept"],
            period_end,
        )
        assert values
        assert AAPL_GOLDEN["periods"]["FY2023"]["revenue"] in values

    def test_net_income_fy2024_matches_golden(self):
        period_end = AAPL_GOLDEN["periods"]["FY2024"]["period_end"]
        values = _get_unframed_annual_values(
            AAPL_GOLDEN["cik"],
            AAPL_GOLDEN["net_income_concept"],
            period_end,
        )
        assert values
        assert AAPL_GOLDEN["periods"]["FY2024"]["net_income"] in values

    def test_group_facts_contains_apple_revenue(self):
        """_group_facts_by_filing must include Apple's unframed annual revenue."""
        facts = _load_facts(AAPL_GOLDEN["cik"])
        grouped = FilingIngestionService._group_facts_by_filing(facts)

        target_period = AAPL_GOLDEN["periods"]["FY2024"]["period_end"]
        target_val = AAPL_GOLDEN["periods"]["FY2024"]["revenue"]

        found = any(
            concept_name == AAPL_GOLDEN["revenue_concept"]
            and fv.end == target_period
            and fv.val == target_val
            for fact_values in grouped.values()
            for concept_name, fv in fact_values
        )
        assert found, "Apple FY2024 revenue not found after _group_facts_by_filing"


# ---------------------------------------------------------------------------
# Regression: removing frame filter must break test_consolidated_not_segment
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_segment_values_exist_for_tesla():
    """Sanity check: Tesla must actually have segment revenue entries (no frame)
    so that test_consolidated_not_segment is a meaningful guard."""
    facts = _load_facts(TSLA_GOLDEN["cik"])
    revenue_concept = facts.get_concept(TSLA_GOLDEN["revenue_concept"])
    assert revenue_concept is not None
    usd_values = revenue_concept.units.USD or []
    segment_entries = [v for v in usd_values if v.fp == "FY" and not v.frame]
    assert len(segment_entries) > 0, (
        "Tesla has no segment revenue entries — the A2 regression guard "
        "would not be meaningful without them"
    )
