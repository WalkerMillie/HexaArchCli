# collection — 요구사항 (traceability)

- [COL-001] 수집 잡 상태기계 IDLE→RUNNING→SUCCEEDED/FAILED, 재시도 FAILED→RUNNING.
  - 종류: 추가형 · 상태: active
  - 연결: domain/collection_state.py, domain/collection_job.py, tests/test_collection.py
- [COL-002] 같은 source 동시 RUNNING 금지 (관계 불변식, 스토어 강제).
  - 종류: 추가형 · 상태: active · 위험: 🔴 (TOCTOU → DB 유니크/락 필요)
  - 연결: adapters/in_memory.py(InMemoryJobRegistry), application/run_collection.py
- [COL-003] 실거래 (complex_id, 면적, 층, 계약일) 자연키 → 멱등 upsert.
  - 종류: 추가형 · 상태: active
  - 연결: domain/records.py(TradeRecord.natural_key), adapters/in_memory.py
- [COL-004] 부분 수집 결과로는 SUCCEEDED 전이 불가.
  - 종류: 추가형 · 상태: active
  - 연결: domain/collection_job.py::succeed, domain/records.py(CollectionResult.is_partial)
