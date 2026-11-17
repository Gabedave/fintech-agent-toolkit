"""Independent observed-action scoring. No model response is execution evidence."""
from .evaluator import load_cases, score, sensitivity

__all__ = ['load_cases', 'score', 'sensitivity']
