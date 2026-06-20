"""LLM 백엔드 계약 — 구조화 출력(JSON 스키마 강제) 한 번 호출."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class LLMError(Exception):
    """LLM 호출/파싱 실패. extract의 복구 루프와 구분되는 '인프라' 오류."""


@runtime_checkable
class LLMBackend(Protocol):
    def complete(self, *, system: str, user: str,
                 json_schema: dict, model: str | None = None) -> dict:
        """system+user를 주고, json_schema를 강제해 dict(구조화 출력)를 받는다.

        스키마 강제는 백엔드 책임. 의미 검증(전이↔상태 등)은 호출자(extract)가
        Spec.model_validate로 한 번 더 한다 — 스키마는 형태만 보장하므로."""
        ...
