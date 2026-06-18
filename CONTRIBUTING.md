# المساهمة في prompt-guard

شكراً لاهتمامك! أسهل وأقيّم مساهمة هي **إضافة أنماط هجوم جديدة**.

## إضافة نمط هجوم
1. افتح `src/prompt_guard/patterns/attacks.yaml`
2. أضف مدخلاً جديداً بالحقول: `id`, `category`, `weight` (0-1), `pattern` (regex), `description`
3. أضف عيّنة اختبار في `tests/test_heuristic.py`
4. شغّل `pytest tests/` للتأكد من نجاح الاختبارات
5. أرسل pull request

## تشغيل الاختبارات محلياً
```bash
pip install -e ".[dev]"
pytest tests/ -v
```
