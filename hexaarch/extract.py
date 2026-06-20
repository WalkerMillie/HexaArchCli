"""extract — 정책문서 → 스펙 초안. (DESIGN §4, §16.5)

파이프라인: 정책 텍스트 + Spec의 JSON 스키마(강제) → LLM → dict
            → Spec.model_validate(의미 검증) → 실패 시 오류를 되먹여 복구 재시도.

스키마는 '형태'만 보장한다. "전이는 선언된 상태만", "가드 edge는 실재 전이만",
"자기 전이 금지" 같은 의미 규칙은 spec.py 검증기가 잡는다 — 그래서 LLM 출력도
반드시 model_validate를 통과해야 다음 단계(scaffold)로 간다(§16.5: 깨진 IR 거부).
extract는 사람을 대신해 그 검증 오류를 LLM에 되먹여 자가 복구한다.
"""

from __future__ import annotations

import yaml
from pydantic import ValidationError

from hexaarch.llm.base import LLMBackend, LLMError
from hexaarch.spec import Spec

SYSTEM = """너는 헥사고날/클린 아키텍처 도메인 모델러다.
주어진 정책/기획 문서를 읽고 domain-spec.yaml에 해당하는 구조(JSON)를 추출한다.

규칙:
- 바운디드 컨텍스트별로 contexts에 나눈다.
- 상태기계(생명주기)가 있는 개념은 kind: aggregate 로, states와 transitions를 채운다.
  transitions는 {출발상태: [도착상태...]}. 자기 전이(같은 상태로)는 금지.
- 조건/자격에 따라 갈리는 전이는 guards에 넣는다. 필드명은 edge이고 형식은 "출발->도착".
  edge는 반드시 실재하는 transition이어야 한다.
- 순수 계산/공식은 kind: calculation 으로 formulas에 넣는다(계산은 반드시 formulas 필요).
- 규칙표·요율표·룩업·구간표는 decision_tables에 넣는다(kind: range|lookup|flag).
- 단순 참조 데이터는 kind: reference.
- 각 id는 문서의 요구사항 ID를 쓰고, 없으면 컨텍스트약자-001 식으로 부여한다.
- 컨텍스트 간 의존은 relations(to/via: event|call)로 표현한다.
- 문서에 근거가 있는 것만 만든다. 추측으로 지어내지 말고, 모르면 비운다.

**계층 분리(가장 중요)** — 도메인 코어에는 '판단·규칙·생명주기'만 둔다:
- 표현/UI(정렬·화면), 내보내기(CSV/리포트), 로깅·감사, 성능 목표, 인증/인가 같은
  비도메인 관심사는 스펙에 도메인 요소로 **만들지 마라**(어댑터/인프라 몫 — 제외).
- 알림·이메일·외부 API 호출처럼 '바깥으로 나가는' 의존은 도메인 로직이 아니라
  ports_out(아웃바운드 포트) 이름으로 표현한다.
- 계산은 calculation, 표/요율은 decision_tables로 빼서 도메인 코어를 얇게 유지한다.

**이름 규칙** — contexts.name·도메인(애그리거트) 키·states는 그대로 코드 식별자가 된다.
  반드시 **영문**으로: 컨텍스트=lower_snake, 애그리거트=PascalCase, 상태=UPPER_SNAKE.
  한글/공백 금지. 한글 원문은 desc/name(설명 필드)에만 쓴다.

출력은 제공된 JSON 스키마를 정확히 따른다."""


def build_schema() -> dict:
    return Spec.model_json_schema()


def extract(policy_text: str, backend: LLMBackend, *,
            model: str | None = None, max_repair: int = 2) -> Spec:
    schema = build_schema()
    user = f"다음 정책 문서에서 스펙을 추출하라.\n\n----\n{policy_text}\n----"
    last_err: Exception | None = None
    for _ in range(max_repair + 1):
        raw = backend.complete(system=SYSTEM, user=user, json_schema=schema, model=model)
        try:
            return Spec.model_validate(raw)
        except ValidationError as e:
            last_err = e
            user = (
                f"다음 정책 문서에서 스펙을 추출하라.\n\n----\n{policy_text}\n----\n\n"
                f"[직전 출력이 의미 검증에서 실패했다. 아래 오류를 고쳐 다시 출력하라.]\n{e}"
            )
    raise LLMError(f"{max_repair + 1}회 시도 후에도 스펙 검증 실패:\n{last_err}")


def spec_to_yaml(spec: Spec) -> str:
    data = spec.model_dump(exclude_defaults=True)
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
