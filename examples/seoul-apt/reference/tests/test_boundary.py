"""§9-③ 경계 위반 테스트 — 모든 컨텍스트의 domain이 어댑터/인프라/타 컨텍스트 import 금지.

import-linter 없이 stdlib AST로 구현(좁은 검증 단계). 규칙은 .arch/import-rules.toml과 동일 의도:
  - domain은 adapters/application/ports/외부프레임워크 import 금지
  - 컨텍스트 domain은 다른 컨텍스트를 직접 import 금지 (이벤트/포트/합성루트로만)
  - shared(공유 커널)는 허용.
"""

import ast
import pathlib
import unittest

SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
CONTEXTS = SRC / "contexts"

FORBIDDEN_GENERIC = (
    "adapters", "application", ".ports",
    "django", "rest_framework", "sqlalchemy", "requests", "httpx", "celery", "redis",
)
ALL_CONTEXTS = {p.name for p in CONTEXTS.iterdir() if p.is_dir() and not p.name.startswith("__")}


def _imports(path: pathlib.Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                yield n.name
        elif isinstance(node, ast.ImportFrom):
            yield node.module or ""


class DomainBoundary(unittest.TestCase):
    def test_all_context_domains_are_clean(self):
        violations = []
        for ctx in sorted(ALL_CONTEXTS):
            ddir = CONTEXTS / ctx / "domain"
            if not ddir.exists():
                continue
            others = ALL_CONTEXTS - {ctx}
            for py in ddir.rglob("*.py"):
                for mod in _imports(py):
                    for bad in FORBIDDEN_GENERIC:
                        if bad in mod:
                            violations.append(f"{ctx}/domain/{py.name}: import '{mod}' (금지: {bad})")
                    for other in others:
                        if f"contexts.{other}" in mod:
                            violations.append(f"{ctx}/domain/{py.name}: 타컨텍스트 import '{mod}'")
        self.assertEqual(violations, [], "도메인 경계 위반:\n" + "\n".join(violations))


if __name__ == "__main__":
    unittest.main()
