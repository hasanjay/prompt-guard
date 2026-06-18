"""منسّق خط الأنابيب: يشغّل الطبقات بالتسلسل ويجمّع النتائج.

الإطار رباعي الطبقات:
    1. Heuristic   — كشف الأنماط (input)
    2. Context     — تحليل سياقي (input)
    3. Sanitizer   — تعقيم علاجي (input، لا يحجب بل يحوّل)
    4. Output      — مراقبة مخرجات النموذج (output)

``check``        يشغّل طبقات المدخل (1-3) ويُرجع GuardResult مع المدخل المُعقّم.
``check_output`` يشغّل الطبقة 4 على رد النموذج ويُرجع GuardResult مع المخرج المُنقّح.
"""

from __future__ import annotations

from .layers.base import BaseLayer
from .layers.heuristic import HeuristicLayer
from .layers.context import ContextLayer
from .layers.sanitizer import SanitizerLayer
from .layers.output import OutputLayer
from .result import Decision, GuardResult, LayerResult


class Guard:
    """الواجهة الرئيسية للمكتبة."""

    def __init__(
        self,
        layers: list[BaseLayer] | None = None,
        sanitizer: SanitizerLayer | None = None,
        output_layer: OutputLayer | None = None,
        enable_sanitizer: bool = True,
        enable_output: bool = True,
        block_threshold: float = 0.55,
    ) -> None:
        self.layers: list[BaseLayer] = (
            layers
            if layers is not None
            else [HeuristicLayer(block_threshold=0.55), ContextLayer(block_threshold=0.55)]
        )
        # None + enable=True → طبقة افتراضية؛ enable=False → معطّلة فعلاً
        if sanitizer is not None:
            self.sanitizer = sanitizer
        else:
            self.sanitizer = SanitizerLayer() if enable_sanitizer else None
        if output_layer is not None:
            self.output_layer = output_layer
        else:
            self.output_layer = OutputLayer() if enable_output else None
        self.block_threshold = block_threshold

    def check(self, text: str, return_layer_scores: bool = False) -> GuardResult:
        """يفحص مدخل المستخدم عبر الطبقات الكاشفة ويُعقّمه."""
        if not isinstance(text, str):
            raise TypeError("يجب أن يكون المدخل نصاً (str)")

        layer_results = [layer.inspect(text) for layer in self.layers]
        max_score = max((lr.risk_score for lr in layer_results), default=0.0)
        decision = self._aggregate_decision(max_score, layer_results)

        sanitized = text
        if self.sanitizer is not None:
            sanitized, applied = self.sanitizer.sanitize(text)
            if applied:
                layer_results.append(
                    LayerResult(
                        layer_name="sanitizer",
                        risk_score=0.0,
                        decision=Decision.ALLOW,
                        reason="طُبّق تعقيم: " + "؛ ".join(applied),
                        matched=applied,
                    )
                )

        reasons = [
            lr.reason for lr in layer_results
            if lr.decision != Decision.ALLOW and lr.layer_name != "sanitizer"
        ]
        summary = "؛ ".join(reasons) if reasons else "لم تُكتشف مؤشرات هجوم"

        return GuardResult(
            risk_score=max_score,
            decision=decision,
            sanitized_input=sanitized,
            reason=summary,
            layer_results=layer_results,
        )

    def check_output(self, output: str, original_input: str | None = None) -> GuardResult:
        """يفحص رد النموذج عبر الطبقة الرابعة (مراقبة المخرجات)."""
        if not isinstance(output, str):
            raise TypeError("يجب أن يكون المخرج نصاً (str)")
        if self.output_layer is None:
            return GuardResult(
                risk_score=0.0,
                decision=Decision.ALLOW,
                sanitized_input=output,
                reason="طبقة مراقبة المخرجات معطّلة",
            )

        layer_result, redacted = self.output_layer.inspect_output(output)
        return GuardResult(
            risk_score=layer_result.risk_score,
            decision=layer_result.decision,
            sanitized_input=redacted,
            reason=layer_result.reason,
            layer_results=[layer_result],
        )

    def _aggregate_decision(self, max_score: float, layer_results: list) -> Decision:
        """يحدد القرار النهائي (سياسة fail-safe)."""
        if max_score >= self.block_threshold:
            return Decision.BLOCK
        if any(lr.decision == Decision.BLOCK for lr in layer_results):
            return Decision.BLOCK
        if any(lr.decision == Decision.WARN for lr in layer_results):
            return Decision.WARN
        return Decision.ALLOW
