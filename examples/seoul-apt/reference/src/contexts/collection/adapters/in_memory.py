"""인메모리 어댑터 — #1 동시성·멱등 upsert를 '스토어 레벨'에서 강제(관계 불변식의 거처).

실전에선 Postgres 유니크 제약 + 락. 여기선 같은 강제력을 인메모리로 시뮬레이션해
'#1은 Aggregate가 아니라 어댑터/스토어가 강제한다'는 결론을 실증.
"""

from contexts.collection.domain.exceptions import ConcurrentCollection
from contexts.collection.domain.records import TradeRecord


class InMemoryTradeRepository:
    def __init__(self):
        self._by_key: dict[tuple, TradeRecord] = {}

    def upsert(self, records: list[TradeRecord]) -> tuple[int, int]:
        inserted = updated = 0
        for r in records:
            if r.natural_key in self._by_key:
                updated += 1
            else:
                inserted += 1
            self._by_key[r.natural_key] = r   # 자연키로 멱등
        return inserted, updated

    def count(self) -> int:
        return len(self._by_key)


class InMemoryJobRegistry:
    def __init__(self):
        self._active: set[str] = set()

    def acquire(self, source: str) -> None:
        if source in self._active:
            raise ConcurrentCollection(f"source '{source}' 이미 RUNNING")  # #1
        self._active.add(source)

    def release(self, source: str) -> None:
        self._active.discard(source)
