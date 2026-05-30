"""Standalone regression tests for the XBRL false-positive fix (Tesla case).

Covers, without needing a live database or LLM:
  1. Accounting-equation tri-state: missing data -> 'inconclusive' (not a failure),
     balanced -> 'passed', genuinely unbalanced -> 'failed'.
  2. determine_conclusion: missing/inconclusive data never forces ADVERSE; only a
     genuine integrity failure (or high risk) does.
  3. Composition-based derivation of balance-sheet aggregates (alias gaps), with
     the database lookup monkeypatched.
  4. CheckResult.status defaulting from `passed` for back-compat.

Run with: python scripts/test_xbrl_fix.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from auditchain.agents.supervisor import determine_conclusion
from auditchain.schemas.components import CheckResult, FinancialPeriod
from auditchain.schemas.enums import AuditConclusion
from auditchain.tools import financial_data
from auditchain.tools.reconciliation import check_accounting_equation

_eq = check_accounting_equation.func  # unwrap the LangChain @tool


def test_accounting_equation_tristate() -> None:
    missing = _eq(
        FinancialPeriod(
            filing_id=1, total_assets=100.0, total_liabilities=60.0, stockholders_equity=None
        )
    )
    assert missing.status == "inconclusive", missing.status
    assert missing.passed is False
    assert "Stockholders' Equity" in (missing.notes or ""), missing.notes

    balanced = _eq(
        FinancialPeriod(
            filing_id=1, total_assets=100.0, total_liabilities=60.0, stockholders_equity=40.0
        )
    )
    assert balanced.status == "passed", balanced.status

    unbalanced = _eq(
        FinancialPeriod(
            filing_id=1, total_assets=100.0, total_liabilities=60.0, stockholders_equity=10.0
        )
    )
    assert unbalanced.status == "failed", unbalanced.status
    print("OK  accounting_equation tri-state")


def _integrity_failed(checks: list[CheckResult]) -> bool:
    # Mirrors the deterministic derivation in supervisor_node.
    return any(getattr(c, "status", None) == "failed" for c in checks)


def test_determine_conclusion() -> None:
    inconclusive = _eq(
        FinancialPeriod(
            filing_id=1, total_assets=100.0, total_liabilities=60.0, stockholders_equity=None
        )
    )
    failed = _eq(
        FinancialPeriod(
            filing_id=1, total_assets=100.0, total_liabilities=60.0, stockholders_equity=10.0
        )
    )
    # Missing data with low risk must stay CLEAN (the bug forced ADVERSE here).
    assert determine_conclusion(10.0, _integrity_failed([inconclusive])) == AuditConclusion.CLEAN
    # Genuine integrity failure -> ADVERSE.
    assert determine_conclusion(10.0, _integrity_failed([failed])) == AuditConclusion.ADVERSE
    # Risk thresholds still apply.
    assert determine_conclusion(80.0, False) == AuditConclusion.ADVERSE
    assert determine_conclusion(30.0, False) == AuditConclusion.QUALIFIED
    assert determine_conclusion(5.0, False) == AuditConclusion.CLEAN
    print("OK  determine_conclusion ignores inconclusive, honors genuine failure")


def test_derivation_by_composition() -> None:
    # Simulate a filer that tags only the pieces, not the aggregates.
    fake_db = {
        "LiabilitiesNoncurrent": 70.0,
        "StockholdersEquity": 30.0,  # parent only
        "MinorityInterest": 5.0,  # NCI
    }

    def fake_lookup(session, filing_id, concept_names):
        for c in concept_names:
            if c in fake_db:
                return fake_db[c], c
        return None, None

    original = financial_data._get_value_for_concept
    financial_data._get_value_for_concept = fake_lookup
    try:
        values = {"current_liabilities": 40.0, "total_liabilities": None, "stockholders_equity": None}
        provenance: dict[str, str] = {}
        financial_data._derive_balance_sheet_aggregates(None, 1, values, provenance)

        assert values["total_liabilities"] == 110.0, values["total_liabilities"]  # 40 + 70
        assert values["stockholders_equity"] == 35.0, values["stockholders_equity"]  # 30 + 5 (NCI)
        assert "LiabilitiesCurrent + LiabilitiesNoncurrent" in provenance["total_liabilities"]
        assert "StockholdersEquity + MinorityInterest" in provenance["stockholders_equity"]
    finally:
        financial_data._get_value_for_concept = original
    print("OK  derivation by composition (Liabilities & NCI-inclusive equity)")


def test_derivation_last_resort_identity() -> None:
    # Only the balance-sheet total (RHS) and equity are available.
    fake_db = {"LiabilitiesAndStockholdersEquity": 100.0}

    def fake_lookup(session, filing_id, concept_names):
        for c in concept_names:
            if c in fake_db:
                return fake_db[c], c
        return None, None

    original = financial_data._get_value_for_concept
    financial_data._get_value_for_concept = fake_lookup
    try:
        values = {"current_liabilities": None, "total_liabilities": None, "stockholders_equity": 40.0}
        provenance: dict[str, str] = {}
        financial_data._derive_balance_sheet_aggregates(None, 1, values, provenance)
        assert values["total_liabilities"] == 60.0, values["total_liabilities"]  # 100 - 40
        assert "LiabilitiesAndStockholdersEquity - StockholdersEquity" in provenance["total_liabilities"]
    finally:
        financial_data._get_value_for_concept = original
    print("OK  derivation last-resort identity (RHS - equity)")


def test_checkresult_status_default() -> None:
    assert CheckResult(name="x", passed=True).status == "passed"
    assert CheckResult(name="x", passed=False).status == "failed"
    assert CheckResult(name="x", passed=False, status="inconclusive").status == "inconclusive"
    print("OK  CheckResult.status defaulting")


if __name__ == "__main__":
    test_accounting_equation_tristate()
    test_determine_conclusion()
    test_derivation_by_composition()
    test_derivation_last_resort_identity()
    test_checkresult_status_default()
    print("\nALL XBRL FIX TESTS PASSED")
