"""Integration tests for deterministic repository evidence operations."""

from __future__ import annotations

import pytest

from repomind.evidence.engine import EvidenceEngine
from repomind.services.index_service import IndexService


@pytest.fixture
def evidence_project(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "flow.py").write_text(
        """
def helper(value: int) -> int:
    return value + 1


def run(value: int) -> int:
    return helper(value)
""".strip()
        + "\n",
        encoding="utf-8",
    )

    index_dir = project / ".repomind"
    result = IndexService(index_dir=str(index_dir)).index_directory(str(project))
    assert result.success
    return project, index_dir


class TestEvidenceSearch:
    def test_search_returns_citable_source_evidence(self, evidence_project):
        _, index_dir = evidence_project
        bundle = EvidenceEngine(index_dir=str(index_dir)).search_symbols("helper")

        assert bundle.evidences
        evidence = bundle.evidences[0]
        assert evidence.evidence_id
        assert evidence.source == "search"
        assert evidence.file_path == "flow.py"
        assert "def helper" in (evidence.snippet or "")
        assert bundle.symbols[0].qualified_name == "flow.helper"

    def test_get_symbol_source_returns_full_symbol(self, evidence_project):
        _, index_dir = evidence_project
        evidence = EvidenceEngine(index_dir=str(index_dir)).get_symbol_source(
            "flow.run"
        )

        assert evidence is not None
        assert evidence.source == "source"
        assert evidence.start_line == 5
        assert "return helper(value)" in (evidence.snippet or "")


class TestEvidenceRelations:
    def test_expand_callees_preserves_direction(self, evidence_project):
        _, index_dir = evidence_project
        bundle = EvidenceEngine(index_dir=str(index_dir)).expand_relations(
            "flow.run", direction="callees"
        )

        assert len(bundle.relations) == 1
        relation = bundle.relations[0]
        assert relation.source == "flow.run"
        assert relation.target == "flow.helper"
        assert bundle.evidences[0].metadata["direction"] == "callees"
