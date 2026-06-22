"""RCA (Root Cause Analysis) component for RepoMind CLI.

Design: clean sectioned layout, no enclosing panel. Uses indentation
and subtle separators instead of heavy box borders.
"""

from rich.console import Console
from rich.text import Text
from rich.rule import Rule

from repomind.models.schemas import RCAResult


def show_rca_result(console: Console, result: RCAResult) -> None:
    """Display root cause analysis result with clean sectioned layout.

    Args:
        console: Rich console instance
        result: RCA result
    """
    # Header
    console.print()
    header = Text()
    header.append("  Root cause analysis", style="bold red")
    console.print(header)
    console.print(Rule(style="dim", characters="─"))

    # Error line
    err_line = Text()
    err_line.append("  error  ", style="dim")
    err_line.append(result.root_cause, style="bold red")
    console.print(err_line)

    # Confidence
    conf_style = (
        "bold green"
        if result.confidence >= 0.7
        else "bold yellow"
        if result.confidence >= 0.4
        else "bold red"
    )
    conf_line = Text()
    conf_line.append("  confidence  ", style="dim")
    conf_line.append(f"{result.confidence:.0%}", style=conf_style)
    console.print(conf_line)

    # Location
    if result.evidence:
        loc_line = Text()
        loc_line.append("  location  ", style="dim")
        loc_line.append(result.evidence[0], style="cyan")
        console.print(loc_line)

    console.print()

    # Call chain section
    if result.call_chain:
        console.print(Text("  Call chain", style="bold"))
        console.print(Rule(style="dim", characters="─"))
        for i, frame in enumerate(result.call_chain):
            is_last = i == len(result.call_chain) - 1
            if is_last:
                line = Text()
                line.append("    ✗ ", style="bold red")
                line.append(frame, style="bold red")
            else:
                line = Text()
                line.append("    → ", style="dim")
                line.append(frame, style="dim")
            console.print(line)
        console.print()

    # Analysis section
    if result.explanation:
        console.print(Text("  Analysis", style="bold"))
        console.print(Rule(style="dim", characters="─"))
        for line_text in result.explanation.split("\n"):
            console.print(Text(f"  {line_text}", style="white"))
        console.print()

    # Affected symbols section
    if result.affected_symbols:
        console.print(Text("  Affected symbols", style="bold"))
        console.print(Rule(style="dim", characters="─"))
        for sym in result.affected_symbols[:10]:
            line = Text()
            line.append("    • ", style="dim")
            line.append(sym.name, style="cyan")
            line.append(f"  ({sym.type.value})", style="dim")
            line.append(f"  {sym.file_path}:{sym.start_line}", style="dim cyan")
            console.print(line)
        console.print()

    # Suggested fix section
    if result.suggested_fix:
        console.print(Text("  Suggested fix", style="bold"))
        console.print(Rule(style="dim", characters="─"))
        for line_text in result.suggested_fix.split("\n"):
            console.print(Text(f"  {line_text}", style="green"))
        console.print()


def show_rca_trace_input(console: Console) -> None:
    """Display RCA trace input prompt (clean, no panel).

    Args:
        console: Rich console instance
    """
    console.print()
    header = Text()
    header.append("  Root cause analysis", style="bold yellow")
    console.print(header)
    console.print(Rule(style="dim", characters="─"))

    inst = Text()
    inst.append("  Paste stack trace below.", style="white")
    console.print(inst)

    inst2 = Text()
    inst2.append("  Press ", style="dim")
    inst2.append("Enter twice", style="cyan")
    inst2.append(" to submit, or ", style="dim")
    inst2.append("Ctrl+C", style="cyan")
    inst2.append(" to cancel.", style="dim")
    console.print(inst2)
    console.print()
