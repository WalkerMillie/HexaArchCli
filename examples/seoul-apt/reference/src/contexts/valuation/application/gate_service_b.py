"""[Approach B] 유스케이스는 '포트로 데이터만 읽어 Aggregate에 넘긴다'. 판단은 Aggregate.

B안에서는 application이 얇다: 거래량/한도를 읽어 VO로 Aggregate 메서드에 전달할 뿐,
가드·불변식 판정은 전부 Aggregate 안에 있다. 판단이 한 곳에 응집 → 생성기 템플릿화 쉬움.
"""

from contexts.valuation.domain.analysis_eligibility_b import AnalysisEligibilityB
from contexts.valuation.domain.value_objects import Money
from contexts.valuation.ports.regulation_limit_query import RegulationLimitQuery
from contexts.valuation.ports.trade_volume_query import TradeVolumeQuery


class GateServiceB:
    def __init__(self, volume_query: TradeVolumeQuery, limit_query: RegulationLimitQuery):
        self.volume_query = volume_query
        self.limit_query = limit_query

    def reevaluate(self, elig: AnalysisEligibilityB) -> None:
        elig.reevaluate(self.volume_query.recent(elig.complex_id))

    def analyze(
        self,
        elig: AnalysisEligibilityB,
        *,
        loan: Money,
        price: Money,
        equity: Money,
        effective_rate: float,
        assumed_growth: float,
    ) -> dict:
        return elig.analyze(
            loan=loan,
            price=price,
            equity=equity,
            effective_rate=effective_rate,
            assumed_growth=assumed_growth,
            reg_limit=self.limit_query.max_loan(elig.complex_id),
        )
