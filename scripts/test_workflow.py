"""End-to-end test script for the AuditChain workflow graph.

Usage:
    python -m scripts.test_workflow
"""

import time
from rich.console import Console
from rich.panel import Panel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from auditchain.core.logging import configure_logging
from auditchain.graph.workflow import build_audit_graph

console = Console()


def run_workflow_test(graph, company_ticker, console):
    """Executes the full audit workflow for a given company."""
    console.rule(f"[bold cyan]Full Audit: {company_ticker}[/bold cyan]", style="cyan")
    
    question = (
        f"Please perform a complete financial audit on the last 3 years of financials for {company_ticker}. "
        "Fetch the data, reconcile the fundamental accounting equations, and analyze the historical trends for anomalies."
    )
    console.print(f"[bold yellow]Request:[/bold yellow] {question}\n")

    start_time = time.time()
    
    try:
        # Invoke the graph with the initial message
        result = graph.invoke({"messages": [HumanMessage(content=question)]})
        end_time = time.time()
        duration = end_time - start_time
        
        messages = result.get("messages", [])
        
        # We'll track final AIMessages (those without tool calls) to identify agents
        # 1st = Collector, 2nd = Reconciler, 3rd = Anomaly Detector
        final_ai_messages_count = 0

        for i, msg in enumerate(messages):
            if isinstance(msg, HumanMessage):
                continue
            
            if isinstance(msg, AIMessage):
                if msg.tool_calls:
                    # Collector calling tools
                    for tc in msg.tool_calls:
                        console.print(
                            f"[bold green]Node Activity:[/bold green] AI is calling tool [white]{tc['name']}[/white] "
                            f"with args: [dim]{tc['args']}[/dim]"
                        )
                else:
                    final_ai_messages_count += 1
                    
                    if final_ai_messages_count == 1:
                        # Collector finishing
                        console.print(f"[bold cyan]Collector Output:[/bold cyan]\n{msg.content}\n")
                    elif final_ai_messages_count == 2:
                        # Reconciler finishing
                        console.print(
                            Panel(
                                msg.content,
                                title=f"[bold magenta]Reconciliation Report: {company_ticker}[/bold magenta]",
                                border_style="magenta",
                            )
                        )
                    else:
                        # Anomaly Detector (last agent)
                        console.print(
                            Panel(
                                msg.content,
                                title=f"[bold cyan]Anomaly Detection Report: {company_ticker}[/bold cyan]",
                                border_style="cyan",
                            )
                        )
            
            elif isinstance(msg, ToolMessage):
                content_preview = (msg.content[:200] + "...") if len(msg.content) > 200 else msg.content
                console.print(f"[bold blue]Tool Result:[/bold blue] {content_preview}")

        console.print(f"\n[bold]Total Execution Time:[/bold] [cyan]{duration:.2f}s[/cyan]\n")

    except Exception as e:
        console.print(f"[bold red]Workflow failed for {company_ticker}:[/bold red] {e}")


def main():
    configure_logging()
    
    console.print("\n[bold cyan]Initializing AuditChain Workflow Graph...[/bold cyan]")
    graph = build_audit_graph()
    
    # Run tests
    run_workflow_test(graph, "AAPL", console)
    run_workflow_test(graph, "BHC", console)


if __name__ == "__main__":
    main()
