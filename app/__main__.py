"""
app/__main__.py — команды run (API) и check (локальный JSON).

python -m app run
python -m app check path/to/sample.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.config import Config
from app.pipeline import run_api, run_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("run", help="загрузить вакансии из API и записать отчёт")

    check = sub.add_parser("check", help="проверочный режим на локальном JSON")
    check.add_argument("path", type=Path)

    args = parser.parse_args(argv)
    cfg = Config.from_env()

    if args.command == "run":
        report = run_api(cfg)
        if not report:
            print("Отчёт пуст (API недоступен и нет last_success).", file=sys.stderr)
            return 2
    else:
        report = run_file(cfg, args.path)

    print(f"Вакансий в отчёте: {len(report)}")
    print(f"Замечаний: {sum(len(item['issues']) for item in report)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
