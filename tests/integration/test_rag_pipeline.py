"""Integration tests for the advanced RAG pipeline in QueryService and RCAService."""

from __future__ import annotations

import pytest
from pathlib import Path
from repomind.indexer.file_scanner import IndexService
from repomind.retriever.query_service import QueryService
from repomind.models.schemas import QueryOptions
from repomind.context.context_builder import RCAService


@pytest.fixture
def test_project(tmp_path):
    """Create a mock project structure for RAG testing."""
    project_dir = tmp_path / "rag_project"
    project_dir.mkdir()

    # Create app.py with helper methods
    app_code = """def parse_data(raw):
    # Some logic
    return int(raw)

def run():
    try:
        val = parse_data(None)
        return val
    except Exception as e:
        raise RuntimeError("run failed") from e
"""
    (project_dir / "app.py").write_text(app_code, encoding="utf-8")

    # Index project
    index_dir = project_dir / ".repomind"
    index_svc = IndexService(index_dir=str(index_dir))
    index_svc.index_directory(str(project_dir))

    return project_dir, index_dir


def test_query_service_traceback_rag_skeletonization(test_project):
    project_dir, index_dir = test_project
    
    query_svc = QueryService(index_dir=str(index_dir))
    
    # Traceback query targeting app.py, line 7 (inside run())
    traceback_query = f"""I got this traceback:
Traceback (most recent call last):
  File "{project_dir}/app.py", line 7, in run
    val = parse_data(None)
TypeError: int() argument must be a string, a bytes-like object or a real number, not 'NoneType'
"""
    
    # We query with traceback.
    # The QueryService should detect the traceback, parse the active line (line 7),
    # and when returning app.run symbol, skeletonize app.py so parse_data is collapsed but run is kept intact.
    opts = QueryOptions(include_code=True)
    res = query_svc.search(traceback_query, options=opts)
    
    # Assert query_svc found symbols
    assert len(res.symbols) >= 1
    
    # Check if code skeletonization was applied:
    app_symbols = [s for s in res.symbols if "app.py" in s.file_path or "app.py" in s.name]
    assert len(app_symbols) > 0
    assert "# ... [" in app_symbols[0].snippet
    assert "val = parse_data(None)" in app_symbols[0].snippet
    
def test_rca_service_traceback_skeletonization(test_project):
    project_dir, index_dir = test_project
    rca_svc = RCAService(index_dir=str(index_dir))
    
    # Mock traceback
    traceback = f"""Traceback (most recent call last):
  File "{project_dir}/app.py", line 7, in run
    val = parse_data(None)
TypeError: int() argument must be a string
"""
    # collect_trace_evidence should return evidence snippets that are skeletonized if active lines are parsed.
    bundle = rca_svc.collect_trace_evidence(traceback)
    assert len(bundle.evidences) >= 1
    
    # Let's verify the first evidence's snippet contains skeletonized annotations like "# ... [X lines collapsed]"
    # and keeps line 7 intact.
    evidence = bundle.evidences[0]
    assert "# ... [" in evidence.snippet
    assert "val = parse_data(None)" in evidence.snippet
