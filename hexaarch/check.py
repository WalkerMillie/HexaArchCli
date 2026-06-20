"""변경 가드 — 생성 프로젝트가 스펙 골격을 깨뜨렸는지 판정. (DESIGN §9, §16)

지속 바이브코딩의 안전벨트. 사람/AI가 매 편집 후 돌리는 루프용.

생성기(scaffold)가 결정론적이므로 "이 파일의 생성 영역이 어떤 모습이어야 하는가"는
스펙에서 다시 계산할 수 있다. 그래서:

    check = regenerate(spec) → impl 블록만 마스킹하고 비교 (drift)
          + 도메인 코드 import 정적 스캔 (boundary)

- **drift**: impl 블록 *밖*(프레임워크 소유 영역 = 상태표·_transition·예외·전이테스트·
  경계테스트·결정표 헤더)이 재생성본과 다르면 위반. 누군가 가드를 무력화한 것.
- **missing**: 스펙이 생성해야 할 골격 파일이 프로젝트에서 사라짐.
- **boundary**: 도메인 코드(impl 블록 포함)가 어댑터/인프라/타컨텍스트를 import하면 위반.
  impl 블록 안의 '로직'은 자유다. 단 경계는 거기서도 못 넘는다.

impl 블록 안의 내용과 프레임워크가 만들지 않은 새 파일(유스케이스·VO·어댑터 등)은
검사 대상이 아니다 — 거기가 바이브코딩이 마음껏 사는 곳이다.

비-목표(v1): impl 완성도(스펙에 새 가드가 생겼는데 구현이 비었는지)는 아직 검사 안 함.
"""

from __future__ import annotations

import ast
import difflib
import tempfile
from dataclasses import dataclass
from pathlib import Path

from hexaarch.scaffold import FORBIDDEN_IMPORTS, scaffold
from hexaarch.spec import Spec

_IMPL_OPEN = ">>> impl"
_IMPL_CLOSE = "<<< impl"
_IMPL_SENTINEL = "<<<IMPL-REGION: developer-owned>>>"


@dataclass
class Violation:
    kind: str        # "drift" | "missing" | "boundary"
    path: str        # 프로젝트 기준 상대 경로
    detail: str

    def __str__(self) -> str:
        head = f"  [{self.kind}] {self.path}"
        return f"{head}\n" + "\n".join(f"      {ln}" for ln in self.detail.splitlines())


@dataclass
class CheckReport:
    violations: list[Violation]
    checked_files: int

    @property
    def ok(self) -> bool:
        return not self.violations


def _mask_impl(text: str) -> str:
    """impl 블록 *본문*을 센티넬로 치환. 마커 줄은 남겨 구조 자체는 비교한다.

    마커를 지우면 본문이 일반 텍스트로 남아 재생성본과 어긋나므로 drift로 잡힌다
    (= 마커 삭제도 위반)."""
    out: list[str] = []
    skipping = False
    for line in text.splitlines():
        if _IMPL_OPEN in line:
            out.append(line)
            out.append(_IMPL_SENTINEL)
            skipping = True
            continue
        if _IMPL_CLOSE in line:
            skipping = False
            out.append(line)
            continue
        if not skipping:
            out.append(line)
    return "\n".join(out)


def _first_diff(expected: str, actual: str) -> str:
    diff = difflib.unified_diff(
        expected.splitlines(), actual.splitlines(),
        fromfile="스펙 재생성(기대)", tofile="현재 프로젝트", lineterm="",
    )
    lines = list(diff)[:9]
    return "생성 영역이 스펙과 다름 (가드 변조 의심):\n" + "\n".join(lines)


def _domain_imports(path: Path):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                yield n.name
        elif isinstance(node, ast.ImportFrom):
            yield node.module or ""


def _boundary_scan(proj_root: Path) -> list[Violation]:
    """프로젝트의 실제 도메인 파일 전부를 정적 스캔 (생성물 여부 무관).

    바이브코딩으로 추가된 새 도메인 파일도 경계는 지켜야 하므로 regen이 아닌
    프로젝트 자체를 훑는다."""
    contexts = proj_root / "src" / "contexts"
    if not contexts.is_dir():
        return []
    all_ctx = {p.name for p in contexts.iterdir()
               if p.is_dir() and not p.name.startswith("__")}
    out: list[Violation] = []
    for ctx in sorted(all_ctx):
        dom = contexts / ctx / "domain"
        if dom.is_dir():
            for py in sorted(dom.rglob("*.py")):
                rel = py.relative_to(proj_root)
                for mod in _domain_imports(py):
                    hit = next((f for f in FORBIDDEN_IMPORTS if f in mod), None)
                    if hit:
                        out.append(Violation("boundary", str(rel),
                                             f"도메인이 금지 대상 import: {mod}  (금지어: {hit})"))
                    for other in all_ctx - {ctx}:
                        if f"contexts.{other}" in mod:
                            out.append(Violation("boundary", str(rel),
                                                 f"도메인이 타 컨텍스트 import: {mod}"))
        # §2 — web 어댑터는 도메인을 직접 import 금지(반드시 application 유스케이스 경유).
        web = contexts / ctx / "adapters" / "web"
        if web.is_dir():
            for py in sorted(web.rglob("*.py")):
                rel = py.relative_to(proj_root)
                for mod in _domain_imports(py):
                    if f"contexts.{ctx}.domain" in mod:
                        out.append(Violation("boundary", str(rel),
                            f"web 어댑터가 도메인 직접 import: {mod} "
                            "(§2 — application 유스케이스를 통해야 함)"))
    return out


def check(spec: Spec, project_dir: str | Path) -> CheckReport:
    proj_root = Path(project_dir)
    violations: list[Violation] = []
    checked = 0

    with tempfile.TemporaryDirectory() as tmp:
        scaffold(spec, tmp)
        regen_root = Path(tmp)
        for gen_file in sorted(regen_root.rglob("*")):
            if not gen_file.is_file():
                continue
            rel = gen_file.relative_to(regen_root)
            checked += 1
            proj_file = proj_root / rel
            if not proj_file.exists():
                violations.append(Violation(
                    "missing", str(rel), "스펙이 생성해야 할 골격 파일이 프로젝트에 없음 (삭제됨?)"))
                continue
            gen_text = gen_file.read_text(encoding="utf-8")
            proj_text = proj_file.read_text(encoding="utf-8")
            if rel.suffix == ".csv":
                # 생성 영역 = 주석 + 헤더 (prefix). 그 뒤 데이터 행은 자유.
                if not proj_text.startswith(gen_text):
                    violations.append(Violation(
                        "drift", str(rel), "결정표의 생성 영역(주석/헤더)이 변경됨"))
                continue
            exp, act = _mask_impl(gen_text), _mask_impl(proj_text)
            if exp != act:
                violations.append(Violation("drift", str(rel), _first_diff(exp, act)))

    # drift 비교가 끝난 뒤 도메인 경계는 프로젝트 전체 기준으로 별도 스캔.
    violations += _boundary_scan(proj_root)

    # 출력 안정화: 종류 → 경로 순.
    violations.sort(key=lambda v: (v.kind, v.path))
    return CheckReport(violations, checked)
