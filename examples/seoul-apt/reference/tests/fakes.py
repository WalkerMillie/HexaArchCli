"""포트 페이크 — 도메인은 인프라 없이 테스트된다(헥사고날의 핵심 증명)."""

from contexts.valuation.domain.value_objects import Money, VolumeStat


class FakeVolumeQuery:
    def __init__(self, count: int):
        self._count = count

    def recent(self, complex_id: str) -> VolumeStat:
        return VolumeStat(recent_count=self._count)


class FakeLimitQuery:
    def __init__(self, limit_won: int):
        self._limit = Money(limit_won)

    def max_loan(self, complex_id: str) -> Money:
        return self._limit


# 정책문서 §5.1/§5.2 워크드 예시 값
EOK = 100_000_000  # 1억
PRICE = Money(10 * EOK)   # 매매 10억
LOAN = Money(6 * EOK)     # 대출 6억
EQUITY = Money(4 * EOK)   # 자기자본 4억
RATE = 0.05              # 실효금리 5%
GROWTH = 0.05            # 가정 상승률 5%
