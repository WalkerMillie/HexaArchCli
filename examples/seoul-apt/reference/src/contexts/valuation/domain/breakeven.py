"""손익분기 상승률 — 순수 수식 (무상태 도메인, 한계 #5의 실체).

req: VAL-001  손익분기 상승률(%) = 대출비중 × 실효금리
  예) 대출 6억 / 매매 10억(60%) × 금리 5% = 연 3.0% 이상 올라야 본전 (정책문서 §5.1)

이 모듈엔 상태기계가 없다 — §4.1 스키마(states/transitions 중심)로는 표현 못 하는
'계산 도메인'. 생성기는 이런 도메인을 kind: calculation 으로 다뤄야 함(스키마 확장 #5).
"""

from contexts.valuation.domain.exceptions import InvariantViolation
from contexts.valuation.domain.value_objects import Money


def breakeven_rate(loan: Money, price: Money, effective_rate: float) -> float:
    if price.won <= 0:
        raise InvariantViolation("매매가는 양수여야 한다")
    loan_ratio = loan.won / price.won
    return loan_ratio * effective_rate
