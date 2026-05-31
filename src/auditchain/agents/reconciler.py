"""Reconciler Agent module.

The Reconciler Agent is responsible for validating the mathematical consistency
of financial data. It checks the accounting equation, year-over-year variations,
and accruals ratios using structured data provided by the Collector.
"""

from typing import Any

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from pydantic import ValidationError

from auditchain.core.config import get_settings
from auditchain.core.logging import get_logger
from auditchain.schemas.reports import ReconciliationReport
from auditchain.schemas.components import CheckResult, RedFlag
from auditchain.tools.reconciliation import (
    check_accounting_equation,
    check_yoy_consistency,
    compare_income_vs_cashflow,
)
from auditchain.tools.structured_output import submit_reconciliation

logger = get_logger(__name__)

RECONCILER_SYSTEM_PROMPT = """
You are the Reconciler Agent in AuditChain, a multi-agent SEC fraud detection system.

═══════════════════════════════════════════════════════════════
CRITICAL OUTPUT REQUIREMENTS — READ BEFORE ANYTHING ELSE
═══════════════════════════════════════════════════════════════

Your submission to submit_reconciliation MUST include BOTH the `checks` array AND the `red_flags` array.

These arrays are NOT redundant — they serve completely different purposes:
- `checks` = raw technical verification data (evidence)
- `red_flags` = FORMAL CONCERNS that trigger downstream risk scoring

WITHOUT red_flags, the entire audit's risk score will be ZERO regardless of how many checks fail. The Supervisor agent calculates risk ONLY from red_flags, not from checks.

ABSOLUTE RULE: If you submit with passed=False but red_flags is empty, your submission is INVALID and the audit will produce incorrect results. Every genuinely FAILED check (numbers present but equation does not balance) MUST have a corresponding red_flag. Checks that are INCONCLUSIVE (status="inconclusive", caused by missing/unreadable data) are EXEMPT — do NOT create a red_flag for them and do NOT count them as failures.

═══════════════════════════════════════════════════════════════

Your role is to validate the mathematical consistency and accounting integrity of the financial data collected for a target company.

TOOLS AVAILABLE:
- check_accounting_equation: verify Assets = Liabilities + Equity for a single period.
- check_yoy_consistency: compare current vs prior periods for excessive variations.
- compare_income_vs_cashflow: calculate accruals ratio (Net Income vs Operating Cash Flow).
- submit_reconciliation: finalize and submit your structured ReconciliationReport (call ONCE at the end).

REQUIRED WORKFLOW:
1. Examine the CompanyData provided in the user message.
2. Call check_accounting_equation on the current_period.
3. Call check_yoy_consistency comparing the current_period against ONLY the most recent historical_period (historical_periods[0] — the immediately prior fiscal year). Do NOT compare against older periods; the ±50% threshold is calibrated for consecutive annual periods and will produce false positives on multi-year spans for any company with sustained growth.
4. Call compare_income_vs_cashflow on the current_period.
5. For EVERY check where the equation genuinely FAILS (numbers exist but do not balance, status="failed"), create a RedFlag. Checks with status="inconclusive" (data was missing — the tool's notes name the missing field) require NO red_flag and must NOT mark the report as failed.
6. Call submit_reconciliation with checks, red_flags, passed, summary.

SEVERITY MAPPING FOR RED FLAGS (consecutive years only):
- Accounting Equation failure -> severity: "critical", category: "accounting_equation"
- YoY variation > 50% (current vs immediately prior year) -> severity: "high", category: "cash_flow_inconsistency"
- YoY variation 20-50% (current vs immediately prior year) -> severity: "medium", category: "cash_flow_inconsistency"
- Income vs Cashflow inconsistency -> severity: "high", category: "cash_flow_inconsistency"

Every RedFlag MUST have: detected_by="reconciler", confidence=0.95 or higher.

═══════════════════════════════════════════════════════════════
EXAMPLE — A submit_reconciliation call when accounting_equation FAILS:
═══════════════════════════════════════════════════════════════

submit_reconciliation(
  filing_id=12345,
  passed=false,
  checks=[
    {"name": "accounting_equation_2024", "passed": false, "expected": 30000000000.0, "actual": 28500000000.0, "tolerance": 0.01, "notes": "Assets do not equal Liabilities + Equity"},
    {"name": "yoy_revenue_2024_vs_2023", "passed": true, "expected": null, "actual": 0.05, "tolerance": 0.25, "notes": "Revenue change within tolerance"}
  ],
  red_flags=[
    {"detected_by": "reconciler", "category": "accounting_equation", "severity": "critical", "title": "Unbalanced Balance Sheet", "description": "Total assets ($30.0B expected) do not match liabilities + equity ($28.5B actual), a $1.5B discrepancy exceeding the 1% tolerance.", "confidence": 1.0}
  ]
)

Notice: 1 check failed -> 1 red_flag created. This is mandatory.

═══════════════════════════════════════════════════════════════

CRITICAL RULES:
- INCONCLUSIVE CHECKS: a check that could not run because a field was missing/unreadable
  has status="inconclusive". It is NOT a failure and NOT a fraud signal. Do NOT create a
  red_flag for it, and do NOT let it drive passed=False in your submission. Mention it
  plainly in the summary, naming the missing field (the tool's notes already state which
  field was not found).
- VALIDATION: count(red_flags) MUST >= count(checks that genuinely FAILED, i.e.
  status="failed"). Inconclusive checks require NO red_flag and do NOT count as failures.
- NEVER invent any number. Only use values from the provided CompanyData.
- Submit ONLY ONCE via submit_reconciliation when you have completed all checks.
"""


def build_reconciler_agent() -> Any:
    """Builds the Reconciler Agent with mathematical validation and submission tools.
    
    Uses a smarter LLM model to handle complex mathematical reasoning and structured output.
    """
    settings = get_settings()

    llm = ChatOpenAI(
        model=settings.llm_fast_model,
        api_key=settings.openai_api_key.get_secret_value(),
        temperature=0,
    )

    tools = [
        check_accounting_equation,
        check_yoy_consistency,
        compare_income_vs_cashflow,
        submit_reconciliation,
    ]

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=RECONCILER_SYSTEM_PROMPT,
    )

    logger.info(
        "reconciler_agent_built",
        model=settings.llm_fast_model,
        tool_count=len(tools)
    )

    return agent


def extract_reconciliation_from_messages(messages: list) -> ReconciliationReport | None:
    """Examines an agent's message history and extracts the ReconciliationReport 
    submitted via the submit_reconciliation tool. Returns None if the tool was never called.
    """
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc["name"] == "submit_reconciliation":
                    try:
                        args = tc["args"]
                        # The tool parameter is named 'report'
                        report_data = args.get("report", args)
                        
                        # Phase A Fix: Map and validate checks and red_flags explicitly
                        mapped_checks = []
                        raw_checks = report_data.get("checks", [])
                        if isinstance(raw_checks, list):
                            for c in raw_checks:
                                if not isinstance(c, dict): continue
                                # Attempt to map "result" to "actual" if LLM confused them
                                if "result" in c and "actual" not in c:
                                    c["actual"] = c["result"]
                                try:
                                    mapped_checks.append(CheckResult.model_validate(c))
                                except ValidationError:
                                    logger.warning("reconciler_extraction_skip_invalid_check", check_name=c.get("name"))

                        mapped_flags = []
                        raw_flags = report_data.get("red_flags", [])
                        if isinstance(raw_flags, list):
                            for f in raw_flags:
                                if not isinstance(f, dict): continue
                                try:
                                    mapped_flags.append(RedFlag.model_validate(f))
                                except ValidationError:
                                    logger.warning("reconciler_extraction_skip_invalid_flag", title=f.get("title"))

                        # Build the report with validated objects
                        return ReconciliationReport(
                            filing_id=report_data.get("filing_id"),
                            passed=report_data.get("passed", True),
                            summary=report_data.get("summary") or report_data.get("discrepancies", ""),
                            checks=mapped_checks,
                            red_flags=mapped_flags
                        )
                    except Exception as e:
                        logger.error("extract_reconciliation_error", error=str(e))
                        return None
    
    logger.warning("extract_reconciliation_no_submission_found")
    return None
