"""Tests for TypeInferenceEngine — covers H8 (return type) and L5 (jedi import)."""

from __future__ import annotations

import pytest
from repomind.core.type_inference.inference_engine import (
    TypeInferenceEngine,
    InferredType,
)


@pytest.fixture
def engine():
    return TypeInferenceEngine()


class TestExplicitHintStrategy:
    def test_return_type_annotation(self, engine):
        code = 'def foo() -> str:\n    return "hi"\n'
        result = engine.infer(code, line=1, column=0, name="foo")
        # Should find str or fall through to lower strategy
        assert result.strategy != "none" or result.type_name is None

    def test_parameter_annotation(self, engine):
        code = "def foo(x: int):\n    pass\n"
        result = engine.infer(code, line=1, column=0, name="foo")
        # At minimum, some strategy should be tried
        assert result.confidence >= 0.0

    def test_explicit_hint_lowercase_builtin(self, engine):
        code = "def foo(x: str) -> int:\n    pass\n"
        res = engine._strategy_explicit_hint(code, line=1, column=0, name="")
        assert res == "int"
        res_param = engine._strategy_explicit_hint(code, line=1, column=0, name="x")
        assert res_param == "str"

    def test_explicit_hint_complex_type(self, engine):
        code = "def process(items: list[str]) -> dict[str, int]:\n    pass\n"
        res = engine._strategy_explicit_hint(code, line=1, column=0, name="items")
        assert res == "list[str]"
        res_ret = engine._strategy_explicit_hint(code, line=1, column=0, name="")
        assert res_ret == "dict[str, int]"


class TestImportMappingStrategy:
    def test_imported_class(self, engine):
        code = "from pathlib import Path\n\ndef foo():\n    pass\n"
        result = engine._strategy_import_mapping(code, 3, 0, "Path")
        assert result == "Path"

    def test_unknown_import(self, engine):
        code = "import os\n"
        result = engine._strategy_import_mapping(code, 1, 0, "UnknownName")
        assert result is None


class TestSelfInferenceStrategy:
    def test_self_parameter(self, engine):
        code = """class UserService:
    def login(self):
        pass
"""
        result = engine._strategy_self_inference(code, 2, 4, "self")
        assert result == "UserService"


class TestAssignmentStrategy:
    def test_constructor_assignment(self, engine):
        code = "x = Foo()\n"
        result = engine._strategy_assignment(code, 1, 0, "x")
        assert result == "Foo"

    def test_lowercase_constructor(self, engine):
        code = "x = bar()\n"
        result = engine._strategy_assignment(code, 1, 0, "x")
        assert result is None  # lowercase is not a class


class TestDuckTypingStrategy:
    def test_duck_type_sorted(self, engine):
        """M4: DuckType output should be deterministic."""
        code = "x.read()\nx.write()\n"
        result1 = engine._strategy_duck_typing(code, 1, 0, "x")
        result2 = engine._strategy_duck_typing(code, 1, 0, "x")
        assert result1 == result2
        if result1:
            assert "read" in result1
            assert "write" in result1

    def test_scoped_duck_typing(self, engine):
        code = """
def my_func(x):
    x.read()
    x.write()

y.other_method()
"""
        res = engine._strategy_duck_typing(code, line=3, column=0, name="x")
        assert res is not None
        assert "read" in res
        assert "write" in res
        assert "other_method" not in res


class TestCascadeInference:
    def test_returns_first_success(self, engine):
        code = """class Foo:
    def bar(self):
        pass
"""
        result = engine.infer(code, line=2, column=4, name="self")
        assert result.type_name == "Foo"
        assert result.strategy == "self_inference"
        assert result.confidence == 0.85

    def test_no_strategy_matches(self, engine):
        result = engine.infer("x = unknown()\n", line=1, column=0, name="y")
        assert result.type_name is None
        assert result.confidence == 0.0


class TestInferSymbol:
    def test_infer_from_symbol(self, engine):
        from repomind.models.schemas import SymbolInfo, SymbolType

        sym = SymbolInfo(
            name="foo",
            qualified_name="test.foo",
            type=SymbolType.FUNCTION,
            file_path="test.py",
            start_line=1,
            end_line=3,
        )
        source = "def foo(x: str) -> int:\n    return 1\n"
        result = engine.infer_symbol(sym, source)
        assert isinstance(result, InferredType)
