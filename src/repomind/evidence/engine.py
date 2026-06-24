"""Unified deterministic evidence operations for MCP tools and agents."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from repomind.evidence.source_extractor import SourceExtractor
from repomind.models.evidence import Evidence, EvidenceBundle
from repomind.models.schemas import (
    QueryOptions,
    RelationType,
    SymbolInfo,
    SymbolRelation,
)
from repomind.retriever.query_service import QueryService

RelationDirection = Literal["callers", "callees", "both"]


def _evidence_id(source: str, *parts: object) -> str:
    raw = ":".join([source, *(str(part) for part in parts)])
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{source}-{digest}"


class EvidenceEngine:
    """Collect repository facts without performing generative LLM reasoning."""

    def __init__(
        self,
        index_dir: str,
        query_service: QueryService | None = None,
        max_source_lines: int = 80,
    ):
        self.index_dir = Path(index_dir).resolve()
        self.project_root = self.index_dir.parent
        self.query_service = query_service or QueryService(
            index_dir=str(self.index_dir)
        )
        self.source_extractor = SourceExtractor(
            self.project_root, max_lines=max_source_lines
        )

    @property
    def degraded_features(self) -> list[str]:
        return list(self.query_service.retriever.degraded_features)

    def search_symbols(self, query: str, limit: int = 8) -> EvidenceBundle:
        result = self.query_service.search(
            query,
            options=QueryOptions(
                max_results=limit,
                include_code=True,
                graph_hops=1,
            ),
        )
        evidences = [
            Evidence(
                evidence_id=_evidence_id(
                    "search", symbol.qualified_name, symbol.start_line
                ),
                source="search",
                file_path=symbol.file_path,
                symbol=symbol.qualified_name,
                start_line=symbol.start_line,
                end_line=symbol.end_line,
                snippet=symbol.snippet,
                relevance_score=result.confidence,
                reason=f"Matched repository query '{query}'.",
                metadata={"retrieval_sources": result.sources},
            )
            for symbol in result.symbols
        ]
        return EvidenceBundle(
            summary=f"Found {len(evidences)} repository symbols for '{query}'.",
            evidences=evidences,
            symbols=result.symbols,
            degraded_features=self.degraded_features,
        )

    def get_symbol_source(self, qualified_name: str) -> Evidence | None:
        symbol = self.query_service.get_symbol_info(qualified_name)
        if symbol is None:
            return None
        snippet = self.source_extractor.extract_symbol(symbol)
        return Evidence(
            evidence_id=_evidence_id("source", qualified_name, symbol.start_line),
            source="source",
            file_path=symbol.file_path,
            symbol=qualified_name,
            start_line=symbol.start_line,
            end_line=symbol.end_line,
            snippet=snippet,
            relevance_score=1.0,
            reason=f"Exact indexed source for '{qualified_name}'.",
        )

    def expand_relations(
        self,
        qualified_name: str,
        direction: RelationDirection = "both",
    ) -> EvidenceBundle:
        if direction not in {"callers", "callees", "both"}:
            raise ValueError(f"Unsupported relation direction: {direction}")

        relations: list[SymbolRelation] = []
        evidences: list[Evidence] = []
        symbols: list[SymbolInfo] = []

        if direction in {"callers", "both"}:
            for row in self.query_service.get_callers(qualified_name):
                relation, evidence, symbol = self._relation_from_row(
                    row,
                    source=row["qualified_name"],
                    target=qualified_name,
                    direction="callers",
                )
                relations.append(relation)
                evidences.append(evidence)
                symbols.append(symbol)

        if direction in {"callees", "both"}:
            for row in self.query_service.get_callees(qualified_name):
                relation, evidence, symbol = self._relation_from_row(
                    row,
                    source=qualified_name,
                    target=row["qualified_name"],
                    direction="callees",
                )
                relations.append(relation)
                evidences.append(evidence)
                symbols.append(symbol)

        return EvidenceBundle(
            summary=(
                f"Found {len(relations)} {direction} relations for '{qualified_name}'."
            ),
            evidences=evidences,
            symbols=symbols,
            relations=relations,
            degraded_features=self.degraded_features,
        )

    def _relation_from_row(
        self,
        row: dict,
        *,
        source: str,
        target: str,
        direction: Literal["callers", "callees"],
    ) -> tuple[SymbolRelation, Evidence, SymbolInfo]:
        confidence = min(1.0, max(0.0, float(row.get("confidence", 1.0))))
        symbol = self.query_service._dict_to_symbol_info(row)
        snippet = self.source_extractor.extract_symbol(symbol)
        relation = SymbolRelation(
            source=source,
            target=target,
            relation_type=RelationType.CALLS,
            line_number=row.get("line_number"),
            weight=confidence,
        )
        evidence = Evidence(
            evidence_id=_evidence_id(
                "graph", source, target, row.get("line_number", "")
            ),
            source="graph",
            file_path=symbol.file_path,
            symbol=symbol.qualified_name,
            start_line=symbol.start_line,
            end_line=symbol.end_line,
            snippet=snippet,
            relevance_score=confidence,
            reason=f"Static call relation {source} -> {target}.",
            metadata={
                "direction": direction,
                "call_type": row.get("call_type", "unknown"),
            },
        )
        return relation, evidence, symbol
