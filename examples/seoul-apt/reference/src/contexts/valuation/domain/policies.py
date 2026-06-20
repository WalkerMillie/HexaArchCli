"""[Approach A] 가드/조건을 도메인 '정책객체'로 분리. (한계 #2/#3 처리안 A)

A안 철학: Aggregate는 무조건 전이만 아는 '얇은' 객체로 두고, 조건부 판단(가드)과
크로스 컨텍스트 규칙은 별도 정책객체가 처리한다. 정책객체도 도메인 코어에 있으므로
§2(판단은 코어)는 지킨다 — 단지 Aggregate 밖, 같은 도메인 안.
"""

from contexts.valuation.domain.value_objects import Money, VolumeStat

# req: VAL-005  매물 게이트 MVP = 거래량 프록시 (최근 거래 N건 미만이면 잠김)
DEFAULT_MIN_TRADES = 3


class GateEligibilityPolicy:
    """#2 조건부 전이의 가드: 거래량이 임계 이상이면 잠금 해제 가능."""

    def __init__(self, min_trades: int = DEFAULT_MIN_TRADES):
        self.min_trades = min_trades

    def is_unlockable(self, vol: VolumeStat) -> bool:
        return vol.recent_count >= self.min_trades


class LoanRegulationPolicy:
    """#3 크로스 컨텍스트 불변식: 대출액 ≤ regulation 한도."""

    def within_limit(self, loan: Money, reg_limit: Money) -> bool:
        return loan <= reg_limit
