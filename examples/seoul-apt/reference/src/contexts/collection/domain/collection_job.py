"""수집 잡 Aggregate — 깨끗한 상태기계(B형). 가드 없음, 불변식만.

#1(동시성)은 단일 객체로 못 닫는 '관계 불변식'이라 여기 없다 → 스토어/레지스트리(어댑터)가 강제.
이 Aggregate가 책임지는 건: 전이 규칙(방어선 A) + 부분수집 금지(방어선 B).
"""

from contexts.collection.domain.collection_state import ALLOWED, JobState
from contexts.collection.domain.exceptions import IllegalTransition, InvariantViolation
from contexts.collection.domain.records import CollectionResult


class CollectionJob:
    def __init__(self, source: str, state: JobState = JobState.IDLE):
        self.source = source
        self.state = state

    def _transition(self, to: JobState) -> None:
        if to not in ALLOWED[self.state]:
            raise IllegalTransition(self.state, to)   # 방어선 A
        self.state = to

    def start(self) -> None:
        self._transition(JobState.RUNNING)

    def succeed(self, result: CollectionResult) -> None:
        if result.is_partial:
            raise InvariantViolation(  # 방어선 B (req: COL-004)
                f"부분 수집({result.fetched}/{result.expected})으로 SUCCEEDED 불가"
            )
        self._transition(JobState.SUCCEEDED)

    def fail(self, reason: str) -> None:
        self.reason = reason
        self._transition(JobState.FAILED)
