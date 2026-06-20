"""수집 레코드 + 결과 VO.

req: COL-003  실거래는 (complex_id, 면적, 층, 계약일) 자연키 → 멱등 upsert.
req: COL-004  부분 수집 결과로는 SUCCEEDED 불가.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TradeRecord:
    complex_id: str
    area: float
    floor: int
    contract_date: str   # ISO yyyy-mm-dd
    price_won: int

    @property
    def natural_key(self) -> tuple:
        return (self.complex_id, self.area, self.floor, self.contract_date)


@dataclass(frozen=True)
class CollectionResult:
    fetched: int
    expected: int

    @property
    def is_partial(self) -> bool:
        return self.fetched < self.expected
