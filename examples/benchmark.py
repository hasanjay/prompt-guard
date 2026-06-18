"""تشغيل قياس أداء prompt-guard على مجموعة التقييم المستقلة.

استخدام:  python examples/benchmark.py
"""

from prompt_guard import Guard
from prompt_guard.benchmark import run_benchmark

if __name__ == "__main__":
    print("تدريب المصنّف وتشغيل القياس...\n")
    guard = Guard()
    result = run_benchmark(guard)

    print(result.report())
    print("\nجدول Markdown (للورقة البحثية / README):\n")
    print(result.markdown_table())

    if result.misclassified:
        print("الحالات المُصنَّفة خطأً (لتحسين البيانات لاحقاً):")
        for text, label, score in result.misclassified:
            kind = "هجوم فات" if label == 1 else "إنذار كاذب"
            print(f"  [{kind}] خطورة {score:.2f} — {text[:55]}")
