"""Reasoner module to decide the next action in diagnostic loop."""

import json
import logging
from typing import Any
import litellm

from repomind.agent.prompts import REASONER_SYSTEM_PROMPT
from repomind.models.diagnostic import DiagnosticState
from repomind.utils.config import load_config

logger = logging.getLogger(__name__)

class Reasoner:
    """Decides the next tool to call."""

    def __init__(self, model: str | None = None):
        config = load_config()
        self.model = model or config.llm.model or "claude-sonnet-4-6"
        self.api_key = config.llm.api_key
        self.base_url = config.llm.base_url
        
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_code",
                    "description": "Perform code-aware hybrid search for a query.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"}
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "expand_call_chain",
                    "description": "Traverse the static call graph topology starting from a qualified code symbol (BFS).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "qualified_name": {"type": "string"}
                        },
                        "required": ["qualified_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "stop_diagnosis",
                    "description": "Call this when confident in the root cause.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reason": {"type": "string"}
                        },
                        "required": ["reason"]
                    }
                }
            }
        ]

    def decide_next_step(self, state: DiagnosticState) -> tuple[str, dict[str, Any]]:
        """Return the (tool_name, arguments) to execute next."""
        evidences_str = json.dumps([e.model_dump() for e in state.evidences], indent=2)
        hypotheses_str = json.dumps([h.model_dump() for h in state.hypotheses], indent=2)
        history_str = json.dumps([t.model_dump() for t in state.tool_history], indent=2)

        prompt = REASONER_SYSTEM_PROMPT.format(
            issue=state.issue,
            hypotheses=hypotheses_str,
            evidences=evidences_str,
            tool_history=history_str
        )

        litellm_args = {}
        if self.api_key:
            litellm_args["api_key"] = self.api_key
        if self.base_url:
            litellm_args["base_url"] = self.base_url

        try:
            response = litellm.completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                tools=self.tools,
                tool_choice="auto",
                timeout=30,
                **litellm_args
            )
            
            message = response.choices[0].message
            if getattr(message, "tool_calls", None):
                tool_call = message.tool_calls[0]
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                return name, args
            else:
                # Fallback if no tool was chosen
                content = message.content or ""
                return "stop_diagnosis", {"reason": "Model returned text instead of a tool call."}
        except Exception as e:
            logger.warning("Reasoner failed: %s", e)
            return "stop_diagnosis", {"reason": f"Reasoner error: {e}"}
