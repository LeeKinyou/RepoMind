"""Unit tests for DiagnosticAgent LangGraph nodes and transitions."""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock
import pytest
from repomind.agent.state_graph import (
    planner_node,
    executor_node,
    verifier_node,
    judge_node,
    check_stopping_condition,
    AgentState,
)
from repomind.models.diagnostic import DiagnosticHypothesis, ToolInvocation


@patch("litellm.completion")
def test_planner_node(mock_comp):
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = json.dumps({
        "plan": ["1. Search database errors", "2. Check query_service.py"]
    })
    mock_comp.return_value = mock_resp

    state: AgentState = {
        "issue": "Database table missing",
        "plan": [],
        "current_plan_step": 0,
        "evidences": [],
        "hypotheses": [],
        "tool_history": [],
        "iteration": 0,
        "stop_reason": None,
        "verification_results": [],
        "index_dir": "",
    }

    res = planner_node(state)
    assert "plan" in res
    assert len(res["plan"]) == 2
    assert "1. Search database errors" in res["plan"]


@patch("litellm.completion")
def test_planner_node_resets_step_on_plan_change(mock_comp):
    # LLM returns a new plan
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = json.dumps({
        "plan": ["New Plan Step 1"]
    })
    mock_comp.return_value = mock_resp

    state: AgentState = {
        "issue": "Database table missing",
        "plan": ["Old Plan Step 1"],
        "current_plan_step": 2,
        "evidences": [],
        "hypotheses": [],
        "tool_history": [],
        "iteration": 1,
        "stop_reason": None,
        "verification_results": [],
        "index_dir": "",
    }

    res = planner_node(state)
    assert res.get("plan") == ["New Plan Step 1"]
    assert res.get("current_plan_step") == 0


@patch("litellm.completion")
def test_planner_node_keeps_step_on_same_plan(mock_comp):
    # LLM returns the same plan
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = json.dumps({
        "plan": ["Old Plan Step 1"]
    })
    mock_comp.return_value = mock_resp

    state: AgentState = {
        "issue": "Database table missing",
        "plan": ["Old Plan Step 1"],
        "current_plan_step": 2,
        "evidences": [],
        "hypotheses": [],
        "tool_history": [],
        "iteration": 1,
        "stop_reason": None,
        "verification_results": [],
        "index_dir": "",
    }

    res = planner_node(state)
    assert res.get("plan") == ["Old Plan Step 1"]
    assert "current_plan_step" not in res


def test_check_stopping_condition_continue():
    state: AgentState = {
        "issue": "Auth error",
        "plan": [],
        "current_plan_step": 0,
        "evidences": [],
        "hypotheses": [
            DiagnosticHypothesis(
                hypothesis_id="hyp_0",
                description="Maybe typo",
                confidence=0.5,
                supporting_evidence_ids=[],
                conflicting_evidence_ids=[],
            )
        ],
        "tool_history": [],
        "iteration": 1,
        "stop_reason": None,
        "verification_results": [],
        "index_dir": "",
    }
    assert check_stopping_condition(state) == "continue"


def test_check_stopping_condition_stop_confidence():
    state: AgentState = {
        "issue": "Auth error",
        "plan": [],
        "current_plan_step": 0,
        "evidences": [],
        "hypotheses": [
            DiagnosticHypothesis(
                hypothesis_id="hyp_0",
                description="Suspect table",
                confidence=0.85,
                supporting_evidence_ids=[],
                conflicting_evidence_ids=[],
            )
        ],
        "tool_history": [],
        "iteration": 1,
        "stop_reason": None,
        "verification_results": [],
        "index_dir": "",
    }
    assert check_stopping_condition(state) == "stop"


def test_check_stopping_condition_stop_max_iterations():
    state: AgentState = {
        "issue": "Auth error",
        "plan": [],
        "current_plan_step": 0,
        "evidences": [],
        "hypotheses": [],
        "tool_history": [],
        "iteration": 5,
        "stop_reason": None,
        "verification_results": [],
        "index_dir": "",
    }
    assert check_stopping_condition(state) == "stop"
