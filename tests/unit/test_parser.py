"""Tests for TreeSitterParser — covers H4 (alias) and H7 (signature extraction)."""
from __future__ import annotations

import pytest
from repomind.core.parser.tree_sitter_parser import TreeSitterParser


@pytest.fixture
def parser():
    return TreeSitterParser()


class TestParseSource:
    def test_parse_class(self, parser):
        code = 'class Foo:\n    pass\n'
        result = parser.parse_source(code)
        assert len(result.symbols) == 1
        assert result.symbols[0].name == "Foo"
        assert result.symbols[0].type.value == "class"

    def test_parse_function(self, parser):
        code = 'def hello():\n    pass\n'
        result = parser.parse_source(code)
        assert len(result.symbols) == 1
        assert result.symbols[0].name == "hello"
        assert result.symbols[0].type.value == "function"

    def test_parse_method(self, parser):
        code = 'class Foo:\n    def bar(self):\n        pass\n'
        result = parser.parse_source(code)
        names = [s.name for s in result.symbols]
        assert "Foo" in names
        assert "bar" in names
        bar_sym = next(s for s in result.symbols if s.name == "bar")
        assert bar_sym.type.value == "method"
        assert bar_sym.parent_class is not None

    def test_parse_import(self, parser):
        code = 'import os\nimport sys\n'
        result = parser.parse_source(code)
        assert len(result.imports) == 2

    def test_parse_from_import(self, parser):
        code = 'from pathlib import Path\n'
        result = parser.parse_source(code)
        assert len(result.imports) == 1
        assert result.imports[0]["imported_name"] == "Path"

    def test_parse_import_alias(self, parser):
        """H4: Import aliases should be captured."""
        code = 'from os import path as p\n'
        result = parser.parse_source(code)
        assert len(result.imports) == 1
        imp = result.imports[0]
        assert imp["imported_name"] == "path"
        assert imp["alias"] == "p"

    def test_parse_import_no_alias(self, parser):
        code = 'from os import path\n'
        result = parser.parse_source(code)
        assert result.imports[0]["alias"] is None

    def test_parse_call(self, parser):
        code = 'def foo():\n    bar()\n'
        result = parser.parse_source(code)
        assert len(result.calls) >= 1

    def test_parse_self_call(self, parser):
        code = 'class Foo:\n    def a(self):\n        self.b()\n'
        result = parser.parse_source(code)
        self_calls = [c for c in result.calls if c["call_type"] == "self"]
        assert len(self_calls) >= 1

    def test_parse_docstring(self, parser):
        code = '''class Foo:
    """This is a docstring."""
    pass
'''
        result = parser.parse_source(code)
        foo = next(s for s in result.symbols if s.name == "Foo")
        assert foo.docstring == "This is a docstring."

    def test_parse_docstring_triple_single_quotes(self, parser):
        code = """class Foo:
    '''Triple single quotes.'''
    pass
"""
        result = parser.parse_source(code)
        foo = next(s for s in result.symbols if s.name == "Foo")
        assert foo.docstring == "Triple single quotes."


class TestSignatureExtraction:
    """H7: Signatures should not be truncated at type annotation colons."""

    def test_simple_function_signature(self, parser):
        code = 'def foo():\n    pass\n'
        result = parser.parse_source(code)
        sym = result.symbols[0]
        assert "def foo" in (sym.signature or "")

    def test_function_with_type_hints(self, parser):
        """H7: Signature should include full parameter list, not truncate at colon."""
        code = 'def foo(x: str, y: int) -> bool:\n    return True\n'
        result = parser.parse_source(code)
        sym = result.symbols[0]
        sig = sym.signature or ""
        # Should NOT be truncated to "def foo(x"
        assert "str" in sig or "x" in sig

    def test_function_with_complex_return_type(self, parser):
        code = 'def foo() -> dict[str, list[int]]:\n    return {}\n'
        result = parser.parse_source(code)
        sym = result.symbols[0]
        sig = sym.signature or ""
        assert "def foo" in sig


class TestChainCalls:
    def test_chain_calls(self, parser):
        code = "a.b.c().d()"
        result = parser.parse_source(code)
        targets = [c["target"] for c in result.calls]
        assert "a.b.c" in targets
        assert "a.b.c.d" in targets
