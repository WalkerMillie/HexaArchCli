"""아웃바운드 포트 — 외부 API / 저장소 / 동시성 레지스트리 (인터페이스만)."""

from typing import Protocol

from contexts.collection.domain.records import TradeRecord


class TradeSource(Protocol):
    """외부 실거래가 API (국토부 등)."""
    def fetch(self, source: str) -> list[TradeRecord]: ...


class TradeRepository(Protocol):
    """멱등 upsert. 반환=(insert건수, update건수). (req: COL-003)"""
    def upsert(self, records: list[TradeRecord]) -> tuple[int, int]: ...


class JobRegistry(Protocol):
    """#1 동시성 강제 — 같은 source 중복 RUNNING 방지(실제론 DB 유니크/락)."""
    def acquire(self, source: str) -> None: ...   # 이미 active면 ConcurrentCollection
    def release(self, source: str) -> None: ...
