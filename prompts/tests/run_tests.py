
import json
import sys
from pathlib import Path

# Корень проекта
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from llm_analyzer import call_llm

TESTS_PATH = Path(__file__).parent / "test_cases.json"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_PATH = RESULTS_DIR / "latest.json"


def run_test(test):
    vacancy = test["vacancy"]
    expected = test["expected"]

    # Запускаем именно наш анализатор с актуальным промтом
    issues = call_llm(vacancy)

    themes = [issue.get("theme") for issue in issues]

    # Проверяем обязательные категории
    missing = [
        theme for theme in expected.get("must_find", [])
        if theme not in themes
    ]

    # Проверяем запрещённые категории
    unexpected = [
        theme for theme in expected.get("must_not_find", [])
        if theme in themes
    ]

    # Проверяем отсутствие замечаний в чистой вакансии
    empty_failed = (
        expected.get("expect_empty", False)
        and len(issues) != 0
    )

    # Проверяем цитаты на соответствие исходным данным
    vacancy_text = json.dumps(vacancy, ensure_ascii=False)

    invalid_quotes = [
        issue.get("quote", "")
        for issue in issues
        if issue.get("quote", "") not in vacancy_text
    ]

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
                print(json.dumps(
                    result["checks"],
                    ensure_ascii=False,
                    indent=2
                ))

        except Exception as e:
            results.append({
                "id": test["id"],
                "name": test["name"],
                "passed": False,
                "error": str(e)
            })

            print(f"Ошибка: {e}")

    passed = sum(r["passed"] for r in results)
    total = len(results)

    report = {
        "passed": passed,
        "total": total,
        "success_rate": round(passed / total * 100, 2) if total else 0,
        "results": results
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 40)
    print(f"Пройдено: {passed}/{total}")
    print(f"Успешность: {report['success_rate']}%")
    print(f"Отчёт сохранён: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
