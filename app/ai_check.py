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
logging.basicConfig(level=logging.INFO)

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "prompt_v3.md"
SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8")

DEFAULT_MODEL = "qwen2.5:7b"
NUM_CTX = 4096
NUM_PREDICT = 256

# ~2.5-3 символа на токен для русского: промт длиннее этого
# рискует не влезть в NUM_CTX вместе с вакансией и ответом
PROMPT_CHARS_WARN = 6000

logger.info("prompt %s: %d chars", PROMPT_PATH.name, len(SYSTEM_PROMPT))
if len(SYSTEM_PROMPT) > PROMPT_CHARS_WARN:
    logger.warning(
        "Prompt is %d chars, may not fit into num_ctx=%d - Ollama would "
        "truncate it silently (look for 'truncating input prompt' in its log)",
        len(SYSTEM_PROMPT),
        NUM_CTX,
    )

AMBIGUITY = "Формулировки без конкретики"
CONTRADICTION = "Противоречия между полями или между полем и текстом вакансии"

RECOMMENDATIONS = {
    AMBIGUITY: "Уточнить, что именно подразумевается в этой формулировке.",
    CONTRADICTION: "Согласовать конфликтующие сведения.",
}


class AIIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme: Literal[AMBIGUITY, CONTRADICTION]
    field: str = Field(max_length=100)
    quote: str = Field(max_length=600)
    problem: str = Field(max_length=300)


class AIResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issues: list[AIIssue] = Field(max_length=5)


def _model_schema() -> dict:
    """Схема для Ollama: уже, чем у pydantic-модели (только AMBIGUITY, до 3 замечаний)."""
    schema = AIResponse.model_json_schema()

    props = schema["$defs"]["AIIssue"]["properties"]
    props["theme"] = {"type": "string", "enum": [AMBIGUITY], "title": "Theme"}
    props["problem"]["maxLength"] = 150
    props["quote"]["maxLength"] = 200
    schema["properties"]["issues"]["maxItems"] = 3

    return schema


def _norm(value) -> str:
    text = str(value).casefold().replace("ё", "е")
    text = re.sub(r"[«»\"'“”]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _nums(text: str) -> set[str]:
    # "60 000" и "60000" должны давать одно и то же число
    text = re.sub(r"(?<=\d)[\s\u00a0](?=\d{3}\b)", "", text)
    return set(re.findall(r"\d+", text))


def _flatten(data) -> dict[str, str]:
    """Вложенные данные -> {путь.к.полю: нормализованный текст}."""
    out: dict[str, str] = {}

    def walk(path, node):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(f"{path}.{k}" if path else str(k), v)
        elif isinstance(node, (list, tuple)):
            for item in node:
                walk(path, item)
        elif node is not None:
            text = _norm(node)
            if text:
                out[path] = f"{out.get(path, '')} {text}".strip()

    walk("", data)
    return out


def _find_fields(name: str, fields: dict[str, str]) -> list[str]:
    """Ищет поле по полному пути, а если не нашлось - по последнему сегменту."""
    name = _norm(name)

    exact = [k for k in fields if _norm(k) == name]
    if exact:
        return exact

    return [k for k in fields if _norm(k).split(".")[-1] == name]


def _check(issue: AIIssue, fields: dict[str, str], whole: str) -> str | None:
    """None, если замечание прошло проверку, иначе причина отказа."""
    quotes = [_norm(q) for q in issue.quote.split("||")]

    expected = {AMBIGUITY: 1, CONTRADICTION: 2}.get(issue.theme)
    if expected is None:
        return "unknown_theme"
    if len(quotes) != expected:
        return "wrong_quote_count"

    # короткими могут быть только числа вроде "0"
    for q in quotes:
        if not q or (len(q) < 5 and not re.fullmatch(r"-?\d+(?:[.,]\d+)?", q)):
            return "empty_or_short_quote"

    if not all(q in whole for q in quotes):
        return "quote_not_in_source"

    candidates = _find_fields(issue.field, fields)
    if not candidates:
        return "unknown_field"

    in_field = [f for f in candidates if quotes[0] in fields[f]]
    if not in_field:
        return "quote_not_in_field"

    if issue.theme == CONTRADICTION:
        # вторая цитата должна быть в каком-то другом поле
        if not any(
            f not in in_field and quotes[1] in text
            for f, text in fields.items()
        ):
            return "second_quote_not_in_another_field"

    if _nums(issue.problem) - _nums(whole):
        return "invented_number"

    return None


def analyze(vacancy: Vacancy) -> list[dict]:
    """Просит локальную LLM найти в вакансии расплывчатые формулировки.

    Противоречия ищет rule-модуль, а не LLM. Каждое замечание модели
    проверяется по тексту вакансии, непрошедшие отбрасываются.
    """
    model = os.getenv("AI_MODEL", DEFAULT_MODEL)
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    client = ollama.Client(host=host, timeout=300)

    # conditions не входит в text_fields() из models.py, добавляем руками
    text_fields = vacancy.text_fields()
    if vacancy.conditions:
        text_fields["conditions"] = vacancy.conditions

    vacancy_data = {
        "text_fields": text_fields,
        "structured_fields": vacancy.structured_fields(),
    }
    fields = _flatten(vacancy_data)
    whole = " ".join(fields.values())

    logger.info("vacancy %s: model=%s fields=%s", vacancy.id, model, list(fields))

    # системный промт всегда первый и не меняется - Ollama кэширует его,
    # так что для следующих вакансий считается только их текст
    try:
        response = client.chat(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(vacancy_data, ensure_ascii=False),
                },
            ],
            format=_model_schema(),
            options={
                "temperature": 0,
                "seed": 0,
                "num_ctx": NUM_CTX,
                "num_predict": NUM_PREDICT,
            },
            keep_alive="30m",
        )
        parsed = AIResponse.model_validate_json(response.message.content)
    except Exception:
        logger.exception("LLM failed for vacancy %s", vacancy.id)
        raise

    logger.info(
        "vacancy %s: load=%.1fs prompt=%.1fs gen=%.1fs tokens=%s prompt_tokens=%s",
        vacancy.id,
        (response.load_duration or 0) / 1e9,
        (response.prompt_eval_duration or 0) / 1e9,
        (response.eval_duration or 0) / 1e9,
        response.eval_count,
        response.prompt_eval_count,
    )

    issues = []
    seen = set()

    for issue in parsed.issues:
        key = (issue.theme, _norm(issue.field), _norm(issue.quote))
        reason = _check(issue, fields, whole)
        if reason is None and key in seen:
            reason = "duplicate"

        if reason:
            logger.warning(
                "vacancy %s: dropped (%s) field=%s quote=%r",
                vacancy.id,
                reason,
                issue.field,
                issue.quote,
            )
            continue

        seen.add(key)
        issues.append(
            {
                "topic": issue.theme,
                "field": issue.field,
                "quote": issue.quote.replace("||", " / "),
                "problem": issue.problem,
                "recommendation": RECOMMENDATIONS[issue.theme],
                "source": "ai",
            }
        )

    logger.info(
        "vacancy %s: %d of %d issues accepted",
        vacancy.id,
        len(issues),
        len(parsed.issues),
    )
    return issues
