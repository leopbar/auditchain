"""Test script for the Investigation Tools (Semantic Search).

Tests search_disclosures, find_related_parties, and detect_language_patterns
using real data for Apple (AAPL) and Bausch Health (BHC).

Usage:
    python -m scripts.test_investigation_tools
"""

import sys
import re
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from auditchain.core.logging import configure_logging
from auditchain.tools.investigation import (
    search_disclosures,
    find_related_parties,
    detect_language_patterns
)

console = Console()


def extract_top_similarity(output: str) -> float:
    """Helper to extract the highest similarity score from tool output string."""
    matches = re.findall(r"Similarity: (\d+\.\d+)%", output)
    if matches:
        return max(float(m) for m in matches)
    return 0.0


def extract_results_count(output: str) -> int:
    """Helper to count results in the formatted output string."""
    if "No relevant disclosures found" in output:
        return 0
    return len(re.findall(r"--- Result \d+", output))


def run_tests_for_filing(filing_id: int, company_name: str):
    """Executes a series of semantic search tests for a specific filing."""
    console.rule(f"[bold cyan]Testing {company_name} (Filing ID: {filing_id})[/bold cyan]", style="cyan")
    
    test_results = []
    
    # Test 1: Revenue Recognition Search
    console.print(f"\n[bold yellow]Task 1: Search 'revenue recognition policy' (Notes)[/bold yellow]")
    res1 = search_disclosures.invoke({
        "filing_id": filing_id, 
        "query": "revenue recognition policy", 
        "section": "notes_to_financials"
    })
    console.print(Panel(res1, border_style="dim"))
    test_results.append({
        "tool": "search_disclosures (Revenue)", 
        "count": extract_results_count(res1), 
        "top_sim": extract_top_similarity(res1)
    })

    # Test 2: Risks and Uncertainties Search
    console.print(f"\n[bold yellow]Task 2: Search 'significant risks and uncertainties' (Risk Factors)[/bold yellow]")
    res2 = search_disclosures.invoke({
        "filing_id": filing_id, 
        "query": "significant risks and uncertainties", 
        "section": "risk_factors"
    })
    console.print(Panel(res2, border_style="dim"))
    test_results.append({
        "tool": "search_disclosures (Risks)", 
        "count": extract_results_count(res2), 
        "top_sim": extract_top_similarity(res2)
    })

    # Test 3: Related Parties
    console.print(f"\n[bold yellow]Task 3: Find Related Parties[/bold yellow]")
    res3 = find_related_parties.invoke({"filing_id": filing_id})
    console.print(Panel(res3, border_style="dim"))
    test_results.append({
        "tool": "find_related_parties", 
        "count": extract_results_count(res3), 
        "top_sim": extract_top_similarity(res3)
    })

    # Test 4: Language Patterns
    console.print(f"\n[bold yellow]Task 4: Detect Language Patterns (Red Flags)[/bold yellow]")
    res4 = detect_language_patterns.invoke({"filing_id": filing_id})
    console.print(Panel(res4, border_style="dim"))
    test_results.append({
        "tool": "detect_language_patterns", 
        "count": extract_results_count(res4), 
        "top_sim": extract_top_similarity(res4)
    })

    return test_results


def main():
    configure_logging()
    console.print("\n[bold reverse cyan] AuditChain: Investigation Tools Validation [/bold reverse cyan]\n")
    
    filings = [
        (25, "Apple Inc. (AAPL)"),
        (137, "Bausch Health (BHC)")
    ]
    
    all_summary_data = []
    
    for fid, name in filings:
        try:
            results = run_tests_for_filing(fid, name)
            for r in results:
                all_summary_data.append({
                    "company": name,
                    **r
                })
        except Exception as e:
            console.print(f"[bold red]Error testing {name}:[/bold red] {str(e)}")
        console.print("\n")

    # Final Summary Table
    summary_table = Table(title="Semantic Search Investigation Summary")
    summary_table.add_column("Company", style="cyan")
    summary_table.add_column("Tool", style="magenta")
    summary_table.add_column("Results Found", justify="right")
    summary_table.add_column("Top Similarity", justify="right")

    for row in all_summary_data:
        sim_color = "green" if row["top_sim"] > 70 else "yellow"
        summary_table.add_row(
            row["company"],
            row["tool"],
            str(row["count"]),
            f"[{sim_color}]{row['top_sim']:.1f}%[/{sim_color}]"
        )

    console.print(summary_table)
    console.print("\n[bold cyan]End of Investigation Tools Validation[/bold cyan]\n")


if __name__ == "__main__":
    main()
