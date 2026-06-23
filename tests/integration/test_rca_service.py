"""Integration tests for RCAService."""

from __future__ import annotations

import pytest
from repomind.services.index_service import IndexService
from repomind.services.rca_service import RCAService


@pytest.fixture
def rca_service(tmp_dir):
    return RCAService(index_dir=str(tmp_dir / ".repomind"))


class TestAnalyzeTrace:
    def test_parse_trace(self, rca_service):
        trace = """Traceback (most recent call last):
  File "/app/auth.py", line 42, in login
    user = db.query(User, username)
  File "/app/db.py", line 15, in query
    result = self.execute(sql)
sqlite3.OperationalError: no such table: users"""
        result = rca_service.analyze_trace(trace)
        assert result.root_cause is not None
        assert result.confidence >= 0.0

    def test_parse_trace_frames(self, rca_service):
        trace = """Traceback (most recent call last):
  File "/app/main.py", line 1, in <module>
    main()
  File "/app/app.py", line 10, in main
    run()
RuntimeError: something failed"""
        result = rca_service.analyze_trace(trace)
        assert len(result.call_chain) >= 1

    def test_empty_trace(self, rca_service):
        result = rca_service.analyze_trace("")
        assert result.confidence == 0.0


class TestTraceEvidenceMode:
    def test_collect_trace_evidence_is_deterministic_and_citable(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        source = project / "app.py"
        source.write_text(
            "def run():\n    raise RuntimeError('boom')\n",
            encoding="utf-8",
        )
        index_dir = project / ".repomind"
        IndexService(index_dir=str(index_dir)).index_directory(str(project))
        service = RCAService(index_dir=str(index_dir))

        trace = f"""Traceback (most recent call last):
  File "{source}", line 2, in run
    raise RuntimeError("boom")
RuntimeError: boom"""

        bundle = service.collect_trace_evidence(trace)

        assert bundle.evidences
        assert bundle.evidences[0].source == "trace"
        assert bundle.evidences[0].symbol == "app.run"
        assert "raise RuntimeError" in (bundle.evidences[0].snippet or "")
        assert bundle.metadata["error_type"] == "RuntimeError"
        assert bundle.metadata["proximate_cause"]["file_path"] == "app.py"
