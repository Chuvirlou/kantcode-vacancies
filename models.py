"""
models.py — внутренняя модель вакансии.

Граница между «сырым API» и анализатором/ИИ.
Нормализатор превращает raw dict -> Vacancy, дальше всё работает только с Vacancy.
Правила (rules.py) работают с raw dict напрямую — это осознанно, чтобы не зависеть
от модели. Vacancy нужна для ИИ-шага и для report.py (id, url).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Vacancy:
    id: str
    url: str | None = None
    title: str | None = None
    source: str | None = None

    company_name: str | None = None
    company_inn: str | None = None
    company_ogrn: str | None = None

    region_name: str | None = None
    region_code: str | None = None
    location: str | None = None
    lat: str | None = None
    lng: str | None = None

    salary_text: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    term_text: str | None = None

    employment: str | None = None
    schedule: str | None = None
    schedule_comment: str | None = None
    shift: list[str] = field(default_factory=list)

    duty: str | None = None
    requirements: str | None = None
    qualification: str | None = None

    education: str | None = None
    experience_years: int | None = None

    conditions: str | None = None
    work_places: int | None = None
    skills: list[str] = field(default_factory=list)
    medical_documents: str | None = None

    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def as_raw(self) -> dict[str, Any]:
        """Сырой dict для check_rules(). Правила работают с полями API."""
        return self.raw

    def text_fields(self) -> dict[str, str]:
        """
        Все непустые текстовые поля, где может быть спрятан график/оплата.
        Включает salary_text и term_text — иначе ИИ не увидит оплату в тексте.
        """
        candidates = {
            "duty": self.duty,
            "requirements": self.requirements,
            "qualification": self.qualification,
            "term.text": self.term_text,
            "salary": self.salary_text,
            "scheduleTypeComment": self.schedule_comment,
        }
        return {k: v.strip() for k, v in candidates.items() if v and v.strip()}

    def structured_fields(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.salary_min is not None:
            out["salary_min"] = self.salary_min
        if self.salary_max is not None:
            out["salary_max"] = self.salary_max
        if self.employment:
            out["employment"] = self.employment
        if self.schedule:
            out["schedule"] = self.schedule
        if self.shift:
            out["shift"] = list(self.shift)
        if self.schedule_comment:
            out["scheduleTypeComment"] = self.schedule_comment
        if self.location:
            out["location"] = self.location
        if self.education:
            out["education"] = self.education
        if self.experience_years is not None:
            out["experience"] = self.experience_years
        return out

    def has_employment(self) -> bool:
        return bool(self.employment and self.employment.strip())

    def has_schedule(self) -> bool:
        return bool(self.schedule and self.schedule.strip())
