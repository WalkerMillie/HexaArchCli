"""실측(field) 테스트 — '진짜 개발된 프로젝트'에서 가드가 동작하는가.

test_check의 기준선(생성→곧바로 검사)은 같은 생성기 출력과 자기 비교라 거의 순환적이다.
여기서는 impl 블록을 실제 로직으로 채우고 새 파일(VO·유스케이스)을 추가해 골격에서
'벗어난' 상태를 만든 뒤 — 그래도 check가 통과하는지(정상 바이브코딩 허용),
그리고 골격에 없던 새 도메인 파일의 경계 위반도 잡는지를 실측한다.
"""

import pathlib
import re
import tempfile
import unittest

from hexaarch.check import check
from hexaarch.scaffold import scaffold
from hexaarch.spec import load_spec

EXAMPLE = pathlib.Path(__file__).resolve().parent.parent / "examples" / "seoul-apt" / "domain-spec.yaml"
AGG = "src/contexts/valuation/domain/analysis_eligibility.py"


def _develop(root: pathlib.Path) -> None:
    """impl 블록을 실제 로직으로 채우고 깨끗한 새 파일들을 추가 (정상 바이브코딩)."""
    agg = root / AGG
    body = (
        "    # >>> impl: editable  (AI 바이브코딩은 여기만)\n"
        "    def unlock(self, trade_volume: int, threshold: int) -> None:\n"
        "        if trade_volume < threshold:\n"
        "            raise InvariantViolation('VAL-005')\n"
        "        self._transition(AnalysisEligibilityState.READY)\n"
        "    # <<< impl"
    )
    agg.write_text(re.sub(r"    # >>> impl: editable.*?    # <<< impl", body,
                          agg.read_text(), flags=re.S))
    # 새 VO (도메인, 경계 준수)
    (root / "src/contexts/valuation/domain/value_objects.py").write_text(
        "from dataclasses import dataclass\n\n\n"
        "@dataclass(frozen=True)\nclass LoanLimit:\n    max_loan: int\n")
    # 새 유스케이스 (application 신설)
    app = root / "src/contexts/valuation/application"
    app.mkdir(parents=True, exist_ok=True)
    (app / "__init__.py").write_text("")
    (app / "unlock_analysis.py").write_text(
        "from contexts.valuation.domain.analysis_eligibility import AnalysisEligibility\n\n\n"
        "def run(agg: AnalysisEligibility, vol: int, thr: int) -> None:\n"
        "    agg.unlock(vol, thr)\n")


class FieldTest(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec(EXAMPLE)

    def test_developed_project_still_passes_check(self):
        # impl 채움 + 새 파일 추가로 골격에서 벗어나도 정상 작업은 통과해야 한다.
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            scaffold(self.spec, root)
            _develop(root)
            report = check(self.spec, root)
            self.assertTrue(report.ok, "\n".join(str(v) for v in report.violations))

    def test_forbidden_import_in_a_brand_new_domain_file_is_caught(self):
        # 골격에 없던 새 도메인 파일이 타 컨텍스트를 import해도 잡혀야 한다.
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            scaffold(self.spec, root)
            _develop(root)
            new = root / "src/contexts/valuation/domain/cross_peek.py"
            new.write_text("from contexts.regulation.domain import decision_tables\n")
            report = check(self.spec, root)
            self.assertFalse(report.ok)
            self.assertTrue(any(
                v.kind == "boundary" and v.path.endswith("cross_peek.py")
                for v in report.violations))


if __name__ == "__main__":
    unittest.main()
