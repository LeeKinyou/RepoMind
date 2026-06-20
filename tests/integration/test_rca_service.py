"""Integration tests for RCAService."""
from __future__ import annotations

import pytest
from repomind.services.rca_service import RCAService


@pytest.fixture
def rca_service(tmp_dir):
    return RCAService(index_dir=str(tmp_dir / ".repomind"))


class TestAnalyzeTrace:
    def test_parse_trace(self, rca_service):
        trace = '''Traceback (most recent call last):
  File "/app/auth.py", line 42, in login
    user = db.query(User, username)
  File "/app/db.py", line 15, in query
    result = self.execute(sql)
sqlite3.OperationalError: no such table: users'''
        result = rca_service.analyze_trace(trace)
        assert result.root_cause is not None
        assert result.confidence >= 0.0

    def test_parse_trace_frames(self, rca_service):
        trace = '''Traceback (most recent call last):
  File "/app/main.py", line 1, in <module>
    main()
  File "/app/app.py", line 10, in main
    run()
RuntimeError: something failed'''
        result = rca_service.analyze_trace(trace)
        assert len(result.call_chain) >= 1

    def test_empty_trace(self, rca_service):
        result = rca_service.analyze_trace("")
        assert result.confidence == 0.0

    def test_extract_error_info(self, rca_service):
        error_type, msg = rca_service._extract_error_info(
            "ValueError: invalid literal"
        )
        assert error_type == "ValueError"
        assert "invalid literal" in msg
