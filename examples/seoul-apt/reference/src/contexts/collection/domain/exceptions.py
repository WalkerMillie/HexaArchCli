"""collection 도메인 예외."""


class CollectionError(Exception):
    pass


class IllegalTransition(CollectionError):
    """방어선 A — 허용 안 된 잡 상태 전이."""

    def __init__(self, frm, to):
        self.frm = frm
        self.to = to
        super().__init__(f"불허 전이: {frm.name} -> {to.name}")


class InvariantViolation(CollectionError):
    """방어선 B — 불변식 위반 (예: 부분 수집으로 SUCCEEDED 불가)."""


class ConcurrentCollection(CollectionError):
    """#1 동시성 — 같은 source가 이미 RUNNING. (관계 불변식, 스토어가 강제)"""
