"""본체 테스트 — 웹 어댑터(DRF) 생성 + §2 판단 누출 방어 경계.

web=drf면 application 유스케이스 + DRF 어댑터(serializer/view/urls)를 생성하고,
web→application→domain 방향을 강제한다(web이 도메인 직접 import하면 boundary 위반).
DRF 미설치 환경이라 런타임이 아닌 ast 유효성 + check + 경계로 검증.
"""

import ast
import pathlib
import tempfile
import unittest

from hexaarch.check import check
from hexaarch.scaffold import scaffold
from hexaarch.spec import Spec

VIEWS = "src/contexts/valuation/adapters/web/views.py"


def _spec(web: str | None):
    infra = {"database": "pg", "messaging": "ev"}
    if web is not None:
        infra["web"] = web
    return Spec.model_validate({
        "version": "0.1",
        "infrastructure": infra,
        "contexts": [{"name": "valuation", "domains": {"Thing": {
            "kind": "aggregate", "states": ["A", "B"], "transitions": {"A": ["B"]}}}}],
    })


class WebGeneration(unittest.TestCase):
    def test_generates_layered_web_adapter(self):
        spec = _spec("drf")
        with tempfile.TemporaryDirectory() as d:
            scaffold(spec, d)
            root = pathlib.Path(d)
            for rel in ("src/contexts/valuation/application/thing_service.py",
                        "src/contexts/valuation/application/__init__.py",
                        VIEWS,
                        "src/contexts/valuation/adapters/web/serializers.py",
                        "src/contexts/valuation/adapters/web/urls.py"):
                self.assertTrue((root / rel).exists(), rel)
                ast.parse((root / rel).read_text())          # 유효 파이썬
            views = (root / VIEWS).read_text()
            self.assertIn("from contexts.valuation.application import", views)
            self.assertIn("ThingService", views)
            # 서비스(application)는 도메인을 import해도 됨(올바른 방향)
            svc = (root / "src/contexts/valuation/application/thing_service.py").read_text()
            self.assertIn("from contexts.valuation.domain.thing import Thing", svc)
            self.assertTrue(check(spec, d).ok)               # drift 일관성

    def test_web_off_by_default(self):
        spec = _spec(None)                                   # web 미지정 → none
        self.assertEqual(spec.infrastructure.web, "none")
        with tempfile.TemporaryDirectory() as d:
            scaffold(spec, d)
            self.assertFalse((pathlib.Path(d) / "src/contexts/valuation/adapters/web").exists())
            self.assertFalse((pathlib.Path(d) / "src/contexts/valuation/application").exists())

    def test_view_importing_domain_is_boundary_violation(self):
        spec = _spec("drf")
        with tempfile.TemporaryDirectory() as d:
            scaffold(spec, d)
            v = pathlib.Path(d) / VIEWS
            v.write_text("from contexts.valuation.domain.thing import Thing  # §2 위반\n" + v.read_text())
            report = check(spec, d)
            self.assertFalse(report.ok)
            self.assertTrue(any(
                x.kind == "boundary" and x.path.endswith("web/views.py")
                for x in report.violations), [str(x) for x in report.violations])


if __name__ == "__main__":
    unittest.main()
