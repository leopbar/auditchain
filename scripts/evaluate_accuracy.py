"""Accuracy evaluation script for AuditChain.

This script runs the full audit workflow against a benchmark of known fraud 
and control cases to evaluate the system's detection precision, recall, and accuracy.

Usage:
    python -m scripts.evaluate_accuracy
"""

import uuid
import time
import json
import datetime
import traceback
from pathlib import Path
from typing import Any, List

from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from auditchain.core.config import get_settings
from auditchain.core.logging import configure_logging, get_logger
from auditchain.graph.workflow import build_audit_graph
from auditchain.graph.state import create_initial_state
from auditchain.data.known_fraud_cases import get_benchmark_companies, FraudCase
from auditchain.schemas.enums import AuditConclusion

# Initialize components
configure_logging()
logger = get_logger(__name__)
console = Console()
settings = get_settings()

def get_system_prediction(final_report: Any) -> str:
    """Categorizes the audit result into FLAGGED, CLEAN, or CAUTIOUS."""
    if not final_report:
        return "SYSTEM_ERROR"
    
    # AuditConclusion values are lowercase (e.g., 'clean', 'adverse')
    conclusion = final_report.audit_conclusion
    score = final_report.risk_score
    
    if conclusion == AuditConclusion.ADVERSE or (conclusion == AuditConclusion.QUALIFIED and score > 50):
        return "FLAGGED"
    elif conclusion == AuditConclusion.CLEAN or score <= 20:
        return "CLEAN"
    else:
        return "CAUTIOUS"

def main():
    console.print(Panel("[bold green]AuditChain Accuracy Evaluation Benchmark[/bold green]", subtitle="v1.0"))
    
    # 1. Setup
    # Use the fast model (gpt-4o-mini) as requested
    graph = build_audit_graph()
    benchmark_companies = get_benchmark_companies()
    results = []
    
    # 2. Filtering for available local data
    data_dir = Path("data/raw/sec_edgar")
    available_companies = []
    for comp in benchmark_companies:
        facts_path = data_dir / comp.cik / "company_facts.json"
        if facts_path.exists():
            available_companies.append(comp)
        else:
            console.print(f"[dim]Skipping {comp.name} ({comp.ticker}) - No local data found in {facts_path}[/dim]")
            
    total_comps = len(available_companies)
    if total_comps == 0:
        console.print("[bold red]No companies with local data found for evaluation![/bold red]")
        return

    console.print(f"\n[bold]Starting evaluation for {total_comps} companies...[/bold]\n")
    
    # 3. Execution Loop
    for i, comp in enumerate(available_companies, 1):
        console.print(f"[bold cyan]Auditing {comp.name} ({comp.ticker})... ({i} of {total_comps})[/bold cyan]")
        
        run_id = str(uuid.uuid4())
        initial_state = create_initial_state(
            audit_run_id=run_id, 
            company_cik=comp.cik, 
            company_ticker=comp.ticker
        )
        
        start_time = time.time()
        try:
            # Invoke the graph
            output = graph.invoke(initial_state)
            duration = time.time() - start_time
            
            final_report = output.get("final_report")
            usage_metadata = output.get("usage_metadata", {})
            tokens = usage_metadata.get("total_tokens", 0)
            cost = usage_metadata.get("total_cost_usd", 0.0)
            
            prediction = get_system_prediction(final_report)
            
            ground_truth = "FRAUD" if comp.is_known_fraud else "CLEAN"
            match = False
            # Logic: Match if Fraud detected as FLAGGED or Clean detected as CLEAN
            if ground_truth == "FRAUD" and prediction == "FLAGGED": match = True
            if ground_truth == "CLEAN" and prediction == "CLEAN": match = True
            
            results.append({
                "company": comp.name,
                "ticker": comp.ticker,
                "cik": comp.cik,
                "ground_truth": ground_truth,
                "conclusion": final_report.audit_conclusion.value if final_report else "ERROR",
                "risk_score": final_report.risk_score if final_report else 0.0,
                "red_flags": len(output.get("consolidated_red_flags", []) or output.get("red_flags", [])),
                "prediction": prediction,
                "match": match,
                "duration": duration,
                "tokens": tokens,
                "cost": cost,
                "status": "SUCCESS"
            })
            
            console.print(f" [green]✓[/green] Done. Prediction: {prediction} (Match: {match})")
            
        except Exception as e:
            duration = time.time() - start_time
            console.print(f" [bold red]✗[/bold red] Error auditing {comp.name}: {str(e)}")
            logger.error("evaluation_task_failed", company=comp.ticker, error=str(e), traceback=traceback.format_exc())
            
            results.append({
                "company": comp.name,
                "ticker": comp.ticker,
                "cik": comp.cik,
                "ground_truth": "FRAUD" if comp.is_known_fraud else "CLEAN",
                "conclusion": "SYSTEM_ERROR",
                "risk_score": 0.0,
                "red_flags": 0,
                "prediction": "SYSTEM_ERROR",
                "match": False,
                "duration": duration,
                "tokens": 0,
                "cost": 0.0,
                "status": "FAILED",
                "error": str(e)
            })
            
        # Cooldown between companies to reset TPM limits
        if i < total_comps:
            console.print(f"[dim]Waiting 90 seconds to reset Rate Limits...[/dim]")
            time.sleep(90)
            
    # 4. Metric Calculations
    tp = sum(1 for r in results if r["ground_truth"] == "FRAUD" and r["prediction"] == "FLAGGED")
    tn = sum(1 for r in results if r["ground_truth"] == "CLEAN" and r["prediction"] == "CLEAN")
    fp = sum(1 for r in results if r["ground_truth"] == "CLEAN" and r["prediction"] == "FLAGGED")
    fn = sum(1 for r in results if r["ground_truth"] == "FRAUD" and r["prediction"] == "CLEAN")
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    accuracy = (tp + tn) / len(results) if len(results) > 0 else 0.0
    
    total_cost = sum(r["cost"] for r in results)
    total_tokens = sum(r["tokens"] for r in results)
    total_duration = sum(r["duration"] for r in results)
    
    # 5. Reporting
    # Detailed Table
    table = Table(title="AuditChain Accuracy Evaluation - Detailed Results", show_header=True, header_style="bold")
    table.add_column("Company", style="cyan", min_width=20)
    table.add_column("Ground Truth", justify="center")
    table.add_column("Conclusion", justify="center")
    table.add_column("Score", justify="right")
    table.add_column("Flags", justify="right")
    table.add_column("Prediction", justify="center")
    table.add_column("Match", justify="center")
    table.add_column("Cost", justify="right")
    
    for r in results:
        match_icon = "[green]✓[/green]" if r["match"] else "[red]✗[/red]"
        gt_label = f"[bold red]FRAUD[/bold red]" if r["ground_truth"] == "FRAUD" else "[bold green]CLEAN[/bold green]"
        
        pred_color = "yellow"
        if r["prediction"] == "FLAGGED": pred_color = "red"
        if r["prediction"] == "CLEAN": pred_color = "green"
        
        table.add_row(
            f"{r['company']} ({r['ticker']})",
            gt_label,
            r["conclusion"].upper(),
            f"{r['risk_score']:.1f}",
            str(r["red_flags"]),
            f"[{pred_color}]{r['prediction']}[/{pred_color}]",
            match_icon,
            f"${r['cost']:.3f}"
        )
    
    console.print("\n", table, "\n")
    
    # Summary Metrics Panel
    summary_text = [
        f"[bold cyan]Aggregation Metrics[/bold cyan]",
        f"Precision (TP/TP+FP): [bold]{precision:.2%}[/bold]",
        f"Recall (TP/TP+FN):    [bold]{recall:.2%}[/bold]",
        f"Accuracy (TP+TN/ALL): [bold]{accuracy:.2%}[/bold]",
        f"\n[bold cyan]Confusion Matrix[/bold cyan]",
        f"                   [dim]PRED: CLEAN[/dim]   [dim]PRED: FLAGGED[/dim]",
        f"[dim]GT: CLEAN (Ctrl)[/dim]    [green]TN: {tn}[/green]            [red]FP: {fp}[/red]",
        f"[dim]GT: FRAUD (Cases)[/dim]   [red]FN: {fn}[/red]            [green]TP: {tp}[/green]",
        f"\n[bold cyan]Execution Profile[/bold cyan]",
        f"Total Cost:     ${total_cost:.4f}",
        f"Total Tokens:   {total_tokens:,}",
        f"Total Duration: {total_duration/60:.1f} minutes",
        f"Avg Time/Co:    {total_duration/len(results):.1f}s"
    ]
    console.print(Panel("\n".join(summary_text), title="Accuracy Benchmark Summary", border_style="bold green", expand=False))
    
    # 6. Save Results
    output_data = {
        "evaluation_timestamp": datetime.datetime.now().isoformat(),
        "metrics": {
            "precision": precision,
            "recall": recall,
            "accuracy": accuracy,
            "counts": {"tp": tp, "tn": tn, "fp": fp, "fn": fn}
        },
        "totals": {
            "cost": total_cost,
            "tokens": total_tokens,
            "duration_seconds": total_duration
        },
        "individual_results": results
    }
    
    output_path = Path("data/processed/evaluation_results.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=4)
    
    console.print(f"\n[bold green]Detailed evaluation results saved to:[/bold green] {output_path}")

if __name__ == "__main__":
    main()
