"""Tests for structured diagnostic evidence and agent state models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from repomind.models.diagnostic import (
    DiagnosticHypothesis,
    DiagnosticState,
    ToolInvocation,
)
from repomind.models.evidence import Evidence, EvidenceBundle


def make_evidence(evidence_id: str = "ev-1") -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source="trace",
        file_path="src/app.py",
        symbol="app.run",
        start_line=10,
        end_line=12,
        snippet="raise RuntimeError('boom')",
        relevance_score=0.9,
        reason="Matched the innermost traceback frame.",
    )


class TestEvidence:
    def test_relevance_score_is_bounded(self):
        with pytest.raises(ValidationError):
            make_evidence().model_copy(update={"relevance_score": 1.5}).model_validate(
                {
                    **make_evidence().model_dump(),
                    "relevance_score": 1.5,
                }
            )

    def test_bundle_reports_degraded_features(self):
        bundle = EvidenceBundle(
            summary="Local retrieval completed.",
            evidences=[make_evidence()],
            degraded_features=["vector_search"],
        )

        assert bundle.degraded_features == ["vector_search"]


class TestDiagnosticState:
    def test_rejects_hypothesis_with_unknown_evidence_reference(self):
        state = DiagnosticState(
            issue="RuntimeError: boom",
            evidences=[make_evidence()],
            hypotheses=[
                DiagnosticHypothesis(
                    hypothesis_id="hyp-1",
                    description="The run function raises directly.",
                    confidence=0.8,
                    supporting_evidence_ids=["missing"],
                )
            ],
        )

        with pytest.raises(ValueError, match="unknown evidence IDs"):
            state.validate_evidence_references()

    def test_accepts_hypothesis_with_known_evidence_reference(self):
        state = DiagnosticState(
            issue="RuntimeError: boom",
            evidences=[make_evidence()],
            hypotheses=[
                DiagnosticHypothesis(
                    hypothesis_id="hyp-1",
                    description="The run function raises directly.",
                    confidence=0.8,
                    supporting_evidence_ids=["ev-1"],
                )
            ],
            tool_history=[
                ToolInvocation(
                    tool_name="map_traceback",
                    arguments={"trace": "RuntimeError: boom"},
                    iteration=0,
                    success=True,
                    new_evidence_ids=["ev-1"],
                )
            ],
        )

        state.validate_evidence_references()
