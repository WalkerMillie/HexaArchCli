"""결정론적 생성기 — 스펙 → §3 골격. LLM 미사용(DESIGN §4).

생성(결정론): 상태 enum+전이테이블, _transition, 예외, 포트 시그니처 스텁,
  전이 매트릭스 테스트, 경계가드(import-rules + boundary 테스트), 결정표 CSV 스텁.
보존(impl 블록 §6): 가드/불변식/수식/도메인 메서드 본문 — AI가 채움.

같은 스펙 → 같은 바이트(정렬·결정 순서 고정). Jinja2 trim 설정으로 안정 출력.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from jinja2 import Environment

from hexaarch.spec import Context, Domain, Spec, load_spec

_env = Environment(trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _enum_name(agg: str) -> str:
    return f"{agg}State"


STATE_T = _env.from_string(
    '''"""[GENERATED] {{ agg }} 상태 + 전이 테이블. 방어선 A. 스펙에서 결정론 생성 — 직접 수정 금지."""

from enum import Enum, auto


class {{ enum }}(Enum):
{% for s in states %}    {{ s }} = auto()
{% endfor %}

ALLOWED = {
{% for s in states %}    {{ enum }}.{{ s }}: { {{ transitions.get(s, []) | map('prefixenum', enum) | join(', ') }} },
{% endfor %}}
'''
)

EXC_T = _env.from_string(
    '''"""[GENERATED] {{ ctx }} 도메인 예외."""


class {{ ctxcap }}Error(Exception):
    pass


class IllegalTransition({{ ctxcap }}Error):
    """방어선 A — 허용 안 된 전이."""

    def __init__(self, frm, to):
        self.frm = frm
        self.to = to
        super().__init__(f"불허 전이: {frm.name} -> {to.name}")


class InvariantViolation({{ ctxcap }}Error):
    """방어선 B — 불변식 위반."""
'''
)

AGG_T = _env.from_string(
    '''"""[GENERATED 골격 + impl 보호구역] {{ agg }} Aggregate (B형).

상태 머신은 생성됨. 가드/불변식/도메인 메서드는 impl 블록에서 채운다(§6).
"""

from contexts.{{ ctx }}.domain.{{ state_mod }} import ALLOWED, {{ enum }}
from contexts.{{ ctx }}.domain.exceptions import IllegalTransition, InvariantViolation  # noqa: F401


class {{ agg }}:
    def __init__(self, state: {{ enum }} = {{ enum }}.{{ first }}):
        self.state = state

    # >>> generated: do-not-edit
    def _transition(self, to: {{ enum }}) -> None:
        if to not in ALLOWED[self.state]:
            raise IllegalTransition(self.state, to)
        self.state = to
    # <<< generated

    # >>> impl: editable  (AI 바이브코딩은 여기만)
{% for g in guards %}    # guard: {{ g.id }} on {{ g.edge }} — {{ g.desc }}
{% endfor %}{% for inv in invariants %}    # invariant: {{ inv.id }} — {{ inv.desc }}
{% endfor %}{% for ri in relationship_invariants %}    # rel-invariant: {{ ri.id }} — {{ ri.desc }} (enforced_by: {{ ri.enforced_by }})
{% endfor %}    # <<< impl
'''
)

PORTS_T = _env.from_string(
    '''"""[GENERATED 골격] {{ ctx }} 아웃바운드 포트 — 시그니처는 impl에서."""

from typing import Protocol

{% for p in ports %}
class {{ p }}(Protocol):
    # >>> impl: editable (method signatures)
    ...
    # <<< impl

{% endfor %}'''
)

TRANS_TEST_T = _env.from_string(
    '''"""[GENERATED] {{ agg }} 전이 매트릭스 테스트 — §9-① (전이 거부). 스펙에서 생성."""

import unittest

from contexts.{{ ctx }}.domain.{{ agg_mod }} import {{ agg }}
from contexts.{{ ctx }}.domain.exceptions import IllegalTransition
from contexts.{{ ctx }}.domain.{{ state_mod }} import ALLOWED, {{ enum }}


class {{ agg }}Transitions(unittest.TestCase):
    def test_full_matrix(self):
        for frm in {{ enum }}:
            for to in {{ enum }}:
                agg = {{ agg }}(state=frm)
                if to in ALLOWED[frm]:
                    agg._transition(to)
                    self.assertEqual(agg.state, to)
                else:
                    with self.assertRaises(IllegalTransition):
                        agg._transition(to)


if __name__ == "__main__":
    unittest.main()
'''
)

IMPORT_RULES_T = _env.from_string(
    '''# [GENERATED] 방어선 C — 경계 가드 (DESIGN §3.4)
{% for ctx in contexts %}
[[rule]]
name = "{{ ctx }}.domain은 adapters/application 의존 금지"
forbidden = "contexts.{{ ctx }}.domain -> contexts.{{ ctx }}.adapters | contexts.{{ ctx }}.application"
{% endfor %}
'''
)

# 방어선 C — 도메인 코어가 import하면 안 되는 것들 (어댑터/인프라/타컨텍스트).
# check.py가 같은 규칙으로 정적 스캔하므로 단일 출처로 둔다.
FORBIDDEN_IMPORTS = ("adapters", "application", ".ports", "django", "rest_framework",
                     "sqlalchemy", "requests", "httpx", "celery", "redis")

BOUNDARY_TEST = '''"""[GENERATED] §9-③ 경계 위반 테스트 (stdlib AST). 도메인은 어댑터/인프라/타컨텍스트 import 금지."""

import ast
import pathlib
import unittest

SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
CONTEXTS = SRC / "contexts"
FORBIDDEN = __FORBIDDEN_REPR__
ALL = {p.name for p in CONTEXTS.iterdir() if p.is_dir() and not p.name.startswith("__")}


def _imports(path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for n in node.names:
                yield n.name
        elif isinstance(node, ast.ImportFrom):
            yield node.module or ""


class DomainBoundary(unittest.TestCase):
    def test_all_clean(self):
        bad = []
        for ctx in sorted(ALL):
            d = CONTEXTS / ctx / "domain"
            if not d.exists():
                continue
            for py in d.rglob("*.py"):
                for mod in _imports(py):
                    if any(f in mod for f in FORBIDDEN):
                        bad.append(f"{ctx}/domain/{py.name}: {mod}")
                    for other in ALL - {ctx}:
                        if f"contexts.{other}" in mod:
                            bad.append(f"{ctx}/domain/{py.name}: 타컨텍스트 {mod}")
        self.assertEqual(bad, [], "\\n".join(bad))


if __name__ == "__main__":
    unittest.main()
'''

BOUNDARY_TEST = BOUNDARY_TEST.replace("__FORBIDDEN_REPR__", repr(FORBIDDEN_IMPORTS))

AGENTS_T = _env.from_string(
    '''# AGENTS.md — 이 프로젝트에서 바이브코딩하는 규칙

이 골격은 HexaArch가 `domain-spec.yaml`에서 **결정론적으로 생성**했다.
계속 코드를 짜되 아래 규칙을 깨면 `hexaarch check`가 빌드를 막는다.

## 컨텍스트 (바운디드)
{% for c in contexts %}
- **{{ c.name }}** — {{ c.domains.keys() | join(', ') or '결정표/참조' }}
{% endfor %}

## 절대 규칙
1. **impl 블록 안에서만 짠다.** `>>> impl: editable` ~ `<<< impl` 사이가 네 영역이다.
   그 밖(상태표·`_transition`·예외·전이/경계 테스트·결정표 헤더)은 생성 영역 —
   고치려면 코드가 아니라 `domain-spec.yaml`을 고치고 재생성한다.
2. **도메인은 아무것도 import하지 않는다.** `contexts/*/domain/`은 어댑터·인프라·
   타 컨텍스트를 import 금지 (금지어: {{ forbidden | join(', ') }}).
   크로스 컨텍스트 데이터는 값(VO)으로 주입받고, 동기 조회는 합성 루트에서 배선한다.
3. **상태 전이는 스펙이 정한 것만.** 새 상태/전이가 필요하면 스펙을 고친다.
4. **새 파일은 자유.** 유스케이스·VO·어댑터 등 프레임워크가 안 만든 파일은 마음껏 추가.
   단 도메인 디렉터리에 두면 규칙 2가 적용된다.

## 매 편집 후
```
hexaarch check {{ spec_hint }} .
```
위반 0이어야 한다. drift = 생성 영역을 건드림 / boundary = 경계 침범 / missing = 골격 삭제.
'''
)


def _prefixenum(states, enum):
    return [f"{enum}.{s}" for s in states]


_env.filters["prefixenum"] = lambda s, enum: f"{enum}.{s}"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def scaffold(spec: Spec, out_dir: str | Path) -> list[str]:
    out = Path(out_dir)
    if out.exists():
        shutil.rmtree(out)
    src = out / "src"
    written: list[str] = []

    def w(rel: str, content: str):
        _write(src / rel, content)
        written.append(rel)

    w("contexts/__init__.py", "")
    ctx_names = [c.name for c in spec.contexts]

    for c in spec.contexts:
        base = f"contexts/{c.name}"
        w(f"{base}/__init__.py", "")
        if c.domains:
            w(f"{base}/domain/__init__.py", "")
            w(f"{base}/domain/exceptions.py",
              EXC_T.render(ctx=c.name, ctxcap=c.name.capitalize()))
        for agg, d in c.domains.items():
            _emit_domain(w, c, agg, d)
        if c.decision_tables:
            _emit_decision_tables(w, c)

    # 테스트 + 경계 설정
    _write(out / "tests" / "__init__.py", "")
    for c in spec.contexts:
        for agg, d in c.domains.items():
            if d.kind == "aggregate":
                tt = TRANS_TEST_T.render(
                    ctx=c.name, agg=agg, agg_mod=_snake(agg),
                    state_mod=f"{_snake(agg)}_state", enum=_enum_name(agg),
                )
                _write(out / "tests" / f"test_{c.name}_{_snake(agg)}_transitions.py", tt)
                written.append(f"tests/test_{c.name}_{_snake(agg)}_transitions.py")
    _write(out / "tests" / "test_boundary.py", BOUNDARY_TEST)
    _write(out / ".arch" / "import-rules.toml",
           IMPORT_RULES_T.render(contexts=ctx_names))
    _write(out / "AGENTS.md",
           AGENTS_T.render(contexts=spec.contexts, forbidden=FORBIDDEN_IMPORTS,
                           spec_hint="domain-spec.yaml"))
    written.append("AGENTS.md")
    return written


def _emit_domain(w, c: Context, agg: str, d: Domain) -> None:
    base = f"contexts/{c.name}"
    if d.kind == "aggregate":
        state_mod = f"{_snake(agg)}_state"
        enum = _enum_name(agg)
        w(f"{base}/domain/{state_mod}.py",
          STATE_T.render(agg=agg, enum=enum, states=d.states, transitions=d.transitions))
        w(f"{base}/domain/{_snake(agg)}.py",
          AGG_T.render(ctx=c.name, agg=agg, state_mod=state_mod, enum=enum,
                       first=d.states[0], guards=d.guards, invariants=d.invariants,
                       relationship_invariants=d.relationship_invariants))
        if d.ports_out:
            w(f"{base}/ports/__init__.py", "")
            w(f"{base}/ports/ports_out.py", PORTS_T.render(ctx=c.name, ports=d.ports_out))
    elif d.kind == "calculation":
        names = "\n".join(
            f"# {f.id}: {f.name} — 순수 수식, impl에서 구현" for f in d.formulas
        )
        w(f"{base}/domain/{_snake(agg)}.py",
          f'"""[GENERATED 골격] {agg} (무상태 calculation). 수식 본문은 impl.\n\n{names}\n"""\n')


def _emit_decision_tables(w, c: Context) -> None:
    base = f"contexts/{c.name}"
    w(f"{base}/domain/__init__.py", "")
    for t in c.decision_tables:
        cols = []
        if t.versioned:
            cols += ["version", "effective_date"]
        if t.kind == "range":
            for i in t.inputs:
                cols += [f"{i}_min", f"{i}_max"]
        else:
            cols += list(t.inputs)
        cols += [t.output]
        header = ",".join(cols)
        w(f"{base}/domain/decision_tables/{t.name}.csv",
          f"# [GENERATED 스텁] {t.id} {t.name} (kind={t.kind}). 행은 채워라.\n{header}\n")


def main(spec_path: str, out_dir: str) -> None:
    spec = load_spec(spec_path)          # §16.5 검증 통과해야 진행
    files = scaffold(spec, out_dir)
    print(f"generated {len(files)} files into {out_dir}")


if __name__ == "__main__":
    import sys
    main(sys.argv[1], sys.argv[2])
