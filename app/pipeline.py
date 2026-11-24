"""
app/pipeline.py — собирает всё, пишет report.json.

Правила получают сырой dict (Vacancy.as_raw()), ИИ — Vacancy (text_fields +
structured_fields). ИИ-шаг — заглушка, пока ai_check.py не готов.
"""

from __future__ import annotations

import sys
from pathlib import Path

from app.config import Config
from app.fetcher import FetchError
from app.loader import load_from_api, load_from_file
from app.report import build_report, read_last_success, write_last_success, write_report
from models import Vacancy
from normalizer import normalize_many


def _run_rules(vacancies: list[Vacancy], cfg: Config) -> dict[str, list[dict]]:
    if not cfg.rules_enabled:
        return {v.id: [] for v in vacancies}
    try:
        from rules import check_rules

        return {v.id: check_rules(v.as_raw()) for v in vacancies}
    except ImportError:
        print("[pipeline] rules.py не найден, правила пропущены", file=sys.stderr)
        return {v.id: [] for v in vacancies}


def _run_ai(vacancies: list[Vacancy], cfg: Config) -> dict[str, list[dict]]:
    if not cfg.ai_enabled:
        return {v.id: [] for v in vacancies}
    try:
        from app.ai_check import analyze
    except ImportError:
        print("[pipeline] ai_check недоступен, ИИ-шаг пропущен", file=sys.stderr)
        return {v.id: [] for v in vacancies}
    return {v.id: analyze(v) for v in vacancies}


def _merge(
    rule_issues: dict[str, list[dict]], ai_issues: dict[str, list[dict]]
) -> dict[str, list[dict]]:
    merged: dict[str, list[dict]] = {}
    for vid in set(rule_issues) | set(ai_issues):
        merged[vid] = rule_issues.get(vid, []) + ai_issues.get(vid, [])
    return merged


def run_api(cfg: Config) -> list[dict]:
    try:
        raws = load_from_api(cfg)
    except FetchError as exc:
        print(f"[pipeline] API недоступен: {exc}", file=sys.stderr)
        last = read_last_success(cfg.last_success_path)
        if last is not None:
            print(
                f"[pipeline] сохранён последний успешный отчёт: {cfg.last_success_path}",
                file=sys.stderr,
            )
        return last or []

    vacancies = normalize_many(raws)
    issues = _merge(_run_rules(vacancies, cfg), _run_ai(vacancies, cfg))
    report = build_report(vacancies, issues)
    write_report(cfg.output_path, report)
    write_last_success(cfg.last_success_path, report)
    return report


def run_file(cfg: Config, path: str | Path) -> list[dict]:
    raws = load_from_file(path)
    vacancies = normalize_many(raws)
    issues = _merge(_run_rules(vacancies, cfg), _run_ai(vacancies, cfg))
    report = build_report(vacancies, issues)
    write_report(cfg.output_path, report)
    return report
