"""Unit tests for TracebackQueryParser."""

from __future__ import annotations

import pytest
from repomind.context.traceback_parser import TracebackQueryParser


def test_parse_clean_traceback():
    trace = """Traceback (most recent call last):
  File "src/repomind/retriever/query_service.py", line 42, in search
    results = self.retriever.retrieve(query)
  File "src/repomind/retriever/hybrid_retriever.py", line 124, in retrieve
    bm25_hits = self.bm25.search(query)
AttributeError: 'NoneType' object has no attribute 'search'"""

    parser = TracebackQueryParser()
    result = parser.parse_query(trace)

    assert result["is_traceback"] is True
    assert len(result["frames"]) == 2
    assert result["frames"][0]["file_path"] == "src/repomind/retriever/query_service.py"
    assert result["frames"][0]["line_number"] == 42
    assert result["frames"][0]["function_name"] == "search"
    assert result["frames"][0]["code_line"] == "results = self.retriever.retrieve(query)"
    assert result["frames"][1]["function_name"] == "retrieve"
    assert result["frames"][1]["code_line"] == "bm25_hits = self.bm25.search(query)"
    assert result["exception_type"] == "AttributeError"
    assert result["exception_message"] == "'NoneType' object has no attribute 'search'"


def test_parse_noisy_traceback():
    query = """
I ran into an issue while starting the server:
```
Traceback (most recent call last):
  File "/app/auth.py", line 15, in login
    user = db.query(User, username)
sqlite3.OperationalError: no such table: users
```
Can you help me fix this?
"""
    parser = TracebackQueryParser()
    result = parser.parse_query(query)

    assert result["is_traceback"] is True
    assert len(result["frames"]) == 1
    assert result["frames"][0]["file_path"] == "/app/auth.py"
    assert result["frames"][0]["line_number"] == 15
    assert result["frames"][0]["function_name"] == "login"
    assert result["frames"][0]["code_line"] == "user = db.query(User, username)"
    assert result["exception_type"] == "sqlite3.OperationalError"
    assert result["exception_message"] == "no such table: users"


def test_parse_no_traceback():
    query = "How is Python source code parsed using Tree-sitter?"
    parser = TracebackQueryParser()
    result = parser.parse_query(query)

    assert result["is_traceback"] is False
    assert len(result["frames"]) == 0
    assert result["exception_type"] is None
    assert result["exception_message"] is None
