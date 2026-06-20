"""[Approach A] 얇은 Aggregate — 전이는 무조건만. 가드/불변식은 밖(정책+유스케이스).

대조군. 가드/크로스규칙은 여기 없다 → policies.py + application 에서 조립.
장점: Aggregate가 단순. 단점: '판단'이 도메인 정책객체와 유스케이스로 분산됨.
"""

from contexts.valuation.domain.exceptions import IllegalTransition
from contexts.valuation.domain.gate_state import ALLOWED, GateState


class AnalysisEligibilityA:
    def __init__(self, complex_id: str, state: GateState = GateState.LOCKED):
        self.complex_id = complex_id
        self.state = state

    def _transition(self, to: GateState) -> None:
        if to not in ALLOWED[self.state]:
            raise IllegalTransition(self.state, to)   # 방어선 A
        self.state = to

    # 어댑터/유스케이스는 이 무조건 메서드들만 호출한다.
    def unlock(self) -> None:
        self._transition(GateState.READY)

    def lock(self) -> None:
        self._transition(GateState.LOCKED)

    def mark_analyzed(self) -> None:
        self._transition(GateState.ANALYZED)
