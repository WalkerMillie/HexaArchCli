"""값 객체 — 크로스 컨텍스트 데이터는 '값'으로 도메인에 주입된다.

핵심: market.거래량, regulation.한도 같은 다른 컨텍스트의 데이터를 도메인이 직접
조회하지 않는다. 어댑터/유스케이스가 포트로 읽어 VO로 만들어 넘긴다. 그래서 도메인은
다른 컨텍스트나 인프라를 import하지 않는다. (DESIGN §2 / 한계 #3 처리의 공통 토대)

Money는 공유 커널(shared)에 있다 — regulation도 쓰므로. 여기선 재노출만.
"""

from dataclasses import dataclass

from shared.money import Money  # noqa: F401  (re-export: 기존 import 경로 유지)

__all__ = ["Money", "VolumeStat"]


@dataclass(frozen=True)
class VolumeStat:
    """market에서 읽어온 거래량 프록시. (매물 게이트 MVP 정의)"""

    recent_count: int   # 최근 window_months 내 실거래 건수
    window_months: int = 6
