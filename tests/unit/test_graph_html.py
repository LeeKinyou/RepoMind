from __future__ import annotations

import json
import re

from repomind.cli.components.graph_html import render_graph_html, write_graph_html
from repomind.models.schemas import (
    CallGraphResult,
    RelationType,
    SymbolInfo,
    SymbolRelation,
    SymbolType,
)


def _symbol(name: str) -> SymbolInfo:
    return SymbolInfo(
        name=name,
        qualified_name=f"pkg.{name}",
        type=SymbolType.FUNCTION,
        file_path=f"src/{name}.py",
        start_line=1,
        end_line=3,
    )


def _graph() -> CallGraphResult:
    return CallGraphResult(
        nodes=[_symbol("root"), _symbol("left"), _symbol("right"), _symbol("shared")],
        edges=[
            SymbolRelation(
                source="pkg.root",
                target="pkg.left",
                relation_type=RelationType.CALLS,
            ),
            SymbolRelation(
                source="pkg.root",
                target="pkg.right",
                relation_type=RelationType.CALLS,
            ),
            SymbolRelation(
                source="pkg.left",
                target="pkg.shared",
                relation_type=RelationType.CALLS,
            ),
            SymbolRelation(
                source="pkg.right",
                target="pkg.shared",
                relation_type=RelationType.CALLS,
            ),
            SymbolRelation(
                source="pkg.shared",
                target="pkg.root",
                relation_type=RelationType.CALLS,
            ),
        ],
    )


def _payload(html: str) -> dict:
    match = re.search(
        r'<script id="graph-data" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match is not None
    return json.loads(match.group(1))


def test_render_graph_html_preserves_shared_nodes_cycles_and_all_edges():
    html = render_graph_html(_graph(), "pkg.root", depth=3)
    payload = _payload(html)

    assert {node["id"] for node in payload["nodes"]} == {
        "pkg.root",
        "pkg.left",
        "pkg.right",
        "pkg.shared",
    }
    assert len(payload["edges"]) == 5
    assert {
        (edge["source"], edge["target"]) for edge in payload["edges"]
    } == {
        ("pkg.root", "pkg.left"),
        ("pkg.root", "pkg.right"),
        ("pkg.left", "pkg.shared"),
        ("pkg.right", "pkg.shared"),
        ("pkg.shared", "pkg.root"),
    }
    assert payload["root"] == "pkg.root"
    assert payload["depth"] == 3


def test_write_graph_html_creates_standalone_file(tmp_path):
    output = write_graph_html(_graph(), "pkg.root", 2, tmp_path)

    assert output.parent == tmp_path
    assert output.suffix == ".html"
    content = output.read_text(encoding="utf-8")
    assert "<svg" in content
    assert "https://" not in content
