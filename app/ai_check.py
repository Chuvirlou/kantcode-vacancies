"""
app/ai_check.py — ИИ-проверки вакансий.

ЗАГЛУШКА для роли ИИ.
Роль ИИ должна заменить тело функции analyze() на реальный вызов модели.
Пайплайн ожидает, что функция вернёт список замечаний в формате SPEC.md:
{"topic": str, "field": str, "quote": str, "problem": str, "recommendation": str, "source": "ai"}
"""

from __future__ import annotations

from models import Vacancy


def analyze(vacancy: Vacancy) -> list[dict]:
    """
    Анализирует вакансию с помощью ИИ.
    Пока возвращает пустой список (ИИ отключен или ещё не реализован).
    """
    # TODO(ai-role): Реализовать вызов LLM.
    # Для передачи данных в модель используйте:
    # 1. vacancy.text_fields() — словарь текстовых полей (обязанности, требования, оплата и т.д.)
    # 2. vacancy.structured_fields() — структурированные данные (вилка, график, занятость)

    return []
