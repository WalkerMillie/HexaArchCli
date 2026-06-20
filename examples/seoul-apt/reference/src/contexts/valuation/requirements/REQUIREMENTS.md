# valuation — 요구사항 (traceability, DESIGN §5.2)

각 요구사항은 ID로 코드·테스트와 연결된다. 코드엔 `# req: VAL-xxx` 주석.

- [VAL-001] 손익분기 상승률 = 대출비중 × 실효금리.
  - 종류: 추가형 · 상태: active
  - 연결: domain/breakeven.py, tests/test_formulas.py
- [VAL-002] 레버리지 ROE = (매매가×상승률 − 대출액×금리) / 자기자본.
  - 종류: 추가형 · 상태: active
  - 연결: domain/roe.py, tests/test_formulas.py
- [VAL-003] 분석 게이트 상태기계 LOCKED→READY→ANALYZED. 미허용 전이는 거부.
  - 종류: 추가형 · 상태: active
  - 연결: domain/gate_state.py, domain/analysis_eligibility_{a,b}.py, tests/test_transitions.py
- [VAL-004] 손익분기/ROE는 대출액 ≤ 규제한도일 때만 유효 (크로스 컨텍스트 불변식 #3).
  - 종류: 수정형 · 상태: active · 위험: 🔴 (regulation 의존)
  - 연결: A=application/gate_service_a.py(LoanRegulationPolicy), B=domain/analysis_eligibility_b.py::analyze, tests/test_invariants.py
- [VAL-005] 매물 게이트 MVP = 거래량 프록시 (최근 거래 N건 미만이면 LOCKED) (조건부 전이 #2).
  - 종류: 추가형 · 상태: active
  - 연결: A=domain/policies.py, B=domain/analysis_eligibility_b.py::reevaluate, tests/test_gate_guard.py
