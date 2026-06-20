"""본체 테스트 — check 가드. 생성→통과, 그리고 음성 대조(가드 무력화→실패)."""

import pathlib
import tempfile
import unittest

from hexaarch.check import check
from hexaarch.scaffold import scaffold
from hexaarch.spec import load_spec

EXAMPLE = pathlib.Path(__file__).resolve().parent.parent / "examples" / "seoul-apt" / "domain-spec.yaml"

AGG = "src/contexts/valuation/domain/analysis_eligibility.py"
STATE = "src/contexts/valuation/domain/analysis_eligibility_state.py"


class CheckBaseline(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec(EXAMPLE)

    def test_freshly_generated_passes(self):
        with tempfile.TemporaryDirectory() as d:
            scaffold(self.spec, d)
            report = check(self.spec, d)
            self.assertTrue(report.ok, "\n".join(str(v) for v in report.violations))
            self.assertGreater(report.checked_files, 0)

    def test_editing_inside_impl_block_is_allowed(self):
        # impl 블록 안에 자유롭게 로직을 채워도 통과해야 한다 (바이브코딩 영역).
        with tempfile.TemporaryDirectory() as d:
            scaffold(self.spec, d)
            f = pathlib.Path(d) / AGG
            text = f.read_text()
            text = text.replace(
                "    # <<< impl",
                "    def is_ready(self):  # 개발자가 채운 도메인 로직\n"
                "        return self.state.name == 'READY'\n"
                "    # <<< impl",
            )
            f.write_text(text)
            self.assertTrue(check(self.spec, d).ok)


class CheckTeeth(unittest.TestCase):
    """가드에 이빨이 있는가 — 무력화 시도는 전부 잡혀야 한다."""

    def setUp(self):
        self.spec = load_spec(EXAMPLE)

    def test_tampering_generated_transition_is_drift(self):
        with tempfile.TemporaryDirectory() as d:
            scaffold(self.spec, d)
            f = pathlib.Path(d) / AGG
            # _transition의 가드 체크를 무력화 (불허 전이를 통과시킴).
            text = f.read_text().replace(
                "        if to not in ALLOWED[self.state]:",
                "        if False:  # 가드 제거 시도",
            )
            f.write_text(text)
            report = check(self.spec, d)
            self.assertFalse(report.ok)
            self.assertTrue(any(v.kind == "drift" and v.path == AGG for v in report.violations))

    def test_tampering_state_table_is_drift(self):
        with tempfile.TemporaryDirectory() as d:
            scaffold(self.spec, d)
            f = pathlib.Path(d) / STATE
            # ALLOWED 전이표에 임의 전이 추가 시도.
            text = f.read_text().replace("ALLOWED = {", "ALLOWED = {  # 변조\n")
            f.write_text(text)
            report = check(self.spec, d)
            self.assertTrue(any(v.kind == "drift" for v in report.violations))

    def test_forbidden_import_in_domain_is_boundary(self):
        with tempfile.TemporaryDirectory() as d:
            scaffold(self.spec, d)
            f = pathlib.Path(d) / AGG
            # impl 블록 '안'이라도 경계는 못 넘는다.
            text = f.read_text().replace(
                "    # >>> impl: editable",
                "    import requests  # 경계 침범 시도\n    # >>> impl: editable",
            )
            f.write_text(text)
            report = check(self.spec, d)
            self.assertTrue(any(v.kind == "boundary" and v.path == AGG for v in report.violations))

    def test_deleting_skeleton_file_is_missing(self):
        with tempfile.TemporaryDirectory() as d:
            scaffold(self.spec, d)
            (pathlib.Path(d) / STATE).unlink()
            report = check(self.spec, d)
            self.assertTrue(any(v.kind == "missing" for v in report.violations))

    def test_deleting_impl_markers_is_drift(self):
        # 마커를 지워 보호구역을 없애려는 시도도 drift로 잡혀야 한다.
        with tempfile.TemporaryDirectory() as d:
            scaffold(self.spec, d)
            f = pathlib.Path(d) / AGG
            text = f.read_text().replace("    # >>> impl: editable  (AI 바이브코딩은 여기만)", "")
            f.write_text(text)
            self.assertFalse(check(self.spec, d).ok)


if __name__ == "__main__":
    unittest.main()
