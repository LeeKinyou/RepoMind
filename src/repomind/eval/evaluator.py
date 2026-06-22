"""Evaluator module for running RepoMind benchmark tests and printing metrics."""

from __future__ import annotations

import os
import json
import time
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from repomind.services.query_service import QueryService
from repomind.models.schemas import QueryOptions

console = Console()


class RepoMindEvaluator:
    """Evaluation framework for codebase search, symbol mapping, and context hit rates."""

    def __init__(self, index_dir: str = ".repomind"):
        self.index_dir = index_dir

    def evaluate(
        self, benchmark_json_path: str, project_path: str | None = None
    ) -> dict:
        """Run evaluation suite against the benchmark cases JSON."""
        project_path = project_path or os.getcwd()
        db_path = os.path.join(self.index_dir, "index.db")

        if not os.path.exists(db_path):
            console.print(
                f"[bold red]Error:[/bold red] Database not found at {db_path}. Please run index command first."
            )
            return {"success": False}

        with open(benchmark_json_path, encoding="utf-8") as f:
            cases = json.load(f)

        query_service = QueryService(index_dir=self.index_dir)

        results = []
        total_top1_hits = 0
        total_top3_hits = 0
        total_function_hits = 0
        total_cases = len(cases)

        console.print(
            Panel.fit(
                f"Starting RepoMind Evaluation on {total_cases} cases...",
                border_style="bold blue",
            )
        )

        for case in cases:
            case_id = case["case_id"]
            query = case["query"]
            expected_files = case["expected_files"]
            expected_funcs = case["expected_functions"]

            start_time = time.time()
            # Execute search
            opts = QueryOptions(max_results=5)
            query_res = query_service.search(query, options=opts)
            elapsed = time.time() - start_time

            # Calculate Top-1 File Hit
            top1_hit = False
            top3_hit = False
            func_hits = 0

            # Normalise project paths for comparison
            # expected_files are e.g. "src/repomind/core/parser/tree_sitter_parser.py"
            # symbols' file_path are e.g. "src/repomind/core/parser/tree_sitter_parser.py" (or absolute, but we normalized it to relative relative to project_path!)
            norm_expected_files = {Path(f).as_posix().lower() for f in expected_files}

            returned_files = []
            returned_funcs = []
            for r in query_res.symbols:
                # Convert symbol file_path to posix relative path for comparison
                # Note: symbols file_path might be absolute or relative depending on index_directory
                try:
                    rel_p = (
                        Path(r.file_path).relative_to(project_path).as_posix().lower()
                    )
                except ValueError:
                    rel_p = Path(r.file_path).as_posix().lower()
                returned_files.append(rel_p)
                returned_funcs.append(r.name)

            if returned_files:
                if returned_files[0] in norm_expected_files:
                    top1_hit = True

                # Check top-3 hits
                for rf in returned_files[:3]:
                    if rf in norm_expected_files:
                        top3_hit = True
                        break

            # Calculate Function Hit
            for ef in expected_funcs:
                if ef in returned_funcs:
                    func_hits += 1

            func_hit_rate = func_hits / len(expected_funcs) if expected_funcs else 1.0

            if top1_hit:
                total_top1_hits += 1
            if top3_hit:
                total_top3_hits += 1
            if expected_funcs:
                total_function_hits += func_hit_rate
            else:
                total_function_hits += 1.0  # Default to 100% if no functions expected

            results.append(
                {
                    "case_id": case_id,
                    "type": case.get("type", "Query"),
                    "top1_hit": top1_hit,
                    "top3_hit": top3_hit,
                    "func_hit_rate": func_hit_rate,
                    "elapsed": elapsed,
                }
            )

        # Calculate final metrics
        top1_rate = total_top1_hits / total_cases
        top3_rate = total_top3_hits / total_cases
        func_rate = total_function_hits / total_cases

        # Print table
        table = Table(
            title="RepoMind Benchmark Case Details",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Case ID", style="dim", width=12)
        table.add_column("Type")
        table.add_column("Top-1 File Hit", justify="center")
        table.add_column("Top-3 File Hit", justify="center")
        table.add_column("Function Hit Rate", justify="right")
        table.add_column("Latency (s)", justify="right")

        for r in results:
            table.add_row(
                r["case_id"],
                r["type"],
                "[green]PASSED[/green]" if r["top1_hit"] else "[red]FAILED[/red]",
                "[green]PASSED[/green]" if r["top3_hit"] else "[red]FAILED[/red]",
                f"{r['func_hit_rate'] * 100:.1f}%",
                f"{r['elapsed']:.3f}s",
            )

        console.print(table)
        console.print("\n")

        # Summary Panel
        summary_text = (
            f"[bold cyan]Top-1 File Hit Rate[/bold cyan] : {top1_rate * 100:.1f}%\n"
            f"[bold cyan]Top-3 File Hit Rate[/bold cyan] : {top3_rate * 100:.1f}%\n"
            f"[bold cyan]Function Hit Rate[/bold cyan]   : {func_rate * 100:.1f}%\n"
        )
        console.print(
            Panel(
                summary_text,
                title="RepoMind Evaluation Metrics Summary",
                border_style="bold green",
            )
        )

        return {
            "success": True,
            "top1_rate": top1_rate,
            "top3_rate": top3_rate,
            "func_rate": func_rate,
            "cases_evaluated": total_cases,
        }
