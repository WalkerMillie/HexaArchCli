"""§9-① 상태 전이 거부 테스트 — 허용 안 된 전이가 예외를 던지는가. (req: VAL-003)

A·B 두 Aggregate 모두 동일한 전이 규칙을 따르는지 확인.
"""

import unittest

from contexts.valuation.domain.analysis_eligibility_a import AnalysisEligibilityA
from contexts.valuation.domain.analysis_eligibility_b import AnalysisEligibilityB
from contexts.valuation.domain.exceptions import IllegalTransition
from contexts.valuation.domain.gate_state import GateState


class TransitionRejection(unittest.TestCase):
    def test_a_locked_cannot_jump_to_analyzed(self):
        elig = AnalysisEligibilityA("c1")  # LOCKED
        with self.assertRaises(IllegalTransition):
            elig.mark_analyzed()           # LOCKED -> ANALYZED 불허

    def test_a_locked_to_ready_ok(self):
        elig = AnalysisEligibilityA("c1")
        elig.unlock()
        self.assertEqual(elig.state, GateState.READY)

    def test_b_locked_cannot_jump_to_analyzed_via_transition(self):
        elig = AnalysisEligibilityB("c1")  # LOCKED
        with self.assertRaises(IllegalTransition):
            elig._transition(GateState.ANALYZED)

    def test_b_ready_to_analyzed_allowed(self):
        elig = AnalysisEligibilityB("c1")
        elig._transition(GateState.READY)
        elig._transition(GateState.ANALYZED)
        self.assertEqual(elig.state, GateState.ANALYZED)


if __name__ == "__main__":
    unittest.main()
