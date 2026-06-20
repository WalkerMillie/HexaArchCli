"""합성 루트(composition root) — 컨텍스트 간 동기 쿼리 배선이 사는 유일한 곳.

발견 #9 (신규, regulation 추가하며 드러남): valuation은 regulation의 한도가 필요한데,
이건 '이벤트'로 표현하기 어색한 *동기 읽기 쿼리*다(§3.4는 도메인↔도메인 직접의존 금지지만
동기 쿼리는 이벤트로 못 바꿈). 해법: 포트는 소비자(valuation)가 정의하고, 그 포트를 구현하는
어댑터를 **합성 루트**에 둔다. 두 컨텍스트 도메인은 서로를 모른 채 유지되고, 배선만 여기서 안다.
"""

from datetime import date

from contexts.regulation.domain.decision_table import LoanLimitTable
from contexts.valuation.ports.regulation_limit_query import RegulationLimitQuery
from shared.money import Money


class DecisionTableLimitAdapter(RegulationLimitQuery):
    """valuation의 RegulationLimitQuery 포트를 regulation 결정표로 구현."""

    def __init__(self, table: LoanLimitTable, price_of: dict[str, Money], as_of: date):
        self._table = table
        self._price_of = price_of
        self._as_of = as_of

    def max_loan(self, complex_id: str) -> Money:
        price = self._price_of[complex_id]
        return self._table.max_loan_for(price, self._as_of)
