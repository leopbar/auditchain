"""Curated catalog of US-listed companies with documented accounting fraud.

These serve as ground truth for evaluating AuditChain's detection accuracy.
All cases are based on public SEC enforcement actions (AAERs), DOJ filings,
or admitted restatements.

Reference: SEC Accounting and Auditing Enforcement Releases
https://www.sec.gov/divisions/enforce/friactions.htm
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FraudCase:
    cik: str
    ticker: str
    name: str
    fraud_period: tuple[str, str]
    fraud_type: str
    description: str
    aaer_reference: str | None = None
    is_known_fraud: bool = True


KNOWN_FRAUD_CASES: list[FraudCase] = [
    FraudCase(
        cik="0000885590",
        ticker="BHC",
        name="Bausch Health Companies",
        fraud_period=("2014", "2016"),
        fraud_type="related_party_revenue_inflation",
        description=(
            "The company (formerly Valeant Pharmaceuticals) used a secretly "
            "controlled specialty pharmacy called Philidor to inflate revenue "
            "through undisclosed related party sales. Resulted in class action, "
            "$45M SEC settlement in 2020, and corporate rebranding in 2018."
        ),
        aaer_reference="SEC v. Valeant 2020",
        is_known_fraud=True,
    ),
    FraudCase(
        cik="0000723527",
        ticker="WCOEQ",
        name="WorldCom Inc",
        fraud_period=("1999", "2002"),
        fraud_type="expense_capitalization",
        description=(
            "Capitalized $3.8B of operating expenses (line costs) as capital "
            "expenditures to inflate earnings. Largest accounting fraud at the time."
        ),
        aaer_reference="AAER 1658",
    ),
    FraudCase(
        cik="0001628280",
        ticker="LK",
        name="Luckin Coffee Inc",
        fraud_period=("2019", "2020"),
        fraud_type="revenue_fabrication",
        description=(
            "Fabricated approximately $310M in sales through fake transactions "
            "and shell companies. Delisted from NASDAQ in 2020."
        ),
        aaer_reference="SEC v. Luckin Coffee 2020",
    ),
    FraudCase(
        cik="0001318605",
        ticker="TSLA",
        name="Tesla Inc",
        fraud_period=("2018", "2018"),
        fraud_type="disclosure_misstatement",
        description=(
            "CEO disclosure misstatement (going-private tweet). Included as a "
            "non-financial-statement-fraud control case for testing specificity."
        ),
        aaer_reference="SEC v. Musk 2018",
        is_known_fraud=False,
    ),
    FraudCase(
        cik="0000866787",
        ticker="HPQ",
        name="Hewlett-Packard (Autonomy acquisition)",
        fraud_period=("2009", "2011"),
        fraud_type="revenue_recognition",
        description=(
            "Autonomy executives accused of inflating revenue before HP "
            "acquisition. $8.8B writedown in 2012."
        ),
        aaer_reference="SEC v. Hussain 2018",
    ),
    FraudCase(
        cik="0000074260",
        ticker="OXY",
        name="Occidental Petroleum",
        fraud_period=("2020", "2020"),
        fraud_type="control_case",
        description=(
            "Clean control case — no known fraud. Used to test false positive rate."
        ),
        is_known_fraud=False,
    ),
    FraudCase(
        cik="0000320193",
        ticker="AAPL",
        name="Apple Inc",
        fraud_period=("2023", "2023"),
        fraud_type="control_case",
        description="Clean control case — no known fraud. Tests false positive rate.",
        is_known_fraud=False,
    ),
]


def get_benchmark_companies() -> list[FraudCase]:
    """Return the full benchmark list (fraud + control cases)."""
    return KNOWN_FRAUD_CASES.copy()


def get_fraud_only() -> list[FraudCase]:
    """Return only confirmed fraud cases."""
    return [c for c in KNOWN_FRAUD_CASES if c.is_known_fraud]


def get_control_companies() -> list[FraudCase]:
    """Return only clean control cases (no known fraud)."""
    return [c for c in KNOWN_FRAUD_CASES if not c.is_known_fraud]
