"""
tests/test_pipeline.py
Проверка пайплайна и записи отчёта.
Запуск: python -m pytest tests/ -q
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import Config
from app.pipeline import run_file


def test_check_mode_on_sample(tmp_path):
    sample = ROOT / "kantkod_sample_vacancies.json"
    if not sample.exists():
        print("SKIP: нет kantkod_sample_vacancies.json")
        return

    cfg = Config()
    cfg.output_path = str(tmp_path / "report.json")
    report = run_file(cfg, sample)

    assert report, "отчёт пуст"
    ids = [item["id"] for item in report]
    assert len(ids) == len(set(ids)), "дубликаты id в отчёте"

    for item in report:
        assert set(item) == {"id", "url", "issues"}
        assert isinstance(item["issues"], list)
        # Если правила подключены, проверяем формат замечаний
        for issue in item["issues"]:
            assert set(issue) == {
                "topic",
                "field",
                "quote",
                "problem",
                "recommendation",
                "source",
            }

    # Проверяем, что файл действительно записался
    saved = json.loads(Path(cfg.output_path).read_text(encoding="utf-8"))
    assert saved == report
    print(
        f"check-режим: {len(report)} вакансий, {sum(len(i['issues']) for i in report)} замечаний"
    )


def test_duplicate_ids_are_deduplicated():
    from normalizer import normalize_many

    raw = {
        "id": "same-id",
        "job-name": "Инженер",
        "duty": "d",
        "requirements": "r",
        "salary_min": 1,
        "salary_max": 2,
        "schedule": "s",
        "employment": "e",
        "addresses": {"address": [{"location": "l"}]},
    }

    # Передаем две вакансии с одинаковым ID, но разными названиями
    vacs = normalize_many([raw, {**raw, "job-name": "Инженер 2"}])

    assert len(vacs) == 1
    assert vacs[0].title == "Инженер 2"  # последняя версия перезаписывает
    print("дедупликация по id: OK")


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        test_check_mode_on_sample(Path(d))
    test_duplicate_ids_are_deduplicated()
    print("\nВсе проверки пайплайна пройдены.")
