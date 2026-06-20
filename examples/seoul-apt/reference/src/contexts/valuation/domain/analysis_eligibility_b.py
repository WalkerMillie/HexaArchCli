"""[Approach B] 가드/불변식을 Aggregate에 내장. (한계 #2/#3 처리안 B)

B안 철학: 조건부 전이(가드)와 크로스 불변식을 Aggregate 메서드 안에서 강제한다.
크로스 데이터(거래량·규제한도)는 '값(VO)'으로 주입받으므로 도메인은 여전히 다른
컨텍스트/인프라를 import하지 않는다 (§2 유지). 판단이 한 곳(Aggregate)에 응집됨.
"""

from contexts.valuation.domain.breakeven import breakeven_rate
from contexts.valuation.domain.exceptions import IllegalTransition, InvariantViolation
from contexts.valuation.domain.gate_state import ALLOWED, GateState
from contexts.valuation.domain.roe import leverage_roe
from contexts.valuation.domain.value_objects import Money, VolumeStat

# req: VAL-005
DEFAULT_MIN_TRADES = 3


class AnalysisEligibilityB:
    def __init__(self, complex_id: str, state: GateState = GateState.LOCKED):
        self.complex_id = complex_id
        self.state = state

    def _transition(self, to: GateState) -> None:
        if to not in ALLOWED[self.state]:
            raise IllegalTransition(self.state, to)   # 방어선 A
        self.state = to

    # req: VAL-005  #2 조건부 전이 — 가드를 메서드 안에 내장
    def reevaluate(self, vol: VolumeStat, *, min_trades: int = DEFAULT_MIN_TRADES) -> None:
        target = GateState.READY if vol.recent_count >= min_trades else GateState.LOCKED
        if target == self.state:
            return
        self._transition(target)

    # req: VAL-004  #3 크로스 불변식 — 대출액 ≤ 규제한도일 때만 분석 산출
    def analyze(
        self,
        *,
        loan: Money,
        price: Money,
        equity: Money,
        effective_rate: float,
        assumed_growth: float,
        reg_limit: Money,        # regulation 한도를 값으로 주입 (포트로 읽어 전달)
    ) -> dict:
        if self.state != GateState.READY:
            raise InvariantViolation("게이트가 READY가 아니면 분석 불가")  # 게이트 불변식
        if not (loan <= reg_limit):
            raise InvariantViolation("대출액 > 규제한도 → 분석 무효")     # 방어선 B (#3)
        result = {
            "breakeven": breakeven_rate(loan, price, effective_rate),
            "roe": leverage_roe(price, loan, equity, assumed_growth, effective_rate),
        }
        self._transition(GateState.ANALYZED)
        return result
