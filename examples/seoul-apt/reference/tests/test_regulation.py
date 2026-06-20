"""regulation 결정표 — range 룩업(#6) + 버저닝(#7) + 완전성(§9-④, 이빨 포함). req: REG-001"""

import unittest
from datetime import date

from contexts.regulation.adapters.csv_loader import load_loan_limit_table
from contexts.regulation.domain.decision_table import EOK, LoanLimitTable, RangeRule
from contexts.regulation.domain.exceptions import IncompleteDecisionTable
from shared.money import Money


class DecisionTableTest(unittest.TestCase):
    def setUp(self):
        self.table = load_loan_limit_table()

    def test_range_lookup_v1(self):
        d = date(2026, 6, 20)   # → 2026v1
        self.assertEqual(self.table.max_loan_for(Money(10 * EOK), d), Money(6 * EOK))
        self.assertEqual(self.table.max_loan_for(Money(20 * EOK), d), Money(4 * EOK))
        self.assertEqual(self.table.max_loan_for(Money(30 * EOK), d), Money(2 * EOK))

    def test_band_edge_inclusive_lower(self):
        d = date(2026, 6, 20)
        self.assertEqual(self.table.max_loan_for(Money(15 * EOK), d), Money(4 * EOK))  # 15 → [15,25)

    def test_versioning_coexistence(self):
        # #7 조건부 공존: 같은 표에 v1·v2 공존, as_of로 선택
        self.assertEqual(self.table.max_loan_for(Money(10 * EOK), date(2026, 6, 20)), Money(6 * EOK))
        self.assertEqual(self.table.max_loan_for(Money(10 * EOK), date(2026, 8, 1)), Money(5 * EOK))

    def test_completeness_ok(self):
        self.assertEqual(self.table.check_completeness(), [])

    def test_completeness_detects_gap(self):
        bad = LoanLimitTable([
            RangeRule("x", date(2026, 1, 1), Money(0), Money(10 * EOK), Money(6 * EOK)),
            RangeRule("x", date(2026, 1, 1), Money(12 * EOK), None, Money(2 * EOK)),  # 공백 10~12
        ])
        with self.assertRaises(IncompleteDecisionTable):
            bad.assert_complete()
        self.assertTrue(any("공백" in p for p in bad.check_completeness()))

    def test_completeness_detects_overlap(self):
        bad = LoanLimitTable([
            RangeRule("x", date(2026, 1, 1), Money(0), Money(15 * EOK), Money(6 * EOK)),
            RangeRule("x", date(2026, 1, 1), Money(10 * EOK), None, Money(2 * EOK)),  # 겹침
        ])
        self.assertTrue(any("겹침" in p for p in bad.check_completeness()))


if __name__ == "__main__":
    unittest.main()
