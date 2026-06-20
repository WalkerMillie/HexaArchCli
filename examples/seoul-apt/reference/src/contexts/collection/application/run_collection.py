"""유스케이스 — 수집 잡 실행 오케스트레이션(B형: 얇음, 판단은 Aggregate/스토어).

흐름: 레지스트리 acquire(#1) → 잡 start → 외부 fetch → 멱등 upsert → succeed/fail → release.
application에는 상태/정책 if 분기가 없다(§2). 동시성은 레지스트리가, 전이/부분수집은 Aggregate가.
"""

from contexts.collection.domain.collection_job import CollectionJob
from contexts.collection.domain.collection_state import JobState
from contexts.collection.domain.records import CollectionResult
from contexts.collection.ports.ports_out import JobRegistry, TradeRepository, TradeSource


class RunCollection:
    def __init__(self, source_api: TradeSource, repo: TradeRepository, registry: JobRegistry):
        self.source_api = source_api
        self.repo = repo
        self.registry = registry

    def __call__(self, job: CollectionJob) -> tuple[int, int]:
        self.registry.acquire(job.source)          # #1: 동시 실행이면 여기서 거부
        try:
            job.start()
            records = self.source_api.fetch(job.source)
            stat = self.repo.upsert(records)        # 멱등
            job.succeed(CollectionResult(fetched=len(records), expected=len(records)))
            return stat
        except Exception:
            if job.state == JobState.RUNNING:
                job.fail("collection error")
            raise
        finally:
            self.registry.release(job.source)
