"""الفئة المجردة التي ترث منها كل الطبقات الدفاعية.

أي طبقة جديدة (سياقية، تعقيم، مراقبة مخرجات) تنفّذ ``inspect`` فقط،
فيعمل خط الأنابيب معها تلقائياً.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..result import LayerResult


class BaseLayer(ABC):
    """واجهة موحّدة لكل طبقة دفاعية.

    Attributes:
        name: اسم الطبقة الظاهر في النتائج.
    """

    name: str = "base"

    @abstractmethod
    def inspect(self, text: str) -> LayerResult:
        """يفحص النص ويُرجع نتيجة الطبقة.

        Args:
            text: النص المراد فحصه (مدخل مستخدم أو مخرج نموذج).

        Returns:
            LayerResult يحوي درجة الخطورة والقرار والسبب.
        """
        raise NotImplementedError
