"""الطبقة 1: كشف الأنماط (Heuristic Detection).

أسرع طبقة وأرخصها. تطابق نص المدخل مع قاعدة أنماط هجوم معروفة
(regex + أوزان) وتحسب درجة خطورة مجمّعة.

التصميم:
    - كل نمط له وزن يعكس قوة دلالته على هجوم.
    - الدرجة النهائية تُجمّع بصيغة احتمالية ناعمة بحيث لا تتجاوز 1.0،
      وتطابق عدة أنماط يرفع الثقة دون أن يكسر السقف.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from ..result import Decision, LayerResult
from .base import BaseLayer

# مسار ملف الأنماط الافتراضي (داخل الحزمة)
_DEFAULT_PATTERNS = Path(__file__).parent.parent / "patterns" / "attacks.yaml"


@dataclass
class _CompiledPattern:
    """نمط مُجمّع جاهز للمطابقة السريعة."""

    id: str
    category: str
    weight: float
    regex: re.Pattern
    description: str


class HeuristicLayer(BaseLayer):
    """طبقة كشف الأنماط الخبيثة.

    Args:
        sensitivity: مُعامل حساسية (0-1). الأعلى يرفع درجات الخطورة
            ويجعل الطبقة أكثر صرامة. الافتراضي 1.0 (بلا تعديل).
        warn_threshold: عتبة تحويل القرار إلى WARN.
        block_threshold: عتبة تحويل القرار إلى BLOCK.
        patterns_path: مسار بديل لملف الأنماط (للتخصيص/التجارب).
    """

    name = "heuristic"

    def __init__(
        self,
        sensitivity: float = 1.0,
        warn_threshold: float = 0.4,
        block_threshold: float = 0.7,
        patterns_path: str | Path | None = None,
    ) -> None:
        self.sensitivity = max(0.0, min(1.0, sensitivity))
        self.warn_threshold = warn_threshold
        self.block_threshold = block_threshold
        self._patterns = self._load_patterns(patterns_path or _DEFAULT_PATTERNS)

    @staticmethod
    def _load_patterns(path: str | Path) -> list[_CompiledPattern]:
        """يحمّل ويجمّع الأنماط من ملف YAML."""
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        compiled: list[_CompiledPattern] = []
        for entry in data.get("patterns", []):
            try:
                regex = re.compile(entry["pattern"])
            except re.error as exc:  # نمط معطوب لا يُسقط الأداة كلها
                raise ValueError(
                    f"نمط غير صالح id={entry.get('id')}: {exc}"
                ) from exc
            compiled.append(
                _CompiledPattern(
                    id=entry["id"],
                    category=entry.get("category", "unknown"),
                    weight=float(entry.get("weight", 0.5)),
                    regex=regex,
                    description=entry.get("description", ""),
                )
            )
        return compiled

    def inspect(self, text: str) -> LayerResult:
        """يفحص النص ويُرجع نتيجة الطبقة."""
        matched_ids: list[str] = []
        matched_reasons: list[str] = []
        weights: list[float] = []

        for pat in self._patterns:
            if pat.regex.search(text):
                matched_ids.append(pat.id)
                matched_reasons.append(pat.description or pat.id)
                weights.append(pat.weight * self.sensitivity)

        score = self._combine(weights)
        decision = self._decide(score)

        if matched_reasons:
            reason = "تطابقت أنماط: " + "؛ ".join(matched_reasons)
        else:
            reason = "لم تتطابق أي أنماط معروفة"

        return LayerResult(
            layer_name=self.name,
            risk_score=score,
            decision=decision,
            reason=reason,
            matched=matched_ids,
        )

    @staticmethod
    def _combine(weights: list[float]) -> float:
        """يجمّع أوزان الأنماط المتطابقة في درجة واحدة ضمن [0, 1].

        نستخدم الجمع الاحتمالي الناعم (noisy-OR):
            score = 1 - ∏(1 - wᵢ)
        فكل نمط إضافي يرفع الثقة دون تجاوز 1.0.
        """
        product = 1.0
        for w in weights:
            product *= (1.0 - max(0.0, min(1.0, w)))
        return 1.0 - product

    def _decide(self, score: float) -> Decision:
        if score >= self.block_threshold:
            return Decision.BLOCK
        if score >= self.warn_threshold:
            return Decision.WARN
        return Decision.ALLOW
