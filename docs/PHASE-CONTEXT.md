# HexaArch — Phase 2 작업 컨텍스트 앵커

> ⚠️ 이 문서의 목적: **좁게 파고들 때 전체 맥락 유실 방지.** 세션이 바뀌거나 좁은 작업에 매몰돼도
> 여기만 보면 "지금 어디고, 무엇을 미뤘고, 왜 이렇게 정했나"가 복원된다. 작업 진행마다 갱신.

## 0. 전체 그림 (페이즈)

- **Phase 0 (완료)**: 설계안 `DESIGN-v0.5.md`, 드라이브케이스 `examples/seoul-apt/policy.md` (rev1).
- **Phase 1 (완료, 폐기)**: seoul-apt를 §4.1 스펙으로 강제 응결 → 스키마 한계 8개 채집(아래 §2). 산출물은 스크래치패드(폐기).
- **Phase 2 (진행중)**: 레퍼런스 골격 풀 설계 + 구현. **좁게 시작**: `valuation` 게이트부터, 가드 A/B 비교 검증.
- **Phase 3 (예정)**: 스펙에서 재생성 → 레퍼런스와 대조 검증.

## 1. 고정된 설계 결정 (바뀌면 안 됨)

- 본체 = 순수 Python/Typer CLI (FastAPI 불필요).
- LLM = 사용자 Claude 구독 세션(`claude -p` + `setup-token`), API키 폴백.
- 생성 디폴트 = **DRF** (단 계산/판단은 도메인 코어 강제, §2 누출 방어).
- 생성물 배포 = git + docker compose, K3s는 옵트인 애드온 (seoul-apt는 미배포).
- 진행 = 문서 §15 순서.

## 2. Phase 1에서 채집한 스키마 한계 8개 + 처리 방침

| # | 한계 | 처리 | 상태 |
|---|------|------|------|
| 0 | 멀티 컨텍스트 미지원 | 🟢 `contexts:` 리스트로 확장 | 설계논의 보류(확정 안 함) |
| 4 | `policies` 의미 과적재(수식 vs 결정표) | 🟢 `decision_tables:`↔`formulas:` 분리 | 설계논의 보류 |
| 5 | 무상태 도메인 표현 불가 | 🟢 `kind: aggregate\|calculation\|reference` | 설계논의 보류 |
| 6 | 결정표 필드 부재 | 🟢 `kind: range\|lookup\|flag` | 설계논의 보류 |
| 7 | 결정표 버저닝 부재 | 🟢 `effective_date`/`version` | 설계논의 보류 |
| 8 | `messaging`(이벤트)↔작업큐 혼동 | 🟢 `messaging`/`task_queue` 분리 | 설계논의 보류 |
| 1 | 동시성 불변식(관계 불변식) | 🟡 impl(DB 유니크/락) | ✅ 실측 — Aggregate 밖, JobRegistry(어댑터/스토어)가 강제. 멱등 upsert도 |
| **2** | **조건부 전이(guard)** | 🔴 A/B 실험 | ✅ **해결 — B형 채택**(가드는 Aggregate, 크로스데이터는 VO 주입) |
| **3** | **크로스컨텍스트 불변식** | 🔴 A/B 실험 | ✅ **해결 — B형 + 합성루트 배선**(실물 결정표로 닫음) |
| 5 | 무상태 도메인 | 🟢 kind:calculation | ✅ 실측(breakeven/roe 순수 수식) |
| 6 | 결정표 range | 🟢 kind:range | ✅ 실측(loan_limit.csv + LoanLimitTable) |
| 7 | 결정표 버저닝 | 🟢 effective_date | ✅ 실측(v1/v2 공존, as_of 선택) |
| **9** | **컨텍스트 간 동기 쿼리 배선** (regulation 추가하며 신규 발견) | 🟢 합성루트(composition root) + 소비자정의 포트 | ✅ 실측(`composition/wiring.py`) |

> 🟢 (0,4,8)은 아직 "설계만 논의" — 스펙 스키마 형태 이슈라 Phase 3(스펙 작성) 때 드러남. (0 멀티컨텍스트, 4 policies 분리, 8 messaging/task_queue).
>
> **검증 현황**: `examples/seoul-apt/reference/` 23/23 green. §9-①②③④ 전부 구현+이빨 확인.
> 채점 결과는 §3.1, 컨텍스트 간 배선 발견 #9는 `composition/wiring.py` 헤더 참고.

## 3. 현재 좁은 작업 — valuation 게이트 (범위)

대상: `valuation.AnalysisEligibility` (게이트) + 최소 의존.
- 상태기계: `LOCKED → READY → ANALYZED` (READY→LOCKED 재잠금 허용).
- #2 가드: `LOCKED→READY` 트리거가 `market.거래량`(외부 데이터).
- #3 크로스 불변식: "손익분기/ROE는 대출액 ≤ regulation.한도일 때만 유효".
- 무상태 #5: breakeven/roe = 순수 수식(상태 없음).

**가드 두 방식 동시 구현 후 비교:**
- **A (얇은 Aggregate + 정책객체)**: 전이 무조건, 가드/조건은 도메인 정책객체 + 유스케이스 조립. 크로스데이터=포트.
- **B (Aggregate 내장)**: 전이 메서드가 VO를 받아 가드/불변식 내장.
- 공통: 도메인은 어댑터/ORM/HTTP import 0 (§2). 크로스데이터는 값(VO)로 주입.

**비교 채점 축**: §2 순수성 / 판단 응집 / **생성기 친화(템플릿 역추출 난이도)** / §2 누출 위험 / §9 테스트 용이성.

### 3.1 실험 결과 (2026-06-20, 구현·검증 완료)

`examples/seoul-apt/reference/`에 A·B 둘 다 구현. **15/15 테스트 green**, 경계 가드 음성대조도 통과(금지 import → FAILED, 제거 → OK). 워크드 예시 수치 검증(손익분기 0.03, ROE 0.05).

| 채점 축 | A (얇음+정책객체) | B (Aggregate 내장) |
|---|---|---|
| §2 도메인 순수성 | ✅ (경계테스트 green) | ✅ (경계테스트 green) |
| **§2 누출 (실측)** | 🔴 **누출됨** — `gate_service_a.py`(application)에 "READY 아니면 분석불가"+"한도 초과 거부" 같은 *도메인 판단*이 들어감 | 🟢 application은 포트 읽어 전달만(`if 정책` 없음) |
| 판단 응집 | 분산(policies + application) | 집중(Aggregate `reevaluate`/`analyze`) |
| 생성기 친화 | 약함(판단이 impl블록에 흩어짐) | 강함(states/transitions/invariants → Aggregate 메서드로 직번역) |
| 복잡로직 확장 | 정책객체 분해 쉬움 | analyze 인자 비대 우려 |

**판정: B를 기본 골격으로.** §2 누출이 A에서 실제로 발생(application이 도메인 판단을 떠안음) — HexaArch가 가장 싫어하는 패턴. B는 application을 순수 오케스트레이션으로 유지.
**단, A의 정책객체는 버리지 않음**: 규칙이 복잡/재사용되면 **Aggregate가 정책객체를 호출**하는 하이브리드(판단의 주체는 Aggregate, 정책객체는 순수 헬퍼). → 스펙 매핑: states/transitions/invariants→Aggregate(B), decision_tables/formulas→정책·수식객체(A의 분해).

## 3.9 ⚠️ 레퍼런스의 위상 — 학습용·폐기 전제

`examples/seoul-apt/reference/`는 **최종 산출물이 아니다.** Phase 3에서 스펙으로 재생성하면 이 손작업 골격은
**폐기·교체**된다. 목적은 ① "헥사고날 준수"의 조작적 정의 고정 ② 스키마 한계 실측 ③ 생성기 템플릿
역추출 근거. 따라서 production 광택(엣지케이스·성능)보다 **한계 실측·형태 합의**가 우선.

## 4. Phase 2 완료 상태 (2026-06-20)

- ✅ 구현 컨텍스트: `valuation`(게이트, A/B→B채택) · `regulation`(결정표) · `collection`(수집잡). + `shared`(Money) + `composition`(배선).
- ✅ 한계 실측: #1·#2·#3·#5·#6·#7·#9 + §9 ①②③④. 전부 테스트로 이빨 확인.
- ✅ 32/32 green (stdlib unittest, 외부 의존 0).

### 남은 것 (Phase 3로 이월)
- 한계 #0(멀티컨텍스트)·#4(policies 분리)·#8(messaging/task_queue) — **스펙 스키마 형태 이슈**라 spec 작성 시 드러남.
- DRF view·DB 어댑터·Celery·docker-compose — 인프라. 도메인 코어 검증이 우선이라 보류(헥사고날).
- `market`/`rates`/`watchlist` (CRUD) — 생성기 일반화로 처리 확인.

## 5. Phase 3 — 완료 (2026-06-20). 핵심 가설 입증됨 ✅

산출물:
- `examples/seoul-apt/domain-spec.yaml` — 확장 스키마 적용 SSOT (#0/#4/#5/#6/#7/#8 형태 확정).
- `hexaarch/spec.py` — Pydantic 스펙 IR + 검증(§16.5) + 스펙레벨 충돌판정(전이↔상태, 가드↔전이, 자기전이 금지).
- `hexaarch/scaffold.py` — 결정론 생성기(YAML+Pydantic+Jinja2). 상태기계·_transition·예외·포트스텁·전이매트릭스테스트·경계가드 생성. 가드/불변식/수식은 §6 impl 보호구역.
- `out/ (생성, gitignore)` — 생성 결과(22파일).

검증 3종 (전부 통과):
1. **결정론** — 두 번 생성 바이트 동일.
2. **의미 수렴** — 생성 ALLOWED == 레퍼런스(손작업) ALLOWED (게이트·수집잡 동치).
3. **생성 골격 §9** — 전이 매트릭스 + 경계 테스트 green.

확정된 것:
- 스키마 확장 6개 모두 실제 spec.yaml + Pydantic으로 **고정**.
- 생성/보존 경계(§6): generated=상태머신·_transition·시그니처 / impl=가드·불변식·수식·도메인메서드.
- 새 발견 #10: **YAML `on/off/yes/no` 푸시건** — 가드 필드 `on`이 boolean으로 파싱됨 → `edge`로 개명. (검증기가 잡아냄 = §16.5 효용 실증.)

남은 것(이번 PoC 범위 밖, 정직히 명시):
- 생성기는 아직 상태기계 중심. 결정표 로직(LoanLimitTable)·DRF 어댑터·Celery는 미생성(라이브러리/impl).
- 리치 메서드(reevaluate/analyze/succeed 등 다중엣지+가드+수식 결합)는 impl — 스펙만으론 생성 불가(설계대로).
- `propose`/`gate`(§10 변경 게이트), `extract`/`select-arch`(LLM, 사용자세션), CLI(Typer) — 미착수.

## 5. §9 검증 4종 (레퍼런스가 반드시 갖출 것)

1. 상태 전이 거부 테스트  2. 불변식 테스트(요구사항ID별)  3. 경계 위반 테스트(import-linter)  4. 결정표 완전성.
(현재 좁은 작업에선 1·2 + 경계 일부. 3·4는 regulation 들어올 때 완성.)
