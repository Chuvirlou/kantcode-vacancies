"""
app/loader.py — единая точка входа для данных.

Рабочий режим:  load_from_api(cfg)  -> list[raw dict]
Проверочный:    load_from_file(path) -> list[raw dict]
Оба возвращают сырые dict в формате API; нормализация — в normalizer.py.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.config import Config
from app.fetcher import fetch_vacancies
from normalizer import detect_and_extract


def load_from_api(cfg: Config) -> list[dict]:
    return fetch_vacancies(cfg)


def load_from_file(path: str | Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    _, raws = detect_and_extract(data)
    return raws
