"""Project registry for RepoMind CLI.

Manages a persistent list of recently used projects so users can switch
between them with the /project command. The registry is stored as JSON
in the user's home directory (~/.repomind/projects.json).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path


REGISTRY_PATH = Path.home() / ".repomind" / "projects.json"
MAX_PROJECTS = 20


@dataclass
class ProjectEntry:
    """A single project entry in the registry."""

    name: str
    path: str
    last_used: float = field(default_factory=time.time)
    indexed: bool = False
    file_count: int = 0
    symbol_count: int = 0

    def touch(self) -> None:
        """Update last_used timestamp to now."""
        self.last_used = time.time()


class ProjectRegistry:
    """Persistent registry of recently used projects."""

    def __init__(self, path: Path | None = None) -> None:
        """Initialize the registry.

        Args:
            path: Optional override for the registry file path.
                  Defaults to ~/.repomind/projects.json
        """
        self.path = path or REGISTRY_PATH
        self._projects: dict[str, ProjectEntry] = {}
        self._load()

    def _load(self) -> None:
        """Load the registry from disk."""
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            for entry_data in data.get("projects", []):
                entry = ProjectEntry(**entry_data)
                # Use resolved path string as key for uniqueness
                self._projects[entry.path] = entry
        except (json.JSONDecodeError, TypeError, ValueError):
            # Corrupt registry — start fresh
            self._projects = {}

    def _save(self) -> None:
        """Persist the registry to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "projects": [
                asdict(entry)
                for entry in sorted(
                    self._projects.values(),
                    key=lambda e: e.last_used,
                    reverse=True,
                )[:MAX_PROJECTS]
            ]
        }
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def add(
        self,
        path: str | Path,
        name: str | None = None,
        indexed: bool = False,
        file_count: int = 0,
        symbol_count: int = 0,
    ) -> ProjectEntry:
        """Add or update a project in the registry.

        Args:
            path: Project path (will be resolved to absolute)
            name: Optional display name (defaults to directory name)
            indexed: Whether the project is indexed
            file_count: Number of indexed files
            symbol_count: Number of indexed symbols

        Returns:
            The project entry
        """
        resolved = str(Path(path).resolve())
        display_name = name or Path(resolved).name

        if resolved in self._projects:
            entry = self._projects[resolved]
            entry.name = display_name
            entry.indexed = indexed
            entry.file_count = file_count
            entry.symbol_count = symbol_count
        else:
            entry = ProjectEntry(
                name=display_name,
                path=resolved,
                indexed=indexed,
                file_count=file_count,
                symbol_count=symbol_count,
            )
            self._projects[resolved] = entry

        entry.touch()
        self._save()
        return entry

    def remove(self, path: str | Path) -> bool:
        """Remove a project from the registry.

        Args:
            path: Project path

        Returns:
            True if the project was removed, False if it wasn't found
        """
        resolved = str(Path(path).resolve())
        if resolved in self._projects:
            del self._projects[resolved]
            self._save()
            return True
        return False

    def get(self, path: str | Path) -> ProjectEntry | None:
        """Get a project entry by path.

        Args:
            path: Project path

        Returns:
            Project entry or None if not found
        """
        resolved = str(Path(path).resolve())
        return self._projects.get(resolved)

    def list_all(self) -> list[ProjectEntry]:
        """List all projects, most recently used first.

        Returns:
            List of project entries
        """
        return sorted(
            self._projects.values(),
            key=lambda e: e.last_used,
            reverse=True,
        )

    def find_by_name(self, name: str) -> ProjectEntry | None:
        """Find a project by display name (case-insensitive).

        Args:
            name: Project name

        Returns:
            Project entry or None if not found
        """
        name_lower = name.lower()
        for entry in self._projects.values():
            if entry.name.lower() == name_lower:
                return entry
        return None

    def __len__(self) -> int:
        return len(self._projects)

    def __contains__(self, path: object) -> bool:
        if not isinstance(path, (str, Path)):
            return False
        return str(Path(path).resolve()) in self._projects
