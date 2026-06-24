"""LangGraph-based state graph definition for DiagnosticAgent orchestration."""

from __future__ import annotations

import json
import logging
from typing import TypedDict, List, Optional, Callable, Any

import litellm
from langgraph.graph import StateGraph, END

from repomind.models.diagnostic import DiagnosticHypothesis, ToolInvocation
from repomind.models.evidence import Evidence
from repomind.retriever.query_service import QueryService
from repomind.agent.prompts import (
    PLANNER_SYSTEM_PROMPT,
    EXECUTOR_SYSTEM_PROMPT,
    VERIFIER_SYSTEM_PROMPT,
    JUDGE_SYSTEM_PROMPT,
)
from repomind.utils.config import load_config
from repomind.sandbox.executor import SandboxExecutor

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    issue: str
    plan: list[str]
    current_plan_step: int
    evidences: list[Evidence]
    hypotheses: list[DiagnosticHypothesis]
    tool_history: list[ToolInvocation]
    iteration: int
    stop_reason: Optional[str]
    verification_results: list[dict]
    index_dir: str


def planner_node(state: AgentState) -> dict:
    """Refines and updates the diagnostic plan based on current state."""
    config = load_config()
    model = config.llm.model or "claude-sonnet-4-6"
    api_key = config.llm.api_key
    base_url = config.llm.base_url

    hypotheses_str = json.dumps([h.model_dump() for h in state["hypotheses"]], indent=2)
    evidences_str = json.dumps([e.model_dump() for e in state["evidences"]], indent=2)
    history_str = json.dumps([t.model_dump() for t in state["tool_history"]], indent=2)

    prompt = PLANNER_SYSTEM_PROMPT.format(
        issue=state["issue"],
        hypotheses=hypotheses_str,
        evidences=evidences_str,
        tool_history=history_str,
    )

    litellm_args = {}
    if api_key:
        litellm_args["api_key"] = api_key
    if base_url:
        litellm_args["base_url"] = base_url

    try:
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            timeout=30,
            **litellm_args,
        )
        content = response.choices[0].message.content or ""
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]

        parsed = json.loads(content)
        new_plan = parsed.get("plan", state["plan"])
        if new_plan != state["plan"]:
            return {"plan": new_plan, "current_plan_step": 0}
        return {"plan": new_plan}
    except Exception as e:
        logger.warning("Planner node failed: %s", e)
        if not state["plan"]:
            return {"plan": ["1. Search code for relevant symbols"], "current_plan_step": 0}
        return {}


def executor_node(state: AgentState) -> dict:
    """Selects and runs code retrieval tools based on the current plan step."""
    config = load_config()
    model = config.llm.model or "claude-sonnet-4-6"
    api_key = config.llm.api_key
    base_url = config.llm.base_url

    query_svc = QueryService(index_dir=state["index_dir"])

    evidences_str = json.dumps([e.model_dump() for e in state["evidences"]], indent=2)
    history_str = json.dumps([t.model_dump() for t in state["tool_history"]], indent=2)
    plan_str = json.dumps(state["plan"], indent=2)

    prompt = EXECUTOR_SYSTEM_PROMPT.format(
        issue=state["issue"],
        plan=plan_str,
        current_plan_step=state["current_plan_step"],
        evidences=evidences_str,
        tool_history=history_str,
    )

    tools = [
        {
            "type": "function",
            "function": {
                "name": "search_code",
                "description": "Perform code-aware hybrid search for a query.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "expand_call_chain",
                "description": "Traverse the static call graph topology starting from a qualified code symbol (BFS).",
                "parameters": {
                    "type": "object",
                    "properties": {"qualified_name": {"type": "string"}},
                    "required": ["qualified_name"],
                },
            },
        },
    ]

    litellm_args = {}
    if api_key:
        litellm_args["api_key"] = api_key
    if base_url:
        litellm_args["base_url"] = base_url

    try:
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            tools=tools,
            tool_choice="auto",
            timeout=30,
            **litellm_args,
        )

        message = response.choices[0].message
        if getattr(message, "tool_calls", None):
            tool_call = message.tool_calls[0]
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)

            success = False
            error = None
            new_evidence_ids = []

            new_evs = list(state["evidences"])
            if tool_name == "search_code":
                query = tool_args.get("query", "")
                res = query_svc.search(query, options=None)

                for sym in res.symbols:
                    ev_id = f"search_{sym.qualified_name}"
                    new_ev = Evidence(
                        evidence_id=ev_id,
                        source="search",
                        file_path=sym.file_path,
                        symbol=sym.qualified_name,
                        start_line=sym.start_line,
                        end_line=sym.end_line,
                        snippet=sym.snippet or sym.docstring or "No snippet",
                        relevance_score=0.8,
                        reason=f"Found via search: {query}",
                    )
                    if not any(e.evidence_id == ev_id for e in new_evs):
                        new_evs.append(new_ev)
                    new_evidence_ids.append(ev_id)
                success = True

            elif tool_name == "expand_call_chain":
                qname = tool_args.get("qualified_name", "")
                graph_res = query_svc.get_call_graph(qname, depth=1)

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
                        reason=f"Related to {qname} via call graph",
                    )
                    if not any(e.evidence_id == ev_id for e in new_evs):
                        new_evs.append(new_ev)
                    new_evidence_ids.append(ev_id)
                success = True

            invocation = ToolInvocation(
                tool_name=tool_name,
                arguments=tool_args,
                iteration=state["iteration"],
                success=success,
                new_evidence_ids=new_evidence_ids,
                error=error,
            )

            next_step = (
                state["current_plan_step"] + 1
                if state["current_plan_step"] < len(state["plan"])
                else state["current_plan_step"]
            )

            return {
                "evidences": new_evs,
                "tool_history": state["tool_history"] + [invocation],
                "current_plan_step": next_step,
            }
    except Exception as e:
        logger.warning("Executor node failed: %s", e)

    return {}


def verifier_node(state: AgentState) -> dict:
    """Generates and runs python verification scripts in sandbox context."""
    config = load_config()
    model = config.llm.model or "claude-sonnet-4-6"
    api_key = config.llm.api_key
    base_url = config.llm.base_url

    evidences_str = json.dumps([e.model_dump() for e in state["evidences"]], indent=2)
    history_str = json.dumps([t.model_dump() for t in state["tool_history"]], indent=2)
    plan_str = json.dumps(state["plan"], indent=2)

    prompt = VERIFIER_SYSTEM_PROMPT.format(
        issue=state["issue"],
        plan=plan_str,
        evidences=evidences_str,
        tool_history=history_str,
    )

    tools = [
        {
            "type": "function",
            "function": {
                "name": "execute_verification_script",
                "description": "Run a Python script in a sandboxed executor to verify reproduction or dynamic state.",
                "parameters": {
                    "type": "object",
                    "properties": {"script": {"type": "string"}},
                    "required": ["script"],
                },
            },
        }
    ]

    litellm_args = {}
    if api_key:
        litellm_args["api_key"] = api_key
    if base_url:
        litellm_args["base_url"] = base_url

    try:
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            tools=tools,
            tool_choice="auto",
            timeout=30,
            **litellm_args,
        )

        message = response.choices[0].message
        if getattr(message, "tool_calls", None):
            tool_call = message.tool_calls[0]
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)

            if tool_name == "execute_verification_script":
                script_str = tool_args.get("script", "")

                sandbox_mode = config.sandbox.mode or "subprocess"
                executor = SandboxExecutor(
                    mode=sandbox_mode, timeout=config.sandbox.timeout or 60
                )
                res = executor.run_python_code(script_str)

                ver_res = {
                    "script": script_str,
                    "success": res.success,
                    "exit_code": res.exit_code,
                    "stdout": res.stdout,
                    "stderr": res.stderr,
                    "elapsed_seconds": res.elapsed_seconds,
                    "error_message": res.error_message,
                }

                new_evidence_ids = []
                new_evs = list(state["evidences"])
                ev_id = f"verification_run_{len(state['verification_results'])}"
                new_ev = Evidence(
                    evidence_id=ev_id,
                    source="trace",
                    file_path="sandbox",
                    symbol="verification_script",
                    start_line=1,
                    end_line=len(script_str.splitlines()),
                    snippet=f"--- SCRIPT ---\n{script_str}\n--- STDOUT ---\n{res.stdout}\n--- STDERR ---\n{res.stderr}",
                    relevance_score=0.9,
                    reason=f"Sandbox verification execution result (Exit code: {res.exit_code})",
                )
                new_evs.append(new_ev)
                new_evidence_ids.append(ev_id)

                invocation = ToolInvocation(
                    tool_name=tool_name,
                    arguments=tool_args,
                    iteration=state["iteration"],
                    success=res.success,
                    new_evidence_ids=new_evidence_ids,
                    error=res.error_message,
                )

                return {
                    "verification_results": state["verification_results"] + [ver_res],
                    "evidences": new_evs,
                    "tool_history": state["tool_history"] + [invocation],
                }
    except Exception as e:
        logger.warning("Verifier node failed: %s", e)

    return {}


def judge_node(state: AgentState) -> dict:
    """Updates candidate hypotheses using consolidated RAG and execution evidence."""
    config = load_config()
    model = config.llm.model or "claude-sonnet-4-6"
    api_key = config.llm.api_key
    base_url = config.llm.base_url

    new_evidence_ids = []
    if state["tool_history"]:
        new_evidence_ids = state["tool_history"][-1].new_evidence_ids
    new_evidence_objs = [
        e for e in state["evidences"] if e.evidence_id in new_evidence_ids
    ]

    if not new_evidence_objs:
        new_evidence_objs = state["evidences"]

    evidence_str = json.dumps([e.model_dump() for e in new_evidence_objs], indent=2)
    hypotheses_str = json.dumps([h.model_dump() for h in state["hypotheses"]], indent=2)

    prompt = JUDGE_SYSTEM_PROMPT.format(
        issue=state["issue"],
        hypotheses=hypotheses_str,
        new_evidence=evidence_str,
    )

    litellm_args = {}
    if api_key:
        litellm_args["api_key"] = api_key
    if base_url:
        litellm_args["base_url"] = base_url

    try:
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            timeout=30,
            **litellm_args,
        )
        content = response.choices[0].message.content or ""
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]

        parsed = json.loads(content)
        if isinstance(parsed, dict) and "hypotheses" in parsed:
            parsed = parsed["hypotheses"]

        if isinstance(parsed, list):
            new_hypotheses = []
            for i, h in enumerate(parsed):
                new_hypotheses.append(
                    DiagnosticHypothesis(
                        hypothesis_id=h.get(
                            "hypothesis_id", f"hyp_{len(state['hypotheses']) + i}"
                        ),
                        description=h.get("description", "Unknown"),
                        confidence=float(h.get("confidence", 0.0)),
                        supporting_evidence_ids=h.get("supporting_evidence_ids", []),
                        conflicting_evidence_ids=h.get("conflicting_evidence_ids", []),
                    )
                )
            return {
                "hypotheses": new_hypotheses,
                "iteration": state["iteration"] + 1,
            }
    except Exception as e:
        logger.warning("Judge node failed: %s", e)

    return {"iteration": state["iteration"] + 1}


def check_stopping_condition(state: AgentState) -> str:
    """Condition function checking for max iterations or confident hypothesis."""
    if state["iteration"] >= 5:
        return "stop"

    if state["hypotheses"]:
        best_hyp = max(state["hypotheses"], key=lambda h: h.confidence)
        if best_hyp.confidence >= 0.8:
            return "stop"

    return "continue"


def create_agent_graph() -> StateGraph:
    """Builds and compiles the state graph workflow."""
    workflow = StateGraph(AgentState)
    workflow.add_node("planner", planner_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("verifier", verifier_node)
    workflow.add_node("judge", judge_node)

    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "executor")
    workflow.add_edge("executor", "verifier")
    workflow.add_edge("verifier", "judge")

    workflow.add_conditional_edges(
        "judge",
        check_stopping_condition,
        {"continue": "planner", "stop": END},
    )

    return workflow.compile()
