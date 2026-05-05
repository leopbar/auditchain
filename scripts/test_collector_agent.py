"""Interactive test script for the Collector Agent.

Usage:
    python -m scripts.test_collector_agent
"""

import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from auditchain.core.logging import configure_logging
from auditchain.agents.collector import build_collector_agent

console = Console()


def run_test(agent, test_id: int, test_name: str, question: str) -> dict:
    """Runs a single test case through the agent and displays the flow."""
    console.rule(f"[bold cyan]{test_name}[/bold cyan]", style="cyan")
    console.print(f"[bold yellow]User question:[/bold yellow] {question}")

    start_time = time.time()
    tool_calls_count = 0
    total_messages = 0
    
    try:
        result = agent.invoke({"messages": [{"role": "user", "content": question}]})
        end_time = time.time()
        total_time = end_time - start_time
        
        messages = result["messages"]
        total_messages = len(messages)

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
                    # Final answer
                    console.print(
                        Panel(
                            msg.content,
                            title="[bold magenta]Final Answer[/bold magenta]",
                            border_style="magenta",
                        )
                    )
            
            elif isinstance(msg, ToolMessage):
                content_preview = (msg.content[:300] + "...") if len(msg.content) > 300 else msg.content
                console.print(f"[bold blue]Tool '{msg.name}' returned:[/bold blue]\n[dim]{content_preview}[/dim]")

        # Metadata extraction
        last_msg = messages[-1]
        input_tokens = 0
        output_tokens = 0
        if hasattr(last_msg, "usage_metadata") and last_msg.usage_metadata:
            input_tokens = last_msg.usage_metadata.get("input_tokens", 0)
            output_tokens = last_msg.usage_metadata.get("output_tokens", 0)

        # Cost estimation (GPT-4o-mini prices)
        # Input: $0.15 / 1M tokens -> 0.00015 / 1K tokens
        # Output: $0.60 / 1M tokens -> 0.0006 / 1K tokens
        cost = (input_tokens * 0.15 / 1_000_000) + (output_tokens * 0.60 / 1_000_000)

        console.print(f"\n[bold]Statistics:[/bold]")
        console.print(f"  - Execution Time: [cyan]{total_time:.2f}s[/cyan]")
        console.print(f"  - Message Count:  {total_messages}")
        console.print(f"  - Tool Calls:     {tool_calls_count}")
        console.print(f"  - Tokens Used:    [white]{input_tokens + output_tokens}[/white] (In: {input_tokens}, Out: {output_tokens})")
        console.print(f"  - Estimated Cost: [green]${cost:.6f} USD[/green]\n")

        return {
            "id": test_id,
            "desc": test_name,
            "tool_calls": tool_calls_count,
            "time": total_time,
            "cost": cost,
            "status": "PASS"
        }

    except Exception as e:
        console.print(f"[bold red]Test Failed with error:[/bold red] {e}")
        return {
            "id": test_id,
            "desc": test_name,
            "tool_calls": 0,
            "time": 0,
            "cost": 0,
            "status": "FAIL"
        }


def main() -> None:
    configure_logging()

    console.print("\n[bold cyan]Building Collector Agent...[/bold cyan]")
    agent = build_collector_agent()
    
    test_cases = [
        ("Test 1: Simple analysis", "Make an initial analysis of company AAPL"),
        ("Test 2: Known fraud case", "Make an initial analysis of company BHC"),
        ("Test 3: Ambiguous question", "Which companies in the database are known fraud cases?"),
    ]

    summary_data = []

    for i, (name, question) in enumerate(test_cases, 1):
        result = run_test(agent, i, name, question)
        summary_data.append(result)

    # Final Summary Table
    table = Table(title="Collector Agent Test Summary", show_header=True, header_style="bold cyan")
    table.add_column("Test #", justify="right")
    table.add_column("Description")
    table.add_column("Tool Calls", justify="center")
    table.add_column("Total Time (s)", justify="right")
    table.add_column("Estimated Cost (USD)", justify="right")
    table.add_column("Status", justify="center")

    passed_count = 0
    for row in summary_data:
        status_color = "green" if row["status"] == "PASS" else "red"
        table.add_row(
            str(row["id"]),
            row["desc"],
            str(row["tool_calls"]),
            f"{row['time']:.2f}s",
            f"${row['cost']:.6f}",
            f"[{status_color}]{row['status']}[/{status_color}]"
        )
        if row["status"] == "PASS":
            passed_count += 1

    console.print(table)
    console.print(f"\n[bold]{passed_count} of {len(test_cases)} tests completed successfully.[/bold]\n")


if __name__ == "__main__":
    main()
