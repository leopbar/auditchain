"""Interactive test script for the Reconciler Agent.

Usage:
    python -m scripts.test_reconciler_agent
"""

import time
from rich.console import Console
from rich.panel import Panel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from auditchain.core.logging import configure_logging, get_logger
from auditchain.agents.reconciler import build_reconciler_agent

logger = get_logger(__name__)
console = Console()


def run_test(agent, test_name, question, console):
    """Executes a reconciliation test and displays the trace and results."""
    console.rule(f"[bold cyan]{test_name}[/bold cyan]", style="cyan")
    console.print(f"[bold yellow]User question:[/bold yellow] {question}")

    start_time = time.time()
    tool_calls_count = 0
    
    try:
        result = agent.invoke({"messages": [{"role": "user", "content": question}]})
        end_time = time.time()
        duration = end_time - start_time
        
        messages = result.get("messages", [])
        
        for msg in messages:
            if isinstance(msg, HumanMessage):
                continue
                
            if isinstance(msg, AIMessage):
                if msg.tool_calls:
                    tool_calls_count += len(msg.tool_calls)
                    for tc in msg.tool_calls:
                        console.print(
                            f"[bold green]AI → calling tool:[/bold green] [white]{tc['name']}[/white] "
                            f"with args: [dim]{tc['args']}[/dim]"
                        )
                else:
                    # Final Reconciliation Report
                    console.print(
                        Panel(
                            msg.content,
                            title="[bold magenta]Reconciliation Report[/bold magenta]",
                            border_style="magenta",
                        )
                    )
            
            elif isinstance(msg, ToolMessage):
                content_preview = (msg.content[:300] + "...") if len(msg.content) > 300 else msg.content
                console.print(f"[bold blue]Tool '{msg.name}' returned:[/bold blue]\n[dim]{content_preview}[/dim]")

        # Stats and Metadata
        last_msg = messages[-1] if messages else None
        input_tokens = 0
        output_tokens = 0
        if last_msg and hasattr(last_msg, "usage_metadata") and last_msg.usage_metadata:
            input_tokens = last_msg.usage_metadata.get("input_tokens", 0)
            output_tokens = last_msg.usage_metadata.get("output_tokens", 0)

        console.print(f"\n[bold]Statistics:[/bold]")
        console.print(f"  - Execution Time: [cyan]{duration:.2f}s[/cyan]")
        console.print(f"  - Tool Calls:     {tool_calls_count}")
        console.print(f"  - Tokens Used:    [white]{input_tokens + output_tokens}[/white] (In: {input_tokens}, Out: {output_tokens})\n")

    except Exception as e:
        console.print(f"[bold red]Test Failed with error:[/bold red] {e}")


def main():
    configure_logging()
    
    console.print("\n[bold cyan]Building Reconciler Agent...[/bold cyan]")
    agent = build_reconciler_agent()
    
    test_cases = [
        (
            "Test 1: Clean Math (Apple)", 
            "Reconcile the latest financials for AAPL. Make sure to check the Fundamental Accounting Equation."
        ),
        (
            "Test 2: Fraud/Anomaly Case (BHC)", 
            "Reconcile the latest financials for BHC. Make sure to check the Fundamental Accounting Equation."
        ),
    ]

    for name, question in test_cases:
        try:
            run_test(agent, name, question, console)
        except Exception as e:
            console.print(f"[bold red]Unexpected error in test loop:[/bold red] {e}")


if __name__ == "__main__":
    main()
