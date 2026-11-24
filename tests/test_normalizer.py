"""
tests/test_normalizer.py
Запуск: python -m pytest tests/ -q
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from normalizer import (
    detect_and_extract,
    load_vacancies_from_file,
    normalize_many,
    normalize_vacancy,
)

# Ищем файлы с данными, которые лежат в корне или в data/probe
FIXTURES = [
    ROOT / "data" / "probe" / "page_offset_0.json",
    ROOT / "data" / "probe" / "page_offset_1.json",
    ROOT / "data" / "probe" / "page_offset_2.json",
    ROOT / "my_sample.json",
    ROOT / "kantkod_sample_vacancies.json",
]


def test_normalize_all_fixtures():
    total = 0
    for path in FIXTURES:
        if not path.exists():
            print(f"SKIP (нет файла): {path}")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        fmt, raws = detect_and_extract(data)
        assert fmt == "api_response", f"{path}: неожиданный формат {fmt}"
        assert raws, f"{path}: не извлечено ни одной вакансии"

        vacs = normalize_many(raws)
        assert len(vacs) == len(raws), f"{path}: потеряны при дедупликации"
        for v in vacs:
            assert v.id, f"{path}: вакансия без id"
            assert v.title, f"{path}: id={v.id} без title"
        total += len(vacs)
        print(f"{path.name}: {len(vacs)} вакансий OK")
    assert total > 0


def test_text_fields_includes_salary_and_term():
    """Проверяем, что ИИ увидит оплату в тексте, а не только в duty/requirements."""
    path = ROOT / "my_sample.json"
    if not path.exists():
        return
    vacs = load_vacancies_from_file(path)
    by_title = {v.title: v for v in vacs}

    engineer = by_title.get("Инженер по метрологии")
    assert engineer is not None
    tf = engineer.text_fields()
    assert "salary" in tf and "45000" in tf["salary"]
    assert "term.text" in tf

    cook = by_title.get("повар")
    assert cook is not None
    assert "term.text" in cook.text_fields()
    assert "Оклад 14000" in cook.text_fields()["term.text"]

    print("text_fields() с оплатой: OK")


def test_minimal_raw_does_not_crash():
    """Проверяем, что нормализатор не падает на пустой вакансии."""
    v = normalize_vacancy({"id": "x"})
    assert v.id == "x"
    assert v.title is None
    assert v.shift == []
    assert v.text_fields() == {}
    assert v.structured_fields() == {}
    print("Минимальный raw: OK")


def test_kantkod_sample_qualification_fallback():
    """Проверяем, что мы вытащили qualification из вложенного requirement."""
    path = ROOT / "kantkod_sample_vacancies.json"
    if not path.exists():
        return
    vacs = load_vacancies_from_file(path)
    by_id = {v.id: v for v in vacs}
    assert (
        by_id["DEMO-39-003"].qualification
        and "5 лет" in by_id["DEMO-39-003"].qualification
    )
    assert (
        by_id["DEMO-39-008"].qualification
        and "гибкий" in by_id["DEMO-39-008"].qualification
    )
    print("qualification fallback: OK")


if __name__ == "__main__":
    test_normalize_all_fixtures()
    test_text_fields_includes_salary_and_term()
    test_minimal_raw_does_not_crash()
    test_kantkod_sample_qualification_fallback()
    print("\nВсе проверки нормализатора пройдены.")
