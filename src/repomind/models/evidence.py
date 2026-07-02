"""Structured evidence models shared by services, agents, and MCP tools."""

from __future__ import annotations

from typing import Literal, TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from repomind.models.schemas import RCAResult

from repomind.models.schemas import SymbolInfo, SymbolRelation

EvidenceSource = Literal["trace", "search", "graph", "source", "test"]


class Evidence(BaseModel):
    """A single repository fact that can be independently inspected."""

    evidence_id: str
    source: EvidenceSource
    file_path: str
    symbol: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    snippet: str | None = None
    relevance_score: float = Field(ge=0.0, le=1.0)
    reason: str
    metadata: dict[str, object] = Field(default_factory=dict)


class EvidenceBundle(BaseModel):
    """Structured result returned by deterministic evidence operations."""

    summary: str
    evidences: list[Evidence] = Field(default_factory=list)
    symbols: list[SymbolInfo] = Field(default_factory=list)
    relations: list[SymbolRelation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    degraded_features: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)

    def to_legacy_result(self) -> "RCAResult":
        from repomind.models.schemas import RCAResult, EvidenceItem, IndexSnapshot

        root_cause = self.summary or "Unknown Error"
        evidences = []
        call_chain = []
        for ev in self.evidences:
            evidences.append(
                EvidenceItem(
                    file_path=ev.file_path,
                    symbol=ev.symbol,
                    start_line=ev.start_line,
                    end_line=ev.end_line,
                    snippet=ev.snippet or "",
                    source=ev.source,
                    score=ev.relevance_score,
                    why_relevant=ev.reason,
                )
            )
            if ev.source == "trace":
                call_chain.append(f"{ev.file_path}:{ev.start_line} in {ev.symbol}")
        
        confidence = 0.0
        if evidences:
            confidence = 0.8 if self.symbols else 0.4

        snapshot_data = self.metadata.get("snapshot")
        snapshot = (
            IndexSnapshot.model_validate(snapshot_data)
            if isinstance(snapshot_data, dict)
            else None
        )

        return RCAResult(
            root_cause=root_cause,
            confidence=confidence,
            affected_symbols=self.symbols,
            call_chain=call_chain,
            explanation="Deterministic evidence collection mode (LLM disabled).",
            suggested_fix=None,
            evidence=[],
            evidences=evidences,
            verification_command="uv run pytest",
            snapshot=snapshot,
        )
