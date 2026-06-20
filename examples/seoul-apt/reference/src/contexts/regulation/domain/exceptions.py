"""regulation 도메인 예외."""


class RegulationError(Exception):
    pass


class NoMatchingBand(RegulationError):
    """가격이 어느 결정표 구간에도 안 걸림 (완전성 위반의 런타임 증상)."""


class IncompleteDecisionTable(RegulationError):
    """결정표 완전성 위반 — 구간 공백/겹침. (§9-④)"""

    def __init__(self, problems):
        self.problems = problems
        super().__init__("결정표 완전성 위반:\n" + "\n".join(problems))
