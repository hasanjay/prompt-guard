"""الطبقة 2: التحليل السياقي (Context-Aware Detection).

جوهر الإطار البحثي: بدل مطابقة كلمات حرفية (الطبقة 1)، تتعلّم هذه
الطبقة **النية** من أمثلة، فتكتشف هجمات مُعاد صياغتها لا تطابق أي نمط.

التصميم:
    - مصنّف خفيف (TF-IDF على مستوى الكلمات والحروف + Logistic Regression).
    - يُدرَّب ذاتياً عند أول استخدام على عيّنات مدمجة (بلا إنترنت).
    - يُخرج احتمالاً معايَراً [0,1] يصلح للقياس العلمي.
    - واجهة قابلة للترقية: مرّر training_data خاصاً بك، أو استبدل
      المُوجِّه (vectorizer) بنموذج تضمينات أقوى لاحقاً.

ملاحظة: يتطلب scikit-learn. إن لم يكن مثبتاً، تُعطّل الطبقة بأمان
وتُرجع درجة 0 مع تنبيه، فلا تتعطل الأداة كلها.
"""

from __future__ import annotations

from ..result import Decision, LayerResult
from .base import BaseLayer

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import FeatureUnion, Pipeline
    _SKLEARN_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SKLEARN_AVAILABLE = False


class ContextLayer(BaseLayer):
    """طبقة التحليل السياقي المبنية على مصنّف مُدرَّب.

    Args:
        threshold: عتبة احتمال اعتبار المدخل هجوماً (يُفعّل WARN).
        block_threshold: عتبة الحجب المباشر.
        training_data: عيّنات تدريب مخصّصة [(نص, تصنيف)]. إن تُركت None
            تُستخدم العيّنات المدمجة.
    """

    name = "context"

    def __init__(
        self,
        threshold: float = 0.5,
        block_threshold: float = 0.8,
        training_data: list[tuple[str, int]] | None = None,
    ) -> None:
        self.threshold = threshold
        self.block_threshold = block_threshold
        self._model = None
        self._enabled = _SKLEARN_AVAILABLE
        if self._enabled:
            self._train(training_data)

    def _train(self, training_data: list[tuple[str, int]] | None) -> None:
        """يدرّب المصنّف على العيّنات (المدمجة أو المخصّصة)."""
        if training_data is None:
            from ..data.training_samples import TRAINING_SAMPLES
            training_data = TRAINING_SAMPLES

        texts = [t for t, _ in training_data]
        labels = [y for _, y in training_data]

        # دمج خصائص الكلمات والحروف: الحروف تلتقط التهرّب والتشويه،
        # الكلمات تلتقط البنية الدلالية.
        word_vec = TfidfVectorizer(
            analyzer="word", ngram_range=(1, 2), min_df=1, sublinear_tf=True
        )
        char_vec = TfidfVectorizer(
            analyzer="char_wb", ngram_range=(3, 5), min_df=1, sublinear_tf=True
        )
        features = FeatureUnion([("word", word_vec), ("char", char_vec)])

        clf = LogisticRegression(max_iter=1000, class_weight="balanced", C=2.0)
        self._model = Pipeline([("features", features), ("clf", clf)])
        self._model.fit(texts, labels)

    def inspect(self, text: str) -> LayerResult:
        """يفحص النص ويُرجع احتمال كونه هجوماً."""
        if not self._enabled or self._model is None:
            return LayerResult(
                layer_name=self.name,
                risk_score=0.0,
                decision=Decision.ALLOW,
                reason="الطبقة السياقية معطّلة (scikit-learn غير مثبّت)",
            )

        # احتمال الفئة 1 (هجوم)
        proba = float(self._model.predict_proba([text])[0][1])
        decision = self._decide(proba)

        if proba >= self.threshold:
            reason = f"المصنّف السياقي يقدّر احتمال الهجوم بـ {proba:.2f}"
        else:
            reason = f"المصنّف السياقي يقدّر المدخل سليماً (خطورة {proba:.2f})"

        return LayerResult(
            layer_name=self.name,
            risk_score=proba,
            decision=decision,
            reason=reason,
        )

    def _decide(self, score: float) -> Decision:
        if score >= self.block_threshold:
            return Decision.BLOCK
        if score >= self.threshold:
            return Decision.WARN
        return Decision.ALLOW
