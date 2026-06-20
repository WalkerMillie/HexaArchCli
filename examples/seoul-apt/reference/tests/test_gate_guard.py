"""#2 조건부 전이(거래량 가드) — A/B 동치 검증. (req: VAL-005)

게이트는 거래량 프록시로 잠금/해제된다. 두 방식이 같은 결과를 내는가.
"""

import unittest

from contexts.valuation.application.gate_service_a import GateServiceA
from contexts.valuation.application.gate_service_b import GateServiceB
from contexts.valuation.domain.analysis_eligibility_a import AnalysisEligibilityA
from contexts.valuation.domain.analysis_eligibility_b import AnalysisEligibilityB
from contexts.valuation.domain.gate_state import GateState
from tests.fakes import FakeLimitQuery, FakeVolumeQuery


class GateGuard(unittest.TestCase):
    def _service_a(self, count):
        return GateServiceA(FakeVolumeQuery(count), FakeLimitQuery(0)), AnalysisEligibilityA("c1")

    def _service_b(self, count):
        return GateServiceB(FakeVolumeQuery(count), FakeLimitQuery(0)), AnalysisEligibilityB("c1")

    def test_a_low_volume_stays_locked(self):
        svc, elig = self._service_a(count=1)   # < 3
        svc.reevaluate(elig)
        self.assertEqual(elig.state, GateState.LOCKED)

    def test_a_enough_volume_unlocks(self):
        svc, elig = self._service_a(count=5)   # >= 3
        svc.reevaluate(elig)
        self.assertEqual(elig.state, GateState.READY)

    def test_b_low_volume_stays_locked(self):
        svc, elig = self._service_b(count=1)
        svc.reevaluate(elig)
        self.assertEqual(elig.state, GateState.LOCKED)

    def test_b_enough_volume_unlocks(self):
        svc, elig = self._service_b(count=5)
        svc.reevaluate(elig)
        self.assertEqual(elig.state, GateState.READY)

    def test_ab_equivalent_relock_when_volume_dries(self):
        # READY 상태에서 거래량이 마르면 둘 다 LOCKED로 재잠금
        sa, ea = self._service_a(count=5); sa.reevaluate(ea)
        sb, eb = self._service_b(count=5); sb.reevaluate(eb)
        sa.volume_query = FakeVolumeQuery(0); sa.reevaluate(ea)
        sb.volume_query = FakeVolumeQuery(0); sb.reevaluate(eb)
        self.assertEqual(ea.state, GateState.LOCKED)
        self.assertEqual(eb.state, GateState.LOCKED)


if __name__ == "__main__":
    unittest.main()
