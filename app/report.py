"""
app/report.py — сборка отчёта и атомарная запись.

Формат (SPEC.md): список {id, url, issues: []}.
Дедупликация замечаний по (topic, field, quote).
last_success.json — последний успешный отчёт; не перезаписывается при ошибке API.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from models import Vacancy


def _issue_key(issue: dict) -> tuple:
    return (issue.get("topic"), issue.get("field"), issue.get("quote"))


def dedupe_issues(issues: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    out: list[dict] = []
    for issue in issues:
        key = _issue_key(issue)
        if key in seen:
            continue
        seen.add(key)
        out.append(issue)
    return out


def build_report(
    vacancies: list[Vacancy], issues_by_id: dict[str, list[dict]]
) -> list[dict]:
    report = []
    for v in vacancies:
        report.append(
            {
                "id": v.id,
                "url": v.url,
                "issues": dedupe_issues(issues_by_id.get(v.id, [])),
            }
        )
    return report


def _atomic_write(path: str | Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def write_report(path: str | Path, report: list[dict]) -> None:
    _atomic_write(path, report)


def write_last_success(path: str | Path, report: list[dict]) -> None:
    _atomic_write(path, report)


def read_last_success(path: str | Path) -> list[dict] | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
