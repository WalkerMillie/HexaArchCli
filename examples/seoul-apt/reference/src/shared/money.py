"""공유 커널 — Money. 여러 컨텍스트(valuation, regulation)가 쓰는 값 객체.

컨텍스트 간 도메인을 직접 import하면 격리가 깨지므로(§3.4), 공통 VO는 shared 커널에 둔다.
shared는 어느 컨텍스트에도 의존하지 않는 가장 안쪽 공통층.
"""

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Money:
    """원(KRW) 단위 금액. order=True로 한도 비교(≤) 가능."""

    won: int

    def __post_init__(self):
        if self.won < 0:
            raise ValueError("금액은 음수 불가")
