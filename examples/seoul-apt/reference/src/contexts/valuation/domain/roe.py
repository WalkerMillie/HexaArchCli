"""레버리지 ROE — 순수 수식 (무상태 도메인, 한계 #5).

req: VAL-002  순익 = (매매가 × 가정상승률) − (대출액 × 실효금리);  ROE = 순익 / 자기자본
  예) 10억, 자기자본 4억, 대출 6억@5%, 상승 5% → 순익 2,000만 → ROE 5.0% (정책문서 §5.2)
"""

from contexts.valuation.domain.exceptions import InvariantViolation
from contexts.valuation.domain.value_objects import Money


def leverage_roe(
    price: Money,
    loan: Money,
    equity: Money,
    assumed_growth: float,
    effective_rate: float,
) -> float:
    if equity.won <= 0:
        raise InvariantViolation("자기자본은 양수여야 한다")
    gain = price.won * assumed_growth
    interest = loan.won * effective_rate
    net = gain - interest
    return net / equity.won
