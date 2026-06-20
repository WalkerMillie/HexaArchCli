# HexaArch

> **Policy-Driven Hexagonal Scaffolding Framework**
> 정책 문서에서 헥사고날/클린 아키텍처 골격을 **결정론적으로 생성**하고,
> 상태·불변식·경계를 **빌드 단계에서 강제**하는 메타 프레임워크.

설계 철학: *"자동 생성"이 아니라 "명시적 모델 + 자동 강제".*

---

## 왜 만드는가 (의의)

소프트웨어가 망가지는 가장 흔한 경로는 **변경의 전파**다. 한 곳을 고치면
도메인 규칙이 어댑터로 새고, 컨텍스트 경계가 무너지고, 누군가 상태 전이 가드를
"잠깐만" 풀어버린다. AI/에이전트로 빠르게 코드를 짜는 시대(바이브코딩)에는 이
속도가 더 빨라진다.

HexaArch는 **단일 정책 스펙(`domain-spec.yaml`)을 진실의 원천(SSOT)으로 삼아**:

1. 거기서 헥사고날 골격을 **결정론적으로 생성**하고 (같은 스펙 → 같은 바이트),
2. 판단(도메인 코어)과 입출력(어댑터)을 구조적으로 분리하며,
3. **계속 코드를 짜도** 원본 규칙·아키텍처가 깨지지 않게 두 개의 가드로 막는다.

목표는 한 줄이다 — **"지속적으로 바이브코딩을 해도, 구조 레벨에서 원본 규칙과
가드 경계가 깨지지 않는 프로젝트."**

---

## 핵심 개념 (간단 규격)

```
정책문서 ──extract──▶ domain-spec.yaml ──scaffold──▶ 골격 ──[바이브코딩]──▶ check / gate
   (LLM)                  (SSOT, 검증)      (결정론)                       (두 입구 가드)
```

| 단계 | 하는 일 |
|---|---|
| **select-arch** | (자문) 정책문서 → 바운디드 컨텍스트 분해 **대안 N개** + 장단점/추천. 스펙 확정 전 설계 탐색. |
| **extract** | 정책/기획 문서 → 스펙 초안. 사용자 Claude 세션(`claude -p`)으로 추출 후 **검증→자가복구** 루프. |
| **validate** | 스펙을 Pydantic + 의미 규칙으로 검증. 깨진 IR(미정의 상태 전이·자기 전이·가드 불일치 등)은 생성 *전에* 거부. |
| **scaffold** | 스펙 → 상태 머신·`_transition`·예외·포트·전이 매트릭스 테스트·경계 가드·`AGENTS.md` 생성. 결정표는 *순수 평가기*(range 구간 룩업 + `effective_date` 버저닝 + **완전성 검사**)와 CSV 로더(어댑터)로 생성. `infrastructure.web: drf`면 application 유스케이스 + DRF 어댑터(serializer/view/urls)까지 생성하고 **web→application→domain** 방향을 강제(§2 판단 누출 방어). — "정책을 도메인 코어에 박는다". |
| **check** | (코드 편집 가드) 매 편집 후 "원본 규칙이 깨졌는지" 판정. `스펙 재생성 → impl 블록만 빼고 비교(drift) + 도메인 import 스캔(boundary)`. |
| **gate** | (스펙 변경 가드) 스펙 old→new를 비교해 **통과/대안/거부**. 가드·불변식·상태 제거는 기본 거부. |

### 두 가지 보호 영역

- **생성/보존 경계 (`>>> generated` / `>>> impl`)**: 골격은 재생성 대상, 비즈니스 로직은 보존.
  바이브코딩은 `>>> impl` 블록 안에서만, 그리고 새 파일로 한다. 그 밖을 건드리면 `check`가 **drift**로 잡는다.
- **도메인 경계**: `contexts/*/domain/`은 어댑터·인프라·타 컨텍스트를 import 금지(`adapters`, `django`,
  `sqlalchemy`, `requests`, `celery` …). impl 블록 안에서도 경계는 못 넘는다 → `check`가 **boundary**로 잡는다.
- **§2 판단 누출 방어**: 웹 어댑터(`adapters/web/`)는 도메인을 직접 import 금지 — 반드시 `application` 유스케이스를 통한다. 뷰에 비즈니스 로직이 새는 걸 구조로 막는다 → `check`가 **boundary**로 잡는다.

### 스펙 한눈에 (`domain-spec.yaml`)

```yaml
version: "0.1"
infrastructure: {database: pg, messaging: redis, task_queue: celery, web: drf}  # web 생략 시 미생성
contexts:
  - name: valuation
    domains:
      AnalysisEligibility:           # 상태기계가 있는 개념
        kind: aggregate
        states: [LOCKED, READY, ANALYZED]
        transitions: {LOCKED: [READY], READY: [ANALYZED]}
        guards:                      # 조건부 전이 — edge는 실재 전이여야 함
          - {edge: "LOCKED->READY", id: VAL-005, desc: 거래량 임계 이상이면 해제}
        invariants:
          - {id: VAL-003, desc: READY 아니면 분석 산출 불가}
      Breakeven:                     # 순수 계산
        kind: calculation
        formulas: [{id: VAL-F1, name: 손익분기 상승률}]
    decision_tables:                 # 규칙표·요율표
      - {name: loan_limit, kind: range, inputs: [price], output: max_loan, versioned: true, id: REG-001}
    relations:
      - {to: collection, via: event, event: CollectionSucceeded}
```

---

## 설치

```bash
pip install -e .            # 의존: pyyaml, pydantic, jinja2
```

## 사용법

```bash
# 0) (선택) 아키텍처 분해 대안 탐색 — 스펙 확정 전 설계 자문
hexaarch select-arch examples/seoul-apt/policy.md --n 3 --model sonnet

# 1) 정책문서 → 스펙 초안 (사용자 Claude 로그인 필요, 별도 API 키 X)
hexaarch extract  examples/seoul-apt/policy.md ./spec.yaml --model sonnet

# 2) 검증 → 골격 생성
hexaarch validate examples/seoul-apt/domain-spec.yaml
hexaarch scaffold examples/seoul-apt/domain-spec.yaml ./out

# 3) 바이브코딩 후 — 규칙이 깨졌는지 (편집할 때마다)
hexaarch check    examples/seoul-apt/domain-spec.yaml ./out

# 4) 스펙을 바꿀 때 — 변경이 안전한지
hexaarch gate     old-spec.yaml new-spec.yaml
```

설치 없이 모듈로: `PYTHONPATH=. python3 -m hexaarch.cli <command> ...`

`extract`는 사용자의 기존 Claude Code 로그인을 그대로 쓴다. 미인증이면 `claude setup-token` 또는 `claude login`.

### 종료 코드

| 코드 | 의미 |
|---|---|
| 0 | 통과 |
| 2 | 스펙 검증 실패 (깨진 IR) |
| 3 | `check` 위반 (drift / boundary / missing) |
| 4 | `gate` 대안 필요 (review) |
| 5 | `gate` 거부 (reject) — `--allow-breaking`으로만 통과 |
| 6 | `extract` 실패 |

---

## 구조

```
hexaarch/            # 본체 (순수 Python, FastAPI 불필요)
  spec.py            #   스펙 IR + Pydantic 검증 + 스펙레벨 충돌 판정
  scaffold.py        #   결정론 생성기 (YAML + Pydantic + Jinja2)
  check.py           #   변경 가드 (drift + boundary)
  gate.py            #   변경 게이트 (스펙 old→new 충돌 판정)
  extract.py         #   정책문서 → 스펙 (추출→검증→자가복구 루프)
  select_arch.py     #   정책문서 → 아키텍처 분해 대안 N개 (LLM 자문)
  llm/               #   LLM 백엔드 추상화 (ClaudeSessionBackend 기본 = claude -p)
  cli.py             #   argparse CLI
examples/seoul-apt/  # 드라이브 케이스 (서울 아파트 의사결정 분석)
  policy.md          #   원본 정책 문서
  domain-spec.yaml   #   추출/정제된 스펙 (SSOT)
  reference/         #   손작업 골든 레퍼런스 — "헥사고날 준수"의 조작적 정의 (32 tests)
docs/PHASE-CONTEXT.md  # 설계·검증 과정 기록
tests/               # 본체 테스트
DESIGN-v0.5.md       # 전체 설계 문서
```

## 검증 상태

```bash
PYTHONPATH=. python3 -m unittest discover -s tests                      # 본체 32 tests
cd examples/seoul-apt/reference && PYTHONPATH=src python3 -m unittest discover -s tests   # 레퍼런스 32 tests
```

입증된 가설(실측):
- **결정론**: 같은 스펙 → 같은 골격(바이트 동일).
- **수렴**: 생성 골격의 상태 전이 테이블 == 손작업 레퍼런스.
- **가드의 이빨**: `_transition`/상태표 변조→drift, 도메인의 금지 import→boundary, 골격 삭제→missing,
  가드·불변식 제거(스펙)→gate 거부. 정상 작업(impl 편집·새 파일)은 통과.
- **전 파이프라인 라이브**: 실제 정책문서(12KB) → `extract`(≈4분) → 검증 통과 스펙 → `scaffold`(27파일)
  → `check` 통과 → 생성 프로젝트 자체 테스트 green.

## 로드맵

1. ✅ 검증 + 결정론 생성 + 경계/상태 가드
2. ✅ 변경 가드 `check` (§9) · 변경 게이트 `gate` (§10)
3. ✅ LLM `extract` (사용자 Claude 세션)
4. ✅ 결정표 로직 생성 (range 룩업·버저닝·완전성 검사 + CSV 로더)
5. ✅ `select-arch` (아키텍처 분해 대안 제시, LLM 자문)
6. ✅ DRF 어댑터/view 스텁 생성 + §2 web→application→domain 경계 강제

## 기술 스택

Python 3.12 · PyYAML · Pydantic 2 · Jinja2 · (stdlib `unittest`/`argparse`/`ast`) · `claude` CLI (extract)
