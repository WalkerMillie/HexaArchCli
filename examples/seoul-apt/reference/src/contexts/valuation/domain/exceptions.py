"""도메인 예외 — 코어가 거부할 때 던진다. (DESIGN §3.2/§3.3)"""


class DomainError(Exception):
    """valuation 도메인의 모든 거부의 베이스."""


class IllegalTransition(DomainError):
    """방어선 A — 허용 안 된 상태 전이. (DESIGN §1 방어선 A)"""

    def __init__(self, frm, to):
        self.frm = frm
        self.to = to
        super().__init__(f"불허 전이: {frm.name} -> {to.name}")


class InvariantViolation(DomainError):
    """방어선 B — 불변식 위반. 깨진 상태로는 진행 불가. (DESIGN §1 방어선 B)"""
