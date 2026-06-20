"""변경 게이트 — *스펙* 변경의 충돌 자동 판정. (DESIGN §10)

`check`가 고정된 스펙 대비 '코드 편집'을 막는다면, `gate`는 '스펙 변경' 자체를 막는다.
두 개의 (이미 검증을 통과한) 스펙 old→new를 구조 비교해 변경마다 판정한다:

  - **pass(통과)**: 가산적·하위호환. 기존 코드/데이터/보장을 깨지 않음.
        컨텍스트/도메인/상태/전이/가드/불변식/수식/포트/결정표 *추가*.
  - **review(대안)**: 재조정 가능하나 마이그레이션/사람 판단 필요.
        전이 제거(상태머신 강화 — 진행중 인스턴스 고립 위험), rename 의심,
        결정표 versioned 토글, 관계/포트 제거.
  - **reject(거부)**: 기존 보장을 *조용히* 제거하거나 데이터/코드를 무효화.
        상태/가드/불변식/수식/도메인/컨텍스트 *제거*, 도메인 kind 변경,
        결정표 모양(kind/inputs/output) 변경.

핵심 철학: 가드(가드·불변식·상태)를 제거하는 변경의 기본값은 **거부**다.
"원본 규칙을 조용히 깨지 않는다"가 이 프레임워크의 존재 이유 — 정말 제거하려면
마이그레이션 + 명시 결재(--allow-breaking)로만 통과시킨다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from hexaarch.spec import Context, Domain, Spec

_ORDER = {"pass": 0, "review": 1, "reject": 2}
_SYMBOL = {"pass": "✓", "review": "△", "reject": "✗"}


@dataclass
class Change:
    verdict: str        # "pass" | "review" | "reject"
    kind: str           # 예: "state.remove", "guard.add"
    where: str          # 예: "valuation.AnalysisEligibility"
    detail: str
    suggestion: str = ""

    def __str__(self) -> str:
        head = f"  {_SYMBOL[self.verdict]} [{self.kind}] {self.where} — {self.detail}"
        if self.suggestion:
            head += f"\n      ↳ 대안: {self.suggestion}"
        return head


@dataclass
class GateReport:
    changes: list[Change] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        return max((c.verdict for c in self.changes),
                   key=lambda v: _ORDER[v], default="pass")

    @property
    def passed(self) -> bool:
        return self.verdict == "pass"

    def counts(self) -> dict[str, int]:
        out = {"pass": 0, "review": 0, "reject": 0}
        for c in self.changes:
            out[c.verdict] += 1
        return out


# ── 변경 분해 ────────────────────────────────────────────────────────────

def _edges(d: Domain) -> set[str]:
    return {f"{frm}->{to}" for frm, tos in d.transitions.items() for to in tos}


def _diff_domain(ctx: str, agg: str, o: Domain, n: Domain) -> list[Change]:
    where = f"{ctx}.{agg}"
    out: list[Change] = []

    if o.kind != n.kind:
        out.append(Change("reject", "domain.kind", where,
                          f"종류 변경 {o.kind}→{n.kind} — 골격 형태가 통째로 바뀜",
                          "새 도메인으로 추가하고 기존을 마이그레이션 후 제거"))

    o_states, n_states = set(o.states), set(n.states)
    added_states = n_states - o_states
    removed_states = o_states - n_states
    for s in sorted(added_states):
        out.append(Change("pass", "state.add", where, f"상태 추가 '{s}'"))
    for s in sorted(removed_states):
        sug = ""
        if added_states:
            sug = f"추가된 상태({', '.join(sorted(added_states))})와 함께면 rename일 수 있음 — rename 마이그레이션 고려"
        out.append(Change("reject", "state.remove", where,
                          f"상태 제거 '{s}' — 그 상태의 기존 인스턴스/코드 무효화",
                          sug or "제거 전 해당 상태 인스턴스 마이그레이션 + --allow-breaking"))

    o_edges, n_edges = _edges(o), _edges(n)
    for e in sorted(n_edges - o_edges):
        out.append(Change("pass", "transition.add", where, f"전이 추가 '{e}'"))
    for e in sorted(o_edges - n_edges):
        out.append(Change("review", "transition.remove", where,
                          f"전이 제거 '{e}' — 상태머신 강화(진행중 인스턴스 고립 위험)",
                          "해당 전이를 기다리는 인스턴스가 없는지 확인 후 진행"))

    out += _diff_by_id(where, "guard", o.guards, n.guards, remove_verdict="reject",
                       remove_detail="가드 제거 — 안전 규칙을 조용히 약화",
                       remove_sug="정말 제거하려면 결정 근거 문서화 + --allow-breaking")
    out += _diff_by_id(where, "invariant", o.invariants, n.invariants, remove_verdict="reject",
                       remove_detail="불변식 제거 — 보장을 약화",
                       remove_sug="결정 근거 문서화 + --allow-breaking")
    out += _diff_by_id(where, "formula", o.formulas, n.formulas, remove_verdict="reject",
                       remove_detail="수식 제거 — 계산 소비자가 깨짐",
                       remove_sug="소비자 이전 후 제거")

    o_ports, n_ports = set(o.ports_out), set(n.ports_out)
    for p in sorted(n_ports - o_ports):
        out.append(Change("pass", "port.add", where, f"아웃바운드 포트 추가 '{p}'"))
    for p in sorted(o_ports - n_ports):
        out.append(Change("review", "port.remove", where,
                          f"포트 제거 '{p}' — 합성 루트 배선이 깨질 수 있음",
                          "어댑터/배선 정리 후 제거"))
    return out


def _diff_by_id(where, label, old_items, new_items, *,
                remove_verdict, remove_detail, remove_sug) -> list[Change]:
    out: list[Change] = []
    o = {x.id: x for x in old_items}
    n = {x.id: x for x in new_items}
    for i in sorted(n.keys() - o.keys()):
        out.append(Change("pass", f"{label}.add", where, f"{label} 추가 '{i}'"))
    for i in sorted(o.keys() - n.keys()):
        out.append(Change(remove_verdict, f"{label}.remove", where,
                          f"{remove_detail} ('{i}')", remove_sug))
    for i in sorted(o.keys() & n.keys()):
        if o[i].model_dump() != n[i].model_dump():
            out.append(Change("review", f"{label}.change", where,
                              f"{label} '{i}' 내용 변경",
                              "의미가 바뀐 건지 확인 — 바뀌었으면 새 id로 추가 권장"))
    return out


def _diff_context(o: Context, n: Context) -> list[Change]:
    out: list[Change] = []
    ctx = o.name

    for agg in sorted(n.domains.keys() - o.domains.keys()):
        out.append(Change("pass", "domain.add", f"{ctx}.{agg}", "새 도메인 추가"))
    for agg in sorted(o.domains.keys() - n.domains.keys()):
        out.append(Change("reject", "domain.remove", f"{ctx}.{agg}",
                          "도메인 제거 — 기존 코드/데이터 무효화",
                          "마이그레이션 후 --allow-breaking"))
    for agg in sorted(o.domains.keys() & n.domains.keys()):
        out += _diff_domain(ctx, agg, o.domains[agg], n.domains[agg])

    ot = {t.name: t for t in o.decision_tables}
    nt = {t.name: t for t in n.decision_tables}
    for name in sorted(nt.keys() - ot.keys()):
        out.append(Change("pass", "decision_table.add", f"{ctx}.{name}", "결정표 추가"))
    for name in sorted(ot.keys() - nt.keys()):
        out.append(Change("reject", "decision_table.remove", f"{ctx}.{name}",
                          "결정표 제거 — CSV 데이터/소비자 무효화", "소비자 이전 후 제거"))
    for name in sorted(ot.keys() & nt.keys()):
        a, b = ot[name], nt[name]
        if (a.kind, a.inputs, a.output) != (b.kind, b.inputs, b.output):
            out.append(Change("reject", "decision_table.shape", f"{ctx}.{name}",
                              "결정표 모양(kind/inputs/output) 변경 — CSV 컬럼/소비자 깨짐",
                              "새 결정표로 추가하고 기존 데이터 이전"))
        elif a.versioned != b.versioned:
            out.append(Change("review", "decision_table.versioned", f"{ctx}.{name}",
                              f"versioned 토글 {a.versioned}→{b.versioned}",
                              "기존 CSV에 version/effective_date 컬럼 마이그레이션 필요"))

    orl = {(r.to, r.via, r.event) for r in o.relations}
    nrl = {(r.to, r.via, r.event) for r in n.relations}
    for r in sorted(nrl - orl):
        out.append(Change("pass", "relation.add", ctx, f"관계 추가 {r}"))
    for r in sorted(orl - nrl):
        out.append(Change("review", "relation.remove", ctx, f"관계 제거 {r}",
                          "이 관계에 의존하는 배선/소비자 확인"))
    return out


def diff_specs(old: Spec, new: Spec) -> list[Change]:
    out: list[Change] = []
    o = {c.name: c for c in old.contexts}
    n = {c.name: c for c in new.contexts}
    for name in sorted(n.keys() - o.keys()):
        out.append(Change("pass", "context.add", name, "새 컨텍스트 추가"))
    for name in sorted(o.keys() - n.keys()):
        out.append(Change("reject", "context.remove", name,
                          "컨텍스트 제거 — 기존 코드/데이터 무효화",
                          "마이그레이션 후 --allow-breaking"))
    for name in sorted(o.keys() & n.keys()):
        out += _diff_context(o[name], n[name])
    out.sort(key=lambda c: (c.where, c.kind))
    return out


def gate(old: Spec, new: Spec) -> GateReport:
    return GateReport(diff_specs(old, new))
