"""Unit tests for CodeSkeletonizer."""

from __future__ import annotations

import pytest
from repomind.context.skeletonizer import CodeSkeletonizer


def test_skeletonize_no_active_lines():
    source = """def foo(x):
    print("foo")
    return x

def bar(y):
    print("bar")
    return y
"""
    skeletonizer = CodeSkeletonizer()
    result = skeletonizer.skeletonize(source, active_lines=set())

    expected = """def foo(x):
    # ... [2 lines collapsed]

def bar(y):
    # ... [2 lines collapsed]
"""
    assert result.strip() == expected.strip()


def test_skeletonize_some_active_lines():
    source = """def foo(x):
    print("foo")
    return x

def bar(y):
    print("bar")
    return y
"""
    skeletonizer = CodeSkeletonizer()
    # Line 6 is inside bar()
    result = skeletonizer.skeletonize(source, active_lines={6})

    # foo() should be collapsed, bar() should be intact and marked
    expected = """def foo(x):
    # ... [2 lines collapsed]

def bar(y):
=>     print("bar")
    return y
"""
    assert result.strip() == expected.strip()


def test_skeletonize_class_methods():
    source = """class Calculator:
    def __init__(self):
        self.val = 0

    def add(self, x):
        self.val += x
        return self.val

    def sub(self, x):
        self.val -= x
        return self.val
"""
    skeletonizer = CodeSkeletonizer()
    # Line 6 is inside add()
    result = skeletonizer.skeletonize(source, active_lines={6})

    # __init__ and sub should be collapsed, add should be intact and marked
    assert "def __init__(self):" in result
    assert "self.val = 0" not in result
    assert "def add(self, x):" in result
    assert "=>         self.val += x" in result
    assert "def sub(self, x):" in result
    assert "self.val -= x" not in result
    assert "# ... [1 lines collapsed]" in result or "# ... [2 lines collapsed]" in result
