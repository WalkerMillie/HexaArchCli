"""분석 게이트 상태 + 전이 테이블. (방어선 A의 데이터)

req: VAL-003  분석 게이트 상태기계 (LOCKED → READY → ANALYZED)

여기 없는 전이는 코어가 거부한다. 새 상태 추가는 반드시 이 파일을 건드려야 하므로
'운영 경로에 그 상태가 없다'는 충돌이 코어에서 즉시 드러난다. (DESIGN §3.2)
"""

from enum import Enum, auto


class GateState(Enum):
    LOCKED = auto()    # 거래량 바닥(매물 프록시) → 깊은 분석 잠김
    READY = auto()     # 게이트 통과 → 분석 가능
    ANALYZED = auto()  # 분석 산출 완료


# 허용 전이를 데이터로 명시.
ALLOWED = {
    GateState.LOCKED:   {GateState.READY},
    GateState.READY:    {GateState.ANALYZED, GateState.LOCKED},   # 거래량 다시 마르면 재잠금
    GateState.ANALYZED: {GateState.READY, GateState.LOCKED},      # 데이터 갱신 시 재평가
}
