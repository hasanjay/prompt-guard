"""هياكل البيانات لنتائج الفحص.

تُرجع كل طبقة دفاعية ``LayerResult``، ويجمع خط الأنابيب النتائج في
``GuardResult`` نهائي يقرأه المستخدم.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Decision(str, Enum):
    """القرار الناتج عن فحص طبقة أو خط الأنابيب كاملاً."""

    ALLOW = "allow"      # آمن، مرّره
    WARN = "warn"        # مشبوه، مرّره مع تنبيه
    BLOCK = "block"      # خطير، احجبه

    def __str__(self) -> str:  # عرض ودّي
        return self.value


@dataclass
class LayerResult:
    """نتيجة فحص طبقة واحدة.

    Attributes:
        layer_name: اسم الطبقة التي أنتجت النتيجة.
        risk_score: درجة الخطورة بين 0.0 (آمن) و 1.0 (هجوم مؤكد).
        decision: قرار هذه الطبقة.
        reason: شرح موجز يفهمه الإنسان لسبب القرار.
        matched: قائمة بالأنماط/الإشارات التي تطابقت (للتفسير والتصحيح).
    """

    layer_name: str
    risk_score: float
    decision: Decision
    reason: str = ""
    matched: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # حصر درجة الخطورة ضمن النطاق المسموح
        self.risk_score = max(0.0, min(1.0, float(self.risk_score)))


@dataclass
class GuardResult:
    """النتيجة النهائية المجمّعة من كل الطبقات.

    Attributes:
        risk_score: أعلى درجة خطورة عبر كل الطبقات.
        decision: القرار النهائي المجمّع.
        sanitized_input: المدخل بعد التعقيم (إن وُجد)، وإلا المدخل الأصلي.
        reason: ملخص سبب القرار النهائي.
        layer_results: نتائج كل طبقة على حدة (للباحثين والتصحيح).
    """

    risk_score: float
    decision: Decision
    sanitized_input: str
    reason: str = ""
    layer_results: list[LayerResult] = field(default_factory=list)

    @property
    def is_safe(self) -> bool:
        """True إذا لم يُحجب الطلب (سماح أو تحذير فقط)."""
        return self.decision != Decision.BLOCK

    @property
    def is_blocked(self) -> bool:
        return self.decision == Decision.BLOCK

    @property
    def layer_scores(self) -> dict[str, float]:
        """قاموس {اسم الطبقة: درجة الخطورة} لسهولة القياس."""
        return {lr.layer_name: lr.risk_score for lr in self.layer_results}

    def explanation(self) -> str:
        """شرح متعدد الأسطر لقرار كل طبقة — مفيد للتصحيح والأبحاث."""
        lines = [f"القرار النهائي: {self.decision} (الخطورة: {self.risk_score:.2f})"]
        for lr in self.layer_results:
            line = f"  - {lr.layer_name}: {lr.decision} ({lr.risk_score:.2f})"
            if lr.reason:
                line += f" — {lr.reason}"
            lines.append(line)
        return "\n".join(lines)
