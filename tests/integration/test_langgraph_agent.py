"""Integration tests for the LangGraph-based DiagnosticAgent."""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock
import pytest
from repomind.agent.diagnostic_agent import DiagnosticAgent
from repomind.models.diagnostic import DiagnosticState


@pytest.fixture
def mock_litellm():
    """Mock litellm.completion to simulate node LLM interactions."""
    with patch("litellm.completion") as mock_comp:
        yield mock_comp


def test_langgraph_agent_full_loop(mock_litellm, tmp_path):
    # Initialize the DiagnosticAgent using the temp index path
    agent = DiagnosticAgent(index_dir=str(tmp_path))

    # Setup mock completions:
    # 1. Planner node -> Plan list JSON
    planner_response = MagicMock()
    planner_response.choices = [MagicMock()]
    planner_response.choices[0].message.content = json.dumps({
        "plan": ["1. Search for auth errors", "2. Verify users table exists"]
    })

    # 2. Executor node -> Tool call to search_code
    executor_response = MagicMock()
    executor_response.choices = [MagicMock()]
    msg_exec = MagicMock()
    tool_call = MagicMock()
    tool_call.function.name = "search_code"
    tool_call.function.arguments = json.dumps({"query": "auth errors"})
    msg_exec.tool_calls = [tool_call]
    msg_exec.content = ""
    executor_response.choices[0].message = msg_exec

    # 3. Verifier node -> Tool call to execute sandbox verification script
    verifier_response = MagicMock()
    verifier_response.choices = [MagicMock()]
    msg_ver = MagicMock()
    tool_call_ver = MagicMock()
    tool_call_ver.function.name = "execute_verification_script"
    tool_call_ver.function.arguments = json.dumps({
        "script": "print('testing sandbox output')"
    })
    msg_ver.tool_calls = [tool_call_ver]
    msg_ver.content = ""
    verifier_response.choices[0].message = msg_ver

    # 4. Judge node -> High confidence hypothesis JSON (forces stopping)
    judge_response = MagicMock()
    judge_response.choices = [MagicMock()]
    judge_response.choices[0].message.content = json.dumps({
        "hypotheses": [
            {
                "hypothesis_id": "hyp_0",
                "description": "sqlite3 table users does not exist in app/db.py",
                "confidence": 0.9,
                "supporting_evidence_ids": [],
                "conflicting_evidence_ids": []
            }
        ]
    })

    # Configure side_effect sequence for litellm.completion
    # Iteration 0: planner_node, executor_node, verifier_node, judge_node
    # Since confidence is 0.9, the graph stops after iteration 0 judge_node runs!
    mock_litellm.side_effect = [
        planner_response,  # planner_node
        executor_response, # executor_node
        verifier_response, # verifier_node
        judge_response,    # judge_node
    ]

    # Run agent
    final_state = agent.run("Auth table missing error")

    # Assert correct execution path & final state assertions
    assert final_state.issue == "Auth table missing error"
    assert "1. Search for auth errors" in final_state.plan
    assert len(final_state.tool_history) >= 2
    assert final_state.tool_history[0].tool_name == "search_code"
    assert final_state.tool_history[1].tool_name == "execute_verification_script"
    assert len(final_state.hypotheses) == 1
    assert final_state.hypotheses[0].confidence == 0.9
    assert "High confidence hypothesis found" in final_state.stop_reason
