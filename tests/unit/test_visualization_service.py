"""Tests for VisualizationService (Mermaid diagram generator) — covers T1."""
from __future__ import annotations

import pytest
from repomind.services.visualization_service import VisualizationService
from repomind.models.schemas import CallGraphResult, SymbolInfo, SymbolType, SymbolRelation, RelationType


class TestVisualizationService:
    def test_call_graph_to_mermaid(self):
        service = VisualizationService()
        
        # Create symbols with special characters to test regex sanitizer (M12)
        nodes = [
            SymbolInfo(
                name="foo", qualified_name="pkg-mod.foo:func()",
                type=SymbolType.FUNCTION, file_path="foo.py",
                start_line=1, end_line=5
            ),
            SymbolInfo(
                name="bar", qualified_name="pkg-mod.bar:func()",
                type=SymbolType.METHOD, file_path="bar.py",
                start_line=10, end_line=15
            ),
        ]
        edges = [
            SymbolRelation(
                source="pkg-mod.foo:func()",
                target="pkg-mod.bar:func()",
                relation_type=RelationType.CALLS
            )
        ]
        
        result = CallGraphResult(nodes=nodes, edges=edges)
        mermaid = service.call_graph_to_mermaid(result)
        
        # Check standard prefix
        assert "graph TD" in mermaid
        # Check node shapes are correctly applied
        assert "pkg_mod_foo_func__[Func]" in mermaid
        assert "pkg_mod_bar_func__(Method)" in mermaid
        # Check connection edges are generated with sanitized IDs
        assert "pkg_mod_foo_func__ -->|calls| pkg_mod_bar_func__" in mermaid

    def test_dependency_tree_to_mermaid(self):
        service = VisualizationService()
        symbols = [
            {"qualified_name": "pkg-mod.foo:func()", "name": "foo"},
            {"qualified_name": "pkg-mod.bar:func()", "name": "bar"},
        ]
        mermaid = service.dependency_tree_to_mermaid(symbols)
        
        assert "graph LR" in mermaid
        assert "pkg_mod_foo_func__[foo]" in mermaid
        assert "pkg_mod_bar_func__[bar]" in mermaid

    def test_node_shape_detection(self):
        service = VisualizationService()
        assert service._node_shape(SymbolType.CLASS) == "[Class]"
        assert service._node_shape(SymbolType.METHOD) == "(Method)"
        assert service._node_shape(SymbolType.FUNCTION) == "[Func]"
