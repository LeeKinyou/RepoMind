"""Diagnostic Agent orchestrator."""

import logging
from typing import Any

from repomind.agent.planner import Planner
from repomind.agent.reasoner import Reasoner
from repomind.agent.evidence_judge import EvidenceJudge
from repomind.models.diagnostic import DiagnosticState, ToolInvocation
from repomind.models.evidence import Evidence
from repomind.retriever.query_service import QueryService

logger = logging.getLogger(__name__)

class DiagnosticAgent:
    """Bounded, state-machine based agent for diagnosis."""

    def __init__(self, index_dir: str):
        self.index_dir = index_dir
        self.query_svc = QueryService(index_dir=index_dir)
        self.planner = Planner()
        self.reasoner = Reasoner()
        self.judge = EvidenceJudge()

    def _execute_tool(self, name: str, args: dict[str, Any], state: DiagnosticState) -> ToolInvocation:
        """Execute a tool and return the invocation trace."""
        success = False
        error = None
        new_evidence_ids = []

        try:
            if name == "search_code":
                query = args.get("query", "")
                res = self.query_svc.search(query, options=None)
                
                # Add to state.evidences
                for sym in res.symbols:
                    ev_id = f"search_{sym.qualified_name}"
                    new_ev = Evidence(
                        evidence_id=ev_id,
                        source="search",
                        file_path=sym.file_path,
                        symbol=sym.qualified_name,
                        start_line=sym.start_line,
                        end_line=sym.end_line,
                        snippet=sym.docstring or "No docstring",
                        relevance_score=0.8,
                        reason=f"Found via search: {query}"
                    )
                    # Deduplicate
                    if not any(e.evidence_id == ev_id for e in state.evidences):
                        state.evidences.append(new_ev)
                    new_evidence_ids.append(ev_id)
                success = True

            elif name == "expand_call_chain":
                qname = args.get("qualified_name", "")
                graph_res = self.query_svc.get_call_graph(qname, depth=1)
                
                for node in graph_res.nodes:
                    ev_id = f"graph_{node.qualified_name}"
                    new_ev = Evidence(
                        evidence_id=ev_id,
                        source="graph",
                        file_path=node.file_path,
                        symbol=node.qualified_name,
                        start_line=node.start_line,
                        end_line=node.end_line,
                        snippet="",
                        relevance_score=0.7,
                        reason=f"Related to {qname} via call graph"
                    )
                    if not any(e.evidence_id == ev_id for e in state.evidences):
                        state.evidences.append(new_ev)
                    new_evidence_ids.append(ev_id)
                success = True

            elif name == "stop_diagnosis":
                state.stop_reason = args.get("reason", "Agent decided to stop.")
                success = True

            else:
                error = f"Unknown tool: {name}"
        except Exception as e:
            error = str(e)
            logger.exception("Error executing tool %s", name)

        return ToolInvocation(
            tool_name=name,
            arguments=args,
            iteration=state.iteration,
            success=success,
            new_evidence_ids=new_evidence_ids,
            error=error
        )

    def run(self, issue: str) -> DiagnosticState:
        """Run the diagnostic agent loop."""
        state = DiagnosticState(issue=issue)

        while not self.planner.evaluate_state(state):
            if state.stop_reason:
                break

            logger.info("Agent Iteration %d starting...", state.iteration)
            tool_name, tool_args = self.reasoner.decide_next_step(state)
            logger.info("Reasoner selected tool: %s", tool_name)

            if tool_name == "stop_diagnosis":
                state.stop_reason = tool_args.get("reason", "Agent decided to stop.")
                break

            invocation = self._execute_tool(tool_name, tool_args, state)
            state.tool_history.append(invocation)

            if invocation.success and invocation.new_evidence_ids:
                self.judge.judge(state, invocation.new_evidence_ids)

            state.iteration += 1

        return state
