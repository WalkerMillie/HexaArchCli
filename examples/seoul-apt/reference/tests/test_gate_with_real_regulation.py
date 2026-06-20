"""#3 크로스 불변식을 '실물'로 닫기 — FakeLimitQuery 대신 진짜 결정표 어댑터로 게이트 분석.

게이트(valuation, B안) + 결정표(regulation) + 합성루트 배선이 한 줄기로 동작하는지 검증.
"""

import unittest
from datetime import date

from composition.wiring import DecisionTableLimitAdapter
from contexts.regulation.adapters.csv_loader import load_loan_limit_table
from contexts.regulation.domain.decision_table import EOK
from contexts.valuation.application.gate_service_b import GateServiceB
from contexts.valuation.domain.analysis_eligibility_b import AnalysisEligibilityB
from contexts.valuation.domain.exceptions import InvariantViolation
from contexts.valuation.domain.gate_state import GateState
from shared.money import Money
from tests.fakes import EQUITY, GROWTH, PRICE, RATE, FakeVolumeQuery


class GateWithRealRegulation(unittest.TestCase):
    def setUp(self):
        table = load_loan_limit_table()
        # 단지 c1 시가 10억 → v1 구간 [0,15) → 한도 6억
        self.limit = DecisionTableLimitAdapter(
            table, price_of={"c1": Money(10 * EOK)}, as_of=date(2026, 6, 20)
        )

    def _ready_gate(self):
        svc = GateServiceB(FakeVolumeQuery(9), self.limit)
        elig = AnalysisEligibilityB("c1")
        svc.reevaluate(elig)   # 거래량 9 → READY
        return svc, elig

    def test_loan_within_real_limit_ok(self):
        svc, elig = self._ready_gate()
        res = svc.analyze(elig, loan=Money(6 * EOK), price=PRICE,
                          equity=EQUITY, effective_rate=RATE, assumed_growth=GROWTH)
        self.assertEqual(elig.state, GateState.ANALYZED)
        self.assertAlmostEqual(res["breakeven"], 0.03)
        self.assertAlmostEqual(res["roe"], 0.05)

    def test_loan_over_real_limit_rejected(self):
        svc, elig = self._ready_gate()
        with self.assertRaises(InvariantViolation):   # 대출 7억 > 한도 6억
            svc.analyze(elig, loan=Money(7 * EOK), price=PRICE,
                        equity=EQUITY, effective_rate=RATE, assumed_growth=GROWTH)


if __name__ == "__main__":
    unittest.main()
