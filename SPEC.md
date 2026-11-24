Проект: проверяем, понятно ли описаны вакансии Калининградской области.
Язык: Python. Библиотеки: requests, pydantic, pytest.
Файлы:
  app/fetcher.py   - скачивает вакансии из API
  app/rules.py     - проверки без ИИ
  app/ai_check.py  - проверки через ИИ
  app/pipeline.py  - собирает всё, пишет report.json
  app/__main__.py  - команды run и check
Замечание (Issue): topic, field, quote, problem, recommendation, source.
Отчёт: список {id, url, issues: []}. Нет замечаний = пустой список.
Главная функция проверки: analyze(vacancy) -> список замечаний.
Не выдумывать факты. Не писать про нарушение закона.
Ключи только в переменных окружения.