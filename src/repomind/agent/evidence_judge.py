"""Evidence Judge module for updating hypotheses based on evidence."""

import json
import logging
from typing import Any
import litellm

from repomind.agent.prompts import JUDGE_SYSTEM_PROMPT
from repomind.models.diagnostic import DiagnosticState, DiagnosticHypothesis
from repomind.utils.config import load_config

logger = logging.getLogger(__name__)

class EvidenceJudge:
    """Updates hypotheses based on newly gathered evidence."""

    def __init__(self, model: str | None = None):
        config = load_config()
        self.model = model or config.llm.model or "claude-sonnet-4-6"
        self.api_key = config.llm.api_key
        self.base_url = config.llm.base_url

    def judge(self, state: DiagnosticState, new_evidence_ids: list[str]) -> None:
        """Evaluate new evidence and update state hypotheses."""
        if not new_evidence_ids:
            return

        # Fetch the new evidence objects
        new_evidence_objs = [e for e in state.evidences if e.evidence_id in new_evidence_ids]
        if not new_evidence_objs:
            return

        evidence_str = json.dumps([e.model_dump() for e in new_evidence_objs], indent=2)
        hypotheses_str = json.dumps([h.model_dump() for h in state.hypotheses], indent=2)

        prompt = JUDGE_SYSTEM_PROMPT.format(
            issue=state.issue,
            hypotheses=hypotheses_str,
            new_evidence=evidence_str
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
                timeout=30,
                response_format={"type": "json_object"}, # If supported, or just prompt engineering
                **litellm_args
            )
            content = response.choices[0].message.content
            # Try to parse the JSON
            # litellm might return markdown formatted json like ```json ... ```
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            
            parsed = json.loads(content)
            # Handle if it's wrapped in an object
            if isinstance(parsed, dict) and "hypotheses" in parsed:
                parsed = parsed["hypotheses"]
            elif isinstance(parsed, dict):
                # Try first list value
                for v in parsed.values():
                    if isinstance(v, list):
                        parsed = v
                        break

            if isinstance(parsed, list):
                new_hypotheses = []
                for i, h in enumerate(parsed):
                    new_hypotheses.append(
                        DiagnosticHypothesis(
                            hypothesis_id=h.get("hypothesis_id", f"hyp_{len(state.hypotheses) + i}"),
                            description=h.get("description", "Unknown"),
                            confidence=float(h.get("confidence", 0.0)),
                            supporting_evidence_ids=h.get("supporting_evidence_ids", []),
                            conflicting_evidence_ids=h.get("conflicting_evidence_ids", [])
                        )
                    )
                # Overwrite state hypotheses
                state.hypotheses = new_hypotheses
                # Ensure referenced IDs exist
                state.validate_evidence_references()
        except Exception as e:
            logger.warning("EvidenceJudge failed: %s", e)
            # If parsing fails, just leave state as is
