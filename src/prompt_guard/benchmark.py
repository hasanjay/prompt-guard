"""محرّك قياس أداء prompt-guard.

يحسب المقاييس المعيارية المستخدمة في أبحاث أمن النماذج اللغوية
والتصنيف الثنائي، ويُخرجها بصيغة جاهزة للتقارير والأوراق العلمية.

المقاييس:
    - Sensitivity / Recall: نسبة الهجمات المكتشفة (TP / (TP+FN))
    - Specificity:          نسبة السليم المُمرَّر صحيحاً (TN / (TN+FP))
    - Precision:            دقة إنذارات الهجوم (TP / (TP+FP))
    - F1:                   التوافق بين الدقة والاستدعاء
    - Accuracy:             النسبة الكلية الصحيحة
    - FPR:                  معدل الإنذار الكاذب (FP / (FP+TN))
    - Latency:              متوسط زمن الفحص لكل عيّنة (مللي ثانية)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class BenchmarkResult:
    """نتيجة القياس المجمّعة مع كل المقاييس."""

    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0
    avg_latency_ms: float = 0.0
    misclassified: list[tuple[str, int, float]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.tp + self.fp + self.tn + self.fn

    @property
    def sensitivity(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 0.0

    recall = sensitivity  # مرادف

    @property
    def specificity(self) -> float:
        denom = self.tn + self.fp
        return self.tn / denom if denom else 0.0

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.sensitivity
        return 2 * p * r / (p + r) if (p + r) else 0.0

    @property
    def accuracy(self) -> float:
        return (self.tp + self.tn) / self.total if self.total else 0.0

    @property
    def fpr(self) -> float:
        denom = self.fp + self.tn
        return self.fp / denom if denom else 0.0

    def report(self) -> str:
        """تقرير نصّي منسّق جاهز للعرض."""
        lines = [
            "═" * 56,
            "  تقرير قياس أداء prompt-guard",
            "═" * 56,
            f"  عدد العيّنات        : {self.total}",
            f"  Sensitivity/Recall : {self.sensitivity:.3f}  (الهجمات المكتشفة)",
            f"  Specificity        : {self.specificity:.3f}  (السليم الممرَّر)",
            f"  Precision          : {self.precision:.3f}  (دقة الإنذارات)",
            f"  F1-score           : {self.f1:.3f}",
            f"  Accuracy           : {self.accuracy:.3f}",
            f"  False Positive Rate: {self.fpr:.3f}",
            f"  متوسط زمن الفحص    : {self.avg_latency_ms:.2f} مللي ثانية",
            "─" * 56,
            f"  TP={self.tp}  FP={self.fp}  TN={self.tn}  FN={self.fn}",
            "═" * 56,
        ]
        return "\n".join(lines)

    def markdown_table(self) -> str:
        """جدول Markdown جاهز لـ README أو الورقة البحثية."""
        return (
            "| المقياس | القيمة |\n"
            "|---------|--------|\n"
            f"| Sensitivity (Recall) | {self.sensitivity:.3f} |\n"
            f"| Specificity | {self.specificity:.3f} |\n"
            f"| Precision | {self.precision:.3f} |\n"
            f"| F1-score | {self.f1:.3f} |\n"
            f"| Accuracy | {self.accuracy:.3f} |\n"
            f"| False Positive Rate | {self.fpr:.3f} |\n"
            f"| Avg Latency (ms) | {self.avg_latency_ms:.2f} |\n"
        )


def run_benchmark(guard, samples: list[tuple[str, int]] | None = None) -> BenchmarkResult:
    """يشغّل القياس على مجموعة تقييم ويُرجع النتائج.

    Args:
        guard: نسخة Guard (أو أي كائن له ``check`` يُرجع ``is_blocked``).
        samples: عيّنات [(نص, تصنيف)]. إن تُركت None تُستخدم مجموعة
            التقييم المستقلة المدمجة.

    Returns:
        BenchmarkResult بكل المقاييس.
    """
    if samples is None:
        from .data.eval_samples import EVAL_SAMPLES
        samples = EVAL_SAMPLES

    result = BenchmarkResult()
    latencies: list[float] = []

    for text, label in samples:
        t0 = time.perf_counter()
        guard_result = guard.check(text)
        latencies.append((time.perf_counter() - t0) * 1000)

        # نعتبر "هجوماً مكتشفاً" = حُجب فعلاً (decision == BLOCK)
        predicted_attack = guard_result.is_blocked

        if label == 1 and predicted_attack:
            result.tp += 1
        elif label == 1 and not predicted_attack:
            result.fn += 1
            result.misclassified.append((text, label, guard_result.risk_score))
        elif label == 0 and predicted_attack:
            result.fp += 1
            result.misclassified.append((text, label, guard_result.risk_score))
        else:
            result.tn += 1

    result.avg_latency_ms = sum(latencies) / len(latencies) if latencies else 0.0
    return result
