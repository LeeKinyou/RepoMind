"""Tests for DiagnosticAgent loop."""

import pytest
from repomind.agent.diagnostic_agent import DiagnosticAgent
from repomind.agent.reasoner import Reasoner
from repomind.agent.evidence_judge import EvidenceJudge
from repomind.models.diagnostic import DiagnosticState, DiagnosticHypothesis

class MockReasoner(Reasoner):
    def __init__(self, actions):
        self.actions = actions
        self.call_count = 0

    def decide_next_step(self, state):
        if self.call_count < len(self.actions):
            action = self.actions[self.call_count]
            self.call_count += 1
            return action
        return "stop_diagnosis", {"reason": "Mock end of actions"}


class MockJudge(EvidenceJudge):
    def judge(self, state, new_evidence_ids):
        # Update hypothesis based on call iteration
        if state.iteration == 0:
            state.hypotheses.append(
                DiagnosticHypothesis(
                    hypothesis_id="hyp_0",
                    description="It's a bug in module A",
                    confidence=0.5,
                    supporting_evidence_ids=new_evidence_ids,
                    conflicting_evidence_ids=[]
                )
            )
        elif state.iteration == 1:
            state.hypotheses[0].confidence = 0.9

def test_diagnostic_agent_trajectory(tmp_path):
    agent = DiagnosticAgent(index_dir=str(tmp_path))
    
    # Mock Reasoner actions
    actions = [
        ("search_code", {"query": "module A error"}),
        ("expand_call_chain", {"qualified_name": "module.A.bug"}),
        ("stop_diagnosis", {"reason": "Found it"})
    ]
    agent.reasoner = MockReasoner(actions)
    agent.judge = MockJudge()
    
    state = agent.run("Error in module A")
    
    assert state.iteration <= 3
    assert state.stop_reason is not None
    assert len(state.tool_history) >= 2
    
    assert state.tool_history[0].tool_name == "search_code"
    assert state.tool_history[1].tool_name == "expand_call_chain"
    
    # Depending on whether the mock judge updated confidence >= 0.8
    # The planner might stop it early.
    # At iteration 0 -> confidence 0.5 -> continues
    # At iteration 1 -> confidence 0.9 -> planner should stop it before Reasoner gets to step 3?
    # Wait, the Planner checks BEFORE iteration loop body.
    # After iteration 1 completes, state.iteration becomes 2, loop checks planner, confidence is 0.9 -> stops!
    # So iteration 2 (stop_diagnosis) might not even be executed. Let's see.
    
    assert "High confidence hypothesis found" in state.stop_reason or state.stop_reason == "Found it"

def test_diagnostic_agent_max_iterations(tmp_path):
    agent = DiagnosticAgent(index_dir=str(tmp_path))
    
    # Just loop search code
    actions = [("search_code", {"query": "loop"})] * 10
    agent.reasoner = MockReasoner(actions)
    
    class NullJudge(EvidenceJudge):
        def judge(self, state, new_evidence_ids):
            pass # Never update confidence
            
    agent.judge = NullJudge()
    
    state = agent.run("Loop forever")
    
    assert state.iteration == 5
    assert "Reached maximum iterations" in state.stop_reason
