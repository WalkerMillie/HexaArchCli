"""collection — 깨끗한 상태기계 + #1 동시성 + 멱등 upsert + 부분수집 금지.

req: COL-001/002/003/004
"""

import unittest

from contexts.collection.adapters.in_memory import InMemoryJobRegistry, InMemoryTradeRepository
from contexts.collection.application.run_collection import RunCollection
from contexts.collection.domain.collection_job import CollectionJob
from contexts.collection.domain.collection_state import JobState
from contexts.collection.domain.exceptions import (
    ConcurrentCollection,
    IllegalTransition,
    InvariantViolation,
)
from contexts.collection.domain.records import CollectionResult, TradeRecord


def _rec(floor=10, date="2026-05-01"):
    return TradeRecord("c1", area=84.9, floor=floor, contract_date=date, price_won=1_000_000_000)


class FakeSource:
    def __init__(self, records):
        self._records = records

    def fetch(self, source):
        return list(self._records)


class StateMachine(unittest.TestCase):
    def test_clean_path(self):
        job = CollectionJob("molt")
        job.start()
        job.succeed(CollectionResult(fetched=3, expected=3))
        self.assertEqual(job.state, JobState.SUCCEEDED)

    def test_idle_cannot_jump_to_succeeded(self):
        job = CollectionJob("molt")
        with self.assertRaises(IllegalTransition):
            job.succeed(CollectionResult(0, 0))

    def test_retry_after_fail(self):
        job = CollectionJob("molt")
        job.start()
        job.fail("boom")
        job.start()   # FAILED → RUNNING 재시도 허용
        self.assertEqual(job.state, JobState.RUNNING)

    def test_partial_result_cannot_succeed(self):
        job = CollectionJob("molt")
        job.start()
        with self.assertRaises(InvariantViolation):   # req: COL-004
            job.succeed(CollectionResult(fetched=2, expected=5))
        self.assertEqual(job.state, JobState.RUNNING)  # 산출 안 됨


class Concurrency(unittest.TestCase):
    def test_same_source_concurrent_rejected(self):  # req: COL-002
        reg = InMemoryJobRegistry()
        reg.acquire("molt")
        with self.assertRaises(ConcurrentCollection):
            reg.acquire("molt")

    def test_release_allows_reacquire(self):
        reg = InMemoryJobRegistry()
        reg.acquire("molt")
        reg.release("molt")
        reg.acquire("molt")  # 재획득 가능


class Idempotency(unittest.TestCase):
    def test_upsert_is_idempotent(self):  # req: COL-003
        repo = InMemoryTradeRepository()
        records = [_rec(floor=10), _rec(floor=11)]
        ins1, upd1 = repo.upsert(records)
        ins2, upd2 = repo.upsert(records)   # 같은 자연키 재수집
        self.assertEqual((ins1, upd1), (2, 0))
        self.assertEqual((ins2, upd2), (0, 2))
        self.assertEqual(repo.count(), 2)   # 행 안 늘어남


class UseCase(unittest.TestCase):
    def test_run_collection_end_to_end(self):
        repo = InMemoryTradeRepository()
        reg = InMemoryJobRegistry()
        uc = RunCollection(FakeSource([_rec(10), _rec(11), _rec(12)]), repo, reg)
        job = CollectionJob("molt")
        ins, upd = uc(job)
        self.assertEqual(job.state, JobState.SUCCEEDED)
        self.assertEqual((ins, upd), (3, 0))

    def test_registry_released_after_run(self):
        repo = InMemoryTradeRepository()
        reg = InMemoryJobRegistry()
        uc = RunCollection(FakeSource([_rec(10)]), repo, reg)
        uc(CollectionJob("molt"))
        # 끝났으면 재실행 가능해야(레지스트리 해제됨)
        uc(CollectionJob("molt"))


if __name__ == "__main__":
    unittest.main()
