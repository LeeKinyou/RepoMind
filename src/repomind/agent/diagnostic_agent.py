"""Diagnostic Agent orchestrator using LangGraph workflow."""

import logging
from typing import Any

from repomind.models.diagnostic import DiagnosticState
from repomind.agent.state_graph import create_agent_graph

logger = logging.getLogger(__name__)


class DiagnosticAgent:
    """Bounded, state-machine based agent for diagnosis powered by LangGraph."""

    def __init__(self, index_dir: str):
        self.index_dir = index_dir
        self.graph = create_agent_graph()

    def run(self, issue: str) -> DiagnosticState:
        """Run the diagnostic agent LangGraph workflow."""
        initial_state = {
            "issue": issue,
            "plan": [],
            "current_plan_step": 0,
            "evidences": [],
            "hypotheses": [],
            "tool_history": [],
            "iteration": 0,
            "stop_reason": None,
            "verification_results": [],
            "index_dir": self.index_dir,
        }

        logger.info("Starting Diagnostic Agent LangGraph workflow...")
        final_state = self.graph.invoke(initial_state)

        # Determine stop reason
        stop_reason = final_state.get("stop_reason")
        if not stop_reason:
            if final_state["iteration"] >= 5:
                stop_reason = f"Reached maximum iterations ({final_state['iteration']})."
            elif final_state["hypotheses"]:
                best_hyp = max(final_state["hypotheses"], key=lambda h: h.confidence)
                if best_hyp.confidence >= 0.8:
                    stop_reason = f"High confidence hypothesis found: {best_hyp.confidence}"
            else:
                stop_reason = "Agent decided to stop."

        return DiagnosticState(
            issue=final_state["issue"],
            iteration=final_state["iteration"],
            hypotheses=final_state["hypotheses"],
            evidences=final_state["evidences"],
            tool_history=final_state["tool_history"],
            stop_reason=stop_reason,
            plan=final_state["plan"],
            current_plan_step=final_state["current_plan_step"],
            verification_results=final_state["verification_results"],
        )
