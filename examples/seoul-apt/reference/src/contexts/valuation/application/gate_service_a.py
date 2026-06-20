"""[Approach A] 유스케이스가 포트로 크로스 데이터를 읽어 '판단을 조립'한다.

A안에서는 application이 두꺼워진다: 포트로 거래량/한도를 읽고, 정책객체로 판정한 뒤,
얇은 Aggregate의 무조건 메서드를 호출한다. ← 판단이 여기로도 샐 위험 지점(§2 주의).
"""

from contexts.valuation.domain.analysis_eligibility_a import AnalysisEligibilityA
from contexts.valuation.domain.breakeven import breakeven_rate
from contexts.valuation.domain.exceptions import InvariantViolation
from contexts.valuation.domain.gate_state import GateState
from contexts.valuation.domain.policies import GateEligibilityPolicy, LoanRegulationPolicy
from contexts.valuation.domain.roe import leverage_roe
from contexts.valuation.domain.value_objects import Money
from contexts.valuation.ports.regulation_limit_query import RegulationLimitQuery
from contexts.valuation.ports.trade_volume_query import TradeVolumeQuery


class GateServiceA:
    def __init__(
        self,
        volume_query: TradeVolumeQuery,
        limit_query: RegulationLimitQuery,
        gate_policy: GateEligibilityPolicy | None = None,
        loan_policy: LoanRegulationPolicy | None = None,
    ):
        self.volume_query = volume_query
        self.limit_query = limit_query
        self.gate_policy = gate_policy or GateEligibilityPolicy()
        self.loan_policy = loan_policy or LoanRegulationPolicy()

    def reevaluate(self, elig: AnalysisEligibilityA) -> None:
        vol = self.volume_query.recent(elig.complex_id)        # 포트로 #2 데이터
        unlockable = self.gate_policy.is_unlockable(vol)       # 정책객체가 가드 판정
        if unlockable and elig.state == GateState.LOCKED:
            elig.unlock()
        elif not unlockable and elig.state in (GateState.READY, GateState.ANALYZED):
            elig.lock()

    def analyze(
        self,
        elig: AnalysisEligibilityA,
        *,
        loan: Money,
        price: Money,
        equity: Money,
        effective_rate: float,
        assumed_growth: float,
    ) -> dict:
        if elig.state != GateState.READY:
            raise InvariantViolation("게이트가 READY가 아니면 분석 불가")
        reg_limit = self.limit_query.max_loan(elig.complex_id)  # 포트로 #3 데이터
        if not self.loan_policy.within_limit(loan, reg_limit):  # 정책객체가 불변식 판정
            raise InvariantViolation("대출액 > 규제한도 → 분석 무효")
        result = {
            "breakeven": breakeven_rate(loan, price, effective_rate),
            "roe": leverage_roe(price, loan, equity, assumed_growth, effective_rate),
        }
        elig.mark_analyzed()
        return result
