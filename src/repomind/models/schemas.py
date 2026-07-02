"""Core data models for RepoMind."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


# === 枚举类型 ===


class SymbolType(str, Enum):
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    MODULE = "module"
    INTERFACE = "interface"
    ENUM = "enum"
    PROPERTY = "property"


class RelationType(str, Enum):
    CALLS = "calls"
    IMPORTS = "imports"
    INHERITS = "inherits"
    CONTAINS = "contains"
    RETURNS = "returns"


def safe_symbol_type(raw: str) -> SymbolType:
    """Safely convert string to SymbolType, warning and falling back to FUNCTION on error."""
    try:
        return SymbolType(raw)
    except ValueError:
        logger.warning("Unknown symbol type '%s', falling back to FUNCTION", raw)
        return SymbolType.FUNCTION


# === 符号模型 ===


class SymbolInfo(BaseModel):
    """代码符号信息"""

    name: str
    qualified_name: str
    type: SymbolType
    file_path: str
    start_line: int
    end_line: int
    docstring: str | None = None
    signature: str | None = None
    is_exported: bool = True
    parent_class: str | None = None
    snippet: str | None = None
    matched_symbols: list[dict] | None = None


class SymbolRelation(BaseModel):
    """符号关系"""

    source: str  # qualified_name
    target: str  # qualified_name
    relation_type: RelationType
    line_number: int | None = None
    weight: float = Field(default=1.0, ge=0.0, le=1.0)  # Legacy, use confidence
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    resolution: str | None = None


# === 索引模型 ===


class IndexOptions(BaseModel):
    """索引配置选项"""

    language: str = "python"
    output_dir: str = ".repomind"
    ignore_patterns: list[str] = Field(
        default_factory=lambda: [
            "**/__pycache__/**",
            "**/.git/**",
            "**/venv/**",
            "**/.venv/**",
        ]
    )
    max_file_size_mb: float = 5.0
    incremental: bool = False
    verbose: bool = False


class IndexResult(BaseModel):
    """索引结果"""

    success: bool
    total_files: int = 0
    indexed_files: int = 0
    skipped_files: int = 0
    total_symbols: int = 0
    total_classes: int = 0
    total_functions: int = 0
    total_imports: int = 0
    total_calls: int = 0
    elapsed_seconds: float = 0.0
    index_path: str = ""
    errors: list[str] = Field(default_factory=list)


# === 查询模型 ===


class FreshnessStatus(str, Enum):
    """Whether the on-disk workspace still matches the persisted index snapshot."""

    CURRENT = "current"
    STALE = "stale"


class FreshnessReport(BaseModel):
    """Workspace/index freshness comparison based on persisted file hashes."""

    status: FreshnessStatus
    index_version: int = 0
    checked_files: int = 0
    unchanged_files: list[str] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)
    new_files: list[str] = Field(default_factory=list)
    deleted_files: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class IndexSnapshot(BaseModel):
    """Index snapshot metadata attached to query and evidence results."""

    index_version: int = 0
    freshness_status: FreshnessStatus = FreshnessStatus.CURRENT
    file_hashes: dict[str, str] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class QueryOptions(BaseModel):
    """查询配置"""

    max_results: int = 10
    include_code: bool = True
    include_docs: bool = True
    expand_graph: bool = True
    graph_hops: int = 2
    mode: str = "full"


class QueryResult(BaseModel):
    """查询结果"""

    answer: str
    symbols: list[SymbolInfo] = Field(default_factory=list)
    relations: list[SymbolRelation] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    sources: list[str] = Field(default_factory=list)
    elapsed_seconds: float = 0.0
    snapshot: IndexSnapshot | None = None


# === RCA 模型 ===


class EvidenceItem(BaseModel):
    """诊断证据条目"""

    file_path: str
    symbol: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    snippet: str
    source: str  # bm25, keyword, graph, traceback
    score: float | None = None
    why_relevant: str | None = None


class RCAResult(BaseModel):
    """根因分析结果"""

    root_cause: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    affected_symbols: list[SymbolInfo] = Field(default_factory=list)
    call_chain: list[str] = Field(default_factory=list)
    explanation: str = ""
    suggested_fix: str | None = None
    # Deprecated: use evidences instead
    evidence: list[str] = Field(default_factory=list)
    evidences: list[EvidenceItem] = Field(default_factory=list)
    verification_command: str | None = None
    snapshot: IndexSnapshot | None = None


class FixResult(BaseModel):
    """修复建议结果"""

    file_path: str
    original_code: str
    suggested_code: str
    explanation: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


# === 图模型 ===


class CallGraphResult(BaseModel):
    """调用图结果"""

    nodes: list[SymbolInfo] = Field(default_factory=list)
    edges: list[SymbolRelation] = Field(default_factory=list)
    root_symbol: str = ""
    depth: int = 0


# === 文件模型 ===


class FileInfo(BaseModel):
    """文件信息"""

    path: str
    language: str
    hash: str
    line_count: int = 0
    size_bytes: int = 0
    last_modified: datetime | None = None
