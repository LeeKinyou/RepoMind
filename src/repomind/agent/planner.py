"""Planner module for evaluating stopping conditions."""

from repomind.models.diagnostic import DiagnosticState

class Planner:
    """Manages diagnostic loop iterations and stopping conditions."""

    def __init__(self, max_iterations: int = 5, confidence_threshold: float = 0.8):
        self.max_iterations = max_iterations
        self.confidence_threshold = confidence_threshold

    def evaluate_state(self, state: DiagnosticState) -> bool:
        """
        Check if diagnosis should stop.
        Sets state.stop_reason and returns True if should stop.
        """
        if state.iteration >= self.max_iterations:
            state.stop_reason = f"Reached maximum iterations ({self.max_iterations})."
            return True

        if state.hypotheses:
            best_hyp = max(state.hypotheses, key=lambda h: h.confidence)
            if best_hyp.confidence >= self.confidence_threshold:
                state.stop_reason = f"High confidence hypothesis found: {best_hyp.confidence}"
                return True

        return False
