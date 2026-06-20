"""대출 한도 결정표 — range 룩업 + 버저닝 + 완전성 검사. (순수 도메인)

한계 실측:
  #6 연속값(가격) → 구간(range) 표현. 모든 조합 열거 불가 → 구간 겹침/공백만 검사(§16.3).
  #7 effective_date 버저닝 → 구버전·신버전 공존(§5.3 조건부 공존).
  §9-④ 완전성 — 빈칸/구간 공백/겹침 없는가.

CSV 파일 '읽기'는 어댑터(csv_loader). 여기는 파싱된 데이터에 대한 순수 판단만.
req: REG-001
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from contexts.regulation.domain.exceptions import IncompleteDecisionTable, NoMatchingBand
from shared.money import Money

EOK = 100_000_000


@dataclass(frozen=True)
class RangeRule:
    version: str
    effective_date: date
    price_min: Money
    price_max: Money | None   # None = 무한대
    max_loan: Money

    def contains(self, price: Money) -> bool:
        if price < self.price_min:
            return False
        return self.price_max is None or price < self.price_max


class LoanLimitTable:
    def __init__(self, rules: list[RangeRule]):
        self.rules = rules

    # ---- 버저닝 (#7) ----
    def active_version_as_of(self, as_of: date) -> str:
        eligible = {r.effective_date for r in self.rules if r.effective_date <= as_of}
        if not eligible:
            raise NoMatchingBand(f"{as_of} 시점에 유효한 규제 버전 없음")
        latest = max(eligible)
        return next(r.version for r in self.rules if r.effective_date == latest)

    def _rules_of(self, version: str) -> list[RangeRule]:
        return sorted(
            (r for r in self.rules if r.version == version),
            key=lambda r: r.price_min.won,
        )

    # ---- range 룩업 (#6) ----
    def max_loan_for(self, price: Money, as_of: date) -> Money:
        version = self.active_version_as_of(as_of)
        for r in self._rules_of(version):
            if r.contains(price):
                return r.max_loan
        raise NoMatchingBand(f"가격 {price.won}원이 어느 구간에도 안 걸림 (version={version})")

    # ---- 완전성 검사 (§9-④): 버전별 [0, ∞) 빈틈/겹침 없이 타일링 ----
    def check_completeness(self) -> list[str]:
        problems: list[str] = []
        for version in {r.version for r in self.rules}:
            rules = self._rules_of(version)
            if not rules:
                continue
            if rules[0].price_min != Money(0):
                problems.append(f"[{version}] 0원부터 시작 안 함 (시작={rules[0].price_min.won})")
            for prev, cur in zip(rules, rules[1:]):
                if prev.price_max is None:
                    problems.append(f"[{version}] 무한 구간 뒤에 또 구간 존재 (max=∞ 이후 {cur.price_min.won})")
                elif cur.price_min.won > prev.price_max.won:
                    problems.append(f"[{version}] 구간 공백: {prev.price_max.won}~{cur.price_min.won}")
                elif cur.price_min.won < prev.price_max.won:
                    problems.append(f"[{version}] 구간 겹침: {cur.price_min.won} < {prev.price_max.won}")
            if rules[-1].price_max is not None:
                problems.append(f"[{version}] 마지막 구간이 열려있지 않음 (max={rules[-1].price_max.won}, ∞이어야)")
        return problems

    def assert_complete(self) -> None:
        problems = self.check_completeness()
        if problems:
            raise IncompleteDecisionTable(problems)
