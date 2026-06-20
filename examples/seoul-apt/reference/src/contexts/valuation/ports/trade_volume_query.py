"""아웃바운드 포트 — market 컨텍스트의 거래량을 읽는 인터페이스.

포트는 domain(VO)에만 의존한다(허용 방향: ports → domain). 구현(어댑터)은 db/api에 산다.
valuation 도메인은 이 포트조차 import하지 않는다 — 데이터는 application이 읽어 VO로 넘긴다.
"""

from typing import Protocol

from contexts.valuation.domain.value_objects import VolumeStat


class TradeVolumeQuery(Protocol):
    def recent(self, complex_id: str) -> VolumeStat: ...
