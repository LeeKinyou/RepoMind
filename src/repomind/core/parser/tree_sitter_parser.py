"""Tree-sitter based Python parser for RepoMind."""
from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass, field

import tree_sitter_python as tspython
from tree_sitter import Language, Parser, Node

from repomind.models.schemas import SymbolInfo, SymbolType
from repomind.utils.path_utils import path_to_module


@dataclass
class ParsedFile:
    """Result of parsing a single file."""
    path: str
    source: bytes
    symbols: list[SymbolInfo] = field(default_factory=list)
    imports: list[dict] = field(default_factory=list)
    calls: list[dict] = field(default_factory=list)
    classes: list[dict] = field(default_factory=list)


class TreeSitterParser:
    """Tree-sitter based parser for Python source code."""

    def __init__(self):
        self._lang = Language(tspython.language())
        self._parser = Parser(self._lang)

    def parse_file(self, file_path: str) -> ParsedFile:
        """Parse a Python file and extract symbols, imports, and calls."""
        path = Path(file_path)
        source = path.read_bytes()
        tree = self._parser.parse(source)
        root = tree.root_node

        pf = ParsedFile(path=str(path), source=source)
        self._walk_node(root, pf, parent_class=None, module_path=self._to_module_path(path))
        return pf

    def parse_source(self, source: str, file_path: str = "<string>") -> ParsedFile:
        """Parse Python source code string."""
        source_bytes = source.encode("utf-8")
        tree = self._parser.parse(source_bytes)
        root = tree.root_node
        pf = ParsedFile(path=file_path, source=source_bytes)
        self._walk_node(root, pf, parent_class=None, module_path=path_to_module(file_path))
        return pf

    def _walk_node(self, node: Node, pf: ParsedFile, parent_class: str | None, module_path: str) -> None:
        for child in node.children:
            if child.type == "class_definition":
                self._extract_class(child, pf, module_path)
            elif child.type == "function_definition":
                self._extract_function(child, pf, parent_class, module_path)
            elif child.type in ("import_statement", "import_from_statement"):
                self._extract_import(child, pf)
            elif child.type == "call":
                self._extract_call(child, pf, parent_class, module_path)
                self._walk_node(child, pf, parent_class, module_path)
            else:
                self._walk_node(child, pf, parent_class, module_path)

    def _extract_class(self, node: Node, pf: ParsedFile, module_path: str) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return
        name = name_node.text.decode("utf-8")
        qname = f"{module_path}.{name}"
        body = node.child_by_field_name("body")
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        docstring = self._extract_docstring(body)

        # Extract parent classes
        bases = node.child_by_field_name("bases")
        parent_names = []
        if bases:
            for base in bases.children:
                if base.type == "identifier":
                    parent_names.append(base.text.decode("utf-8"))
                elif base.type == "attribute":
                    parent_names.append(self._get_attribute_text(base))

        pf.symbols.append(SymbolInfo(
            name=name, qualified_name=qname, type=SymbolType.CLASS,
            file_path=pf.path, start_line=start_line, end_line=end_line,
            docstring=docstring,
        ))
        pf.classes.append({"name": name, "qualified_name": qname, "parents": parent_names})

        # Walk class body for methods
        if body:
            self._walk_node(body, pf, parent_class=qname, module_path=module_path)

    def _extract_function(self, node: Node, pf: ParsedFile, parent_class: str | None, module_path: str) -> None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return
        name = name_node.text.decode("utf-8")
        if parent_class:
            qname = f"{parent_class}.{name}"
            sym_type = SymbolType.METHOD
        else:
            qname = f"{module_path}.{name}"
            sym_type = SymbolType.FUNCTION

        body = node.child_by_field_name("body")
        if body:
            sig_bytes = pf.source[node.start_byte:body.start_byte]
            signature = sig_bytes.decode("utf-8").rstrip().rstrip(":").strip()
        else:
            signature = self._node_text(node).split("\n")[0].strip()
        docstring = self._extract_docstring(body)

        pf.symbols.append(SymbolInfo(
            name=name, qualified_name=qname, type=sym_type,
            file_path=pf.path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            docstring=docstring, signature=signature,
            parent_class=parent_class,
        ))

        # Recurse into function body for nested calls
        if body:
            self._walk_node(body, pf, parent_class, module_path)

    def _extract_import(self, node: Node, pf: ParsedFile) -> None:
        if node.type == "import_from_statement":
            module_node = node.child_by_field_name("module_name")
            module_path = self._node_text(module_node) if module_node else ""
            is_relative = module_path.startswith(".")
            relative_level = len(module_path) - len(module_path.lstrip("."))

            children = list(node.children)
            # Find the 'import' keyword position
            import_idx = -1
            for idx, child in enumerate(children):
                if child.type == "import":
                    import_idx = idx
                    break

            # Only process import targets AFTER the 'import' keyword
            i = import_idx + 1 if import_idx >= 0 else 0
            while i < len(children):
                child = children[i]
                if child.type == "dotted_name":
                    name = self._node_text(child)
                    pf.imports.append({
                        "module_path": module_path.lstrip("."),
                        "imported_name": name,
                        "alias": None,
                        "is_relative": is_relative,
                        "relative_level": relative_level,
                        "line_number": node.start_point[0] + 1,
                    })
                    i += 1
                elif child.type == "aliased_import":
                    # Handle "import X as Y" wrapper
                    name_node = child.child_by_field_name("name")
                    alias_node = child.child_by_field_name("alias")
                    name = self._node_text(name_node) if name_node else ""
                    alias = self._node_text(alias_node) if alias_node else None
                    pf.imports.append({
                        "module_path": module_path.lstrip("."),
                        "imported_name": name,
                        "alias": alias,
                        "is_relative": is_relative,
                        "relative_level": relative_level,
                        "line_number": node.start_point[0] + 1,
                    })
                    i += 1
                else:
                    i += 1
        elif node.type == "import_statement":
            for child in node.children:
                if child.type == "dotted_name":
                    name = self._node_text(child)
                    pf.imports.append({
                        "module_path": name,
                        "imported_name": None,
                        "alias": None,
                        "is_relative": False,
                        "relative_level": 0,
                        "line_number": node.start_point[0] + 1,
                    })
                elif child.type == "aliased_import":
                    name_node = child.child_by_field_name("name")
                    alias_node = child.child_by_field_name("alias")
                    name = self._node_text(name_node) if name_node else ""
                    alias = self._node_text(alias_node) if alias_node else None
                    pf.imports.append({
                        "module_path": name,
                        "imported_name": None,
                        "alias": alias,
                        "is_relative": False,
                        "relative_level": 0,
                        "line_number": node.start_point[0] + 1,
                    })

    def _extract_call(self, node: Node, pf: ParsedFile, parent_class: str | None, module_path: str) -> None:
        func = node.child_by_field_name("function")
        if not func:
            return
        if func.type == "identifier":
            pf.calls.append({
                "caller_class": parent_class,
                "target": self._node_text(func),
                "call_type": "direct",
                "line_number": node.start_point[0] + 1,
            })
        elif func.type == "attribute":
            parts = self._get_attribute_parts(func)
            if parts and parts[0] == "self":
                pf.calls.append({
                    "caller_class": parent_class,
                    "target": parts[-1] if len(parts) > 1 else parts[0],
                    "call_type": "self",
                    "line_number": node.start_point[0] + 1,
                })
            else:
                pf.calls.append({
                    "caller_class": parent_class,
                    "target": ".".join(parts) if parts else "",
                    "call_type": "method",
                    "line_number": node.start_point[0] + 1,
                })

    def _extract_docstring(self, body_node: Node | None) -> str | None:
        if not body_node or not body_node.children:
            return None
        first = body_node.children[0]
        if first.type == "expression_statement" and first.children:
            expr = first.children[0]
            if expr.type == "string":
                text = self._node_text(expr)
                # Strip string prefixes (f, b, r, rb, br, fb, bf)
                for prefix in ("rb", "br", "fb", "bf", "f", "b", "r"):
                    if text.startswith(prefix):
                        text = text[len(prefix):]
                        break
                for quote in ('"""', "'''", '"', "'"):
                    if text.startswith(quote) and text.endswith(quote):
                        return text[len(quote):-len(quote)].strip()
                return text
        return None

    def _node_text(self, node: Node | None) -> str:
        if node is None:
            return ""
        return node.text.decode("utf-8") if node.text else ""

    def _get_attribute_text(self, node: Node) -> str:
        parts = self._get_attribute_parts(node)
        return ".".join(parts)

    def _get_attribute_parts(self, node: Node) -> list[str]:
        parts = []
        for child in node.children:
            if child.type == "identifier":
                parts.append(self._node_text(child))
            elif child.type == "attribute":
                parts.extend(self._get_attribute_parts(child))
        return parts

    def _to_module_path(self, path: Path) -> str:
        return path_to_module(str(path))
