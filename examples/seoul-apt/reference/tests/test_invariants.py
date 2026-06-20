"""§9-② 불변식 + #3 크로스 컨텍스트 불변식 + 수식 정확성. (req: VAL-001/002/004)

A/B 모두: 대출액 > 규제한도면 분석 산출 불가. 정책문서 워크드 예시로 수식 검증.
"""

import unittest

from contexts.valuation.application.gate_service_a import GateServiceA
from contexts.valuation.application.gate_service_b import GateServiceB
from contexts.valuation.domain.analysis_eligibility_a import AnalysisEligibilityA
from contexts.valuation.domain.analysis_eligibility_b import AnalysisEligibilityB
from contexts.valuation.domain.exceptions import InvariantViolation
from contexts.valuation.domain.gate_state import GateState
from tests.fakes import EOK, EQUITY, GROWTH, LOAN, PRICE, RATE, FakeLimitQuery, FakeVolumeQuery


class CrossContextInvariant(unittest.TestCase):
    """#3 — 대출액 ≤ 규제한도일 때만 분석 유효."""

    def _ready_a(self, limit_won):
        svc = GateServiceA(FakeVolumeQuery(9), FakeLimitQuery(limit_won))
        elig = AnalysisEligibilityA("c1"); svc.reevaluate(elig)  # → READY
        return svc, elig

    def _ready_b(self, limit_won):
        svc = GateServiceB(FakeVolumeQuery(9), FakeLimitQuery(limit_won))
        elig = AnalysisEligibilityB("c1"); svc.reevaluate(elig)
        return svc, elig

    def _kw(self):
        return dict(loan=LOAN, price=PRICE, equity=EQUITY, effective_rate=RATE, assumed_growth=GROWTH)

    def test_a_over_limit_rejected(self):
        svc, elig = self._ready_a(limit_won=4 * EOK)  # 한도 4억 < 대출 6억
        with self.assertRaises(InvariantViolation):
            svc.analyze(elig, **self._kw())
        self.assertEqual(elig.state, GateState.READY)  # 산출 안 됐으니 상태 안 변함

    def test_a_within_limit_ok(self):
        svc, elig = self._ready_a(limit_won=6 * EOK)  # 한도 6억 == 대출 6억
        res = svc.analyze(elig, **self._kw())
        self.assertEqual(elig.state, GateState.ANALYZED)
        self.assertAlmostEqual(res["breakeven"], 0.03)
        self.assertAlmostEqual(res["roe"], 0.05)

    def test_b_over_limit_rejected(self):
        svc, elig = self._ready_b(limit_won=4 * EOK)
        with self.assertRaises(InvariantViolation):
            svc.analyze(elig, **self._kw())
        self.assertEqual(elig.state, GateState.READY)

    def test_b_within_limit_ok(self):
        svc, elig = self._ready_b(limit_won=6 * EOK)
        res = svc.analyze(elig, **self._kw())
        self.assertEqual(elig.state, GateState.ANALYZED)
        self.assertAlmostEqual(res["breakeven"], 0.03)
        self.assertAlmostEqual(res["roe"], 0.05)

    def test_cannot_analyze_when_locked(self):
        # 게이트 불변식: LOCKED에선 분석 불가 (A·B 공통)
        sa = GateServiceA(FakeVolumeQuery(0), FakeLimitQuery(6 * EOK)); ea = AnalysisEligibilityA("c1")
        sb = GateServiceB(FakeVolumeQuery(0), FakeLimitQuery(6 * EOK)); eb = AnalysisEligibilityB("c1")
        with self.assertRaises(InvariantViolation):
            sa.analyze(ea, **self._kw())
        with self.assertRaises(InvariantViolation):
            sb.analyze(eb, **self._kw())


if __name__ == "__main__":
    unittest.main()
