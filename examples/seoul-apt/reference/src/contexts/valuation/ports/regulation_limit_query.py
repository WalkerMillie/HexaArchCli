"""아웃바운드 포트 — regulation 컨텍스트의 대출 한도를 읽는 인터페이스. (#3 크로스 의존)"""

from typing import Protocol

from contexts.valuation.domain.value_objects import Money


class RegulationLimitQuery(Protocol):
    def max_loan(self, complex_id: str) -> Money: ...
