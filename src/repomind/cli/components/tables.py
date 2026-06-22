"""Table components for RepoMind CLI.

Design: minimal borders, strong typography, no full-box layout.
Uses indentation and subtle separators instead of heavy panels.
"""

from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.syntax import Syntax
from rich.rule import Rule

from repomind.models.schemas import SymbolInfo, SymbolType


def _get_type_style(sym_type: SymbolType) -> str:
    """Get display style for a symbol type."""
    styles = {
        SymbolType.CLASS: "bold cyan",
        SymbolType.FUNCTION: "bold green",
        SymbolType.METHOD: "bold yellow",
        SymbolType.VARIABLE: "white",
        SymbolType.MODULE: "dim cyan",
        SymbolType.INTERFACE: "bold magenta",
        SymbolType.ENUM: "bold blue",
        SymbolType.PROPERTY: "dim yellow",
    }
    return styles.get(sym_type, "white")


def _get_type_icon(sym_type: SymbolType) -> str:
    """Get a short text icon for a symbol type."""
    icons = {
        SymbolType.CLASS: "C",
        SymbolType.FUNCTION: "F",
        SymbolType.METHOD: "M",
        SymbolType.VARIABLE: "V",
        SymbolType.MODULE: "D",
        SymbolType.INTERFACE: "I",
        SymbolType.ENUM: "E",
        SymbolType.PROPERTY: "P",
    }
    return icons.get(sym_type, "?")


def show_index_stats(console: Console, stats: dict) -> None:
    """Display index statistics as a clean key-value list (no panel).

    Args:
        console: Rich console instance
        stats: Statistics dict
    """
    items = [
        ("files", "Files"),
        ("symbols", "Symbols"),
        ("classes", "Classes"),
        ("functions", "Functions"),
        ("imports", "Imports"),
        ("calls", "Calls"),
    ]

    # Header
    console.print(Text("Index stats", style="bold cyan"))
    console.print(Rule(style="dim", characters="─"))

    # Two-column compact layout
    table = Table(
        box=None,
        show_header=False,
        padding=(0, 2),
        show_edge=False,
    )
    table.add_column(style="dim", min_width=12)
    table.add_column(style="bold white")

    for key, label in items:
        if key in stats:
            table.add_row(label, f"{stats[key]:,}")

    console.print(table)
    console.print()


def show_search_results(
    console: Console,
    query: str,
    results: list[SymbolInfo],
    elapsed: float,
    project_path: str = "",
) -> list[SymbolInfo]:
    """Display search results as a clean numbered list.

    Design: no enclosing panel. Header line + numbered items + footer hint.
    Each item is a single line with type icon, name, location, and docstring.

    Args:
        console: Rich console instance
        query: Query text
        results: Search result list
        elapsed: Elapsed seconds
        project_path: Project path (for relative path display)

    Returns:
        The results list (for interactive selection by the caller)
    """
    if not results:
        console.print()
        line = Text()
        line.append("  No results for ", style="dim")
        line.append(query, style="yellow")
        console.print(line)
        console.print()
        return results

    # Header — query and count on one line
    console.print()
    header = Text()
    header.append("  results for ", style="dim")
    header.append(query, style="bold white")
    header.append("  ", style="")
    header.append(f"{len(results)}", style="bold cyan")
    header.append(f" matches ({elapsed:.3f}s)", style="dim")
    console.print(header)
    console.print(Rule(style="dim", characters="─"))

    # Results — numbered, one per line, no inner table borders
    for i, sym in enumerate(results, 1):
        type_style = _get_type_style(sym.type)
        type_icon = _get_type_icon(sym.type)

        line = Text()
        line.append(f"  {i:>2}. ", style="dim")
        line.append(f"{type_icon} ", style=type_style)
        line.append(sym.name, style=type_style)
        line.append(f"  ({sym.type.value})", style="dim")

        # File location
        file_path = sym.file_path
        if project_path and file_path.startswith(project_path):
            file_path = file_path[len(project_path) :].lstrip("/\\")
        line.append(f"  {file_path}:{sym.start_line}", style="dim cyan")

        console.print(line)

        # Docstring on indented second line (if present)
        if sym.docstring:
            doc = sym.docstring.split("\n")[0][:80]
            doc_line = Text()
            doc_line.append(f"      {doc}", style="dim italic")
            console.print(doc_line)

    console.print()
    # Footer hint
    hint = Text()
    hint.append("  Tip: ", style="dim cyan")
    hint.append("/show <name>", style="cyan")
    hint.append(" for details, ", style="dim")
    hint.append("/graph <name>", style="cyan")
    hint.append(" for call graph", style="dim")
    console.print(hint)
    console.print()

    return results


def show_symbol_detail(
    console: Console,
    symbol: SymbolInfo,
    callers: list[dict] | None = None,
    callees: list[dict] | None = None,
    source_code: str | None = None,
) -> None:
    """Display symbol details with clean sectioned layout (no enclosing panel).

    Args:
        console: Rich console instance
        symbol: Symbol info
        callers: Caller list
        callees: Callee list
        source_code: Source code
    """
    type_style = _get_type_style(symbol.type)
    type_icon = _get_type_icon(symbol.type)

    # Header — symbol name and type
    console.print()
    header = Text()
    header.append(f"  {type_icon} ", style=type_style)
    header.append(symbol.name, style=type_style)
    header.append(f"  ({symbol.type.value})", style="dim")
    console.print(header)
    console.print(Rule(style="dim", characters="─"))

    # Metadata — key/value pairs, indented
    meta = Table(box=None, show_header=False, padding=(0, 2), show_edge=False)
    meta.add_column(style="dim", min_width=10)
    meta.add_column()

    if symbol.parent_class:
        meta.add_row("parent", Text(symbol.parent_class, style="cyan"))

    meta.add_row(
        "location",
        Text(
            f"{symbol.file_path}:{symbol.start_line}-{symbol.end_line}",
            style="dim cyan",
        ),
    )

    if symbol.signature:
        meta.add_row("signature", Text(symbol.signature, style="green"))

    console.print(meta)
    console.print()

    # Documentation section
    if symbol.docstring:
        console.print(Text("  Documentation", style="bold"))
        console.print(Rule(style="dim", characters="─"))
        for doc_line in symbol.docstring.split("\n"):
            console.print(Text(f"  {doc_line}", style="white"))
        console.print()

    # Source code section
    if source_code:
        console.print(Text("  Source", style="bold"))
        console.print(Rule(style="dim", characters="─"))
        syntax = Syntax(
            source_code,
            "python",
            theme="monokai",
            line_numbers=True,
            start_line=symbol.start_line,
            background_color="default",
        )
        console.print(syntax)
        console.print()

    # Call relations section
    if callers or callees:
        console.print(Text("  Call relations", style="bold"))
        console.print(Rule(style="dim", characters="─"))

        if callers:
            console.print(Text(f"  Called by ({len(callers)}):", style="dim"))
            for c in callers[:10]:
                line = Text()
                line.append("    ← ", style="dim")
                line.append(c.get("name", "?"), style="white")
                if c.get("type"):
                    line.append(f"  ({c['type']})", style="dim")
                console.print(line)

        if callees:
            if callers:
                console.print()
            console.print(Text(f"  Calls ({len(callees)}):", style="dim"))
            for c in callees[:10]:
                line = Text()
                line.append("    → ", style="dim")
                line.append(c.get("name", "?"), style="white")
                if c.get("type"):
                    line.append(f"  ({c['type']})", style="dim")
                console.print(line)
        console.print()


def show_paged_source(
    console: Console,
    source_code: str,
    start_line: int,
    page_size: int = 40,
) -> None:
    """Display source code with pagination for long snippets.

    Args:
        console: Rich console instance
        source_code: Source code text
        start_line: Starting line number
        page_size: Lines per page (default 40)
    """
    lines = source_code.split("\n")
    total = len(lines)

    if total <= page_size:
        syntax = Syntax(
            source_code,
            "python",
            theme="monokai",
            line_numbers=True,
            start_line=start_line,
            background_color="default",
        )
        console.print(syntax)
        return

    page_start = 0
    page_num = 1
    while page_start < total:
        page_end = min(page_start + page_size, total)
        page_lines = lines[page_start:page_end]
        page_text = "\n".join(page_lines)

        console.print()
        syntax = Syntax(
            page_text,
            "python",
            theme="monokai",
            line_numbers=True,
            start_line=start_line + page_start,
            background_color="default",
        )
        console.print(syntax)

        info = Text()
        info.append(
            f"  [lines {start_line + page_start}-{start_line + page_end - 1} of {start_line + total - 1}] ",
            style="dim",
        )
        if page_end < total:
            info.append("Press Enter to continue, q to quit", style="dim cyan")
        console.print(info)

        if page_end >= total:
            break

        try:
            choice = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if choice in ("q", "quit", "exit"):
            break

        page_start = page_end
        page_num += 1
