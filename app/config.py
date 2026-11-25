"""
app/config.py — настройки. Значения по умолчанию + переопределение из env.
Секреты (ключи ИИ) — только в env, не в репозитории.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Config:
    source_url: str = "https://opendata.trudvsem.ru/api/v1/vacancies/region/39"
    limit: int = 100
    max_pages: int = 2
    max_vacancies: int = 200
    timeout: int = 30
    retries: int = 3
    retry_backoff: float = 1.5
    user_agent: str = "Kantkod-Pipeline/1.0 (test assignment)"

    output_path: str = "report.json"
    last_success_path: str = "last_success.json"

    rules_enabled: bool = True
    ai_enabled: bool = True

    ai_provider: str = "local"
    ai_model: str = ""
    ai_api_key_env: str = "AI_API_KEY"

    @classmethod
    def from_env(cls) -> Config:
        cfg = cls()
        cfg.source_url = os.getenv("SOURCE_URL", cfg.source_url)
        cfg.limit = int(os.getenv("LIMIT", cfg.limit))
        cfg.max_pages = int(os.getenv("MAX_PAGES", cfg.max_pages))
        cfg.max_vacancies = int(os.getenv("MAX_VACANCIES", cfg.max_vacancies))
        cfg.timeout = int(os.getenv("TIMEOUT", cfg.timeout))
        cfg.retries = int(os.getenv("RETRIES", cfg.retries))
        cfg.output_path = os.getenv("OUTPUT_PATH", cfg.output_path)
        cfg.last_success_path = os.getenv("LAST_SUCCESS_PATH", cfg.last_success_path)
        cfg.rules_enabled = os.getenv("RULES_ENABLED", "1") == "1"
        cfg.ai_enabled = os.getenv("AI_ENABLED", "1") == "1"
        cfg.ai_provider = os.getenv("AI_PROVIDER", cfg.ai_provider)
        cfg.ai_model = os.getenv("AI_MODEL", cfg.ai_model)
        return cfg
