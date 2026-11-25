
import pytest
from pydantic import ValidationError

from app.ai_check import (
    AIIssue,
    AMBIGUITY,
    CONTRADICTION,
    _norm,
    _nums,
    _flatten,
    _field_candidates,
    _check,
)


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

FIELDS = {
    "text_fields.experience": (
        "требуется не менее 5 лет опыта работы аналитиком данных"
    ),
    "structured_fields.experience": "0",
    "text_fields.schedule": (
        "работа полностью дистанционная"
    ),
    "structured_fields.schedule": (
        "ежедневное присутствие в офисе"
    ),
    "text_fields.duty": (
        "выполнение различных поручений руководителя"
    ),
    "text_fields.requirements": (
        "ответственность, активность"
    ),
    "structured_fields.salary_from": "60000",
}

WHOLE = " ".join(FIELDS.values())


# ---------------------------------------------------------------------------
# _norm()
# ---------------------------------------------------------------------------

def test_norm_case():
    assert _norm("ПРИВЕТ") == _norm("привет")


def test_norm_yo():
    assert _norm("всё") == _norm("все")


def test_norm_quotes():
    assert _norm("«Привет»") == _norm("Привет")


def test_norm_spaces():
    assert _norm("  привет   мир  ") == "привет мир"


def test_norm_newlines():
    assert _norm("привет\nмир") == "привет мир"


# ---------------------------------------------------------------------------
# _nums()
# ---------------------------------------------------------------------------

def test_nums_with_spaces():
    assert _nums("60 000") == {"60000"}


def test_nums_without_spaces():
    assert _nums("60000") == {"60000"}


def test_nums_with_nonbreaking_space():
    assert _nums("60\u00a0000") == {"60000"}


def test_nums_different_values():
    assert _nums("70 000") - _nums("60000") == {"70000"}


def test_nums_multiple_numbers():
    assert _nums("От 60 000 до 100 000 рублей") == {
        "60000",
        "100000",
    }


# ---------------------------------------------------------------------------
# _flatten()
# ---------------------------------------------------------------------------

def test_flatten_preserves_nested_paths():
    result = _flatten({
        "text_fields": {
            "experience": "5 лет опыта",
        },
        "structured_fields": {
            "experience": "0",
        },
    })

    assert "text_fields.experience" in result
    assert "structured_fields.experience" in result


def test_flatten_preserves_numbers():
    result = _flatten({
        "salary": 60000,
        "experience": 0,
    })

    assert result["salary"] == "60000"
    assert result["experience"] == "0"


def test_flatten_preserves_boolean():
    result = _flatten({
        "remote": True,
    })

    assert result["remote"] == "true"


def test_flatten_handles_lists():
    result = _flatten({
        "requirements": [
            "Python",
            "SQL",
        ],
    })

    assert "python" in result["requirements"]
    assert "sql" in result["requirements"]


# ---------------------------------------------------------------------------
# _field_candidates()
# ---------------------------------------------------------------------------

def test_field_candidates_short_name():
    result = _field_candidates("experience", FIELDS)

    assert "text_fields.experience" in result
    assert "structured_fields.experience" in result


def test_field_candidates_full_name():
    result = _field_candidates(
        "structured_fields.experience",
        FIELDS,
    )

    assert result == ["structured_fields.experience"]


def test_field_candidates_unknown_field():
    assert _field_candidates("unknown", FIELDS) == []


# ---------------------------------------------------------------------------
# Helpers for _check()
# ---------------------------------------------------------------------------

def make_issue(
    theme,
    field,
    quote,
    problem="Формулировка требует уточнения.",
):
    return AIIssue(
        theme=theme,
        field=field,
        quote=quote,
        problem=problem,
    )


# ---------------------------------------------------------------------------
# _check(): ambiguity
# ---------------------------------------------------------------------------

def test_valid_ambiguity():
    issue = make_issue(
        AMBIGUITY,
        "duty",
        "выполнение различных поручений руководителя",
    )

    assert _check(issue, FIELDS, WHOLE) is None


def test_ambiguity_quote_not_in_source():
    issue = make_issue(
        AMBIGUITY,
        "duty",
        "управление командой из 20 человек",
    )

    assert _check(issue, FIELDS, WHOLE) == "quote_not_in_source"


def test_ambiguity_quote_not_in_field():
    issue = make_issue(
        AMBIGUITY,
        "duty",
        "ответственность, активность",
    )

    assert _check(issue, FIELDS, WHOLE) == "quote_not_in_field"


def test_ambiguity_must_have_one_quote():
    issue = make_issue(
        AMBIGUITY,
        "duty",
        "выполнение различных поручений руководителя || 0",
    )

    assert _check(
        issue,
        FIELDS,
        WHOLE,
    ) == "ambiguity_must_have_one_quote"


# ---------------------------------------------------------------------------
# _check(): contradictions
# ---------------------------------------------------------------------------

def test_valid_contradiction():
    issue = make_issue(
        CONTRADICTION,
        "experience",
        (
            "требуется не менее 5 лет опыта работы аналитиком данных"
            " || 0"
        ),
        "В тексте требуется 5 лет опыта, "
        "но структурированное поле показывает 0.",
    )

    assert _check(issue, FIELDS, WHOLE) is None


def test_contradiction_needs_two_quotes():
    issue = make_issue(
        CONTRADICTION,
        "experience",
        "требуется не менее 5 лет опыта работы аналитиком данных",
    )

    assert _check(
        issue,
        FIELDS,
        WHOLE,
    ) == "contradiction_needs_two_quotes"


def test_contradiction_second_quote_must_be_in_another_field():
    issue = make_issue(
        CONTRADICTION,
        "experience",
        (
            "требуется не менее 5 лет опыта работы аналитиком данных"
            " || аналитиком данных"
        ),
    )

    assert _check(
        issue,
        FIELDS,
        WHOLE,
    ) == "second_quote_not_in_another_field"


def test_contradiction_first_quote_must_be_in_selected_field():
    issue = make_issue(
        CONTRADICTION,
        "experience",
        "ответственность, активность || 0",
    )

    assert _check(
        issue,
        FIELDS,
        WHOLE,
    ) == "first_quote_not_in_field"


# ---------------------------------------------------------------------------
# _check(): quote validation
# ---------------------------------------------------------------------------

def test_short_text_quote_is_rejected():
    issue = make_issue(
        AMBIGUITY,
        "experience",
        "опыт",
    )

    assert _check(
        issue,
        FIELDS,
        WHOLE,
    ) == "empty_or_short_quote"


def test_short_numeric_quote_is_allowed():
    issue = make_issue(
        CONTRADICTION,
        "experience",
        (
            "требуется не менее 5 лет опыта работы аналитиком данных"
            " || 0"
        ),
        "Требуется 5 лет опыта, а структурированное значение равно 0.",
    )

    assert _check(issue, FIELDS, WHOLE) is None


# ---------------------------------------------------------------------------
# _check(): numbers
# ---------------------------------------------------------------------------

def test_invented_number_is_rejected():
    issue = make_issue(
        AMBIGUITY,
        "duty",
        "выполнение различных поручений руководителя",
        "Требуется опыт 15 лет.",
    )

    assert _check(
        issue,
        FIELDS,
        WHOLE,
    ) == "invented_number_in_problem"


def test_number_with_spaces_is_allowed():
    issue = make_issue(
        AMBIGUITY,
        "salary_from",
        "60000",
        "Зарплата составляет 60 000 рублей.",
    )

    assert _check(issue, FIELDS, WHOLE) is None


# ---------------------------------------------------------------------------
# _check(): problem length
# ---------------------------------------------------------------------------

def test_problem_too_long():
    with pytest.raises(ValidationError):
        issue = make_issue(
            AMBIGUITY,
            "duty",
            "выполнение различных поручений руководителя",
            "А" * 301,
        )