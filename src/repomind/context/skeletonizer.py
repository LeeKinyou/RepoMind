"""AST-aware code skeletonizer to compress inactive function bodies."""

from __future__ import annotations

import tree_sitter_python as tspython
from tree_sitter import Language, Parser, Node


class CodeSkeletonizer:
    """Folds function bodies that do not contain any active lines of interest."""

    def __init__(self):
        self._lang = Language(tspython.language())
        self._parser = Parser(self._lang)

    def skeletonize(self, source_code: str, active_lines: set[int]) -> str:
        """Compress code by replacing inactive method/function bodies with comments and marking active lines."""
        if not source_code.strip():
            return source_code

        # 1. Pre-process original source code: append tag comment to active lines
        lines = source_code.splitlines()
        tag = " # REPOMIND_ACTIVE"
        for idx in active_lines:
            if 0 < idx <= len(lines):
                lines[idx - 1] += tag
        tagged_code = "\n".join(lines)

        # 2. Parse tagged source code via Tree-sitter
        source_bytes = tagged_code.encode("utf-8")
        tree = self._parser.parse(source_bytes)
        root = tree.root_node

        # Collect function definition nodes
        fn_nodes: list[Node] = []
        self._find_functions(root, fn_nodes)

        # 3. Determine which function bodies to collapse
        replacements = []
        for node in fn_nodes:
            body = node.child_by_field_name("body")
            if body:
                # Check if this function contains any tagged active lines
                body_bytes = source_bytes[body.start_byte : body.end_byte]
                body_text = body_bytes.decode("utf-8", errors="replace")
                if tag in body_text:
                    continue

                body_lines = body_text.splitlines()
                body_line_count = len(body_lines)
                replacements.append(
                    (body.start_byte, body.end_byte, body_line_count)
                )

        # Sort replacements by start_byte descending (bottom-up) to avoid offset shift
        replacements.sort(key=lambda x: x[0], reverse=True)

        # Apply replacements
        for start_byte, end_byte, line_count in replacements:
            collapsed_msg = f"# ... [{line_count} lines collapsed]"
            replacement = collapsed_msg.encode("utf-8")
            source_bytes = source_bytes[:start_byte] + replacement + source_bytes[end_byte:]

        collapsed_str = source_bytes.decode("utf-8", errors="replace")

        # 4. Post-process to remove tag comments and prepend "=> "
        result_lines = []
        for line in collapsed_str.splitlines():
            if tag in line:
                cleaned_line = line.replace(tag, "")
                result_lines.append("=> " + cleaned_line)
            else:
                result_lines.append(line)

        return "\n".join(result_lines) + ("\n" if collapsed_str.endswith("\n") else "")

    def _find_functions(self, node: Node, fn_nodes: list[Node]) -> None:
        """Walk the AST to find all function definitions recursively."""
        if node.type == "function_definition":
            fn_nodes.append(node)
        
        for child in node.children:
            self._find_functions(child, fn_nodes)
