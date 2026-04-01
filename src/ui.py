"""
Terminal UI utilities — Claude Code-style visuals for Job Profiler Tool.

All output flows through a single rich Console singleton so that spinner
contexts and panel rendering are always coherent.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich import box as rich_box

console = Console(highlight=False)

_BORDER_STYLE = "cyan"
_AGENT_TITLE = "[bold cyan]Job Agent[/bold cyan]"


def print_newline() -> None:
    """Print a blank line — call before a panel after keyboard interrupt."""
    console.print()


# ---------------------------------------------------------------------------
# Banner / greeting
# ---------------------------------------------------------------------------

def print_banner() -> None:
    """Print the application header rule."""
    console.print()
    console.print(
        Rule(
            "[bold cyan]◆  Job Profiler[/bold cyan]  "
            "[dim]AI-powered job search[/dim]",
            style="cyan",
        )
    )
    console.print()


def print_greeting(name: str) -> None:
    """Print a welcome panel addressed to the candidate before the chat loop."""
    body = Text()
    body.append(f"Hello, {name}!\n\n", style="bold white")
    body.append(
        "I'm your job search assistant. Tell me what kind of roles you're\n"
        "looking for — location, seniority, company, or anything else — and\n"
        "I'll search, tailor your resume, and generate a cover letter for each match.\n\n"
    )
    body.append("Type ", style="dim")
    body.append("exit", style="bold yellow")
    body.append(" to quit at any time.", style="dim")
    console.print(
        Panel(
            body,
            title=_AGENT_TITLE,
            border_style=_BORDER_STYLE,
            box=rich_box.ROUNDED,
            padding=(1, 2),
        )
    )
    console.print()


# ---------------------------------------------------------------------------
# Chat I/O
# ---------------------------------------------------------------------------

def print_agent_message(text: str) -> None:
    """Print an agent response in a styled rounded panel with markdown rendering."""
    console.print(
        Panel(
            Markdown(text.strip()),
            title=_AGENT_TITLE,
            border_style=_BORDER_STYLE,
            box=rich_box.ROUNDED,
            padding=(0, 1),
        )
    )
    console.print()


def user_prompt_text() -> str:
    """Return an ANSI-formatted prompt string for use with ``input()``."""
    # Bold green "You ›" — ANSI sequences render correctly in input()
    return "\033[1;32mYou \033[0m\033[32m›\033[0m "


# ---------------------------------------------------------------------------
# Spinner
# ---------------------------------------------------------------------------

@contextmanager
def thinking_spinner(message: str = "Thinking\u2026") -> Generator[None, None, None]:
    """Context manager that shows an animated dots spinner while work runs."""
    with console.status(f"[cyan]{message}[/cyan]", spinner="dots"):
        yield


# ---------------------------------------------------------------------------
# Pipeline progress
# ---------------------------------------------------------------------------

def print_step(message: str) -> None:
    """Print a dim pipeline progress bullet."""
    console.print(f"  [dim cyan]\u2022[/dim cyan] [dim]{message}[/dim]")


def print_success(message: str) -> None:
    """Print a green success line."""
    console.print(f"  [bold green]\u2713[/bold green] {message}")


def print_error(message: str) -> None:
    """Print a red error line."""
    console.print(f"  [bold red]\u2717[/bold red] {message}")


def print_model_switch(from_model: str, to_model: str) -> None:
    """Print a model-switch notification."""
    console.print(
        f"\n  [yellow]\u26a1[/yellow] "
        f"[dim]{from_model} overloaded \u2014 switching to [bold]{to_model}[/bold][/dim]"
    )


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------

def print_onboarding_intro() -> None:
    """Print the onboarding welcome panel."""
    body = Text()
    body.append("No resume.yaml found \u2014 let\u2019s build it together!\n\n", style="bold white")
    body.append(
        "Answer each question naturally, or paste text from your existing\n"
        "resume or LinkedIn profile. Type ",
        style="dim",
    )
    body.append("skip", style="bold yellow")
    body.append(" to leave a section empty.", style="dim")
    console.print(
        Panel(
            body,
            title="[bold cyan]Resume Onboarding[/bold cyan]",
            border_style=_BORDER_STYLE,
            box=rich_box.ROUNDED,
            padding=(1, 2),
        )
    )
    console.print()


def print_section_header(section_name: str) -> None:
    """Print a bold cyan section rule for onboarding."""
    console.print()
    console.print(Rule(f"[bold cyan]{section_name.upper()}[/bold cyan]", style="cyan"))


def print_onboarding_question(prompt: str) -> None:
    """Print a yellow styled onboarding question."""
    console.print()
    console.print(Text(prompt, style="yellow"))
    console.print()


def print_extracted_preview(section: str, yaml_text: str) -> None:
    """Print a YAML preview of the extracted section for the user to review."""
    console.print()
    console.print(
        Panel(
            yaml_text,
            title=f"[bold]Captured: {section.capitalize()}[/bold]",
            border_style="dim cyan",
            box=rich_box.SIMPLE_HEAVY,
            padding=(0, 1),
        )
    )
    console.print()


def onboarding_input_prompt() -> str:
    """Return ANSI-formatted free-text input prompt for onboarding."""
    return "\033[1;33m\u203a\033[0m "


def onboarding_confirm_prompt() -> str:
    """Return ANSI-formatted yes/edit/skip confirmation prompt for onboarding."""
    return (
        "\033[1;33mDoes this look right?\033[0m "
        "\033[2m(yes / edit / skip)\033[0m "
        "\033[33m\u203a\033[0m "
    )


# ---------------------------------------------------------------------------
# General-purpose output helpers
# ---------------------------------------------------------------------------

def print_warning(message: str) -> None:
    """Print a yellow warning line."""
    console.print(f"  [yellow]\u26a0[/yellow] [dim]{message}[/dim]")


def print_info(message: str) -> None:
    """Print a plain informational line."""
    console.print(f"  {message}")


def print_hint(message: str) -> None:
    """Print a dim instructional hint."""
    console.print(f"  [dim]{message}[/dim]")


def print_job_table(jobs: list[dict]) -> None:
    """Print a rich table of jobs from the Google Sheet."""
    table = Table(box=rich_box.SIMPLE_HEAVY, show_edge=False, pad_edge=False)
    table.add_column("Row", style="bold", width=5)
    table.add_column("Status", width=12)
    table.add_column("Job Title", width=30)
    table.add_column("URL", style="dim")
    for j in jobs:
        table.add_row(
            str(j["row"]),
            j["status"],
            j["job_title"][:28],
            j["url"][:50],
        )
    console.print()
    console.print(table)


def print_welcome(title: str, subtitle: str) -> None:
    """Print a welcome header for wizards / first-run screens."""
    console.print()
    console.print(f"  [bold cyan]{title}[/bold cyan]")
    console.print(f"  [dim]{subtitle}[/dim]")
    console.print()


def onboarding_edit_prompt() -> str:
    """Return ANSI-formatted correction prompt for onboarding."""
    return "\033[1;33mWhat should be changed?\033[0m \033[33m\u203a\033[0m "
