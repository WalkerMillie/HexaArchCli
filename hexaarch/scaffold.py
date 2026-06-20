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


def _ident(name: str) -> str:
    """임의 이름 → 안전한 파이썬 식별자 슬러그 (한글/공백 → '', 비면 호출자가 id로 폴백)."""
    s = re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower()
    return s


def _pascal(slug: str) -> str:
    return "".join(p[:1].upper() + p[1:] for p in slug.split("_") if p)


def _table_slug(t) -> str:
    return _ident(t.name) or _ident(t.id)


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

{% if has_aggregates %}

class IllegalTransition({{ ctxcap }}Error):
    """방어선 A — 허용 안 된 전이."""

    def __init__(self, frm, to):
        self.frm = frm
        self.to = to
        super().__init__(f"불허 전이: {frm.name} -> {to.name}")


class InvariantViolation({{ ctxcap }}Error):
    """방어선 B — 불변식 위반."""
{% endif %}
{% if has_tables %}

class NoMatchingRow({{ ctxcap }}Error):
    """결정표에서 입력에 맞는 행 없음 (완전성 위반의 런타임 증상)."""


class IncompleteDecisionTable({{ ctxcap }}Error):
    """결정표 완전성 위반 — 구간 공백/겹침/빈칸. (§9-④)"""

    def __init__(self, problems):
        self.problems = problems
        super().__init__("결정표 완전성 위반:\\n" + "\\n".join(problems))
{% endif %}
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
# port: {{ p.original }}
class {{ p.cls }}(Protocol):
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
            # §2 — web 어댑터는 도메인 직접 import 금지 (application 유스케이스 경유).
            web = CONTEXTS / ctx / "adapters" / "web"
            if web.exists():
                for py in web.rglob("*.py"):
                    for mod in _imports(py):
                        if f"contexts.{ctx}.domain" in mod:
                            bad.append(f"{ctx}/adapters/web/{py.name}: 도메인 직접 import {mod} (§2)")
        self.assertEqual(bad, [], "\\n".join(bad))


if __name__ == "__main__":
    unittest.main()
'''

BOUNDARY_TEST = BOUNDARY_TEST.replace("__FORBIDDEN_REPR__", repr(FORBIDDEN_IMPORTS))

# ── 결정표(decision table) 생성 — 정책을 도메인 코어에 박는다 (DESIGN §5.3, §9-④) ──

DT_RANGE_T = _env.from_string(
    '''"""[GENERATED] {{ name }} 결정표 — range 룩업{% if versioned %} + effective_date 버저닝{% endif %} + 완전성 검사. 순수 도메인.

정책을 도메인 코어에 박는다. 행(데이터)=decision_tables/{{ name }}.csv, 읽기=adapters/{{ name }}_loader.
스펙에서 결정론 생성 — 직접 수정 금지(정책을 바꾸려면 스펙/CSV를 고친다).  req: {{ id }}
"""

from __future__ import annotations

from dataclasses import dataclass
{% if versioned %}from datetime import date
{% endif %}
from contexts.{{ ctx }}.domain.exceptions import IncompleteDecisionTable, NoMatchingRow


@dataclass(frozen=True)
class {{ cls }}Rule:
{% if versioned %}    version: str
    effective_date: date
{% endif %}    {{ inp }}_min: float
    {{ inp }}_max: float | None   # None = 무한대(∞)
    {{ out }}: str

    def contains(self, {{ inp }}: float) -> bool:
        if {{ inp }} < self.{{ inp }}_min:
            return False
        return self.{{ inp }}_max is None or {{ inp }} < self.{{ inp }}_max


class {{ cls }}Table:
    def __init__(self, rules: list[{{ cls }}Rule]):
        self.rules = list(rules)
{% if versioned %}
    def active_version_as_of(self, as_of: date) -> str:
        eligible = {r.effective_date for r in self.rules if r.effective_date <= as_of}
        if not eligible:
            raise NoMatchingRow(f"{as_of} 시점에 유효한 버전 없음")
        latest = max(eligible)
        return next(r.version for r in self.rules if r.effective_date == latest)

    def _grouped(self) -> dict:
        groups: dict = {}
        for r in self.rules:
            groups.setdefault(r.version, []).append(r)
        return {v: sorted(rs, key=lambda r: r.{{ inp }}_min) for v, rs in groups.items()}

    def lookup(self, {{ inp }}: float, as_of: date) -> str:
        for r in self._grouped()[self.active_version_as_of(as_of)]:
            if r.contains({{ inp }}):
                return r.{{ out }}
        raise NoMatchingRow(str({{ inp }}) + " 값이 어느 구간에도 안 걸림")
{% else %}
    def _grouped(self) -> dict:
        return {"-": sorted(self.rules, key=lambda r: r.{{ inp }}_min)}

    def lookup(self, {{ inp }}: float) -> str:
        for r in self._grouped()["-"]:
            if r.contains({{ inp }}):
                return r.{{ out }}
        raise NoMatchingRow(str({{ inp }}) + " 값이 어느 구간에도 안 걸림")
{% endif %}
    def check_completeness(self) -> list[str]:
        """버전별로 [0, ∞)를 빈틈/겹침 없이 타일링하는지 (§9-④)."""
        problems: list[str] = []
        for version, rows in sorted(self._grouped().items()):
            if not rows:
                continue
            if rows[0].{{ inp }}_min != 0:
                problems.append(f"[{version}] 0부터 시작 안 함 (시작={rows[0].{{ inp }}_min})")
            for prev, cur in zip(rows, rows[1:]):
                if prev.{{ inp }}_max is None:
                    problems.append(f"[{version}] ∞ 구간 뒤에 또 구간 존재")
                elif cur.{{ inp }}_min > prev.{{ inp }}_max:
                    problems.append(f"[{version}] 공백: {prev.{{ inp }}_max}~{cur.{{ inp }}_min}")
                elif cur.{{ inp }}_min < prev.{{ inp }}_max:
                    problems.append(f"[{version}] 겹침: {cur.{{ inp }}_min} < {prev.{{ inp }}_max}")
            if rows[-1].{{ inp }}_max is not None:
                problems.append(f"[{version}] 마지막 구간이 ∞로 안 열림 (max={rows[-1].{{ inp }}_max})")
        return problems

    def assert_complete(self) -> None:
        problems = self.check_completeness()
        if problems:
            raise IncompleteDecisionTable(problems)
'''
)

DT_LOOKUP_T = _env.from_string(
    '''"""[GENERATED] {{ name }} 결정표 — {{ kind }} 정확매칭 룩업{% if versioned %} + 버저닝{% endif %}. 순수 도메인.

행=decision_tables/{{ name }}.csv, 읽기=adapters/{{ name }}_loader.  req: {{ id }}
"""

from __future__ import annotations

from dataclasses import dataclass
{% if versioned %}from datetime import date
{% endif %}
from contexts.{{ ctx }}.domain.exceptions import NoMatchingRow


@dataclass(frozen=True)
class {{ cls }}Rule:
{% if versioned %}    version: str
    effective_date: date
{% endif %}{% for i in inputs %}    {{ i }}: str
{% endfor %}    {{ out }}: str


class {{ cls }}Table:
    def __init__(self, rules: list[{{ cls }}Rule]):
        self.rules = list(rules)
{% if versioned %}
    def active_version_as_of(self, as_of: date) -> str:
        eligible = {r.effective_date for r in self.rules if r.effective_date <= as_of}
        if not eligible:
            raise NoMatchingRow(f"{as_of} 시점에 유효한 버전 없음")
        latest = max(eligible)
        return next(r.version for r in self.rules if r.effective_date == latest)
{% endif %}
    def lookup(self, {{ args }}{% if versioned %}, as_of: date{% endif %}) -> str:
        key = ({{ keyexpr }})
{% if versioned %}        version = self.active_version_as_of(as_of)
{% endif %}        for r in self.rules:
{% if versioned %}            if r.version != version:
                continue
{% endif %}            if ({{ rulekey }}) == key:
                return r.{{ out }}
        raise NoMatchingRow(str(key) + " 조합에 맞는 행 없음")
'''
)

DT_RANGE_LOADER_T = _env.from_string(
    '''"""[GENERATED] {{ name }} 로더 — CSV(데이터) → {{ cls }}Table. 어댑터(I/O는 여기서만)."""

from __future__ import annotations

import csv
from pathlib import Path
{% if versioned %}from datetime import date
{% endif %}
from contexts.{{ ctx }}.domain.{{ name }}_table import {{ cls }}Rule, {{ cls }}Table

_CSV = Path(__file__).resolve().parent.parent / "domain" / "decision_tables" / "{{ name }}.csv"


def _num(s: str):
    s = s.strip()
    return None if s == "" else float(s)


def load_{{ name }}_table(path: Path = _CSV) -> {{ cls }}Table:
    rules: list[{{ cls }}Rule] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(line for line in f if not line.lstrip().startswith("#"))
        for row in reader:
            rules.append({{ cls }}Rule(
{% if versioned %}                version=row["version"].strip(),
                effective_date=date.fromisoformat(row["effective_date"].strip()),
{% endif %}                {{ inp }}_min=_num(row["{{ inp }}_min"]),
                {{ inp }}_max=_num(row["{{ inp }}_max"]),
                {{ out }}=row["{{ out }}"].strip(),
            ))
    return {{ cls }}Table(rules)
'''
)

DT_LOOKUP_LOADER_T = _env.from_string(
    '''"""[GENERATED] {{ name }} 로더 — CSV(데이터) → {{ cls }}Table. 어댑터."""

from __future__ import annotations

import csv
from pathlib import Path
{% if versioned %}from datetime import date
{% endif %}
from contexts.{{ ctx }}.domain.{{ name }}_table import {{ cls }}Rule, {{ cls }}Table

_CSV = Path(__file__).resolve().parent.parent / "domain" / "decision_tables" / "{{ name }}.csv"


def load_{{ name }}_table(path: Path = _CSV) -> {{ cls }}Table:
    rules: list[{{ cls }}Rule] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(line for line in f if not line.lstrip().startswith("#"))
        for row in reader:
            rules.append({{ cls }}Rule(
{% if versioned %}                version=row["version"].strip(),
                effective_date=date.fromisoformat(row["effective_date"].strip()),
{% endif %}{% for i in inputs %}                {{ i }}=row["{{ i }}"].strip(),
{% endfor %}                {{ out }}=row["{{ out }}"].strip(),
            ))
    return {{ cls }}Table(rules)
'''
)

DT_RANGE_TEST_T = _env.from_string(
    '''"""[GENERATED] {{ name }} range 결정표 테스트 — 완전성 + 룩업 (§9-④). 스펙에서 생성."""

import unittest
{% if versioned %}from datetime import date
{% endif %}
from contexts.{{ ctx }}.domain.{{ name }}_table import {{ cls }}Rule, {{ cls }}Table
from contexts.{{ ctx }}.domain.exceptions import IncompleteDecisionTable, NoMatchingRow

{% if versioned %}_V = dict(version="v1", effective_date=date(2026, 1, 1))
{% else %}_V: dict = {}
{% endif %}

def _complete():
    return {{ cls }}Table([
        {{ cls }}Rule(**_V, {{ inp }}_min=0.0, {{ inp }}_max=10.0, {{ out }}="A"),
        {{ cls }}Rule(**_V, {{ inp }}_min=10.0, {{ inp }}_max=None, {{ out }}="B"),
    ])


class {{ cls }}TableTest(unittest.TestCase):
    def test_complete_passes(self):
        self.assertEqual(_complete().check_completeness(), [])
        _complete().assert_complete()

    def test_gap_detected(self):
        t = {{ cls }}Table([
            {{ cls }}Rule(**_V, {{ inp }}_min=0.0, {{ inp }}_max=10.0, {{ out }}="A"),
            {{ cls }}Rule(**_V, {{ inp }}_min=20.0, {{ inp }}_max=None, {{ out }}="B"),
        ])
        self.assertTrue(any("공백" in p for p in t.check_completeness()))
        with self.assertRaises(IncompleteDecisionTable):
            t.assert_complete()

    def test_lookup(self):
        self.assertEqual(_complete().lookup(5.0{% if versioned %}, date(2026, 6, 1){% endif %}), "A")
        self.assertEqual(_complete().lookup(50.0{% if versioned %}, date(2026, 6, 1){% endif %}), "B")
        with self.assertRaises(NoMatchingRow):
            _complete().lookup(-1.0{% if versioned %}, date(2026, 6, 1){% endif %})


if __name__ == "__main__":
    unittest.main()
'''
)

DT_LOOKUP_TEST_T = _env.from_string(
    '''"""[GENERATED] {{ name }} {{ kind }} 결정표 테스트 — 정확매칭 룩업. 스펙에서 생성."""

import unittest
{% if versioned %}from datetime import date
{% endif %}
from contexts.{{ ctx }}.domain.{{ name }}_table import {{ cls }}Rule, {{ cls }}Table
from contexts.{{ ctx }}.domain.exceptions import NoMatchingRow

{% if versioned %}_V = dict(version="v1", effective_date=date(2026, 1, 1))
{% else %}_V: dict = {}
{% endif %}

class {{ cls }}TableTest(unittest.TestCase):
    def test_lookup_hit_and_miss(self):
        t = {{ cls }}Table([
            {{ cls }}Rule(**_V, {% for i in inputs %}{{ i }}="k{{ loop.index }}", {% endfor %}{{ out }}="OUT"),
        ])
        self.assertEqual(
            t.lookup({% for i in inputs %}"k{{ loop.index }}", {% endfor %}{% if versioned %}as_of=date(2026, 6, 1){% endif %}),
            "OUT",
        )
        with self.assertRaises(NoMatchingRow):
            t.lookup({% for i in inputs %}"nope{{ loop.index }}", {% endfor %}{% if versioned %}as_of=date(2026, 6, 1){% endif %})


if __name__ == "__main__":
    unittest.main()
'''
)

DT_MULTIRANGE_T = _env.from_string(
    '''"""[GENERATED] {{ name }} 결정표 — 다차원 range 룩업{% if versioned %} + 버저닝{% endif %}. 순수 도메인.

입력 {{ inputs | join(', ') }} 각각의 구간을 모두 만족(AND)하는 행을 찾는다.
다차원 완전성 자동검사는 생략(타일링 비용) — 필요 시 수동 검토.  req: {{ id }}
"""

from __future__ import annotations

from dataclasses import dataclass
{% if versioned %}from datetime import date
{% endif %}
from contexts.{{ ctx }}.domain.exceptions import NoMatchingRow


@dataclass(frozen=True)
class {{ cls }}Rule:
{% if versioned %}    version: str
    effective_date: date
{% endif %}{% for i in inputs %}    {{ i }}_min: float
    {{ i }}_max: float | None
{% endfor %}    {{ out }}: str

    def contains(self, {{ args }}) -> bool:
        return ({% for i in inputs %}({{ i }} >= self.{{ i }}_min and (self.{{ i }}_max is None or {{ i }} < self.{{ i }}_max)){% if not loop.last %} and {% endif %}{% endfor %})


class {{ cls }}Table:
    def __init__(self, rules: list[{{ cls }}Rule]):
        self.rules = list(rules)
{% if versioned %}
    def active_version_as_of(self, as_of: date) -> str:
        eligible = {r.effective_date for r in self.rules if r.effective_date <= as_of}
        if not eligible:
            raise NoMatchingRow(f"{as_of} 시점에 유효한 버전 없음")
        latest = max(eligible)
        return next(r.version for r in self.rules if r.effective_date == latest)
{% endif %}
    def lookup(self, {{ args }}{% if versioned %}, as_of: date{% endif %}) -> str:
{% if versioned %}        version = self.active_version_as_of(as_of)
{% endif %}        for r in self.rules:
{% if versioned %}            if r.version != version:
                continue
{% endif %}            if r.contains({{ argnames }}):
                return r.{{ out }}
        raise NoMatchingRow("어느 구간 조합에도 안 걸림")
'''
)

DT_MULTIRANGE_LOADER_T = _env.from_string(
    '''"""[GENERATED] {{ name }} 로더 — CSV(데이터) → {{ cls }}Table. 어댑터."""

from __future__ import annotations

import csv
from pathlib import Path
{% if versioned %}from datetime import date
{% endif %}
from contexts.{{ ctx }}.domain.{{ name }}_table import {{ cls }}Rule, {{ cls }}Table

_CSV = Path(__file__).resolve().parent.parent / "domain" / "decision_tables" / "{{ name }}.csv"


def _num(s: str):
    s = s.strip()
    return None if s == "" else float(s)


def load_{{ name }}_table(path: Path = _CSV) -> {{ cls }}Table:
    rules: list[{{ cls }}Rule] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(line for line in f if not line.lstrip().startswith("#"))
        for row in reader:
            rules.append({{ cls }}Rule(
{% if versioned %}                version=row["version"].strip(),
                effective_date=date.fromisoformat(row["effective_date"].strip()),
{% endif %}{% for i in inputs %}                {{ i }}_min=_num(row["{{ i }}_min"]),
                {{ i }}_max=_num(row["{{ i }}_max"]),
{% endfor %}                {{ out }}=row["{{ out }}"].strip(),
            ))
    return {{ cls }}Table(rules)
'''
)

DT_MULTIRANGE_TEST_T = _env.from_string(
    '''"""[GENERATED] {{ name }} 다차원 range 결정표 테스트 — 룩업. 스펙에서 생성."""

import unittest
{% if versioned %}from datetime import date
{% endif %}
from contexts.{{ ctx }}.domain.{{ name }}_table import {{ cls }}Rule, {{ cls }}Table
from contexts.{{ ctx }}.domain.exceptions import NoMatchingRow

{% if versioned %}_V = dict(version="v1", effective_date=date(2026, 1, 1))
{% else %}_V: dict = {}
{% endif %}

class {{ cls }}TableTest(unittest.TestCase):
    def test_lookup_hit_and_miss(self):
        t = {{ cls }}Table([
            {{ cls }}Rule(**_V, {% for i in inputs %}{{ i }}_min=0.0, {{ i }}_max=10.0, {% endfor %}{{ out }}="OUT"),
        ])
        self.assertEqual(
            t.lookup({% for i in inputs %}5.0, {% endfor %}{% if versioned %}as_of=date(2026, 6, 1){% endif %}),
            "OUT",
        )
        with self.assertRaises(NoMatchingRow):
            t.lookup({% for i in inputs %}99.0, {% endfor %}{% if versioned %}as_of=date(2026, 6, 1){% endif %})


if __name__ == "__main__":
    unittest.main()
'''
)

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

# ── 웹 어댑터(DRF) — 헥사곤 바깥 링. §2 판단 누출 방어 (DESIGN §11) ──
# 방향: web(adapters) → application(유스케이스) → domain. web은 도메인 직접 import 금지(check가 강제).

SERVICE_T = _env.from_string(
    '''"""[GENERATED 골격] {{ agg }} 유스케이스 (application). §2: 판단/계산은 도메인에, 여기선 조율만.

도메인 메서드를 호출(로드→전이/계산→저장)할 뿐, if로 규칙을 재구현하지 않는다.
아웃바운드 의존(저장소 등)은 포트로 생성자 주입받는다.
"""

from contexts.{{ ctx }}.domain.{{ snake }} import {{ agg }}


class {{ agg }}Service:
    # >>> impl: editable (유스케이스 — 도메인 호출만. 판단/계산 금지)
    def __init__(self, *deps):
        self._deps = deps
    # <<< impl
'''
)

SERIALIZER_T = _env.from_string(
    '''"""[GENERATED 골격] {{ ctx }} 직렬화기 (web adapter)."""

from rest_framework import serializers

{% for agg in aggs %}

class {{ agg }}Serializer(serializers.Serializer):
    # >>> impl: editable (필드 정의)
    pass
    # <<< impl
{% endfor %}'''
)

VIEW_T = _env.from_string(
    '''"""[GENERATED 골격] {{ ctx }} DRF 뷰 (web adapter).

§2: 비즈니스 로직 금지 — application 유스케이스만 호출한다.
도메인 직접 import 금지(check의 boundary가 막는다). 반드시 서비스를 통해서.
"""

from rest_framework.response import Response
from rest_framework.views import APIView

from contexts.{{ ctx }}.application import (
{% for agg in aggs %}    {{ agg }}Service,
{% endfor %})
from contexts.{{ ctx }}.adapters.web.serializers import (
{% for agg in aggs %}    {{ agg }}Serializer,
{% endfor %})

{% for agg in aggs %}

class {{ agg }}View(APIView):
    # >>> impl: editable (요청 파싱 → 서비스 호출 → 응답. 판단/계산 금지)
    def post(self, request):
        raise NotImplementedError
    # <<< impl
{% endfor %}'''
)

URLS_T = _env.from_string(
    '''"""[GENERATED 골격] {{ ctx }} URL 라우팅 (web adapter)."""

from django.urls import path

from contexts.{{ ctx }}.adapters.web.views import (
{% for agg in aggs %}    {{ agg }}View,
{% endfor %})

urlpatterns = [
    # >>> impl: editable (경로 ↔ 뷰 매핑)
{% for item in items %}    path("{{ item.path }}/", {{ item.agg }}View.as_view(), name="{{ item.path }}"),
{% endfor %}    # <<< impl
]
'''
)

APP_INIT_T = _env.from_string(
    '''"""[GENERATED] {{ ctx }} application — 유스케이스 모음."""

{% for agg in aggs %}from contexts.{{ ctx }}.application.{{ snakes[agg] }}_service import {{ agg }}Service
{% endfor %}
__all__ = [{% for agg in aggs %}"{{ agg }}Service"{% if not loop.last %}, {% endif %}{% endfor %}]
'''
)


CALC_T = _env.from_string(
    '''"""[GENERATED 골격] {{ agg }} — 무상태 calculation (순수 함수). I/O·상태 없음.

각 수식을 아래 impl 슬롯에 순수 함수로 구현한다(시그니처는 자유). 분기 규칙이 필요하면 결정표로 뺀다.
"""

from __future__ import annotations

{% for f in formulas %}
# >>> impl: editable — {{ f.id }}: {{ f.name }}
def {{ fns[f.id] }}(*args, **kwargs):
    raise NotImplementedError
# <<< impl

{% endfor %}'''
)

REF_T = _env.from_string(
    '''"""[GENERATED 골격] {{ agg }} — 참조(reference) 데이터. 마스터/룩업, 거의 불변.

조회 모델/인터페이스는 impl에 정의한다(또는 결정표·어댑터로 적재).
"""

from __future__ import annotations

# >>> impl: editable — {{ agg }} 참조 모델/조회
# <<< impl
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
        has_agg = any(d.kind == "aggregate" for d in c.domains.values())
        if c.domains or c.decision_tables:
            w(f"{base}/domain/__init__.py", "")
            w(f"{base}/domain/exceptions.py",
              EXC_T.render(ctx=c.name, ctxcap=c.name.capitalize(),
                           has_aggregates=has_agg, has_tables=bool(c.decision_tables)))
        for agg, d in c.domains.items():
            _emit_domain(w, c, agg, d)
        if c.decision_tables:
            _emit_decision_tables(w, out, written, c)
        if spec.infrastructure.web == "drf" and has_agg:
            _emit_web(w, c)

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
            ports, seen = [], set()
            for i, p in enumerate(d.ports_out, 1):
                cls = _pascal(_ident(p)) or f"Port{i}"
                if cls in seen:
                    cls = f"{cls}{i}"
                seen.add(cls)
                ports.append({"cls": cls, "original": p})
            w(f"{base}/ports/__init__.py", "")
            w(f"{base}/ports/ports_out.py", PORTS_T.render(ctx=c.name, ports=ports))
    elif d.kind == "calculation":
        fns = {f.id: (_ident(f.name) or _ident(f.id)) for f in d.formulas}
        w(f"{base}/domain/{_snake(agg)}.py",
          CALC_T.render(agg=agg, formulas=d.formulas, fns=fns))
    elif d.kind == "reference":
        w(f"{base}/domain/{_snake(agg)}.py", REF_T.render(agg=agg))


def _emit_decision_tables(w, out: Path, written: list[str], c: Context) -> None:
    """결정표 → CSV 스텁 + 순수 평가기(domain) + CSV 로더(adapter) + 테스트.

    range(단일 입력)=구간 룩업+버저닝+완전성 검사, range(다중 입력)=N차원 구간 룩업(완전성 생략),
    lookup/flag=정확매칭 룩업. 모두 평가기(domain)+CSV 로더(adapter)+테스트를 생성."""
    base = f"contexts/{c.name}"
    w(f"{base}/adapters/__init__.py", "")
    for t in c.decision_tables:
        slug = _table_slug(t)
        cls = _pascal(slug)
        is_range = t.kind == "range" and len(t.inputs) == 1
        is_multirange = t.kind == "range" and len(t.inputs) > 1
        # 입력/출력명을 안전한 파이썬 식별자로 정규화 (공백·특수문자·비ASCII → 위치 폴백)
        inputs_safe = [_ident(n) or f"in{i}" for i, n in enumerate(t.inputs, 1)]
        out_safe = _ident(t.output) or "out"

        cols: list[str] = []
        if t.versioned:
            cols += ["version", "effective_date"]
        if is_range or is_multirange:
            for i in inputs_safe:
                cols += [f"{i}_min", f"{i}_max"]
        else:
            cols += list(inputs_safe)
        cols += [out_safe]
        legend = [f"{s}={o}" for s, o in zip(inputs_safe, t.inputs) if s != o]
        if out_safe != t.output:
            legend.append(f"{out_safe}={t.output}")
        legend_note = ("  컬럼매핑: " + ", ".join(legend)) if legend else ""
        w(f"{base}/domain/decision_tables/{slug}.csv",
          f"# [GENERATED 스텁] {t.id} {t.name} (kind={t.kind}). 행(데이터)을 채워라.{legend_note}\n"
          f"{','.join(cols)}\n")

        common = dict(ctx=c.name, name=slug, cls=cls, out=out_safe,
                      versioned=t.versioned, id=t.id, kind=t.kind)
        if is_range:
            inp = inputs_safe[0]
            w(f"{base}/domain/{slug}_table.py", DT_RANGE_T.render(inp=inp, **common))
            w(f"{base}/adapters/{slug}_loader.py", DT_RANGE_LOADER_T.render(inp=inp, **common))
            _write(out / "tests" / f"test_{c.name}_{slug}_table.py",
                   DT_RANGE_TEST_T.render(inp=inp, **common))
        elif is_multirange:
            args = ", ".join(f"{i}: float" for i in inputs_safe)
            argnames = ", ".join(inputs_safe)
            w(f"{base}/domain/{slug}_table.py",
              DT_MULTIRANGE_T.render(inputs=inputs_safe, args=args, argnames=argnames, **common))
            w(f"{base}/adapters/{slug}_loader.py",
              DT_MULTIRANGE_LOADER_T.render(inputs=inputs_safe, **common))
            _write(out / "tests" / f"test_{c.name}_{slug}_table.py",
                   DT_MULTIRANGE_TEST_T.render(inputs=inputs_safe, **common))
        else:
            tail = "," if len(inputs_safe) == 1 else ""
            args = ", ".join(f"{i}: str" for i in inputs_safe)
            keyexpr = ", ".join(inputs_safe) + tail
            rulekey = ", ".join(f"r.{i}" for i in inputs_safe) + tail
            w(f"{base}/domain/{slug}_table.py",
              DT_LOOKUP_T.render(inputs=inputs_safe, args=args, keyexpr=keyexpr,
                                 rulekey=rulekey, **common))
            w(f"{base}/adapters/{slug}_loader.py",
              DT_LOOKUP_LOADER_T.render(inputs=inputs_safe, **common))
            _write(out / "tests" / f"test_{c.name}_{slug}_table.py",
                   DT_LOOKUP_TEST_T.render(inputs=inputs_safe, **common))
        written.append(f"tests/test_{c.name}_{slug}_table.py")


def _emit_web(w, c: Context) -> None:
    """웹 어댑터(DRF) + application 유스케이스. §2: web→application→domain (도메인 직접 import 금지)."""
    base = f"contexts/{c.name}"
    aggs = [a for a, d in c.domains.items() if d.kind == "aggregate"]
    if not aggs:
        return
    snakes = {a: _snake(a) for a in aggs}

    # application 유스케이스 (도메인 호출만)
    for a in aggs:
        w(f"{base}/application/{snakes[a]}_service.py",
          SERVICE_T.render(ctx=c.name, agg=a, snake=snakes[a]))
    w(f"{base}/application/__init__.py",
      APP_INIT_T.render(ctx=c.name, aggs=aggs, snakes=snakes))

    # web 어댑터 (유스케이스만 호출, 도메인 직접 import 금지)
    w(f"{base}/adapters/__init__.py", "")
    w(f"{base}/adapters/web/__init__.py", "")
    w(f"{base}/adapters/web/serializers.py", SERIALIZER_T.render(ctx=c.name, aggs=aggs))
    w(f"{base}/adapters/web/views.py", VIEW_T.render(ctx=c.name, aggs=aggs))
    items = [{"agg": a, "path": snakes[a]} for a in aggs]
    w(f"{base}/adapters/web/urls.py", URLS_T.render(ctx=c.name, aggs=aggs, items=items))


def main(spec_path: str, out_dir: str) -> None:
    spec = load_spec(spec_path)          # §16.5 검증 통과해야 진행
    files = scaffold(spec, out_dir)
    print(f"generated {len(files)} files into {out_dir}")


if __name__ == "__main__":
    import sys
    main(sys.argv[1], sys.argv[2])
