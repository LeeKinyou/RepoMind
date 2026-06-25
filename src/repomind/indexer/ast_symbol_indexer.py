"""AST-based Python symbol extractor using standard library ast."""

from __future__ import annotations

import ast
from typing import Optional
from pathlib import Path

from repomind.models.schemas import SymbolInfo, SymbolType
from repomind.utils.path_utils import path_to_module


class ASTSymbolVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str, module_path: str, source_lines: list[str]):
        self.file_path = file_path
        self.module_path = module_path
        self.source_lines = source_lines
        self.symbols: list[SymbolInfo] = []
        self.scope_stack: list[tuple[str, str]] = []  # (name, type) e.g., ("ClassName", "class")

    def _get_current_prefix(self) -> str:
        if not self.scope_stack:
            return self.module_path
        parts = [self.module_path] + [name for name, _ in self.scope_stack]
        return ".".join(parts)

    def visit_ClassDef(self, node: ast.ClassDef):
        name = node.name
        parent_prefix = self._get_current_prefix()
        qualified_name = f"{parent_prefix}.{name}" if parent_prefix else name
        
        docstring = ast.get_docstring(node)
        
        bases = []
        if hasattr(ast, "unparse"):
            try:
                bases = [ast.unparse(b) for b in node.bases]
            except Exception:
                pass
        
        signature = f"class {name}"
        if bases:
            signature += f"({', '.join(bases)})"
            
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", node.lineno)
        
        parent_class = self.scope_stack[-1][0] if (self.scope_stack and self.scope_stack[-1][1] == "class") else None
        
        # Extract snippet
        start_idx = max(0, start_line - 1)
        end_idx = min(len(self.source_lines), end_line)
        snippet = "\n".join(self.source_lines[start_idx:end_idx])

        self.symbols.append(SymbolInfo(
            name=name,
            qualified_name=qualified_name,
            type=SymbolType.CLASS,
            file_path=self.file_path,
            start_line=start_line,
            end_line=end_line,
            docstring=docstring,
            signature=signature,
            parent_class=parent_class,
            snippet=snippet,
        ))
        
        self.scope_stack.append((name, "class"))
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._visit_func(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._visit_func(node, is_async=True)

    def _visit_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool):
        name = node.name
        parent_prefix = self._get_current_prefix()
        qualified_name = f"{parent_prefix}.{name}" if parent_prefix else name
        
        in_class = any(kind == "class" for _, kind in self.scope_stack)
        sym_type = SymbolType.METHOD if in_class else SymbolType.FUNCTION
        
        docstring = ast.get_docstring(node)
        
        signature = ""
        if hasattr(ast, "unparse"):
            try:
                args_str = ast.unparse(node.args)
                prefix = "async def" if is_async else "def"
                signature = f"{prefix} {name}({args_str})"
            except Exception:
                signature = f"def {name}(...)"
        else:
            signature = f"def {name}(...)"
            
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", node.lineno)
        
        parent_class = self.scope_stack[-1][0] if (self.scope_stack and self.scope_stack[-1][1] == "class") else None
        
        # Extract snippet
        start_idx = max(0, start_line - 1)
        end_idx = min(len(self.source_lines), end_line)
        snippet = "\n".join(self.source_lines[start_idx:end_idx])

        self.symbols.append(SymbolInfo(
            name=name,
            qualified_name=qualified_name,
            type=sym_type,
            file_path=self.file_path,
            start_line=start_line,
            end_line=end_line,
            docstring=docstring,
            signature=signature,
            parent_class=parent_class,
            snippet=snippet,
        ))
        
        self.scope_stack.append((name, "function"))
        self.generic_visit(node)
        self.scope_stack.pop()


class ASTSymbolIndexer:
    """Parses python files using standard AST module to extract code symbols."""

    def extract_symbols(self, source_code: str, file_path: str, project_root: str | None = None) -> list[SymbolInfo]:
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return []
            
        module_path = path_to_module(file_path, project_root=project_root or "")
        source_lines = source_code.splitlines()
        
        visitor = ASTSymbolVisitor(file_path, module_path, source_lines)
        visitor.visit(tree)
        return visitor.symbols

    def generate_symbol_chunk(self, symbol: SymbolInfo, source_code: str) -> str:
        lines = source_code.splitlines()
        start = max(0, symbol.start_line - 1)
        end = min(len(lines), symbol.end_line)
        code_snippet = "\n".join(lines[start:end])
        
        return (
            f"file: {symbol.file_path}\n"
            f"symbol: {symbol.qualified_name}\n"
            f"kind: {symbol.type.value}\n"
            f"signature: {symbol.signature or ''}\n"
            f"docstring: {symbol.docstring or ''}\n"
            f"code:\n"
            f"{code_snippet}"
        )
