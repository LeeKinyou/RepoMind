"""Progressive type inference engine with 6-strategy cascade."""
from __future__ import annotations

import re
from dataclasses import dataclass

from repomind.models.schemas import SymbolInfo


@dataclass
class InferredType:
    """Result of type inference."""
    type_name: str | None
    confidence: float
    strategy: str
    evidence: str = ""


class TypeInferenceEngine:
    """Progressive type inference with 6 strategies, from high to low confidence."""

    STRATEGIES = [
        ("explicit_hint", 0.95),
        ("import_mapping", 0.90),
        ("self_inference", 0.85),
        ("assignment", 0.70),
        ("jedi", 0.60),
        ("duck_typing", 0.40),
    ]

    def infer(self, source: str, line: int, column: int, name: str = "") -> InferredType:
        """Run cascade inference, returning the first successful result."""
        for strategy_name, confidence in self.STRATEGIES:
            method = getattr(self, f"_strategy_{strategy_name}")
            result = method(source, line, column, name)
            if result:
                return InferredType(
                    type_name=result,
                    confidence=confidence,
                    strategy=strategy_name,
                )
        return InferredType(type_name=None, confidence=0.0, strategy="none")

    def infer_symbol(self, symbol: SymbolInfo, source: str) -> InferredType:
        """Infer type for a symbol using its location info."""
        return self.infer(source, symbol.start_line, 0, symbol.name)

    def _strategy_explicit_hint(self, source: str, line: int, column: int, name: str) -> str | None:
        """Strategy 1: Extract explicit type annotations (def foo(x: str) -> int)."""
        lines = source.split("\n")
        if line < 1 or line > len(lines):
            return None
        code_line = lines[line - 1]
        # Check return type annotation using regex for complex types
        match = re.search(r'->\s*([\w\[\],\s\.]+)\s*:', code_line)
        if match:
            ret_type = match.group(1).strip()
            if ret_type and ret_type[0].isupper():
                return ret_type
        # Check parameter annotations
        if ":" in code_line and "(" in code_line:
            match = re.search(r":\s*(\w+)", code_line)
            if match:
                t = match.group(1)
                if t[0].isupper():
                    return t
        return None

    def _strategy_import_mapping(self, source: str, line: int, column: int, name: str) -> str | None:
        """Strategy 2: Resolve type from import statements."""
        for match in re.finditer(r"from\s+[\w.]+\s+import\s+(\w+)", source):
            imported = match.group(1)
            if imported == name or imported.lower() == name.lower():
                return imported
        return None

    def _strategy_self_inference(self, source: str, line: int, column: int, name: str) -> str | None:
        """Strategy 3: Infer self parameter type from class context."""
        if name == "self":
            lines = source.split("\n")
            for i in range(line - 2, max(-1, line - 51), -1):
                if i < 0 or i >= len(lines):
                    continue
                match = re.match(r"class\s+(\w+)", lines[i])
                if match:
                    return match.group(1)
        return None

    def _strategy_assignment(self, source: str, line: int, column: int, name: str) -> str | None:
        """Strategy 4: Infer type from assignment (x = SomeClass())."""
        lines = source.split("\n")
        if line < 1 or line > len(lines):
            return None
        code_line = lines[line - 1]
        match = re.search(rf"{name}\s*=\s*(\w+)\s*\(", code_line)
        if match:
            cls = match.group(1)
            if cls[0].isupper():
                return cls
        return None

    def _strategy_jedi(self, source: str, line: int, column: int, name: str) -> str | None:
        """Strategy 5: Use Jedi for type inference."""
        try:
            import jedi
            script = jedi.Script(source)
            defs = script.infer(line, column)
            if defs:
                return defs[0].name
        except Exception:
            pass
        return None

    def _strategy_duck_typing(self, source: str, line: int, column: int, name: str) -> str | None:
        """Strategy 6: Duck typing inference from method calls."""
        pattern = rf"{re.escape(name)}\.(\w+)\("
        matches = []
        for src_line in source.split("\n"):
            stripped = src_line.strip()
            # Skip comments and string-only lines
            if stripped.startswith("#") or stripped.startswith("'") or stripped.startswith('"'):
                continue
            # Remove inline comments
            code_part = src_line.split("#")[0]
            matches.extend(re.findall(pattern, code_part))
        if matches:
            return f"DuckType({', '.join(sorted(set(matches)))})"
        return None
