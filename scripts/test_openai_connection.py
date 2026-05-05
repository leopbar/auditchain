"""Validate OpenAI API connection and credentials.

Usage:
    python -m scripts.test_openai_connection
"""

import sys

import openai
from langchain_openai import ChatOpenAI
from rich.console import Console

from auditchain.core.config import get_settings
from auditchain.core.logging import configure_logging

console = Console()


def main() -> None:
    # 1. Initialize logging and config
    configure_logging()
    settings = get_settings()

    # 2. Check if API key exists
    if not settings.openai_api_key:
        console.print(
            "\n[bold red]Error:[/bold red] OPENAI_API_KEY is not configured."
        )
        console.print(
            "Please ensure you have an [bold cyan].env[/bold cyan] file with "
            "[bold]OPENAI_API_KEY=sk-...[/bold]"
        )
        sys.exit(1)

    console.print(
        f"\n[bold cyan]Testing OpenAI Connection[/bold cyan] using model: "
        f"[yellow]{settings.llm_fast_model}[/yellow]..."
    )

    try:
        # 3. Create LLM instance
        llm = ChatOpenAI(
            model=settings.llm_fast_model,
            api_key=settings.openai_api_key.get_secret_value(),
        )

        # 4. Invoke simple call
        response = llm.invoke("Say 'AuditChain is working' in exactly those words.")
        content = response.content.strip()

        # 5. Show results
        if "AuditChain is working" in content:
            console.print(
                f"\n[bold green]Success![/bold green] API response: \"{content}\""
            )
        else:
            console.print(
                f"\n[bold yellow]Warning:[/bold yellow] API responded but text didn't match "
                f"exactly. Received: \"{content}\""
            )

        # 6. Extract usage details
        # LangChain stores this in response_metadata or usage_metadata
        usage = getattr(response, "usage_metadata", None)
        if not usage:
            usage = response.response_metadata.get("token_usage", {})

        # Use safe access as keys can vary by library version
        if isinstance(usage, dict):
            input_tokens = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
            output_tokens = (
                usage.get("completion_tokens") or usage.get("output_tokens") or 0
            )
            total_tokens = usage.get("total_tokens") or (input_tokens + output_tokens)
        else:
            input_tokens = getattr(usage, "input_tokens", 0)
            output_tokens = getattr(usage, "output_tokens", 0)
            total_tokens = getattr(usage, "total_tokens", 0)

        # Estimate cost (gpt-4o-mini rates)
        # Input: $0.15 / 1M tokens
        # Output: $0.60 / 1M tokens
        cost_usd = (input_tokens * 0.00015 / 1000) + (output_tokens * 0.0006 / 1000)

        console.print("\n[bold cyan]Usage Statistics:[/bold cyan]")
        console.print(f"  Model used:    [white]{settings.llm_fast_model}[/white]")
        console.print(f"  Input tokens:  [white]{input_tokens}[/white]")
        console.print(f"  Output tokens: [white]{output_tokens}[/white]")
        console.print(f"  Total tokens:  [white]{total_tokens}[/white]")
        console.print(f"  Est. Cost:    [green]${cost_usd:.6f}[/green]")

    except openai.AuthenticationError:
        console.print(
            "\n[bold red]Authentication Error:[/bold red] The provided OpenAI API key is invalid."
        )
        sys.exit(1)
    except openai.RateLimitError:
        console.print(
            "\n[bold red]Rate Limit Error:[/bold red] You have exceeded your quota "
            "or your account has no remaining credits."
        )
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
