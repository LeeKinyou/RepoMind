"""Tests for SymbolResolver — M2 (shared resolution logic)."""

from __future__ import annotations

from repomind.core.call_graph.resolver import SymbolResolver


class TestResolveCaller:
    def test_with_caller_class(self):
        call = {"caller_class": "pkg.MyClass", "target": "foo"}
        assert SymbolResolver.resolve_caller(call, "test.py") == "pkg.MyClass"

    def test_without_caller_class(self):
        call = {"target": "foo", "call_type": "direct"}
        result = SymbolResolver.resolve_caller(call, "auth/login.py")
        assert "auth.login" in result

    def test_init_file(self):
        call = {"target": "foo"}
        result = SymbolResolver.resolve_caller(call, "pkg/__init__.py")
        assert "pkg" in result


class TestResolveCallee:
    def test_self_call(self):
        call = {"target": "bar", "call_type": "self"}
        result = SymbolResolver.resolve_callee(call, "pkg.MyClass", {})
        assert result == "pkg.MyClass.bar"

    def test_direct_call_in_index(self):
        call = {"target": "foo", "call_type": "direct"}
        index = {"foo": ["pkg.module.foo"]}
        result = SymbolResolver.resolve_callee(call, None, index)
        assert result == "pkg.module.foo"

    def test_partial_match_in_index(self):
        call = {"target": "foo", "call_type": "direct"}
        index = {"bar": ["pkg.module.foo"]}
        result = SymbolResolver.resolve_callee(call, None, index)
        assert result == "pkg.module.foo"

    def test_not_in_index_returns_target(self):
        call = {"target": "external_func", "call_type": "direct"}
        result = SymbolResolver.resolve_callee(call, None, {})
        assert result == "external_func"

    def test_empty_target_returns_none(self):
        call = {"target": "", "call_type": "direct"}
        assert SymbolResolver.resolve_callee(call, None, {}) is None
