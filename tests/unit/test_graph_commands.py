from __future__ import annotations

from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

from rich.console import Console

from repomind.cli.commands.graph import GraphCommand
from repomind.cli.commands.tree import TreeCommand
from repomind.models.schemas import CallGraphResult, SymbolInfo, SymbolType


def _symbol() -> SymbolInfo:
    return SymbolInfo(
        name="root",
        qualified_name="pkg.root",
        type=SymbolType.FUNCTION,
        file_path="src/root.py",
        start_line=1,
        end_line=2,
    )


def _command_dependencies(tmp_path: Path):
    symbol = _symbol()
    service = Mock()
    service.lookup_symbol.return_value = [symbol]
    service.get_call_graph.return_value = CallGraphResult(nodes=[symbol], edges=[])
    console = Console(file=StringIO(), force_terminal=False, color_system=None)
    return console, service


def test_graph_command_writes_and_opens_browser_graph(tmp_path):
    console, service = _command_dependencies(tmp_path)
    command = GraphCommand(
        console=console,
        project_path=tmp_path,
        query_service=service,
    )
    output = tmp_path / ".repomind" / "visualizations" / "pkg_root.html"

    with (
        patch(
            "repomind.cli.commands.graph.write_graph_html",
            return_value=output,
        ) as write_html,
        patch("repomind.cli.commands.graph.webbrowser.open") as open_browser,
    ):
        command.execute("root --depth 3")

    write_html.assert_called_once_with(
        service.get_call_graph.return_value,
        "pkg.root",
        3,
        tmp_path / ".repomind" / "visualizations",
    )
    open_browser.assert_called_once_with(output.resolve().as_uri())


def test_tree_command_uses_legacy_tree_renderer(tmp_path):
    console, service = _command_dependencies(tmp_path)
    command = TreeCommand(
        console=console,
        project_path=tmp_path,
        query_service=service,
    )

    with patch("repomind.cli.commands.tree.show_call_graph") as show_tree:
        command.execute("root -d 4")

    show_tree.assert_called_once_with(
        console,
        service.get_call_graph.return_value,
        "pkg.root",
        4,
    )
