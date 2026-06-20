"""Interactive CLI for RepoMind — Repository Intelligence Platform."""
from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich import box

app = typer.Typer(name="repomind", help="Repository Intelligence Platform — 代码仓库智能分析")
console = Console()

# ── Helpers ──────────────────────────────────────────────────────────────


def _find_project_root() -> Path:
    """Walk up from cwd to find a recognizable project root."""
    markers = {".git", "pyproject.toml", "setup.py", "setup.cfg", "Cargo.toml", "package.json"}
    p = Path.cwd()
    for _ in range(10):
        if any((p / m).exists() for m in markers):
            return p
        if p.parent == p:
            break
        p = p.parent
    return Path.cwd()


def _index_dir(project: Path) -> Path:
    return project / ".repomind"


def _ensure_index(project: Path) -> Path:
    """Return index dir; auto-index if it doesn't exist."""
    idx = _index_dir(project)
    if not (idx / "index.db").exists():
        console.print(f"[dim]No index found at {idx}. Indexing first...[/]")
        _do_index(project, verbose=False)
    return idx


def _do_index(project: Path, verbose: bool = False) -> bool:
    """Run indexing and print results."""
    from repomind.services.index_service import IndexService
    from repomind.models.schemas import IndexOptions

    service = IndexService(index_dir=str(_index_dir(project)))
    with console.status("[bold green]Indexing..."):
        result = service.index_directory(str(project), IndexOptions(verbose=verbose))

    if not result.success:
        console.print("[bold red]Index failed:[/]")
        for err in result.errors:
            console.print(f"  [red]![/] {err}")
        return False

    table = Table(box=box.ROUNDED, show_header=False, padding=(0, 2))
    table.add_column(style="cyan", min_width=14)
    table.add_column(style="bold white")
    table.add_row("Files", str(result.indexed_files))
    table.add_row("Symbols", str(result.total_symbols))
    table.add_row("Classes", str(result.total_classes))
    table.add_row("Functions", str(result.total_functions))
    table.add_row("Imports", str(result.total_imports))
    table.add_row("Calls", str(result.total_calls))
    table.add_row("Time", f"{result.elapsed_seconds:.2f}s")
    console.print(Panel(table, title="[bold green]Index Complete[/]", border_style="green"))
    return True


def _strip_project_prefix(qualified_name: str, project: Path) -> str:
    """Strip absolute path prefix from qualified_name, showing relative module path."""
    # Try to strip the project root path
    project_posix = project.as_posix()
    q = qualified_name
    # Handle Windows paths in qualified_name
    for prefix in [project_posix, project.as_posix().replace("/", "."), str(project)]:
        if q.startswith(prefix):
            q = q[len(prefix):].lstrip(".")
            break
    # Also strip common absolute path patterns
    for sep in ["\\\\", "\\"]:
        if sep in q:
            parts = q.split(sep)
            # Find the part that looks like a Python module
            for i, part in enumerate(parts):
                if part in ("src", "repomind", "lib", "app"):
                    q = ".".join(parts[i:])
                    break
            break
    return q


def _display_symbol(sym, idx: int, project: Path) -> None:
    """Display a single symbol result."""
    type_colors = {"class": "bold cyan", "function": "bold green", "method": "bold yellow"}
    type_style = type_colors.get(sym.type.value, "white")

    # Format: [1] ClassName (class) — file.py:42
    name_part = f"[bold white]{sym.name}[/]"
    type_part = f"[{type_style}]({sym.type.value})[/]"
    file_part = f"[dim]{sym.file_path}:{sym.start_line}[/]"

    console.print(f"  [dim]{idx:>2}.[/] {name_part} {type_part}  {file_part}")
    if sym.docstring:
        doc = sym.docstring.split("\n")[0][:80]
        console.print(f"      [dim italic]{doc}[/]")


def _display_code_snippet(file_path: str, line: int, context: int = 3) -> None:
    """Show syntax-highlighted code around a line."""
    p = Path(file_path)
    if not p.exists():
        return
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(0, line - 1 - context)
        end = min(len(lines), line + context)
        snippet = "\n".join(lines[start:end])
        syntax = Syntax(snippet, "python", line_numbers=True, start_line=start + 1,
                        highlight_lines={line}, theme="monokai")
        console.print(syntax)
    except Exception:
        pass


# ── Commands ─────────────────────────────────────────────────────────────


@app.command()
def index(
    path: str = typer.Argument(".", help="项目目录路径（默认当前目录）"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细输出"),
):
    """索引代码仓库"""
    project = Path(path).resolve()
    if not project.exists():
        console.print(f"[red]Path not found:[/] {path}")
        raise typer.Exit(1)
    _do_index(project, verbose)


@app.command()
def query(
    question: str = typer.Argument(..., help="查询问题（自然语言或关键词）"),
    project: str = typer.Option(".", "--project", "-p", help="项目目录"),
    top_k: int = typer.Option(10, "--top", "-n", help="返回结果数量"),
    code: bool = typer.Option(False, "--code", "-c", help="显示代码片段"),
):
    """查询代码仓库"""
    proj = Path(project).resolve()
    idx = _ensure_index(proj)

    from repomind.services.query_service import QueryService
    from repomind.models.schemas import QueryOptions

    service = QueryService(index_dir=str(idx))
    with console.status(f"[bold blue]Searching:[/] {question}"):
        result = service.search(question, QueryOptions(max_results=top_k))

    if not result.symbols:
        console.print(f"[yellow]No results for:[/] {question}")
        return

    console.print(f"\n[bold]{result.answer}[/]\n")
    for i, sym in enumerate(result.symbols, 1):
        _display_symbol(sym, i, proj)
        if code and Path(sym.file_path).exists():
            _display_code_snippet(sym.file_path, sym.start_line)
            console.print()


@app.command()
def show(
    name: str = typer.Argument(..., help="符号名称（类名、函数名）"),
    project: str = typer.Option(".", "--project", "-p", help="项目目录"),
):
    """查看符号详情"""
    proj = Path(project).resolve()
    idx = _ensure_index(proj)

    from repomind.services.query_service import QueryService

    service = QueryService(index_dir=str(idx))
    result = service.search(name, __import__("repomind.models.schemas", fromlist=["QueryOptions"]).QueryOptions(max_results=1))

    if not result.symbols:
        console.print(f"[yellow]Symbol not found:[/] {name}")
        return

    sym = result.symbols[0]
    qname = _strip_project_prefix(sym.qualified_name, proj)

    # Info panel
    info = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    info.add_column(style="cyan", min_width=12)
    info.add_column()
    info.add_row("Name", sym.name)
    info.add_row("Type", sym.type.value)
    info.add_row("Qualified", qname)
    info.add_row("File", f"{sym.file_path}:{sym.start_line}-{sym.end_line}")
    if sym.signature:
        info.add_row("Signature", sym.signature)
    if sym.docstring:
        info.add_row("Docstring", sym.docstring.split("\n")[0])

    console.print(Panel(info, title=f"[bold]{sym.name}[/]", border_style="cyan"))

    # Code
    if Path(sym.file_path).exists():
        console.print("\n[bold]Source:[/]")
        _display_code_snippet(sym.file_path, sym.start_line, context=10)

    # Callers
    callers = service.get_callers(sym.qualified_name)
    if callers:
        console.print(f"\n[bold]Called by ({len(callers)}):[/]")
        for c in callers[:10]:
            console.print(f"  [dim]<-[/] {c.get('name', '?')} [dim]({c.get('type', '?')})[/]")

    # Callees
    callees = service.get_callees(sym.qualified_name)
    if callees:
        console.print(f"\n[bold]Calls ({len(callees)}):[/]")
        for c in callees[:10]:
            console.print(f"  [dim]->[/] {c.get('name', '?')} [dim]({c.get('type', '?')})[/]")


@app.command()
def rca(
    trace_file: str = typer.Option(None, "--trace", "-t", help="Stack trace 文件路径"),
    project: str = typer.Option(".", "--project", "-p", help="项目目录"),
):
    """根因分析 — 分析 stack trace"""
    from repomind.services.rca_service import RCAService

    proj = Path(project).resolve()
    idx = _ensure_index(proj)

    if trace_file:
        p = Path(trace_file)
        if not p.exists():
            console.print(f"[bold red]File not found:[/] {trace_file}")
            raise typer.Exit(code=1)
        trace = p.read_text(encoding="utf-8")
    else:
        console.print("[yellow]Paste stack trace below (press Enter twice to finish):[/]")
        lines = []
        empty_count = 0
        while True:
            try:
                line = input()
                if line.strip() == "":
                    empty_count += 1
                    if empty_count >= 2:
                        break
                else:
                    empty_count = 0
                lines.append(line)
            except EOFError:
                break
        trace = "\n".join(lines)

    if not trace.strip():
        console.print("[red]No trace provided.[/]")
        return

    service = RCAService(index_dir=str(idx))
    with console.status("[bold red]Analyzing..."):
        result = service.analyze_trace(trace)

    # Root cause
    console.print(Panel(
        f"[bold]{result.root_cause}[/]",
        title="[bold red]Root Cause[/]",
        border_style="red",
    ))

    console.print(f"[bold]Confidence:[/] {result.confidence:.0%}")
    console.print(f"\n{result.explanation}")

    if result.call_chain:
        console.print("\n[bold]Call Chain:[/]")
        for i, frame in enumerate(result.call_chain):
            prefix = "[red]![/]" if i == len(result.call_chain) - 1 else "[dim]->[/]"
            console.print(f"  {prefix} {frame}")


@app.command()
def stats(
    project: str = typer.Option(".", "--project", "-p", help="项目目录"),
):
    """显示索引统计"""
    from repomind.services.index_service import IndexService

    proj = Path(project).resolve()
    idx = _index_dir(proj)
    if not (idx / "index.db").exists():
        console.print("[yellow]No index found. Run [bold]repomind index[/] first.[/]")
        return

    service = IndexService(index_dir=str(idx))
    data = service.get_stats()

    table = Table(box=box.ROUNDED, title="Index Stats", show_header=False, padding=(0, 2))
    table.add_column(style="cyan", min_width=12)
    table.add_column(style="bold white")
    for key, val in data.items():
        table.add_row(key, str(val))
    console.print(table)


@app.command()
def clear(
    project: str = typer.Option(".", "--project", "-p", help="项目目录"),
):
    """清除索引数据"""
    from repomind.services.index_service import IndexService

    proj = Path(project).resolve()
    service = IndexService(index_dir=str(_index_dir(proj)))
    service.clear()
    console.print("[bold green]Index cleared.[/]")


@app.command()
def graph(
    name: str = typer.Argument(..., help="符号名称"),
    project: str = typer.Option(".", "--project", "-p", help="项目目录"),
    depth: int = typer.Option(2, "--depth", "-d", help="展开深度"),
):
    """查看符号调用图"""
    proj = Path(project).resolve()
    idx = _ensure_index(proj)

    from repomind.services.query_service import QueryService

    service = QueryService(index_dir=str(idx))
    # Find the symbol first
    result = service.search(name, __import__("repomind.models.schemas", fromlist=["QueryOptions"]).QueryOptions(max_results=1))
    if not result.symbols:
        console.print(f"[yellow]Symbol not found:[/] {name}")
        return

    sym = result.symbols[0]
    graph_result = service.get_call_graph(sym.qualified_name, depth=depth)

    if not graph_result.nodes:
        console.print(f"[yellow]No call graph for:[/] {sym.name}")
        return

    console.print(f"\n[bold]Call Graph for {sym.name}[/] [dim](depth={depth})[/]\n")

    for node in graph_result.nodes:
        qname = _strip_project_prefix(node.qualified_name, proj)
        type_colors = {"class": "cyan", "function": "green", "method": "yellow"}
        color = type_colors.get(node.type.value, "white")
        console.print(f"  [{color}]{node.name}[/] [dim]({node.type.value})[/] [dim]{qname}[/]")

    if graph_result.edges:
        console.print(f"\n[dim]{len(graph_result.edges)} edges:[/]")
        for edge in graph_result.edges[:20]:
            src = _strip_project_prefix(edge.source, proj).split(".")[-1]
            tgt = _strip_project_prefix(edge.target, proj).split(".")[-1]
            console.print(f"  [dim]{src} -> {tgt} ({edge.relation_type.value})[/]")


@app.command()
def repl(
    project: str = typer.Option(".", "--project", "-p", help="项目目录"),
):
    """进入交互模式"""
    _interactive_mode(Path(project).resolve())


# ── Interactive Mode ─────────────────────────────────────────────────────


def _interactive_mode(project: Path):
    """Interactive REPL for RepoMind."""
    console.print(Panel(
        "[bold]RepoMind[/] — Repository Intelligence Platform\n\n"
        "Commands:\n"
        "  [cyan]index[/]              索引当前项目\n"
        "  [cyan]<keyword>[/]          搜索符号（自然语言）\n"
        "  [cyan]show <name>[/]        查看符号详情\n"
        "  [cyan]callers <name>[/]     谁调用了这个符号\n"
        "  [cyan]callees <name>[/]     这个符号调用了谁\n"
        "  [cyan]graph <name>[/]       调用图可视化\n"
        "  [cyan]rca[/]                根因分析（粘贴 stack trace）\n"
        "  [cyan]stats[/]              索引统计\n"
        "  [cyan]clear[/]              清除索引\n"
        "  [cyan]help[/]               显示帮助\n"
        "  [cyan]exit[/]               退出\n",
        title="[bold green]Repomind REPL[/]",
        border_style="green",
        padding=(1, 2),
    ))

    # Auto-index check
    idx = _index_dir(project)
    if not (idx / "index.db").exists():
        console.print("[dim]No index found. Running index...[/]")
        _do_index(project)
    else:
        from repomind.services.index_service import IndexService
        stats_data = IndexService(index_dir=str(idx)).get_stats()
        console.print(f"[dim]Index loaded: {stats_data['files']} files, {stats_data['symbols']} symbols[/]")

    console.print()

    while True:
        try:
            user_input = console.input("[bold green]>[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Bye![/]")
            break

        if not user_input:
            continue

        parts = user_input.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in ("exit", "quit", "q"):
            console.print("[dim]Bye![/]")
            break

        elif cmd == "help":
            _interactive_mode.__doc__  # trigger re-display
            console.print(
                "[cyan]index[/] | [cyan]<keyword>[/] | [cyan]show <name>[/] | "
                "[cyan]callers <name>[/] | [cyan]callees <name>[/] | "
                "[cyan]graph <name>[/] | [cyan]rca[/] | [cyan]stats[/] | [cyan]clear[/] | [cyan]exit[/]"
            )

        elif cmd == "index":
            _do_index(project)

        elif cmd == "stats":
            _do_stats(project)

        elif cmd == "clear":
            from repomind.services.index_service import IndexService
            IndexService(index_dir=str(idx)).clear()
            console.print("[green]Cleared.[/]")

        elif cmd == "show" and arg:
            _do_show(arg, project)

        elif cmd in ("callers", "who-calls", "wc") and arg:
            _do_callers(arg, project)

        elif cmd in ("callees", "calls", "cc") and arg:
            _do_callees(arg, project)

        elif cmd == "graph" and arg:
            _do_graph(arg, project)

        elif cmd == "rca":
            _do_rca_interactive(project)

        else:
            # Default: treat as search query
            _do_query(user_input, project)


def _do_query(question: str, project: Path, top_k: int = 10, show_code: bool = False):
    """Execute a search query."""
    from repomind.services.query_service import QueryService
    from repomind.models.schemas import QueryOptions

    idx = _index_dir(project)
    service = QueryService(index_dir=str(idx))
    with console.status("[dim]Searching...[/]"):
        result = service.search(question, QueryOptions(max_results=top_k))

    if not result.symbols:
        console.print(f"[yellow]No results for:[/] {question}")
        return

    console.print(f"[dim]{len(result.symbols)} results ({result.elapsed_seconds:.3f}s)[/]\n")
    for i, sym in enumerate(result.symbols, 1):
        _display_symbol(sym, i, project)
    console.print()


def _do_show(name: str, project: Path):
    """Show symbol details."""
    from repomind.services.query_service import QueryService
    from repomind.models.schemas import QueryOptions

    idx = _index_dir(project)
    service = QueryService(index_dir=str(idx))
    result = service.search(name, QueryOptions(max_results=1))

    if not result.symbols:
        console.print(f"[yellow]Not found:[/] {name}")
        return

    sym = result.symbols[0]
    qname = _strip_project_prefix(sym.qualified_name, project)

    info = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    info.add_column(style="cyan", min_width=10)
    info.add_column()
    info.add_row("Name", f"[bold]{sym.name}[/]")
    info.add_row("Type", sym.type.value)
    info.add_row("Module", qname.rsplit(".", 1)[0] if "." in qname else "")
    info.add_row("File", f"{sym.file_path}:{sym.start_line}-{sym.end_line}")
    if sym.signature:
        info.add_row("Signature", f"[green]{sym.signature}[/]")
    if sym.docstring:
        info.add_row("Doc", sym.docstring.split("\n")[0])

    console.print(Panel(info, title=f"[bold]{sym.name}[/]", border_style="cyan"))

    # Source code
    if Path(sym.file_path).exists():
        console.print("\n[bold]Source:[/]")
        _display_code_snippet(sym.file_path, sym.start_line, context=8)

    # Relations
    callers = service.get_callers(sym.qualified_name)
    callees = service.get_callees(sym.qualified_name)
    if callers:
        console.print(f"\n[bold]Called by ({len(callers)}):[/]")
        for c in callers[:8]:
            console.print(f"  [dim]<-[/] {c.get('name', '?')}")
    if callees:
        console.print(f"\n[bold]Calls ({len(callees)}):[/]")
        for c in callees[:8]:
            console.print(f"  [dim]->[/] {c.get('name', '?')}")


def _do_callers(name: str, project: Path):
    """Show who calls a symbol."""
    from repomind.services.query_service import QueryService
    from repomind.models.schemas import QueryOptions

    idx = _index_dir(project)
    service = QueryService(index_dir=str(idx))
    result = service.search(name, QueryOptions(max_results=1))
    if not result.symbols:
        console.print(f"[yellow]Not found:[/] {name}")
        return

    sym = result.symbols[0]
    callers = service.get_callers(sym.qualified_name)
    if not callers:
        console.print(f"[dim]No callers for {sym.name}[/]")
        return

    console.print(f"[bold]Who calls {sym.name}[/] [dim]({len(callers)})[/]\n")
    for c in callers:
        console.print(f"  [dim]<-[/] {c.get('name', '?')} [dim]({c.get('type', '?')})[/]")


def _do_callees(name: str, project: Path):
    """Show what a symbol calls."""
    from repomind.services.query_service import QueryService
    from repomind.models.schemas import QueryOptions

    idx = _index_dir(project)
    service = QueryService(index_dir=str(idx))
    result = service.search(name, QueryOptions(max_results=1))
    if not result.symbols:
        console.print(f"[yellow]Not found:[/] {name}")
        return

    sym = result.symbols[0]
    callees = service.get_callees(sym.qualified_name)
    if not callees:
        console.print(f"[dim]{sym.name} doesn't call anything[/]")
        return

    console.print(f"[bold]{sym.name} calls[/] [dim]({len(callees)})[/]\n")
    for c in callees:
        console.print(f"  [dim]->[/] {c.get('name', '?')} [dim]({c.get('type', '?')})[/]")


def _do_graph(name: str, project: Path, depth: int = 2):
    """Show call graph."""
    from repomind.services.query_service import QueryService
    from repomind.models.schemas import QueryOptions

    idx = _index_dir(project)
    service = QueryService(index_dir=str(idx))
    result = service.search(name, QueryOptions(max_results=1))
    if not result.symbols:
        console.print(f"[yellow]Not found:[/] {name}")
        return

    sym = result.symbols[0]
    graph_result = service.get_call_graph(sym.qualified_name, depth=depth)

    if not graph_result.nodes:
        console.print(f"[dim]No call graph for {sym.name}[/]")
        return

    console.print(f"[bold]{sym.name}[/] call graph [dim](depth={depth}, {len(graph_result.nodes)} nodes)[/]\n")

    type_colors = {"class": "cyan", "function": "green", "method": "yellow"}
    for node in graph_result.nodes[:30]:
        color = type_colors.get(node.type.value, "white")
        marker = "*" if node.qualified_name == sym.qualified_name else " "
        console.print(f"  {marker} [{color}]{node.name}[/] [dim]({node.type.value})[/]")

    if len(graph_result.nodes) > 30:
        console.print(f"  [dim]... and {len(graph_result.nodes) - 30} more[/]")

    if graph_result.edges:
        console.print(f"\n[dim]{len(graph_result.edges)} call edges[/]")


def _do_stats(project: Path):
    """Show index stats."""
    from repomind.services.index_service import IndexService

    idx = _index_dir(project)
    if not (idx / "index.db").exists():
        console.print("[yellow]No index. Run [bold]index[/] first.[/]")
        return

    service = IndexService(index_dir=str(idx))
    data = service.get_stats()

    table = Table(box=box.ROUNDED, show_header=False, padding=(0, 2))
    table.add_column(style="cyan", min_width=10)
    table.add_column(style="bold white")
    for key, val in data.items():
        table.add_row(key, str(val))
    console.print(Panel(table, title="[bold]Index Stats[/]", border_style="blue"))


def _do_rca_interactive(project: Path):
    """Interactive RCA — paste a stack trace."""
    console.print("[yellow]Paste stack trace (press Enter twice to finish):[/]\n")
    lines = []
    empty_count = 0
    while True:
        try:
            line = input()
            if line.strip() == "":
                empty_count += 1
                if empty_count >= 2:
                    break
            else:
                empty_count = 0
            lines.append(line)
        except (EOFError, KeyboardInterrupt):
            break

    trace = "\n".join(lines).strip()
    if not trace:
        console.print("[dim]Cancelled.[/]")
        return

    from repomind.services.rca_service import RCAService
    idx = _index_dir(project)
    service = RCAService(index_dir=str(idx))

    with console.status("[bold red]Analyzing..."):
        result = service.analyze_trace(trace)

    console.print(Panel(
        f"[bold]{result.root_cause}[/]",
        title="[bold red]Root Cause[/]",
        border_style="red",
    ))
    console.print(f"[bold]Confidence:[/] {result.confidence:.0%}\n")
    console.print(result.explanation)

    if result.call_chain:
        console.print("\n[bold]Call Chain:[/]")
        for i, frame in enumerate(result.call_chain):
            is_crash = i == len(result.call_chain) - 1
            prefix = "[red bold]![/]" if is_crash else "[dim]->[/]"
            style = "bold red" if is_crash else ""
            console.print(f"  {prefix} [{style}]{frame}[/]")


# ── Entry ────────────────────────────────────────────────────────────────


def main():
    """Entry point — if no args, enter interactive mode."""
    if len(sys.argv) == 1:
        project = _find_project_root()
        _interactive_mode(project)
    else:
        app()


if __name__ == "__main__":
    main()
