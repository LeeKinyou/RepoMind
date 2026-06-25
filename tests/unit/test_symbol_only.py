"""Unit tests for the symbol_only mode components."""

import pytest
from pathlib import Path
from repomind.indexer.ast_symbol_indexer import ASTSymbolIndexer
from repomind.retriever.hybrid_retriever import (
    RetrievalResult,
    aggregate_symbol_results_to_files,
)
from repomind.eval.evaluator import is_function_hit
from repomind.models.schemas import SymbolType, SymbolInfo


def test_ast_symbol_extractor():
    """Verify that ASTSymbolIndexer extracts classes, methods, functions, and async functions."""
    code = """
class RepoIndexer:
    def build_index(self):
        pass

async def async_load():
    pass

def parse_file(path):
    pass
"""
    indexer = ASTSymbolIndexer()
    symbols = indexer.extract_symbols(code, "test_file.py")
    
    # Assert extracted names
    names = [s.name for s in symbols]
    assert "RepoIndexer" in names
    assert "build_index" in names
    assert "async_load" in names
    assert "parse_file" in names
    
    # Assert qualified names
    qnames = [s.qualified_name for s in symbols]
    assert "test_file.RepoIndexer" in qnames
    assert "test_file.RepoIndexer.build_index" in qnames
    assert "test_file.async_load" in qnames
    assert "test_file.parse_file" in qnames

    # Assert types
    types = {s.name: s.type for s in symbols}
    assert types["RepoIndexer"] == SymbolType.CLASS
    assert types["build_index"] == SymbolType.METHOD
    assert types["async_load"] == SymbolType.FUNCTION or types["async_load"] == SymbolType.METHOD
    assert types["parse_file"] == SymbolType.FUNCTION


def test_retrieval_result_properties():
    """Verify that RetrievalResult schema works correctly."""
    doc = {
        "name": "build_index",
        "qualified_name": "RepoIndexer.build_index",
        "file_path": "src/retrieval/indexer.py",
        "start_line": 20,
        "end_line": 80,
    }
    result = RetrievalResult(symbol=doc, score=0.9, source="symbol_only")
    
    assert result.file_path == "src/retrieval/indexer.py"
    assert result.symbol_name == "build_index"
    assert result.qualified_name == "RepoIndexer.build_index"
    assert result.start_line == 20
    assert result.end_line == 80
    assert result.source == "symbol_only"


def test_aggregate_symbol_results_to_files():
    """Verify aggregation of symbol results to file level."""
    res1 = RetrievalResult(
        symbol={"file_path": "src/indexer.py", "name": "build_index"},
        score=0.9,
        source="symbol_only",
    )
    res2 = RetrievalResult(
        symbol={"file_path": "src/indexer.py", "name": "parse_file"},
        score=0.7,
        source="symbol_only",
    )
    res3 = RetrievalResult(
        symbol={"file_path": "src/parser.py", "name": "parse_stack_trace"},
        score=0.8,
        source="symbol_only",
    )

    results = [res1, res2, res3]
    aggregated = aggregate_symbol_results_to_files(results, top_k=5)

    # We should have exactly 2 aggregated results (one for indexer.py, one for parser.py)
    assert len(aggregated) == 2
    
    # Check ranking: indexer.py should be first since max score is 0.9 + 0.1 * 0.7 = 0.97
    assert aggregated[0].file_path == "src/indexer.py"
    assert aggregated[0].score == 0.97
    assert len(aggregated[0].matched_symbols) == 2

    assert aggregated[1].file_path == "src/parser.py"
    assert aggregated[1].score == 0.8
    assert len(aggregated[1].matched_symbols) == 1


def test_is_function_hit_cross_file():
    """Verify that same function names in different files are not incorrectly matched."""
    # Expected function is in a.py
    expected_func = "parse"
    expected_files = ["src/a.py"]
    
    # Actual result is in b.py
    actual_b = {
        "file_path": "src/b.py",
        "name": "parse",
        "line_number": 10,
    }
    
    db_symbols = [
        {"name": "parse", "qualified_name": "src.a.parse", "start_line": 5, "end_line": 20}
    ]

    # This should be False because the file path does not match
    assert not is_function_hit(expected_func, expected_files, actual_b, db_symbols)

    # Actual result is in a.py but name is parse_all and line is outside range
    actual_a_wrong_name = {
        "file_path": "src/a.py",
        "name": "parse_all",
        "line_number": 25,
    }
    assert not is_function_hit(expected_func, expected_files, actual_a_wrong_name, db_symbols)

    # Correct file and name
    actual_a_correct = {
        "file_path": "src/a.py",
        "name": "parse",
        "line_number": 10,
    }
    assert is_function_hit(expected_func, expected_files, actual_a_correct, db_symbols)
