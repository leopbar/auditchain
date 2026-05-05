"""Test script for AuditRepository.

Validates that audit runs, agent steps, and red flags are correctly persisted 
in the PostgreSQL database and can be retrieved and listed.

Usage:
    python -m scripts.test_audit_repository
"""

import uuid
import sys
import traceback
from datetime import datetime
from decimal import Decimal

from rich.console import Console
from rich.table import Table

from auditchain.core.logging import configure_logging, get_logger
from auditchain.data.database import get_session
from auditchain.data.audit_repository import AuditRepository
from auditchain.schemas.components import RedFlag, Evidence
from auditchain.schemas.enums import FlagCategory, FlagSeverity

logger = get_logger(__name__)
console = Console()


def main():
    configure_logging()
    console.print("\n[bold cyan]AuditRepository Validation Test[/bold cyan]\n")

    test_results = []

    def log_result(name, success, notes=""):
        test_results.append({"name": name, "success": success, "notes": notes})

    with get_session() as session:
        repo = AuditRepository(session)
        audit_run_id = str(uuid.uuid4())
        # Use a real filing_id from the DB (25 is Apple in our common dev dataset)
        filing_id = 25 
        
        try:
            # 1. Create Run
            console.print("[dim]1. Testing create_run...[/dim]")
            run = repo.create_run(filing_id=filing_id, audit_run_id=audit_run_id, langgraph_thread_id="test-thread")
            
            # Diagnostic check
            success_id = str(run.id) == audit_run_id
            success_status = run.status == "running"
            success_start = run.started_at is not None
            success = success_id and success_status and success_start
            
            diag_notes = f"ID: {run.id}"
            if not success:
                diag_notes = f"FAIL -> ID_match={success_id}, Status='{run.status}' (expected 'running'), Start={success_start}"
            
            log_result("Create Audit Run", success, diag_notes)

            # 2. Add Agent Steps
            console.print("[dim]2. Testing add_agent_step...[/dim]")
            repo.add_agent_step(
                run_id=audit_run_id,
                agent_name="Collector",
                step_index=1,
                input_data={"ticker": "AAPL"},
                output_data={"status": "collected"},
                tokens_input=1000,
                tokens_output=500,
                cost_usd=0.003
            )
            repo.add_agent_step(
                run_id=audit_run_id,
                agent_name="Reconciler",
                step_index=2,
                input_data={"data_count": 10},
                output_data={"passed": True},
                tokens_input=2000,
                tokens_output=800,
                cost_usd=0.006
            )
            # Re-fetch to check steps count
            run = repo.get_run(audit_run_id)
            success = len(run.steps) == 2
            log_result("Add Agent Steps", success, f"Steps count: {len(run.steps)}")

            # 3. Add Red Flags
            console.print("[dim]3. Testing add_red_flags_from_list...[/dim]")
            pydantic_flags = [
                RedFlag(
                    detected_by="Reconciler",
                    category=FlagCategory.ACCOUNTING_EQUATION,
                    severity=FlagSeverity.HIGH,
                    title="Imbalanced Balance Sheet",
                    description="Assets do not match liabilities and equity.",
                    evidence=[Evidence(source="10-K", metric="Total Assets", value=100000000.0, quote="Assets: $100M mismatch")],
                    confidence=0.95
                ),
                RedFlag(
                    detected_by="Reconciler",
                    category=FlagCategory.DATA_QUALITY,
                    severity=FlagSeverity.MEDIUM,
                    title="Missing Historical Data",
                    description="Revenue for 2022 is missing.",
                    evidence=[],
                    confidence=0.80
                )
            ]
            repo.add_red_flags_from_list(audit_run_id, pydantic_flags)
            # Re-fetch to check flags
            run = repo.get_run(audit_run_id)
            success = len(run.red_flags) == 2
            log_result("Add Red Flags", success, f"Flags count: {len(run.red_flags)}")

            # 4. Complete Run
            console.print("[dim]4. Testing complete_run...[/dim]")
            final_report = {"summary": "Audit completed successfully", "score": 35.5}
            repo.complete_run(
                run_id=audit_run_id,
                risk_score=35.5,
                risk_level="medium",
                total_tokens=4300,
                total_cost_usd=0.009,
                final_report_json=final_report
            )
            run = repo.get_run(audit_run_id)
            success = run.status == "completed" and float(run.risk_score) == 35.5 and run.completed_at is not None
            log_result("Complete Audit Run", success, f"Status: {run.status}")

            # 5. Get Run
            console.print("[dim]5. Testing get_run...[/dim]")
            fetched = repo.get_run(audit_run_id)
            success = fetched is not None and fetched.final_report.get("score") == 35.5
            log_result("Get Audit Run", success)

            # 6. List Runs
            console.print("[dim]6. Testing list_runs...[/dim]")
            runs_list = repo.list_runs(limit=10)
            success = any(str(r.id) == audit_run_id for r in runs_list)
            log_result("List Audit Runs", success, f"List size: {len(runs_list)}")

            # 7. Cleanup (Delete)
            console.print("[dim]7. Testing Cleanup (delete)...[/dim]")
            session.delete(run)
            session.flush()
            deleted = repo.get_run(audit_run_id)
            success = deleted is None
            log_result("Cleanup Deletion", success)
            
            # Commit cleanup
            session.commit()

        except Exception as e:
            console.print(f"[bold red]Test failed with exception:[/bold red]\n{traceback.format_exc()}")
            log_result("Overall Test", False, str(e))
            session.rollback()

    # Summary Table
    table = Table(title="AuditRepository Test Summary")
    table.add_column("Test Case", style="cyan")
    table.add_column("Result", justify="center")
    table.add_column("Notes", style="dim")

    passed_count = 0
    for res in test_results:
        status = "[green]PASS[/green]" if res["success"] else "[red]FAIL[/red]"
        if res["success"]:
            passed_count += 1
        table.add_row(res["name"], status, res["notes"])

    console.print("\n")
    console.print(table)
    console.print(f"\n[bold]{passed_count} of {len(test_results)} sub-tests passed.[/bold]\n")

    if passed_count == len(test_results):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
