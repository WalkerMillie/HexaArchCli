"""select-arch — 정책문서 → 아키텍처 대안 N개. (DESIGN §4 설계 탐색)

`extract`(문서→스펙)의 *앞단*. 스펙을 확정하기 전에 "이 도메인을 어떻게 가를까"의
서로 다른 바운디드 컨텍스트 분해 대안을 장단점과 함께 제시한다 — 사람이 고른다(자문).

extract와 같은 골격: 사용자 Claude 세션 + JSON 스키마 강제 + Pydantic 검증.
출력은 스펙이 아니라 '결정 자료'다 — scaffold로 바로 가지 않는다.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError

from hexaarch.llm.base import LLMBackend, LLMError


class ArchContext(BaseModel):
    name: str
    responsibility: str


class ArchOption(BaseModel):
    name: str
    summary: str
    contexts: list[ArchContext]
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    recommended: bool = False


class ArchProposal(BaseModel):
    alternatives: list[ArchOption]
    recommendation: str


SYSTEM = """너는 DDD/헥사고날 아키텍트다. 정책/기획 문서를 읽고
'이 도메인을 어떻게 바운디드 컨텍스트로 가를까'의 서로 다른 분해 대안을 제시한다.

규칙:
- 대안끼리는 실제로 달라야 한다(컨텍스트 경계의 위치·수·응집 기준이 다르게).
  예: 수집/판단/규제로 가르기 vs 사용자여정 중심 vs 데이터수명주기 중심.
- 각 대안은 컨텍스트 목록(name + responsibility 한 줄)과 pros/cons를 갖는다.
- 트레이드오프는 구체적으로: 결합도, 변경 파급, 트랜잭션 경계, 팀 분담, 과설계 위험 등.
- 정확히 하나의 대안에만 recommended=true. 마지막 recommendation에 '무엇을 왜' 한 문단.
- 문서 근거로만. 지어내지 말 것.
출력은 제공된 JSON 스키마를 정확히 따른다."""


def build_schema() -> dict:
    return ArchProposal.model_json_schema()


def select_arch(policy_text: str, backend: LLMBackend, *,
                n: int = 3, model: str | None = None, max_repair: int = 1) -> ArchProposal:
    schema = build_schema()
    user = (f"다음 정책 문서를 읽고 서로 다른 아키텍처(바운디드 컨텍스트 분해) 대안을 "
            f"{n}개 제시하라.\n\n----\n{policy_text}\n----")
    last_err: Exception | None = None
    for _ in range(max_repair + 1):
        raw = backend.complete(system=SYSTEM, user=user, json_schema=schema, model=model)
        try:
            return ArchProposal.model_validate(raw)
        except ValidationError as e:
            last_err = e
            user = (f"다음 정책 문서로 아키텍처 대안 {n}개를 제시하라.\n\n----\n{policy_text}\n----\n\n"
                    f"[직전 출력이 검증 실패. 아래 오류를 고쳐 다시 출력하라.]\n{e}")
    raise LLMError(f"{max_repair + 1}회 시도 후에도 검증 실패:\n{last_err}")


def render_text(p: ArchProposal) -> str:
    lines: list[str] = []
    for i, opt in enumerate(p.alternatives, 1):
        star = " ★추천" if opt.recommended else ""
        lines.append(f"\n[{i}] {opt.name}{star}")
        lines.append(f"    {opt.summary}")
        lines.append("    컨텍스트:")
        for c in opt.contexts:
            lines.append(f"      - {c.name}: {c.responsibility}")
        if opt.pros:
            lines.append("    + " + " / ".join(opt.pros))
        if opt.cons:
            lines.append("    − " + " / ".join(opt.cons))
    lines.append(f"\n추천: {p.recommendation}")
    return "\n".join(lines)
