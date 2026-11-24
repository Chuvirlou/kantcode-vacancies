"""
app/fetcher.py — загрузка вакансий из API «Работа в России».

offset — номер страницы (0-based). Стоп: пустая страница, max_pages, max_vacancies.
При недоступности API — исключение FetchError; вызывающий решает, что делать
с последним успешным отчётом.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

from app.config import Config


class FetchError(Exception):
    """Не удалось получить данные из API."""


def _build_url(base: str, offset: int, limit: int) -> str:
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}{urllib.parse.urlencode({'offset': offset, 'limit': limit})}"


def fetch_page(cfg: Config, offset: int) -> dict:
    url = _build_url(cfg.source_url, offset, cfg.limit)
    request = urllib.request.Request(url, headers={"User-Agent": cfg.user_agent})

    last_error: Exception | None = None
    for attempt in range(1, cfg.retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=cfg.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
        ) as exc:
            last_error = exc
            if attempt < cfg.retries:
                time.sleep(cfg.retry_backoff * attempt)

    raise FetchError(f"Не удалось получить {url}: {last_error}")


def extract_vacancies(page: dict) -> list[dict]:
    results = page.get("results") or {}
    wrapper = results.get("vacancies") or []
    out = []
    for item in wrapper:
        if isinstance(item, dict) and isinstance(item.get("vacancy"), dict):
            out.append(item["vacancy"])
    return out


def fetch_vacancies(cfg: Config) -> list[dict]:
    """
    Загружает до cfg.max_vacancies вакансий (не более cfg.max_pages страниц).
    Возвращает список сырых vacancy-dict. При ошибке — FetchError.
    """
    collected: list[dict] = []
    for offset in range(cfg.max_pages):
        page = fetch_page(cfg, offset)
        vacancies = extract_vacancies(page)
        if not vacancies:
            break
        collected.extend(vacancies)
        if len(collected) >= cfg.max_vacancies:
            break

    return collected[: cfg.max_vacancies]
