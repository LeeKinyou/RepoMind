"""Typer app definition for RepoMind CLI."""
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

# Create Typer app
app = typer.Typer(
    name="repomind",
    help="Repository Intelligence Platform",
    no_args_is_help=False,
)

# Create console
console = Console()


def _find_project_root() -> Path:
    """Find project root directory."""
    markers = {".git", "pyproject.toml", "setup.py", "setup.cfg", "Cargo.toml", "package.json"}
    p = Path.cwd()
    for _ in range(10):
        if any((p / m).exists() for m in markers):
            return p
        if p.parent == p:
            break
        p = p.parent
    return Path.cwd()


@app.command()
def index(
    path: str = typer.Argument(".", help="Project directory path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Index code repository."""
    from repomind.cli.repl import RepoMindREPL
    from repomind.models.schemas import IndexOptions
    from repomind.cli.components.tables import show_index_stats

    project = Path(path).resolve()
    if not project.exists():
        console.print(f"[red]Path not found: {path}[/]")
        raise typer.Exit(1)

    repl = RepoMindREPL(project)
    with console.status("[bold green]Indexing..."):
        result = repl.index_service.index_directory(str(project), IndexOptions(verbose=verbose))

    if result.success:
        console.print()
        show_index_stats(console, {
            "files": result.indexed_files,
            "symbols": result.total_symbols,
            "classes": result.total_classes,
            "functions": result.total_functions,
            "imports": result.total_imports,
            "calls": result.total_calls,
        })
        console.print()
        console.print(f"[green]Index complete in {result.elapsed_seconds:.2f}s[/]")
    else:
        console.print("[red]Index failed:[/]")
        for err in result.errors:
            console.print(f"  [red]![/] {err}")


@app.command()
def query(
    question: str = typer.Argument(..., help="Query question"),
    project: str = typer.Option(".", "--project", "-p", help="Project directory"),
    top_k: int = typer.Option(10, "--top", "-n", help="Number of results"),
):
    """Query code repository."""
    from repomind.cli.repl import RepoMindREPL
    from repomind.models.schemas import QueryOptions
    from repomind.cli.components.tables import show_search_results
    from repomind.cli.components.progress import show_spinner

    proj = Path(project).resolve()
    repl = RepoMindREPL(proj)

    with show_spinner(console, "Searching..."):
        result = repl.query_service.search(question, QueryOptions(max_results=top_k))

    console.print()
    show_search_results(console, question, result.symbols, result.elapsed_seconds, str(proj))


@app.command()
def show(
    name: str = typer.Argument(..., help="Symbol name"),
    project: str = typer.Option(".", "--project", "-p", help="Project directory"),
):
    """Show symbol details."""
    from repomind.cli.repl import RepoMindREPL
    from repomind.cli.commands.show import ShowCommand

    proj = Path(project).resolve()
    repl = RepoMindREPL(proj)

    cmd = ShowCommand(console=console, project_path=proj, query_service=repl.query_service)
    cmd.execute(name)


@app.command()
def graph(
    name: str = typer.Argument(..., help="Symbol name"),
    project: str = typer.Option(".", "--project", "-p", help="Project directory"),
    depth: int = typer.Option(2, "--depth", "-d", help="Expansion depth"),
):
    """View call graph."""
    from repomind.cli.repl import RepoMindREPL
    from repomind.cli.commands.graph import GraphCommand

    proj = Path(project).resolve()
    repl = RepoMindREPL(proj)

    cmd = GraphCommand(console=console, project_path=proj, query_service=repl.query_service)
    cmd.execute(f"{name} --depth {depth}")


@app.command()
def rca(
    trace_file: str = typer.Option(None, "--trace", "-t", help="Stack trace file path"),
    project: str = typer.Option(".", "--project", "-p", help="Project directory"),
):
    """Root cause analysis."""
    from repomind.cli.repl import RepoMindREPL
    from repomind.cli.commands.rca import RCACommand

    proj = Path(project).resolve()
    repl = RepoMindREPL(proj)

    cmd = RCACommand(console=console, project_path=proj, rca_service=repl.rca_service)
    cmd.execute(trace_file or "")


@app.command()
def stats(
    project: str = typer.Option(".", "--project", "-p", help="Project directory"),
):
    """Show index statistics."""
    from repomind.cli.repl import RepoMindREPL
    from repomind.cli.commands.stats import StatsCommand

    proj = Path(project).resolve()
    repl = RepoMindREPL(proj)

    cmd = StatsCommand(console=console, project_path=proj, index_service=repl.index_service)
    cmd.execute("")


@app.command()
def clear(
    project: str = typer.Option(".", "--project", "-p", help="Project directory"),
):
    """Clear index data."""
    from repomind.cli.repl import RepoMindREPL

    proj = Path(project).resolve()
    repl = RepoMindREPL(proj)

    repl.index_service.clear()
    console.print("[green]Index cleared[/]")


@app.command()
def repl(
    project: str = typer.Option(".", "--project", "-p", help="Project directory"),
):
    """Enter interactive mode."""
    from repomind.cli.repl import run_repl

    proj = Path(project).resolve()
    run_repl(proj)


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context):
    """Repository Intelligence Platform."""
    if ctx.invoked_subcommand is None:
        # Default to interactive mode
        from repomind.cli.repl import run_repl

        project = _find_project_root()
        run_repl(project)
