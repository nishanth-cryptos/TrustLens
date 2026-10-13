"""Direct in-process imports; no duplicated engine or HTTP decision endpoint."""
from knowledge.runtime.engine import ENGINE_VERSION
from knowledge.runtime.result import evaluate_detection_from_governed

__all__ = ["ENGINE_VERSION", "evaluate_detection_from_governed"]
