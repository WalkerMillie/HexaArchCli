"""어댑터 — CSV 파일을 읽어 LoanLimitTable로 변환. (입출력. 판단 금지)

파일 '읽기'만 한다. 완전성 판단·룩업은 도메인(decision_table.py)이 한다.
"""

import csv
import pathlib
from datetime import date

from contexts.regulation.domain.decision_table import EOK, LoanLimitTable, RangeRule
from shared.money import Money

DEFAULT_CSV = pathlib.Path(__file__).resolve().parent.parent / "domain" / "decision_tables" / "loan_limit.csv"


def load_loan_limit_table(path: pathlib.Path = DEFAULT_CSV) -> LoanLimitTable:
    rules: list[RangeRule] = []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(row for row in f if not row.lstrip().startswith("#"))
        for row in reader:
            pmax = row["price_max_eok"].strip()
            rules.append(
                RangeRule(
                    version=row["version"].strip(),
                    effective_date=date.fromisoformat(row["effective_date"].strip()),
                    price_min=Money(int(row["price_min_eok"]) * EOK),
                    price_max=Money(int(pmax) * EOK) if pmax else None,
                    max_loan=Money(int(row["max_loan_eok"]) * EOK),
                )
            )
    return LoanLimitTable(rules)
