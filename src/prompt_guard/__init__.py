"""prompt-guard — دفاع متعدد الطبقات ضد هجمات حقن الأوامر في النماذج اللغوية.

مبنية على إطار العمل البحثي:
    Hasan Jameel Azooz (2025), "Comprehensive, context-aware,
    multi-layered security framework for mitigating prompt injection
    attacks in large language models."
"""

from .pipeline import Guard
from .result import Decision, GuardResult, LayerResult
from .layers.heuristic import HeuristicLayer
from .layers.context import ContextLayer
from .layers.sanitizer import SanitizerLayer
from .layers.output import OutputLayer
from .layers.base import BaseLayer

__version__ = "0.4.0"

__all__ = [
    "Guard",
    "GuardResult",
    "LayerResult",
    "Decision",
    "HeuristicLayer",
    "ContextLayer",
    "SanitizerLayer",
    "OutputLayer",
    "BaseLayer",
]
