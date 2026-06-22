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
                SymbolInfo(
                    name="Foo",
                    qualified_name="test.Foo",
                    type=SymbolType.CLASS,
                    file_path="test.py",
                    start_line=1,
                    end_line=3,
                ),
                SymbolInfo(
                    name="bar",
                    qualified_name="test.Foo.bar",
                    type=SymbolType.METHOD,
                    file_path="test.py",
                    start_line=2,
                    end_line=3,
                    parent_class="test.Foo",
                ),
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
                SymbolInfo(
                    name="caller",
                    qualified_name="test.caller",
                    type=SymbolType.FUNCTION,
                    file_path="test.py",
                    start_line=1,
                    end_line=2,
                ),
                SymbolInfo(
                    name="callee",
                    qualified_name="test.callee",
                    type=SymbolType.FUNCTION,
                    file_path="test.py",
                    start_line=3,
                    end_line=4,
                ),
            ],
            imports=[],
            calls=[
                {
                    "caller_class": None,
                    "target": "callee",
                    "call_type": "direct",
                    "line_number": 2,
                }
            ],
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
                SymbolInfo(
                    name="foo",
                    qualified_name="pkg.mod.foo",
                    type=SymbolType.FUNCTION,
                    file_path="test.py",
                    start_line=1,
                    end_line=2,
                ),
            ],
            imports=[],
            calls=[],
            classes=[],
        )
        builder.build([pf])
        assert "foo" in builder._symbol_index
        assert "pkg.mod.foo" in builder._symbol_index["foo"]

    def test_build_import_and_inheritance_edges(self, builder):
        pf1 = ParsedFile(
            path="other.py",
            source=b"class Parent:\n    pass\ndef helper():\n    pass\n",
            symbols=[
                SymbolInfo(
                    name="Parent",
                    qualified_name="other.Parent",
                    type=SymbolType.CLASS,
                    file_path="other.py",
                    start_line=1,
                    end_line=2,
                ),
                SymbolInfo(
                    name="helper",
                    qualified_name="other.helper",
                    type=SymbolType.FUNCTION,
                    file_path="other.py",
                    start_line=3,
                    end_line=4,
                ),
            ],
            imports=[],
            calls=[],
            classes=[],
        )
        pf2 = ParsedFile(
            path="mod.py",
            source=b"from other import helper\nclass Child(Parent):\n    pass\n",
            symbols=[
                SymbolInfo(
                    name="Child",
                    qualified_name="mod.Child",
                    type=SymbolType.CLASS,
                    file_path="mod.py",
                    start_line=2,
                    end_line=3,
                ),
            ],
            imports=[
                {
                    "module_path": "other",
                    "imported_name": "helper",
                    "alias": None,
                    "is_relative": False,
                    "relative_level": 0,
                    "line_number": 1,
                }
            ],
            calls=[],
            classes=[
                {
                    "name": "Child",
                    "qualified_name": "mod.Child",
                    "parents": ["Parent"],
                    "line_number": 2,
                }
            ],
        )
        graph = builder.build([pf1, pf2])
        # check imports edge and inherits edge
        assert graph.edge_count >= 2

    def test_build_with_fine_grained_calls(self, builder):
        pf = ParsedFile(
            path="test.py",
            source=b"class Foo:\n    def method(self):\n        callee()\n",
            symbols=[
                SymbolInfo(
                    name="Foo",
                    qualified_name="test.Foo",
                    type=SymbolType.CLASS,
                    file_path="test.py",
                    start_line=1,
                    end_line=3,
                ),
                SymbolInfo(
                    name="method",
                    qualified_name="test.Foo.method",
                    type=SymbolType.METHOD,
                    file_path="test.py",
                    start_line=2,
                    end_line=3,
                    parent_class="test.Foo",
                ),
                SymbolInfo(
                    name="callee",
                    qualified_name="test.callee",
                    type=SymbolType.FUNCTION,
                    file_path="test.py",
                    start_line=5,
                    end_line=6,
                ),
            ],
            imports=[],
            calls=[
                {
                    "caller_class": "test.Foo",
                    "caller_qname": "test.Foo.method",
                    "target": "callee",
                    "call_type": "direct",
                    "line_number": 3,
                }
            ],
            classes=[{"name": "Foo", "qualified_name": "test.Foo", "parents": []}],
        )
        graph = builder.build([pf])
        edges = list(graph.graph.edges)
        assert ("test.Foo.method", "test.callee") in edges
