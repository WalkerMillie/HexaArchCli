"""수집 잡 상태 + 전이 테이블 — 가드 없는 깨끗한 상태기계(게이트와 대조).

req: COL-001  IDLE → RUNNING → SUCCEEDED / FAILED, 재시도 FAILED → RUNNING.
"""

from enum import Enum, auto


class JobState(Enum):
    IDLE = auto()
    RUNNING = auto()
    SUCCEEDED = auto()
    FAILED = auto()


ALLOWED = {
    JobState.IDLE:      {JobState.RUNNING},
    JobState.RUNNING:   {JobState.SUCCEEDED, JobState.FAILED},
    JobState.FAILED:    {JobState.RUNNING},   # 재시도
    JobState.SUCCEEDED: {JobState.RUNNING},   # 다음 주기 재수집
}
