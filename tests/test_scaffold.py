"""HexaArch 본체 테스트 — 생성기 결정론 + 생성물 형태."""

import pathlib
import tempfile
import unittest

from hexaarch.scaffold import scaffold
from hexaarch.spec import load_spec

EXAMPLE = pathlib.Path(__file__).resolve().parent.parent / "examples" / "seoul-apt" / "domain-spec.yaml"


def _snapshot(root: pathlib.Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*")) if p.is_file()
    }


class ScaffoldDeterminism(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec(EXAMPLE)

    def test_deterministic_byte_identical(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            scaffold(self.spec, d1)
            scaffold(self.spec, d2)
            self.assertEqual(_snapshot(pathlib.Path(d1)), _snapshot(pathlib.Path(d2)))

    def test_generates_state_machine_and_protected_region(self):
        with tempfile.TemporaryDirectory() as d:
            scaffold(self.spec, d)
            agg = (pathlib.Path(d) / "src/contexts/valuation/domain/analysis_eligibility.py").read_text()
            self.assertIn(">>> generated: do-not-edit", agg)
            self.assertIn(">>> impl: editable", agg)
            self.assertIn("def _transition", agg)
            # 결정표 CSV 스텁(range + 버저닝 컬럼)
            csv = (pathlib.Path(d) / "src/contexts/regulation/domain/decision_tables/loan_limit.csv").read_text()
            self.assertIn("version,effective_date,price_min,price_max,max_loan", csv)
            # 바이브코딩 규칙 파일 (AI 에이전트가 읽는다)
            agents = (pathlib.Path(d) / "AGENTS.md").read_text()
            self.assertIn("impl 블록 안에서만 짠다", agents)
            self.assertIn("hexaarch check", agents)


if __name__ == "__main__":
    unittest.main()
