"""본체 테스트 — calculation/reference 생성 + 산문형(한글·공백·특수문자) 이름의 안전 식별자화.

검증을 통과한 어떤 스펙이든 생성물은 전부 유효한 파이썬이어야 한다(ast.parse).
결정표명·입력/출력·포트·수식명이 한글이어도 깨지지 않고, 원본명은 주석으로 보존.
"""

import ast
import pathlib
import tempfile
import unittest

from hexaarch.check import check
from hexaarch.scaffold import scaffold
from hexaarch.spec import Spec

PROSE = Spec.model_validate({
    "version": "0.1",
    "infrastructure": {"database": "pg", "messaging": "ev"},
    "contexts": [{
        "name": "valuation",
        "domains": {
            "Gate": {"kind": "aggregate", "states": ["A", "B"], "transitions": {"A": ["B"]},
                     "ports_out": ["국토부 실거래가 REST API", "ECOS 금리 REST API", "매물 카운트 폴링(개인용)"]},
            "Calc": {"kind": "calculation",
                     "formulas": [{"id": "VAL-F1", "name": "손익분기 상승률 = 대출비중 × 금리"}]},
            "Ref": {"kind": "reference"},
        },
        "decision_tables": [{"name": "가격대별 대출 한도", "kind": "range",
                             "inputs": ["시가"], "output": "최대 한도", "versioned": True, "id": "DT-1"}],
    }],
})

DOM = "src/contexts/valuation/domain"


def _all_py(root):
    return sorted(root.rglob("*.py"))


class Polish(unittest.TestCase):
    def test_all_generated_python_is_valid(self):
        with tempfile.TemporaryDirectory() as d:
            scaffold(PROSE, d)
            for p in _all_py(pathlib.Path(d)):
                ast.parse(p.read_text(encoding="utf-8"))   # SyntaxError면 실패

    def test_check_passes_on_prose_spec(self):
        with tempfile.TemporaryDirectory() as d:
            scaffold(PROSE, d)
            report = check(PROSE, d)
            self.assertTrue(report.ok, "\n".join(str(v) for v in report.violations))

    def test_calculation_has_function_slot(self):
        with tempfile.TemporaryDirectory() as d:
            scaffold(PROSE, d)
            calc = (pathlib.Path(d) / DOM / "calc.py").read_text()
            ast.parse(calc)
            self.assertIn("def val_f1(", calc)     # 한글 수식명 → id 폴백 함수명
            self.assertIn("VAL-F1", calc)          # req-id 추적성(생성 마커)

    def test_reference_stub_generated(self):
        with tempfile.TemporaryDirectory() as d:
            scaffold(PROSE, d)
            ref = (pathlib.Path(d) / DOM / "ref.py")
            self.assertTrue(ref.exists())          # 이전엔 아무것도 안 나왔음
            self.assertIn("참조", ref.read_text())

    def test_ports_sanitized_with_original_comment(self):
        with tempfile.TemporaryDirectory() as d:
            scaffold(PROSE, d)
            ports = (pathlib.Path(d) / "src/contexts/valuation/ports/ports_out.py").read_text()
            ast.parse(ports)                       # 한글 포트명이 클래스명으로 새지 않음
            self.assertIn("# port: 국토부 실거래가 REST API", ports)   # 원본 보존
            self.assertIn("class Port3(Protocol)", ports)             # 폴백 식별자


if __name__ == "__main__":
    unittest.main()
