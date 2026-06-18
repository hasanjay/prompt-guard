"""الطبقة 4: مراقبة المخرجات (Output Monitoring).

تفحص **رد النموذج** (لا مدخل المستخدم) بحثاً عن آثار هجوم ناجح:
    - تسريب تعليمات النظام (system prompt leakage).
    - تسريب بيانات حساسة (مفاتيح، كلمات مرور، توكنات).
    - علامات الامتثال لهجوم تجاوز (jailbreak compliance).

عند الكشف، تستطيع تنقيح (redact) المخرج قبل وصوله للمستخدم بدل
تسريبه. هذه الطبقة هي شبكة الأمان الأخيرة في الإطار.
"""

from __future__ import annotations

import re

from ..result import Decision, LayerResult
from .base import BaseLayer

# مؤشرات تسريب تعليمات النظام في الرد
_LEAK_INDICATORS = [
    r"(?i)(my |the )?(system )?(prompt|instructions?) (is|are|states?)",
    r"(?i)i (was|am) (instructed|told|configured|programmed) to",
    r"(?i)my (initial|original|core) (instructions?|guidelines?|rules?)",
    r"(?i)you are a helpful assistant",  # بداية شائعة لتعليمات النظام
    r"(أنا|تمّت) (مبرمج|برمجتي|توجيهي) (على|لـ)",
    r"(تعليماتي|توجيهاتي) (الأصلية|الأساسية)",
]

# أنماط بيانات حساسة قد تتسرّب في الرد
_SECRET_PATTERNS = [
    (r"(?i)(api[_\s-]?key|secret[_\s-]?key|access[_\s-]?token)\s*[:=]\s*\S+", "مفتاح/توكن"),
    (r"sk-[A-Za-z0-9]{16,}", "مفتاح بصيغة OpenAI"),
    (r"(?i)password\s*[:=]\s*\S+", "كلمة مرور"),
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "بريد إلكتروني"),
    (r"\b(?:\d[ -]?){13,16}\b", "رقم بطاقة محتمل"),
]

# علامات الامتثال لهجوم تجاوز
_JAILBREAK_COMPLIANCE = [
    r"(?i)(sure|okay|alright|of course),? (here|i('| )?ll|as you).{0,20}(no restrictions|developer mode|dan)",
    r"(?i)as an? (unrestricted|unfiltered|jailbroken) (ai|assistant|model)",
    r"(?i)i (will|can) now ignore (my|the|all) (rules|guidelines|restrictions)",
]


class OutputLayer(BaseLayer):
    """طبقة مراقبة مخرجات النموذج.

    Args:
        block_threshold: عتبة الحجب.
        redact: إن True، يُنقّح المخرج (يستبدل الحساس بـ [REDACTED])
            بدل حجبه كلياً.
    """

    name = "output"

    def __init__(self, block_threshold: float = 0.6, redact: bool = True) -> None:
        self.block_threshold = block_threshold
        self.redact = redact
        self._leak = [re.compile(p) for p in _LEAK_INDICATORS]
        self._secrets = [(re.compile(p), label) for p, label in _SECRET_PATTERNS]
        self._jailbreak = [re.compile(p) for p in _JAILBREAK_COMPLIANCE]

    def inspect(self, text: str) -> LayerResult:
        """يفحص مخرج النموذج. (الواجهة الموحّدة)

        للاستخدام الكامل مع التنقيح استعمل ``inspect_output`` التي تُعيد
        أيضاً النص المُنقّح.
        """
        result, _ = self.inspect_output(text)
        return result

    def inspect_output(self, text: str) -> tuple[LayerResult, str]:
        """يفحص المخرج ويُرجع (النتيجة، النص المُنقّح).

        Returns:
            (LayerResult, redacted_text)
        """
        weights: list[float] = []
        reasons: list[str] = []
        redacted = text

        # 1) تسريب تعليمات النظام
        for pat in self._leak:
            if pat.search(text):
                weights.append(0.7)
                reasons.append("احتمال تسريب تعليمات النظام")
                break

        # 2) تسريب بيانات حساسة (مع تنقيح)
        for pat, label in self._secrets:
            if pat.search(redacted):
                weights.append(0.9)
                reasons.append(f"تسريب بيانات حساسة: {label}")
                if self.redact:
                    redacted = pat.sub("[محجوب]", redacted)

        # 3) امتثال لهجوم تجاوز
        for pat in self._jailbreak:
            if pat.search(text):
                weights.append(0.85)
                reasons.append("علامات امتثال لهجوم تجاوز")
                break

        score = self._combine(weights)
        decision = self._decide(score)
        reason = "؛ ".join(dict.fromkeys(reasons)) if reasons else "المخرج يبدو سليماً"

        return (
            LayerResult(
                layer_name=self.name,
                risk_score=score,
                decision=decision,
                reason=reason,
                matched=list(dict.fromkeys(reasons)),
            ),
            redacted,
        )

    @staticmethod
    def _combine(weights: list[float]) -> float:
        product = 1.0
        for w in weights:
            product *= (1.0 - max(0.0, min(1.0, w)))
        return 1.0 - product

    def _decide(self, score: float) -> Decision:
        if score >= self.block_threshold:
            return Decision.BLOCK
        if score >= self.block_threshold / 2:
            return Decision.WARN
        return Decision.ALLOW
