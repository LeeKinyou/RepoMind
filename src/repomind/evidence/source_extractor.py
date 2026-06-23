"""Bounded source extraction for indexed symbols."""

from __future__ import annotations

from pathlib import Path

from repomind.models.schemas import SymbolInfo


class SourceExtractor:
    """Read indexed source ranges without returning whole large files."""

    def __init__(self, project_root: str | Path, max_lines: int = 80):
        self.project_root = Path(project_root).resolve()
        self.max_lines = max_lines

    def extract_symbol(self, symbol: SymbolInfo) -> str | None:
        """Return the indexed symbol range, bounded by ``max_lines``."""
        path = Path(symbol.file_path)
        if not path.is_absolute():
            path = self.project_root / path
        if not path.is_file():
            return None

        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(0, symbol.start_line - 1)
        end = min(len(lines), symbol.end_line, start + self.max_lines)
        return "\n".join(lines[start:end])
