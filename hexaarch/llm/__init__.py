"""LLM 백엔드 — extract/select-arch 단계가 쓴다 (DESIGN §4, §16.5).

기본은 사용자의 Claude '구독 세션'을 빌려 쓴다(별도 API 키 아님):
로컬 `claude -p` 헤드리스 호출 + `--json-schema`로 §16.5 스키마 강제.
백엔드 추상화라 ApiBackend(API 키)·테스트용 FakeBackend로 교체 가능.
"""

from hexaarch.llm.base import LLMBackend, LLMError
from hexaarch.llm.claude_session import ClaudeSessionBackend

__all__ = ["LLMBackend", "LLMError", "ClaudeSessionBackend"]
