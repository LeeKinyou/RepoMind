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

    def infer(
        self, source: str, line: int, column: int, name: str = ""
    ) -> InferredType:
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

    def _is_valid_type(self, t: str) -> bool:
        t = t.strip()
        if not t:
            return False
        import keyword

        # Split by brackets/non-word characters to check individual components
        parts = re.split(r"[^a-zA-Z0-9_]", t)
        for p in parts:
            if p and keyword.iskeyword(p):
                return False
        return True

    def _get_enclosing_block_lines(self, source: str, line: int) -> list[str]:
        lines = source.split("\n")
        if line < 1 or line > len(lines):
            return lines

        # Find enclosing def signature line
        start_line_idx = line - 1
        # Look upwards for def
        def_line_idx = -1
        for idx in range(start_line_idx, -1, -1):
            if re.match(r"^\s*def\s+\w+", lines[idx]):
                def_line_idx = idx
                break

        if def_line_idx == -1:
            return lines  # Fallback to all lines if not inside a def

        # Determine def line indentation
        def_line = lines[def_line_idx]
        indent = len(def_line) - len(def_line.lstrip())

        # Collect lines below def_line_idx that are indented more
        block_lines = [def_line]
        for idx in range(def_line_idx + 1, len(lines)):
            curr_line = lines[idx]
            if not curr_line.strip():
                block_lines.append(curr_line)
                continue
            curr_indent = len(curr_line) - len(curr_line.lstrip())
            if curr_indent <= indent:
                break
            block_lines.append(curr_line)

        return block_lines

    def _strategy_explicit_hint(
        self, source: str, line: int, column: int, name: str
    ) -> str | None:
        """Strategy 1: Extract explicit type annotations (def foo(x: str) -> int)."""
        lines = source.split("\n")
        if line < 1 or line > len(lines):
            return None
        code_line = lines[line - 1]

        # Is the target the function itself (for return type)?
        # e.g., if code_line has "def name("
        is_fn = False
        if name:
            fn_pattern = rf"def\s+{re.escape(name)}\b"
            if re.search(fn_pattern, code_line):
                is_fn = True
        else:
            # If name is empty, assume we want the return type if present
            is_fn = True

        if is_fn:
            # Check return type annotation using regex for complex types
            match = re.search(r"->\s*([\w\[\],\s\.]+)\s*:", code_line)
            if match:
                ret_type = match.group(1).strip()
                if self._is_valid_type(ret_type):
                    return ret_type
        else:
            # Check parameter annotations
            if ":" in code_line and "(" in code_line:
                if name:
                    param_pattern = (
                        rf"\b{re.escape(name)}\s*:\s*([\w\[\],\s\.]+?)(?:,|\)|=)"
                    )
                    param_match = re.search(param_pattern, code_line)
                    if param_match:
                        t = param_match.group(1).strip()
                        if self._is_valid_type(t):
                            return t
                else:
                    match = re.search(r":\s*([\w\[\],\s\.]+)", code_line)
                    if match:
                        t = match.group(1).strip()
                        if self._is_valid_type(t):
                            return t
        return None

    def _strategy_import_mapping(
        self, source: str, line: int, column: int, name: str
    ) -> str | None:
        """Strategy 2: Resolve type from import statements."""
        for match in re.finditer(r"from\s+[\w.]+\s+import\s+(\w+)", source):
            imported = match.group(1)
            if imported == name or imported.lower() == name.lower():
                return imported
        return None

    def _strategy_self_inference(
        self, source: str, line: int, column: int, name: str
    ) -> str | None:
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

    def _strategy_assignment(
        self, source: str, line: int, column: int, name: str
    ) -> str | None:
        """Strategy 4: Infer type from assignment (x = SomeClass())."""
        if not name:
            return None
        lines = source.split("\n")
        current_idx = line - 1
        # Walk upwards to find assignment to a class constructor call: name = ClassName(
        for i in range(current_idx, max(-1, current_idx - 50), -1):
            if i >= len(lines):
                continue
            code_line = lines[i]
            match = re.search(rf"\b{re.escape(name)}\s*=\s*(\w+)\s*\(", code_line)
            if match:
                cls = match.group(1)
                if cls[0].isupper():
                    return cls
                import builtins
                if hasattr(builtins, cls):
                    return cls
        return None

    def _strategy_jedi(
        self, source: str, line: int, column: int, name: str
    ) -> str | None:
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

    def _strategy_duck_typing(
        self, source: str, line: int, column: int, name: str
    ) -> str | None:
        """Strategy 6: Duck typing inference from method calls."""
        if not name:
            return None
        pattern = rf"\b{re.escape(name)}\.(\w+)\("
        matches = []
        target_lines = self._get_enclosing_block_lines(source, line)
        for src_line in target_lines:
            stripped = src_line.strip()
            # Skip comments and string-only lines
            if (
                stripped.startswith("#")
                or stripped.startswith("'")
                or stripped.startswith('"')
            ):
                continue
            # Remove inline comments
            code_part = src_line.split("#")[0]
            matches.extend(re.findall(pattern, code_part))
        if matches:
            return f"DuckType({', '.join(sorted(set(matches)))})"
        return None
