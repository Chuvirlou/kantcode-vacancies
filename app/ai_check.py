
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Literal

import ollama
from pydantic import BaseModel, ConfigDict, Field

from models import Vacancy


logger = logging.getLogger(__name__)




PROMPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "prompts"
    / "prompt_v3.md"
)

SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8")

DEFAULT_MODEL = "qwen2.5:7b"



AMBIGUITY = "Формулировки без конкретики"

CONTRADICTION = (
    "Противоречия между полями или между полем и текстом вакансии"
)

RECOMMENDATIONS = {
    AMBIGUITY: (
        "Уточнить, что именно подразумевается в этой формулировке."
    ),
    CONTRADICTION: (
        "Согласовать конфликтующие сведения."
    ),
}




ANALYSIS_INSTRUCTIONS = """
Дополнительные обязательные правила анализа.

Ты должен искать ДВА типа проблем:

1. Формулировки без конкретики.
2. Противоречия между полями или между полем и текстом вакансии.

Проверяй оба типа проблем независимо друг от друга.

При поиске противоречий обязательно сравнивай:
- salary и другие упоминания зарплаты;
- schedule и другие упоминания графика;
- employment и другие упоминания занятости;
- структурированные поля и текстовые поля;
- все доступные поля между собой.

Особенно внимательно проверяй поле conditions:
в нём могут находиться дополнительные сведения о зарплате,
графике и условиях работы.

Если в разных полях указаны разные значения одного параметра,
зафиксируй противоречие.

Для каждого противоречия:
- верни ровно две цитаты через разделитель ||;
- первая цитата должна быть из поля, указанного в field;
- вторая цитата должна находиться в другом поле;
- обе цитаты должны дословно присутствовать в исходных данных;
- не придумывай значения и не делай предположений.

В поле field указывай название поля, из которого взята первая цитата.
Например: salary, schedule, employment.

Не создавай замечание, если сведения не противоречат друг другу.

Если проблем нет, верни пустой список issues.

Возвращай только JSON в соответствии с заданной схемой.
"""




class AIIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme: Literal[
        "Формулировки без конкретики",
        "Противоречия между полями или между полем и текстом вакансии",
    ]

    field: str = Field(max_length=100)
    quote: str = Field(max_length=600)
    problem: str = Field(max_length=300)


class AIResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issues: list[AIIssue] = Field(max_length=5)




def _norm(value) -> str:
    """
    Нормализует текст для сравнения:
    - нижний регистр;
    - ё заменяется на е;
    - удаляются кавычки;
    - нормализуются пробелы.
    """

    text = str(value).casefold().replace("ё", "е")

    text = re.sub(
        r"[«»\"'“”]",
        "",
        text,
    )

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def _nums(text: str) -> set[str]:
    """
    Извлекает числа, учитывая разделители разрядов.

    Например:
    60 000 -> 60000
    60 000 -> 60000
    60000  -> 60000
    """

    normalized = re.sub(
        r"(?<=\d)[\s\u00a0](?=\d{3}\b)",
        "",
        text,
    )

    return set(re.findall(r"\d+", normalized))




def _flatten(value, prefix="") -> dict[str, str]:
    """
    Преобразует вложенные данные в словарь:

        полный_путь_поля -> текстовое значение

    Поддерживает словари, списки, числа и строки.
    """

    result: dict[str, str] = {}

    def walk(key, current):
        if isinstance(current, dict):
            for sub_key, sub_value in current.items():
                new_key = (
                    f"{key}.{sub_key}"
                    if key
                    else str(sub_key)
                )

                walk(new_key, sub_value)

        elif isinstance(current, (list, tuple)):
            for item in current:
                walk(key, item)

        elif current is not None:
            text = _norm(current)

            if text:
                result[key] = (
                    f"{result.get(key, '')} {text}"
                ).strip()

    walk(prefix, value)

    return result


def _field_candidates(
    field_name: str,
    fields: dict[str, str],
) -> list[str]:
    """
    Находит поле по полному или короткому имени.
    """

    name = _norm(field_name)

    exact = [
        key
        for key in fields
        if _norm(key) == name
    ]

    if exact:
        return exact

    return [
        key
        for key in fields
        if _norm(key).split(".")[-1] == name
    ]




def _check(
    issue: AIIssue,
    fields: dict[str, str],
    whole: str,
) -> str | None:
    """
    Проверяет замечание AI.

    None означает, что замечание прошло проверку.
    Строка означает причину отклонения.
    """

    parts = [
        _norm(part)
        for part in issue.quote.split("||")
    ]

    # 1. Проверка количества цитат

    if issue.theme == AMBIGUITY:
        if len(parts) != 1:
            return "ambiguity_must_have_one_quote"

    elif issue.theme == CONTRADICTION:
        if len(parts) != 2:
            return "contradiction_needs_two_quotes"

    else:
        return "unknown_theme"

    # 2. Проверка пустых и коротких цитат
    # Короткие числовые значения (например, "0") разрешены.

    if not parts or any(
        not part
        or (
            len(part) < 5
            and not re.fullmatch(r"-?\d+(?:[.,]\d+)?", part)
        )
        for part in parts
    ):
        return "empty_or_short_quote"

    # 3. Проверка наличия цитат в исходных данных

    if not all(part in whole for part in parts):
        return "quote_not_in_source"

    # 4. Проверка неконкретных формулировок

    if issue.theme == AMBIGUITY:

        candidates = _field_candidates(
            issue.field,
            fields,
        )

        if not candidates:
            return "unknown_field"

        if not any(
            parts[0] in _norm(fields[field])
            for field in candidates
        ):
            return "quote_not_in_field"

    # 5. Проверка противоречий

    elif issue.theme == CONTRADICTION:

        candidates = _field_candidates(
            issue.field,
            fields,
        )

        if not candidates:
            return "unknown_field"

        # Первая цитата должна находиться
        # в поле, указанном моделью.

        first_fields = [
            field
            for field in candidates
            if parts[0] in _norm(fields[field])
        ]

        if not first_fields:
            return "first_quote_not_in_field"

        # Вторая цитата должна находиться
        # в другом поле.

        second_fields = [
            field
            for field, value in fields.items()
            if field not in first_fields
            and parts[1] in _norm(value)
        ]

        if not second_fields:
            return "second_quote_not_in_another_field"

    # 6. Проверка выдуманных чисел

    if _nums(issue.problem) - _nums(whole):
        return "invented_number_in_problem"

    # 7. Проверка длины описания

    if len(issue.problem) > 300:
        return "problem_too_long"

    return None


def analyze(vacancy: Vacancy) -> list[dict]:
    """
    Анализирует вакансию с помощью локальной LLM.

    AI ищет:
    - неконкретные формулировки;
    - противоречия между полями.

    Все замечания проходят локальную проверку.
    """

    model = os.getenv(
        "AI_MODEL",
        DEFAULT_MODEL,
    )

    host = os.getenv(
        "OLLAMA_HOST",
        "http://localhost:11434",
    )

    client = ollama.Client(
        host=host,
        timeout=300,
    )

    # Подготовка данных вакансии.
    # conditions передаётся отдельно, поскольку
    # models.py не включает его в text_fields().

    text_fields = vacancy.text_fields()

    if vacancy.conditions:
        text_fields["conditions"] = vacancy.conditions

    vacancy_data = {
        "text_fields": text_fields,
        "structured_fields": vacancy.structured_fields(),
    }

    # Подготовка данных для проверки цитат.

    fields = _flatten(vacancy_data)

    whole = " ".join(fields.values())

    logger.info(
        "Starting AI analysis: vacancy=%s model=%s fields=%s",
        vacancy.id,
        model,
        list(fields.keys()),
    )

    # 1. Запрос к Ollama

    try:
        response = client.chat(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        SYSTEM_PROMPT
                        + "\n\n"
                        + ANALYSIS_INSTRUCTIONS
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        vacancy_data,
                        ensure_ascii=False,
                    ),
                },
            ],
            format=AIResponse.model_json_schema(),
            options={
                "temperature": 0,
                "seed": 0,
                "num_ctx": 4096,
                "num_predict": 1200,
            },
            keep_alive="30m",
        )

        parsed = AIResponse.model_validate_json(
            response.message.content
        )

    except Exception:
        logger.exception(
            "LLM failed for vacancy %s",
            vacancy.id,
        )
        raise

    # 2. Логирование производительности

    logger.info(
        "vacancy %s: load=%.1fs prompt=%.1fs "
        "gen=%.1fs tokens=%s prompt_tokens=%s",
        vacancy.id,
        (response.load_duration or 0) / 1e9,
        (response.prompt_eval_duration or 0) / 1e9,
        (response.eval_duration or 0) / 1e9,
        response.eval_count,
        response.prompt_eval_count,
    )

    logger.info(
        "vacancy %s: AI returned %s issues",
        vacancy.id,
        len(parsed.issues),
    )

    # 3. Проверка и формирование результата

    issues = []
    seen = set()

    for issue in parsed.issues:

        reason = _check(
            issue,
            fields,
            whole,
        )

        # Ключ для удаления дубликатов.

        key = (
            issue.theme,
            _norm(issue.field),
            _norm(issue.quote),
        )

        if not reason and key in seen:
            reason = "duplicate"

        # Отклонённые замечания записываются в лог.

        if reason:
            logger.warning(
                "dropped (%s) vacancy %s: theme=%s field=%s quote=%r",
                reason,
                vacancy.id,
                issue.theme,
                issue.field,
                issue.quote,
            )
            continue

        seen.add(key)

        issues.append(
            {
                "topic": issue.theme,
                "field": issue.field,
                "quote": issue.quote.replace(
                    "||",
                    " / ",
                ),
                "problem": issue.problem,
                "recommendation": RECOMMENDATIONS[
                    issue.theme
                ],
                "source": "ai",
            }
        )

    logger.info(
        "vacancy %s: accepted %s issues",
        vacancy.id,
        len(issues),
    )

    return issues
