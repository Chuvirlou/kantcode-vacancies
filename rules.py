import re
from unicodedata import name

_WORD = re.compile(r"[^\W\d_]+")
_RUSSIAN_LETTER = re.compile(r"[а-яё]", re.IGNORECASE)
_LATIN_LOOKALIKES = "aceopxykmtbh"
_RUSSIAN_LOOKALIKES = "асеорхукмтвн"
_LOOKALIKE_TRANSLATION = str.maketrans(
    _LATIN_LOOKALIKES + _LATIN_LOOKALIKES.upper(),
    _RUSSIAN_LOOKALIKES + _RUSSIAN_LOOKALIKES.upper(),
)


def normalize_text(text: str) -> str:
    def normalize_word(match: re.Match) -> str:
        word = match.group()
        russian_count = len(_RUSSIAN_LETTER.findall(word))
        latin_count = sum(name(letter, "").startswith("LATIN ") for letter in word)
        if russian_count > latin_count:
            return word.translate(_LOOKALIKE_TRANSLATION)
        return word

    return _WORD.sub(normalize_word, text)


def _check_requirements(vacancy: dict) -> list:
    requirements = vacancy.get("requirements")
    if isinstance(requirements, str) and requirements.strip():
        return []

    return [
        {
            "topic": "Пропуск",
            "field": "requirements",
            "quote": "",
            "problem": "Не указаны требования к кандидату.",
            "recommendation": "Укажите, какое образование, опыт и навыки нужны для работы. Если специальных требований нет, напишите об этом.",
            "source": "rule",
        }
    ]


def _check_employment(vacancy: dict) -> list:
    employment = vacancy.get("employment")
    if isinstance(employment, str) and employment.strip():
        return []

    return [
        {
            "topic": "Пропуск",
            "field": "employment",
            "quote": "",
            "problem": "Не указан тип занятости.",
            "recommendation": "Укажите фактический тип занятости, например полную или частичную занятость.",
            "source": "rule",
        }
    ]


def _has_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _missing_issue(field: str, problem: str, recommendation: str) -> dict:
    return {
        "topic": "Пропуск",
        "field": field,
        "quote": "",
        "problem": problem,
        "recommendation": recommendation,
        "source": "rule",
    }


def _check_salary(vacancy: dict) -> list:
    for field in ("salary_min", "salary_max"):
        amount = vacancy.get(field)
        if isinstance(amount, str):
            amount = amount.strip()
        if amount and amount != "0":
            return []

    return [
        _missing_issue(
            "salary", "Не указан размер оплаты.", "Укажите размер оплаты или диапазон"
        )
    ]


def _check_job_name(vacancy: dict) -> list:
    title = vacancy.get("job-name")
    recommendation = "Укажите должность и уточните специализацию или вид работы."
    if not _has_text(title):
        return [
            _missing_issue("job-name", "Не указано название вакансии.", recommendation)
        ]

    general_titles = {"специалист", "работник", "сотрудник", "рабочий"}
    if normalize_text(title).strip().casefold() not in general_titles:
        return []

    return [
        {
            "topic": "Название",
            "field": "job-name",
            "quote": title,
            "problem": "По названию вакансии неясно, какую работу предстоит выполнять.",
            "recommendation": recommendation,
            "source": "rule",
        }
    ]


def _check_duty(vacancy: dict) -> list:
    if _has_text(vacancy.get("duty")):
        return []

    return [
        _missing_issue(
            "duty",
            "Не указаны обязанности.",
            "Перечислите основные задачи, которые сотрудник будет выполнять.",
        )
    ]


def _check_schedule(vacancy: dict) -> list:
    if _has_text(vacancy.get("schedule")):
        return []

    return [
        _missing_issue(
            "schedule",
            "Не указан график работы.",
            "Укажите рабочие дни и часы или порядок чередования смен.",
        )
    ]


def _check_address(vacancy: dict) -> list:
    addresses = vacancy.get("addresses")
    address_list = addresses.get("address") if isinstance(addresses, dict) else None
    if isinstance(address_list, list) and any(
        isinstance(address, dict) and _has_text(address.get("location"))
        for address in address_list
    ):
        return []

    return [
        _missing_issue(
            "addresses.address[].location",
            "Не указан адрес места работы.",
            "Укажите населённый пункт, улицу и номер дома по месту работы.",
        )
    ]


def _contradiction(field: str, quote: str, problem: str, recommendation: str) -> dict:
    return {
        "topic": "Противоречие",
        "field": field,
        "quote": quote,
        "problem": problem,
        "recommendation": recommendation,
        "source": "rule",
    }


def _check_salary_range(vacancy: dict) -> list:
    minimum = vacancy.get("salary_min")
    maximum = vacancy.get("salary_max")
    if not all(type(amount) in (int, float) for amount in (minimum, maximum)):
        return []
    if not minimum > maximum > 0:
        return []

    return [
        _contradiction(
            "salary",
            f"salary_min={minimum}; salary_max={maximum}",
            "Минимальная оплата выше максимальной.",
            "Проверьте и укажите верные границы оплаты",
        )
    ]


def _employment_kind(employment) -> str:
    if not _has_text(employment):
        return ""

    normalized = normalize_text(employment).casefold()
    full = bool(re.search(r"\bполная\b", normalized))
    part_time = bool(re.search(r"\b(?:частичная|неполная)\b", normalized))
    if full == part_time:
        return ""
    return "full" if full else "part_time"


def _check_employment_schedule(vacancy: dict) -> list:
    employment = vacancy.get("employment")
    kind = _employment_kind(employment)
    schedule = vacancy.get("schedule")
    if not kind or not _has_text(schedule):
        return []

    normalized = normalize_text(schedule).strip().casefold()
    if kind == "full":
        conflicting = re.search(r"\bнеполный\b", normalized) and not re.search(
            r"\bполный\b", normalized
        )
    else:
        conflicting = normalized == "полный рабочий день"
    if not conflicting:
        return []

    return [
        _contradiction(
            "schedule",
            f"employment={employment}; schedule={schedule}",
            "Тип занятости противоречит указанному графику работы.",
            "Уточните, какая занятость и какой график верны",
        )
    ]


_FULL_TIME_PHRASES = re.compile(
    r"\b(?:полный\s+рабочий\s+день|полная\s+занятость)\b", re.IGNORECASE
)
_PART_TIME_PHRASES = re.compile(
    r"\b(?:неполный\s+рабочий\s+день|неполная\s+занятость|(?:на\s+)?полставки|подработка)\b",
    re.IGNORECASE,
)


def _find_work_phrase(text: str, pattern: re.Pattern) -> re.Match | None:
    for match in pattern.finditer(text):
        before = text[: match.start()]
        after = text[match.end() :]
        negated_before = re.search(
            r"\b(?:не(?:\s+(?:предусмотрен[ао]?|предлагается|требуется))?|нет|без)\s+$",
            before,
            re.IGNORECASE,
        )
        if not negated_before and not re.match(r"\s+не\b", after, re.IGNORECASE):
            return match
    return None


def _check_employment_description(vacancy: dict) -> list:
    employment = vacancy.get("employment")
    kind = _employment_kind(employment)
    if not kind:
        return []

    if kind == "full":
        expected, conflicting = _FULL_TIME_PHRASES, _PART_TIME_PHRASES
    else:
        expected, conflicting = _PART_TIME_PHRASES, _FULL_TIME_PHRASES

    issues = []
    for field in ("duty", "requirements"):
        text = vacancy.get(field)
        if not _has_text(text):
            continue
        normalized = normalize_text(text)
        match = _find_work_phrase(normalized, conflicting)
        if match is None or _find_work_phrase(normalized, expected) is not None:
            continue

        phrase = text[match.start() : match.end()]
        issues.append(
            _contradiction(
                field,
                f"employment={employment}; {field}={phrase}",
                "Тип занятости в карточке противоречит описанию вакансии.",
                "Уточните, какая занятость верна: в карточке и в описании указано разное",
            )
        )
    return issues


_VAGUE_PHRASES = re.compile(
    r"\b(?:(?P<schedule>(?:гибкий|свободный)\s+график|ненормированный)"
    r"|(?P<salary>достойная\s+зарплата|конкурентная\s+(?:оплата|зарплата)|высокий\s+доход)"
    r"|по\s+договор[её]нности)\b",
    re.IGNORECASE,
)
_HOUR = r"(?:[01]?\d|2[0-4])"
_CLOCK_TIME = rf"{_HOUR}(?:[:.][0-5]\d)?"
_CLOCK_WITH_MINUTES = rf"{_HOUR}[:.][0-5]\d"
_WORK_TIME_DETAILS = re.compile(
    r"\b(?:пн|вт|ср|чт|пт|сб|вс|понедельник\w*|вторник\w*|сред[ауые]|"
    r"четверг\w*|пятниц\w*|суббот\w*|воскресень\w*|будни|будням|(?:будн|выходн)\w*\s+дн\w*)\b"
    r"|(?<![\d/])[1-9]\d?\s*/\s*[1-9]\d?(?![\d/])"
    rf"|\bс\s+{_CLOCK_TIME}\s+до\s+{_CLOCK_TIME}\b"
    rf"|\b{_CLOCK_WITH_MINUTES}\s*[-–—]\s*{_CLOCK_TIME}\b"
    rf"|\bс\s+{_CLOCK_TIME}\s*[-–—]\s*{_CLOCK_TIME}\b"
    r"|\b(?:сутки|день|ночь)\s+через\s+(?:сутки|день|ночь|двое|трое|четверо|\d+)\b"
    r"|\bдень\s*/\s*ночь\b"
    r"|\b(?:дневн\w*|ночн\w*|утренн\w*|вечерн\w*)\s+смен\w*\b"
    r"|\bсмен\w*\s*(?:(?:по|длительностью|составляет)\s+|[:–—-]\s*)?\d{1,2}\s*(?:час\w*|ч)\b"
    r"|\b(?:по\s+\d{1,2}\s*(?:час\w*|ч)|\d{1,2}[-‑– ]часов\w*\s+смен\w*)\b",
    re.IGNORECASE,
)
_SCHEDULE_RECOMMENDATION = "Уточните, в какие дни и смены нужно работать"
_SALARY_RECOMMENDATION = "Укажите размер оплаты или диапазон"


def _has_work_time_details(texts) -> bool:
    return any(
        _has_text(text) and _WORK_TIME_DETAILS.search(normalize_text(text))
        for text in texts
    )


def _shift_entries(shift) -> list:
    if isinstance(shift, str):
        shift = [shift]
    if not isinstance(shift, list):
        return []
    return [entry for entry in shift if _has_text(entry)]


def _agreement_subject(field: str, text: str, match: re.Match) -> str:
    if field in ("salary", "schedule"):
        return field

    # Look in the same clause for the condition being agreed on.
    before = re.split(r"[,.!?;\n]", text[: match.start()])[-1]
    after = re.split(r"[,.!?;\n]", text[match.end() :], maxsplit=1)[0]
    clause = before + " " + after
    pay = re.search(
        r"\b(?:оплат|зарплат|оклад|доход|ставк)\w*|\bзаработн\w*\s+плат",
        clause,
        re.IGNORECASE,
    )
    time = re.search(
        r"\b(?:график|расписан|смен)\w*|\bрабоч\w*\s+(?:врем|час)",
        clause,
        re.IGNORECASE,
    )
    if bool(pay) == bool(time):
        return ""
    return "salary" if pay else "schedule"


def _check_vague_phrases(vacancy: dict) -> list:
    fields = ("schedule", "salary", "duty", "requirements")
    has_work_time = _has_work_time_details(
        [vacancy.get(field) for field in ("schedule", "duty", "requirements")]
        + _shift_entries(vacancy.get("shift"))
    )
    amounts = (vacancy.get("salary_min"), vacancy.get("salary_max"))
    has_pay = any(type(amount) in (int, float) and amount > 0 for amount in amounts)
    agreement_recommendation = "Укажите, какое условие обсуждается, и приведите конкретные условия оплаты или графика"
    recommendations = {
        "schedule": "" if has_work_time else _SCHEDULE_RECOMMENDATION,
        "salary": "" if has_pay else _SALARY_RECOMMENDATION,
        "": "" if has_work_time and has_pay else agreement_recommendation,
    }
    missing_details = {
        "schedule": "не говорит, в какие дни и смены нужно работать",
        "salary": "не называет сумму",
        "": "не уточняет, что именно нужно согласовать — размер оплаты или график работы",
    }

    issues = []
    for field in fields:
        text = vacancy.get(field)
        if not _has_text(text):
            continue
        normalized = normalize_text(text)
        for match in _VAGUE_PHRASES.finditer(normalized):
            subject = match.lastgroup or _agreement_subject(field, normalized, match)
            recommendation = recommendations[subject]
            if recommendation:
                quote = text[match.start() : match.end()]
                issues.append(
                    {
                        "topic": "Неоднозначность",
                        "field": field,
                        "quote": quote,
                        "problem": f'Фраза "{quote}" {missing_details[subject]}.',
                        "recommendation": recommendation,
                        "source": "rule",
                    }
                )
    return issues


def _check_shift_schedule(vacancy: dict) -> list:
    schedule = vacancy.get("schedule")
    if not _has_text(schedule) or not re.search(
        r"смен", normalize_text(schedule), re.IGNORECASE
    ):
        return []

    shift = vacancy.get("shift", [])
    if any(
        " ".join(normalize_text(entry).casefold().split()) != "по графику сменности"
        for entry in _shift_entries(shift)
    ):
        return []
    if _has_work_time_details(
        vacancy.get(field) for field in ("schedule", "duty", "requirements")
    ):
        return []

    return [
        {
            "topic": "Неоднозначность",
            "field": "schedule",
            "quote": f"schedule={schedule}; shift={shift}",
            "problem": "Указана сменная работа, но расписание смен не описано.",
            "recommendation": "Уточните длительность смен, их чередование и время начала и окончания",
            "source": "rule",
        }
    ]


def _check_experience_contradiction(vacancy: dict) -> list:
    """
    Проверяет противоречие между структурным опытом (experience=0)
    и текстом в требовании/квалификации.
    """
    req = vacancy.get("requirement") or {}
    experience = req.get("experience")
    if experience != 0:
        return []

    text_to_check = " ".join(
        filter(
            None,
            [
                vacancy.get("requirements", ""),
                req.get("qualification", ""),
                vacancy.get("qualification", ""),
            ],
        )
    ).lower()

    # Ищем фразы вроде "опыт от 1 года", "не менее 3 лет", "5 лет"
    match = re.search(
        r"(?:опыт[^\d]{0,15}|не менее\s+)(\d+)\s*(?:год|лет)", text_to_check
    )
    if match and int(match.group(1)) > 0:
        quote = match.group(0)
        return [
            _contradiction(
                "requirement.experience",
                f"experience={experience}; в тексте: '{quote}'",
                "В структуре указан опыт 0 лет, но в тексте требуется опыт.",
                "Уточните требуемый опыт работы: укажите одинаковое значение в поле и описании",
            )
        ]
    return []


def _check_remote_office_contradiction(vacancy: dict) -> list:
    """
    Проверяет противоречие: в обязанностях удаленка, а в требованиях/адресе офис.
    """
    duty = normalize_text(vacancy.get("duty") or "").lower()
    req = vacancy.get("requirement") or {}
    qual = normalize_text(
        req.get("qualification") or vacancy.get("qualification") or ""
    ).lower()

    # Ищем удаленку в обязанностях
    remote_match = re.search(r"дистанционн|удаленн|на дому", duty)
    if not remote_match:
        return []

    # Ищем офис в квалификации/требованиях
    office_match = re.search(r"в офисе|присутствие|очн", qual)
    if not office_match:
        return []

    return [
        _contradiction(
            "duty",
            f"duty: '{remote_match.group(0)}'; requirement: '{office_match.group(0)}'",
            "В обязанностях указана удалённая работа, а в требованиях — присутствие в офисе.",
            "Уточните формат работы: удалённо или в офисе",
        )
    ]


def check_rules(vacancy: dict) -> list:
    return [
        *_check_requirements(vacancy),
        *_check_employment(vacancy),
        *_check_salary(vacancy),
        *_check_job_name(vacancy),
        *_check_duty(vacancy),
        *_check_schedule(vacancy),
        *_check_address(vacancy),
        *_check_salary_range(vacancy),
        *_check_employment_schedule(vacancy),
        *_check_employment_description(vacancy),
        *_check_vague_phrases(vacancy),
        *_check_shift_schedule(vacancy),
        # --- НОВЫЕ ПРАВИЛА ---
        *_check_experience_contradiction(vacancy),
        *_check_remote_office_contradiction(vacancy),
    ]
