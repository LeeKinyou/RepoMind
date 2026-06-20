"""Shared symbol resolution logic for RepoMind."""
from __future__ import annotations

from typing import Any, Mapping

from repomind.utils.path_utils import path_to_module


class SymbolResolver:
    """Unified symbol name resolution for caller/callee lookups."""

    @staticmethod
    def resolve_caller(call: Mapping[str, Any], file_path: str) -> str | None:
        """Resolve caller qualified name from a call dict and file path.

        Args:
            call: Call dictionary with at least ``caller_class`` key.
            file_path: Path to the source file containing the call.

        Returns:
            Qualified name of the caller, or ``None`` if unresolvable.
        """
        if call.get("caller_class"):
            return call["caller_class"]
        return path_to_module(file_path)

    @staticmethod
    def resolve_callee(call: Mapping[str, Any], caller_class: str | None, symbol_index: dict[str, list[str]]) -> str | None:
        """Resolve callee qualified name from a call dict.

        Args:
            call: Call dictionary with ``target`` and ``call_type`` keys.
            caller_class: Qualified name of the enclosing class, if any.
            symbol_index: Mapping of symbol short names to lists of qualified names.

        Returns:
            Qualified name of the callee, or ``None`` if unresolvable.
        """
        target = call.get("target", "")
        call_type = call.get("call_type", "direct")

        if call_type == "self" and caller_class:
            return f"{caller_class}.{target}"

        if target in symbol_index:
            candidates = symbol_index[target]
            # Prefer exact match, then first candidate
            if caller_class:
                for qname in candidates:
                    if qname.startswith(caller_class.rsplit(".", 1)[0] + "."):
                        return qname
            return candidates[0]

        # Fast suffix match using target's last part (fixes H2)
        last_part = target.split(".")[-1] if "." in target else target
        if last_part in symbol_index:
            for qname in symbol_index[last_part]:
                if qname.endswith(f".{target}"):
                    return qname

        # Fallback to full scanning (O(N)) if not found (guarantees compatibility with tests)
        for name, qnames in symbol_index.items():
            for qname in qnames:
                if qname.endswith(f".{target}"):
                    return qname

        return target if target else None
