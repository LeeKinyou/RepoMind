"""Call graph builder for RepoMind."""
from __future__ import annotations

from repomind.core.parser.tree_sitter_parser import ParsedFile
from repomind.storage.graph_store import GraphStore
from repomind.models.schemas import SymbolRelation, RelationType
from repomind.core.call_graph.resolver import SymbolResolver
from repomind.utils.path_utils import path_to_module


class CallGraphBuilder:
    """Builds call graph from parsed files into GraphStore."""

    def __init__(self, graph_store: GraphStore | None = None):
        self.graph = graph_store or GraphStore()
        self._symbol_index: dict[str, list[str]] = {}  # name -> [qualified_names]

    def build(self, parsed_files: list[ParsedFile]) -> GraphStore:
        """Build complete call graph from parsed files."""
        # Reset state (fixes M17)
        self._symbol_index = {}

        # Phase 1: Index all symbols
        for pf in parsed_files:
            for sym in pf.symbols:
                self.graph.add_symbol(sym.qualified_name, type=sym.type.value, file_path=sym.file_path)
                self._symbol_index.setdefault(sym.name, []).append(sym.qualified_name)

        # Phase 2: Build import edges (fixes S1)
        for pf in parsed_files:
            for imp in pf.imports:
                qname = self._resolve_import(imp)
                if qname:
                    short_name = qname.rsplit(".", 1)[-1] if "." in qname else qname
                    if short_name in self._symbol_index and qname in self._symbol_index[short_name]:
                        file_qname = path_to_module(pf.path)
                        self.graph.add_relation(SymbolRelation(
                            source=file_qname, target=qname,
                            relation_type=RelationType.IMPORTS,
                            line_number=imp.get("line_number"),
                        ))

        # Phase 3: Build inheritance edges (fixes H1 & M18)
        for pf in parsed_files:
            for cls in pf.classes:
                for parent in cls.get("parents", []):
                    parent_candidates = self._symbol_index.get(parent, [])
                    parent_qname = parent
                    if parent_candidates:
                        # Heuristic: 1. same module
                        module_prefix = cls["qualified_name"].rsplit(".", 1)[0] + "."
                        for cand in parent_candidates:
                            if cand.startswith(module_prefix):
                                parent_qname = cand
                                break
                        else:
                            # Heuristic: 2. imported name matches
                            for imp in pf.imports:
                                alias = imp.get("alias")
                                imp_name = imp.get("imported_name")
                                if (alias and alias == parent) or (not alias and imp_name == parent):
                                    resolved = self._resolve_import(imp)
                                    if resolved in parent_candidates:
                                        parent_qname = resolved
                                        break
                            else:
                                parent_qname = parent_candidates[0]
                                
                    self.graph.add_relation(SymbolRelation(
                        source=cls["qualified_name"],
                        target=parent_qname,
                        relation_type=RelationType.INHERITS,
                        line_number=cls.get("line_number"),
                    ))

        # Phase 4: Build call edges
        for pf in parsed_files:
            for call in pf.calls:
                caller_qname = SymbolResolver.resolve_caller(call, pf.path)
                callee_qname = SymbolResolver.resolve_callee(call, call.get("caller_class"), self._symbol_index)
                if caller_qname and callee_qname:
                    self.graph.add_relation(SymbolRelation(
                        source=caller_qname,
                        target=callee_qname,
                        relation_type=RelationType.CALLS,
                        line_number=call.get("line_number"),
                    ))

        return self.graph

    def _resolve_import(self, imp: dict) -> str | None:
        module = imp.get("module_path", "")
        name = imp.get("imported_name")
        if name:
            return f"{module}.{name}" if module else name
        return module if module else None

    def get_graph(self) -> GraphStore:
        return self.graph
