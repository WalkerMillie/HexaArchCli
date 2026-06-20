"""본체 테스트 — 생성된 결정표 로직이 실제로 동작하는가 (실측).

생성 골격의 결정표 테스트를 서브프로세스로 돌리고(완전성·룩업·버저닝),
생성된 로더에 실제 CSV 데이터를 넣어 load→lookup→assert_complete까지 확인한다.
"""

import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

from hexaarch.scaffold import scaffold
from hexaarch.spec import load_spec

EXAMPLE = pathlib.Path(__file__).resolve().parent.parent / "examples" / "seoul-apt" / "domain-spec.yaml"
CSV_REL = "src/contexts/regulation/domain/decision_tables/loan_limit.csv"


class GeneratedDecisionTable(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec(EXAMPLE)

    def test_generated_project_tests_pass(self):
        # 생성 프로젝트의 전체 테스트(전이+경계+결정표)가 그대로 green인지.
        with tempfile.TemporaryDirectory() as d:
            scaffold(self.spec, d)
            env = {**os.environ, "PYTHONPATH": str(pathlib.Path(d) / "src")}
            r = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                cwd=d, env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_loader_roundtrip_with_real_data(self):
        # 실제 데이터(2개 버전)를 넣고 로더→평가기 동작 실측.
        with tempfile.TemporaryDirectory() as d:
            scaffold(self.spec, d)
            csv = pathlib.Path(d) / CSV_REL
            csv.write_text(csv.read_text() +
                "2026v1,2026-01-01,0,15,6\n"
                "2026v1,2026-01-01,15,,4\n"
                "2026v2,2026-07-01,0,15,5\n"
                "2026v2,2026-07-01,15,,3\n", encoding="utf-8")
            probe = (
                "from contexts.regulation.adapters.loan_limit_loader import load_loan_limit_table\n"
                "from datetime import date\n"
                "t = load_loan_limit_table()\n"
                "t.assert_complete()\n"
                "assert t.active_version_as_of(date(2026,3,1)) == '2026v1'\n"
                "assert t.active_version_as_of(date(2026,8,1)) == '2026v2'\n"
                "assert t.lookup(10, date(2026,3,1)) == '6'\n"
                "assert t.lookup(10, date(2026,8,1)) == '5'\n"
                "assert t.lookup(99, date(2026,8,1)) == '3'\n"
                "print('OK')\n"
            )
            env = {**os.environ, "PYTHONPATH": str(pathlib.Path(d) / "src")}
            r = subprocess.run([sys.executable, "-c", probe],
                               cwd=d, env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("OK", r.stdout)

    def test_incomplete_data_fails_assert(self):
        # 구간 공백이 있는 데이터는 assert_complete가 거부해야 (정책 완전성 강제).
        with tempfile.TemporaryDirectory() as d:
            scaffold(self.spec, d)
            csv = pathlib.Path(d) / CSV_REL
            csv.write_text(csv.read_text() +
                "2026v1,2026-01-01,0,15,6\n"
                "2026v1,2026-01-01,25,,2\n", encoding="utf-8")   # 15~25 공백
            probe = (
                "from contexts.regulation.adapters.loan_limit_loader import load_loan_limit_table\n"
                "from contexts.regulation.domain.exceptions import IncompleteDecisionTable\n"
                "t = load_loan_limit_table()\n"
                "try:\n"
                "    t.assert_complete(); print('NO-RAISE')\n"
                "except IncompleteDecisionTable:\n"
                "    print('REJECTED')\n"
            )
            env = {**os.environ, "PYTHONPATH": str(pathlib.Path(d) / "src")}
            r = subprocess.run([sys.executable, "-c", probe],
                               cwd=d, env=env, capture_output=True, text=True)
            self.assertIn("REJECTED", r.stdout, r.stderr)


if __name__ == "__main__":
    unittest.main()
