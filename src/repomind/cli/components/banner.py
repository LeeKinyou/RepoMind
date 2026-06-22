"""Startup banner and compact status components for RepoMind CLI."""

from __future__ import annotations

from pathlib import Path

from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


WORDMARK_TOP = "R E P O"
WORDMARK_BOTTOM = "M I N D"
TAGLINE = "understand the code before changing it"
MAX_CONTENT_WIDTH = 68


def _status_table(
    project_path: Path,
    project_name: str,
    stats: dict | None,
) -> Table:
    """Build the workspace status table."""
    table = Table.grid(expand=True, padding=(0, 1))
    table.add_column(style="muted", width=10, no_wrap=True)
    table.add_column(ratio=1, overflow="fold")

    table.add_row("project", Text(project_name, style="workspace.name"))
    table.add_row("path", Text(str(project_path), style="workspace.path"))

    if stats:
        files = stats.get("files", 0)
        symbols = stats.get("symbols", 0)
        classes = stats.get("classes", 0)
        status = Text("* index ready", style="status.ready")
        status.append(
            f"   {files:,} files | {symbols:,} symbols | {classes:,} classes",
            style="muted",
        )
    else:
        status = Text("* index required", style="status.pending")
        status.append("   run ", style="muted")
        status.append("/index", style="command")
        status.append(" to analyze this repository", style="muted")
    table.add_row("status", status)
    return table


def show_banner(
    console: Console,
    project_path: Path,
    stats: dict | None = None,
    project_name: str | None = None,
) -> None:
    """Display the RepoMind brand and current workspace state."""
    name = project_name or project_path.name or str(project_path)
    content_width = min(MAX_CONTENT_WIDTH, max(36, console.width - 4))

    console.print()
    logo_lines = [
        "    [bold cyan]____                       __  ____[/bold cyan][bold magenta]            __[/bold magenta]",
        "   [bold cyan]/ __ \\___  ____  ____  ____/  |/  (_)[/bold cyan][bold magenta]___  ____/ /[/bold magenta]",
        "  [bold cyan]/ /_/ / _ \\/ __ \\/ __ \\/ __  /|_/ / /[/bold cyan][bold magenta] __ \\/ __  /[/bold magenta]",
        " [bold cyan]/ _, _/  __/ /_/ / /_/ / /_/ /  / / / /[/bold cyan][bold magenta] / / / /_/ /[/bold magenta]",
        "[bold cyan]/_/ |_|\\___/ .___/\\____/\\__,_/_/  /_/_/[/bold cyan][bold magenta] /_/\\__,_/[/bold magenta]",
        "          [bold cyan]/_/[/bold cyan]",
    ]
    for line in logo_lines:
        console.print(Align.center(Text.from_markup(line)))

    console.print(Align.center(Text(TAGLINE, style="tagline")))
    console.print()
    console.print(
        Align.center(
            Panel(
                _status_table(project_path, name, stats),
                title="[panel.title] workspace [/panel.title]",
                title_align="left",
                border_style="panel.border",
                padding=(0, 1),
                box=box.ROUNDED,
                width=content_width,
            )
        )
    )
    console.print()


def show_status_line(
    console: Console,
    project_name: str,
    indexed: bool,
    extra: str = "",
) -> None:
    """Show a compact status line after a command."""
    line = Text()
    line.append(project_name, style="workspace.name")
    line.append("  ")
    line.append(
        "* indexed" if indexed else "* index required",
        style="status.ready" if indexed else "status.pending",
    )
    if extra:
        line.append(f"  {extra}", style="muted")
    console.print(line)
