"""Tests for data models."""
from __future__ import annotations

import pytest
from repomind.models.schemas import (
    SymbolType, RelationType, SymbolInfo, IndexOptions, IndexResult, QueryResult,
    RCAResult, CallGraphResult, FileInfo,
)


class TestSymbolType:
    def test_enum_values(self):
        assert SymbolType.CLASS == "class"
        assert SymbolType.FUNCTION == "function"
        assert SymbolType.METHOD == "method"

    def test_from_string(self):
        assert SymbolType("class") == SymbolType.CLASS

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            SymbolType("variable")


class TestRelationType:
    def test_enum_values(self):
        assert RelationType.CALLS == "calls"
        assert RelationType.IMPORTS == "imports"
        assert RelationType.INHERITS == "inherits"


class TestSymbolInfo:
    def test_create_minimal(self):
        sym = SymbolInfo(
            name="foo", qualified_name="pkg.foo",
            type=SymbolType.FUNCTION, file_path="test.py",
            start_line=1, end_line=5,
        )
        assert sym.name == "foo"
        assert sym.docstring is None

    def test_create_full(self):
        sym = SymbolInfo(
            name="UserService", qualified_name="auth.UserService",
            type=SymbolType.CLASS, file_path="auth.py",
            start_line=10, end_line=50,
            docstring="User service class",
            signature="class UserService:",
        )
        assert sym.type == SymbolType.CLASS


class TestIndexOptions:
    def test_defaults(self):
        opts = IndexOptions()
        assert opts.language == "python"
        assert opts.max_file_size_mb == 5.0
        assert opts.incremental is False

    def test_custom(self):
        opts = IndexOptions(language="python", max_file_size_mb=10.0)
        assert opts.max_file_size_mb == 10.0


class TestIndexResult:
    def test_create(self):
        result = IndexResult(success=True, total_files=10, indexed_files=8)
        assert result.success is True
        assert result.errors == []


class TestQueryResult:
    def test_create(self):
        result = QueryResult(answer="test", confidence=0.9)
        assert result.symbols == []


class TestRCAResult:
    def test_create(self):
        result = RCAResult(root_cause="test", confidence=0.8)
        assert result.affected_symbols == []
        assert result.suggested_fix is None


class TestCallGraphResult:
    def test_create(self):
        result = CallGraphResult(root_symbol="test")
        assert result.nodes == []


class TestFileInfo:
    def test_create(self):
        info = FileInfo(path="test.py", language="python", hash="abc123")
        assert info.line_count == 0
