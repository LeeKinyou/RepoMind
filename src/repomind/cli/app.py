"""Typer app definition for RepoMind CLI."""

from __future__ import annotations

import os
os.environ["LITELLM_LOG"] = "ERROR"
os.environ["SUPPRESS_LITELLM_DEBUG"] = "True"

from pathlib import Path

import typer
from rich.console import Console
from rich.text import Text
from rich.rule import Rule

# Create Typer app
app = typer.Typer(
    name="repomind",
    help="Repository Intelligence Platform",
    no_args_is_help=False,
)

# Create console
console = Console()


def _find_project_root() -> Path:
    """Find project root directory by walking up looking for common markers."""
    markers = {
        ".git",
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "Cargo.toml",
        "package.json",
    }
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
        console.print(Text(f"  Path not found: {path}", style="red"))
        raise typer.Exit(1)

    repl = RepoMindREPL(project)

    # Header
    console.print()
    header = Text()
    header.append("  Indexing ", style="bold cyan")
    header.append(str(project), style="white")
    console.print(header)
    console.print(Rule(style="dim", characters="─"))

    with console.status("[bold blue]Scanning files..."):
        result = repl.index_service.index_directory(
            str(project), IndexOptions(verbose=verbose)
        )

    if result.success:
        console.print()
        show_index_stats(
            console,
            {
                "files": result.indexed_files,
                "symbols": result.total_symbols,
                "classes": result.total_classes,
                "functions": result.total_functions,
                "imports": result.total_imports,
                "calls": result.total_calls,
            },
        )
        done = Text()
        done.append("  Indexed in ", style="green")
        done.append(f"{result.elapsed_seconds:.2f}s", style="bold green")
        console.print(done)
    else:
        console.print(Text("  Index failed:", style="red"))
        for err in result.errors:
            console.print(Text(f"    ! {err}", style="red"))


@app.command()
def query(
    question: str = typer.Argument(..., help="Query question"),
    project: str = typer.Option(".", "--project", "-p", help="Project directory"),
    top_k: int = typer.Option(10, "--top", "-n", help="Number of results"),
    answer: bool = typer.Option(False, "--answer", help="Ask LLM for a summary answer"),
    show_code: bool = typer.Option(
        False, "--show-code", help="Display matching code snippets"
    ),
):
    """Query code repository."""
    from repomind.cli.repl import RepoMindREPL
    from repomind.models.schemas import QueryOptions
    from repomind.cli.components.tables import show_search_results
    from repomind.cli.components.progress import show_spinner

    proj = Path(project).resolve()
    repl = RepoMindREPL(proj)

    with show_spinner(console, "Searching..."):
        result = repl.query_service.search(
            question, QueryOptions(max_results=top_k, include_code=show_code)
        )

    show_search_results(
        console,
        question,
        result.symbols,
        result.elapsed_seconds,
        str(proj),
        show_code=show_code,
    )

    if answer:
        console.print()
        console.print("  [bold cyan]LLM Answer Summary:[/bold cyan]")
        with show_spinner(console, "Generating answer..."):
            llm_ans = repl.query_service.answer(question, result)
        console.print(f"  {llm_ans}")
        console.print()


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

    cmd = ShowCommand(
        console=console, project_path=proj, query_service=repl.query_service
    )
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

    cmd = GraphCommand(
        console=console, project_path=proj, query_service=repl.query_service
    )
    cmd.execute(f"{name} --depth {depth}")


@app.command()
def tree(
    name: str = typer.Argument(..., help="Symbol name"),
    project: str = typer.Option(".", "--project", "-p", help="Project directory"),
    depth: int = typer.Option(2, "--depth", "-d", help="Expansion depth"),
):
    """View call relationships using the legacy terminal tree."""
    from repomind.cli.repl import RepoMindREPL
    from repomind.cli.commands.tree import TreeCommand

    proj = Path(project).resolve()
    repl = RepoMindREPL(proj)

    cmd = TreeCommand(
        console=console,
        project_path=proj,
        query_service=repl.query_service,
    )
    cmd.execute(f"{name} --depth {depth}")


@app.command("visualize")
def visualize(
    name: str = typer.Argument(..., help="Symbol name"),
    project: str = typer.Option(".", "--project", "-p", help="Project directory"),
    depth: int = typer.Option(2, "--depth", "-d", help="Expansion depth"),
):
    """View call graph (alias for graph command)."""
    graph(name=name, project=project, depth=depth)


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

    cmd = StatsCommand(
        console=console, project_path=proj, index_service=repl.index_service
    )
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
    console.print(Text("  Index cleared.", style="green"))


@app.command()
def repl(
    project: str = typer.Option(".", "--project", "-p", help="Project directory"),
):
    """Enter interactive mode."""
    from repomind.cli.repl import run_repl

    proj = Path(project).resolve()
    run_repl(proj)


@app.command()
def mcp():
    """Start the Model Context Protocol (MCP) stdio server."""
    from repomind.mcp.server import MCPServer

    server = MCPServer()
    server.start()


@app.command()
def eval(
    project: str = typer.Option(".", "--project", "-p", help="Project directory"),
    benchmark: str = typer.Option(
        None, "--benchmark", "-b", help="Path to benchmark JSON file"
    ),
):
    """Run the evaluation suite on the benchmark cases."""
    from repomind.eval.evaluator import RepoMindEvaluator

    proj = Path(project).resolve()

    if benchmark is None:
        import repomind.eval

        eval_dir = Path(repomind.eval.__file__).parent
        benchmark_path = eval_dir / "benchmark_cases.json"
    else:
        benchmark_path = Path(benchmark).resolve()

    if not benchmark_path.exists():
        console.print(
            Text(f"  Benchmark file not found: {benchmark_path}", style="red")
        )
        raise typer.Exit(1)

    evaluator = RepoMindEvaluator(index_dir=str(proj / ".repomind"))
    res = evaluator.evaluate(str(benchmark_path), project_path=str(proj))
    if not res.get("success", False):
        raise typer.Exit(1)


@app.command()
def diagnose(
    trace_file: str = typer.Argument(..., help="Path to stack trace / error log file"),
    project: str = typer.Option(".", "--project", "-p", help="Project directory"),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path for the Markdown report (defaults to diagnose_report.md)",
    ),
    json_format: bool = typer.Option(
        False, "--json", help="Export in JSON format instead of Markdown"
    ),
    mode: str = typer.Option(
        "evidence", "--mode", "-m", help="Diagnostic mode: 'evidence' or 'agent'"
    ),
):
    """Run root cause analysis on a trace and save structured Markdown/JSON evidence report."""
    from repomind.cli.repl import RepoMindREPL
    from repomind.reporter.evidence_report import EvidenceReporter

    proj = Path(project).resolve()
    repl = RepoMindREPL(proj)

    trace_path = Path(trace_file).resolve()
    if not trace_path.exists():
        console.print(Text(f"  Trace file not found: {trace_file}", style="red"))
        raise typer.Exit(1)

    trace = trace_path.read_text(encoding="utf-8", errors="replace")
    query = trace.strip().split("\n")[-1] if trace.strip() else ""

    if mode == "agent":
        from repomind.agent.diagnostic_agent import DiagnosticAgent
        with console.status("[bold blue]Running Diagnostic Agent loop..."):
            agent = DiagnosticAgent(index_dir=str(proj / ".repomind"))
            state = agent.run(trace)
        
        if json_format:
            report_content = state.model_dump_json(indent=2)
            default_filename = "diagnose_report.json"
        else:
            report_content = EvidenceReporter.generate_agent_report(state)
            default_filename = "diagnose_report.md"
    else:
        with console.status("[bold blue]Analyzing trace and generating report..."):
            result = repl.rca_service.analyze_trace(trace)

        if json_format:
            report_content = EvidenceReporter.generate_json_report(result, query=query)
            default_filename = "diagnose_report.json"
        else:
            report_content = EvidenceReporter.generate_markdown_report(result, query=query)
            default_filename = "diagnose_report.md"

    out_path = Path(output or default_filename).resolve()
    EvidenceReporter.save_report(report_content, str(out_path))

    console.print(
        Text(
            f"  Diagnosis report successfully generated and saved to: {out_path}",
            style="green",
        )
    )


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context):
    """Repository Intelligence Platform."""
    if ctx.invoked_subcommand is None:
        # Default to interactive mode
        from repomind.cli.repl import run_repl

        project = _find_project_root()
        run_repl(project)
