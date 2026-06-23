"""Structured evidence models shared by services, agents, and MCP tools."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

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
