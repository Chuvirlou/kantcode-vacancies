import json
import sys
from pathlib import Path

# Allow running this file directly from a checkout.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rules import check_rules


def demo_vacancies() -> list:
    base = {
        "job-name": "Оператор склада",
        "duty": "Принимать товар и регистрировать поставки в системе учёта.",
        "requirements": "Опыт складского учёта от одного года.",
        "salary": "от 50000",
        "salary_min": 50000,
        "salary_max": 60000,
        "currency": "«руб.»",
        "schedule": "Пн–пт, с 9 до 18",
        "shift": ["Пн–пт, с 9 до 18"],
        "addresses": {
            "address": [{"location": "Демонстрационный город, Примерная улица, 1"}]
        },
        "employment": "Полная занятость",
    }
    no_pay = {"salary": "", "salary_min": 0, "salary_max": 0}
    missing_fields = {**base, **no_pay, "shift": []}
    del missing_fields["schedule"], missing_fields["addresses"]

    vacancies = [
        base,
        missing_fields,
        {**base, "salary": "от 90000", "salary_min": 90000, "salary_max": 50000},
        {**base, "duty": "Принимать товар. Условия: работа на полставки."},
        {**base, "schedule": "Сменная работа", "shift": []},
        {
            **base,
            **no_pay,
            "schedule": "Полный рабочий день",
            "shift": [],
            "duty": "Условия: гибкий график, достойная зарплата.",
        },
    ]
    for number, vacancy in enumerate(vacancies, start=1):
        vacancy["id"] = f"demo-{number}"
        vacancy["vac_url"] = f"https://example.invalid/vacancies/demo-{number}"
    return vacancies


def main() -> None:
    for vacancy in demo_vacancies():
        issues = check_rules(vacancy)
        print(vacancy["id"])
        if issues:
            for issue in issues:
                print(json.dumps(issue, ensure_ascii=False))
        else:
            print("[]")


if __name__ == "__main__":
    main()
