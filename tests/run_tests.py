
import json
import sys
from pathlib import Path

# Корень проекта
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.ai_check import analyze
from normalizer import normalize_vacancy

TESTS_PATH = Path(__file__).parent / "test_cases.json"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_PATH = RESULTS_DIR / "latest.json"


def normalize_text(text):
    """Нормализует текст для сравнения цитат."""
    return " ".join(
        str(text).casefold().replace("ё", "е").split()
    )
def split_quotes(issue):
    """
    Разделяет цитаты:
    - обычное замечание: одна цитата;
    - противоречие: две цитаты через /.
    """
    quote = issue.get("quote", "")

    if issue.get("topic") == (
        "Противоречия между полями или между полем и текстом вакансии"
    ):
        return [
            part.strip()
            for part in quote.split("/")
            if part.strip()
        ]

    return [quote.strip()] if quote.strip() else []


def quote_exists(quote, vacancy_raw):
    """
    Проверяет, присутствует ли цитата
    в исходных текстовых значениях вакансии.
    """
    normalized_quote = normalize_text(quote)

    if not normalized_quote:
        return False

    def search(value):
        if isinstance(value, dict):
            return any(search(v) for v in value.values())

        if isinstance(value, list):
            return any(search(v) for v in value)

        if isinstance(value, (str, int, float)):
            return normalized_quote in normalize_text(value)

        return False

    return search(vacancy_raw)

def run_test(test):
    vacancy_raw = test["vacancy"]
    vacancy = normalize_vacancy(vacancy_raw)
    expected = test["expected"]

    # Запускаем ИИ-анализатор
    issues = analyze(vacancy)

    # Проверяем найденные темы
    themes = [issue.get("topic") for issue in issues]

    # Проверяем обязательные категории
    missing = [
        theme
        for theme in expected.get("must_find", [])
        if theme not in themes
    ]

    # Проверяем запрещённые категории
    unexpected = [
        theme
        for theme in expected.get("must_not_find", [])
        if theme in themes
    ]

    # Проверяем отсутствие замечаний в чистой вакансии
    empty_failed = (
        expected.get("expect_empty", False)
        and len(issues) != 0
    )

    # Проверяем каждую цитату отдельно
    invalid_quotes = []

    for issue in issues:
        quotes = split_quotes(issue)

        # У противоречия обязательно должно быть две цитаты
        is_contradiction = (
            issue.get("topic") ==
            "Противоречия между полями или между полем и текстом вакансии"
        )

        if is_contradiction and len(quotes) != 2:
            invalid_quotes.append({
                "quote": issue.get("quote", ""),
                "reason": "Для противоречия нужны ровно две цитаты"
            })
            continue

        if not quotes:
            invalid_quotes.append({
                "quote": issue.get("quote", ""),
                "reason": "Пустая цитата"
            })
            continue

        for quote in quotes:
            if not quote_exists(quote, vacancy_raw):
                invalid_quotes.append({
                    "quote": quote,
                    "reason": "Цитата отсутствует в исходных данных"
                })

    # Итоговый результат теста
    passed = (
        not missing
        and not unexpected
        and not empty_failed
        and not invalid_quotes
    )

    return {
        "id": test["id"],
        "name": test["name"],
        "passed": passed,
        "issues": issues,
        "checks": {
            "missing_expected_themes": missing,
            "unexpected_themes": unexpected,
            "expected_empty_failed": empty_failed,
            "invalid_quotes": invalid_quotes
        }
    }






def main():
    with open(TESTS_PATH, encoding="utf-8") as f:
        tests = json.load(f)

    results = []

    for test in tests:
        print(f"\nТест: {test['name']}")

        try:
            result = run_test(test)
            results.append(result)

            status = "PASS" if result["passed"] else "FAIL"
            print(f"Результат: {status}")

            if not result["passed"]:
                print(
                    json.dumps(
                        result["checks"],
                        ensure_ascii=False,
                        indent=2
                    )
                )

        except Exception as e:
            results.append({
                "id": test["id"],
                "name": test["name"],
                "passed": False,
                "error": str(e)
            })

            print(f"Ошибка: {e}")

    # Подсчёт результатов
    passed = sum(r["passed"] for r in results)
    total = len(results)

    report = {
        "passed": passed,
        "total": total,
        "success_rate": round(passed / total * 100, 2) if total else 0,
        "results": results
    }

    # Сохранение отчёта
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(
            report,
            f,
            ensure_ascii=False,
            indent=2
        )

    print("\n" + "=" * 40)
    print(f"Пройдено: {passed}/{total}")
    print(f"Успешность: {report['success_rate']}%")
    print(f"Отчёт сохранён: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
