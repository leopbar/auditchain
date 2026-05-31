"""Golden reference values for ingestion reconciliation tests.

Values sourced directly from company_facts.json files on disk
(data/raw/sec_edgar/{CIK}/company_facts.json) and cross-checked
against the SEC EDGAR filing viewer.

Tesla (TSLA, CIK 0001318605):
  Dec 31 fiscal year → consolidated facts carry frame='CY20XX'.
  These frame tags are what separates total-company figures from
  segment-level breakdowns (the A2 bug vector).

Apple (AAPL, CIK 0000320193):
  Sep 28 fiscal year → frame='' for annual FY facts because the
  period does not align with the SEC's standard calendar year frames.
  Exercises the fallback path in _get_value_for_concept.

Revenue concept used: RevenueFromContractWithCustomerExcludingAssessedTax
  (the primary modern tag for both companies).
"""

from datetime import date

# ---------------------------------------------------------------------------
# Tesla — consolidated facts identified by frame tag
# ---------------------------------------------------------------------------
TSLA_GOLDEN = {
    "cik": "0001318605",
    "ticker": "TSLA",
    "revenue_concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "net_income_concept": "NetIncomeLoss",
    "assets_concept": "Assets",
    # keyed by the SEC frame tag present in company_facts.json
    "periods": {
        "CY2024": {
            "revenue": 97_690_000_000,
            "net_income": 7_091_000_000,
            "total_assets": 122_070_000_000,  # Q4 instant (CY2024Q4I)
            "period_end": date(2024, 12, 31),
        },
        "CY2023": {
            "revenue": 96_773_000_000,
            "net_income": 14_997_000_000,
            "total_assets": 106_618_000_000,
            "period_end": date(2023, 12, 31),
        },
        "CY2022": {
            "revenue": 81_462_000_000,
            "net_income": 12_556_000_000,
            "total_assets": 82_338_000_000,
            "period_end": date(2022, 12, 31),
        },
    },
}

# ---------------------------------------------------------------------------
# Apple — consolidated facts without frame (non-calendar FY)
# ---------------------------------------------------------------------------
AAPL_GOLDEN = {
    "cik": "0000320193",
    "ticker": "AAPL",
    "revenue_concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "net_income_concept": "NetIncomeLoss",
    "assets_concept": "Assets",
    # keyed by period_end date (no frame tag available)
    "periods": {
        "FY2024": {
            "revenue": 391_035_000_000,
            "net_income": 93_736_000_000,
            "total_assets": 364_980_000_000,
            "period_end": date(2024, 9, 28),
        },
        "FY2023": {
            "revenue": 383_285_000_000,
            "net_income": 96_995_000_000,
            "total_assets": 352_583_000_000,
            "period_end": date(2023, 9, 30),
        },
    },
}

ALL_GOLDEN = [TSLA_GOLDEN, AAPL_GOLDEN]
