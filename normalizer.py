"""
normalizer.py — приведение сырого ответа API к внутренней модели Vacancy.

Работает и для рабочего режима (API), и для проверочного (локальный JSON).
Правила (rules.py) получают сырой dict (Vacancy.as_raw()), ИИ и отчёт — Vacancy.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from models import Vacancy


def _get(d: Any, *path, default=None):
    cur = d
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def _first_address(vac: dict) -> dict:
    addrs = _get(vac, "addresses", "address")
    if isinstance(addrs, list) and addrs and isinstance(addrs[0], dict):
        return addrs[0]
    return {}


def _to_int(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_str(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_vacancy(raw: dict) -> Vacancy:
    """Один сырой dict (внутренний объект vacancy) -> Vacancy."""
    addr = _first_address(raw)
    req = raw.get("requirement") or {}
    if not isinstance(req, dict):
        req = {}
        # --- НАЧАЛО ПРАВКИ ---
    # Обогащаем сырой словарь, чтобы rules.py видел вложенные поля
    if req.get("qualification") and not raw.get("qualification"):
        raw["qualification"] = req.get("qualification")
    # --- КОНЕЦ ПРАВКИ ---

    return Vacancy(
        id=_to_str(raw.get("id")) or "",
        url=_to_str(raw.get("vac_url")),
        title=_to_str(raw.get("job-name")),
        source=_to_str(raw.get("source")),
        company_name=_to_str(_get(raw, "company", "name")),
        company_inn=_to_str(_get(raw, "company", "inn")),
        company_ogrn=_to_str(_get(raw, "company", "ogrn")),
        region_name=_to_str(_get(raw, "region", "name")),
        region_code=_to_str(_get(raw, "region", "region_code")),
        location=_to_str(addr.get("location")),
        lat=_to_str(addr.get("lat")),
        lng=_to_str(addr.get("lng")),
        salary_text=_to_str(raw.get("salary")),
        salary_min=_to_int(raw.get("salary_min")),
        salary_max=_to_int(raw.get("salary_max")),
        currency=_to_str(raw.get("currency")),
        term_text=_to_str(_get(raw, "term", "text")),
        employment=_to_str(raw.get("employment")),
        schedule=_to_str(raw.get("schedule")),
        schedule_comment=_to_str(raw.get("scheduleTypeComment")),
        shift=[s for s in (raw.get("shift") or []) if isinstance(s, str) and s.strip()],
        duty=_to_str(raw.get("duty")),
        requirements=_to_str(raw.get("requirements")),
        # Важное исправление для учебных данных:
        qualification=_to_str(raw.get("qualification") or req.get("qualification")),
        education=_to_str(req.get("education")),
        experience_years=_to_int(req.get("experience")),
        conditions=_to_str(raw.get("conditions")),
        work_places=_to_int(raw.get("work_places")),
        skills=[
            s for s in (raw.get("skills") or []) if isinstance(s, str) and s.strip()
        ],
        medical_documents=_to_str(raw.get("medicalDocuments")),
        raw=raw,
    )


def extract_vacancies_from_api_response(data: dict) -> list[dict]:
    wrapper = _get(data, "results", "vacancies")
    if not isinstance(wrapper, list):
        return []
    out = []
    for item in wrapper:
        if isinstance(item, dict) and isinstance(item.get("vacancy"), dict):
            out.append(item["vacancy"])
    return out


def detect_and_extract(data) -> tuple[str, list[dict]]:
    """
    Автоопределение формата локального JSON (проверочный режим).
    """
    if isinstance(data, dict):
        if isinstance(_get(data, "results", "vacancies"), list):
            return "api_response", extract_vacancies_from_api_response(data)
        if isinstance(data.get("vacancies"), list):
            return "wrapper", _unwrap(data["vacancies"])
    if isinstance(data, list):
        has_wrapper = any(
            isinstance(i, dict) and isinstance(i.get("vacancy"), dict) for i in data
        )
        fmt = "list_with_wrapper" if has_wrapper else "list_flat"
        return fmt, _unwrap(data)
    raise ValueError(f"Неизвестный формат JSON: {type(data)}")


def _unwrap(items: list) -> list[dict]:
    out = []
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("vacancy"), dict):
            out.append(item["vacancy"])
        elif isinstance(item, dict):
            out.append(item)
    return out


def normalize_many(raws: list[dict]) -> list[Vacancy]:
    """
    Список сырых vacancy-dict -> список Vacancy, дедупликация по id.
    """
    by_id: dict[str, Vacancy] = {}
    for raw in raws:
        vac = normalize_vacancy(raw)
        if not vac.id:
            continue
        by_id[vac.id] = vac
    return list(by_id.values())


def load_raws_from_file(path: str | Path) -> list[dict]:
    """Проверочный режим: локальный JSON -> список сырых vacancy-dict."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    _, raws = detect_and_extract(data)
    return raws


def load_vacancies_from_file(path: str | Path) -> list[Vacancy]:
    """Проверочный режим: локальный JSON -> список Vacancy."""
    return normalize_many(load_raws_from_file(path))
