"""Models for controlled diagnostic-agent state and tool traces."""

from __future__ import annotations

from pydantic import BaseModel, Field

from repomind.models.evidence import Evidence


class DiagnosticHypothesis(BaseModel):
    """A root-cause candidate linked to explicit evidence IDs."""

    hypothesis_id: str
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    conflicting_evidence_ids: list[str] = Field(default_factory=list)


class ToolInvocation(BaseModel):
    """One read-only evidence tool invocation in an agent run."""

    tool_name: str
    arguments: dict[str, object]
    iteration: int = Field(ge=0)
    success: bool
    new_evidence_ids: list[str] = Field(default_factory=list)
    error: str | None = None


class DiagnosticState(BaseModel):
    """Durable state for a bounded diagnostic-agent execution."""

    issue: str
    iteration: int = Field(default=0, ge=0)
    hypotheses: list[DiagnosticHypothesis] = Field(default_factory=list)
    evidences: list[Evidence] = Field(default_factory=list)
    tool_history: list[ToolInvocation] = Field(default_factory=list)
    stop_reason: str | None = None
    plan: list[str] = Field(default_factory=list)
    current_plan_step: int = Field(default=0)
    verification_results: list[dict] = Field(default_factory=list)

    def validate_evidence_references(self) -> None:
        """Raise when hypotheses or tool traces cite evidence not in this state."""
        known_ids = {evidence.evidence_id for evidence in self.evidences}
        referenced_ids: set[str] = set()

        for hypothesis in self.hypotheses:
            referenced_ids.update(hypothesis.supporting_evidence_ids)
            referenced_ids.update(hypothesis.conflicting_evidence_ids)
        for invocation in self.tool_history:
            referenced_ids.update(invocation.new_evidence_ids)

        unknown_ids = sorted(referenced_ids - known_ids)
        if unknown_ids:
            raise ValueError(f"unknown evidence IDs: {', '.join(unknown_ids)}")
