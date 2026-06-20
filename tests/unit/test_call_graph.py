"""Tests for CallGraphBuilder — covers C5 (symbol_index)."""
from __future__ import annotations

import pytest
from repomind.core.call_graph.graph_builder import CallGraphBuilder
from repomind.core.parser.tree_sitter_parser import ParsedFile
from repomind.models.schemas import SymbolInfo, SymbolType


@pytest.fixture
def builder():
    return CallGraphBuilder()


class TestCallGraphBuilder:
    def test_build_from_parsed_files(self, builder):
        pf = ParsedFile(
            path="test.py",
            source=b"class Foo:\n    def bar(self):\n        pass\n",
            symbols=[
                SymbolInfo(name="Foo", qualified_name="test.Foo",
                           type=SymbolType.CLASS, file_path="test.py",
                           start_line=1, end_line=3),
                SymbolInfo(name="bar", qualified_name="test.Foo.bar",
                           type=SymbolType.METHOD, file_path="test.py",
                           start_line=2, end_line=3, parent_class="test.Foo"),
            ],
            imports=[],
            calls=[],
            classes=[{"name": "Foo", "qualified_name": "test.Foo", "parents": []}],
        )
        graph = builder.build([pf])
        assert graph.node_count >= 2

    def test_build_with_calls(self, builder):
        pf = ParsedFile(
            path="test.py",
            source=b"def caller():\n    callee()\n",
            symbols=[
                SymbolInfo(name="caller", qualified_name="test.caller",
                           type=SymbolType.FUNCTION, file_path="test.py",
                           start_line=1, end_line=2),
                SymbolInfo(name="callee", qualified_name="test.callee",
                           type=SymbolType.FUNCTION, file_path="test.py",
                           start_line=3, end_line=4),
            ],
            imports=[],
            calls=[{"caller_class": None, "target": "callee", "call_type": "direct", "line_number": 2}],
            classes=[],
        )
        graph = builder.build([pf])
        assert graph.edge_count >= 1

    def test_symbol_index_populated(self, builder):
        """C5: symbol_index should be populated for callee resolution."""
        pf = ParsedFile(
            path="test.py",
            source=b"",
            symbols=[
                SymbolInfo(name="foo", qualified_name="pkg.mod.foo",
                           type=SymbolType.FUNCTION, file_path="test.py",
                           start_line=1, end_line=2),
            ],
            imports=[], calls=[], classes=[],
        )
        builder.build([pf])
        assert "foo" in builder._symbol_index
        assert "pkg.mod.foo" in builder._symbol_index["foo"]
