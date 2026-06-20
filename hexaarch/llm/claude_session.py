"""ClaudeSessionBackend — 사용자 Claude 구독 세션을 빌려 쓰는 기본 백엔드.

로컬 `claude -p --output-format json --json-schema <schema>` 헤드리스 호출.
인증은 사용자의 기존 로그인/`CLAUDE_CODE_OAUTH_TOKEN`을 그대로 탄다(별도 키 X).

발견(실측): `--json-schema`로 강제된 결과는 응답 봉투의 `result`가 아니라
`structured_output` 필드에 담긴다. `--json-schema`는 JSON '문자열' 인자다(파일 X).

주의(ToS): 각자 자기 구독을 자기 머신에서 쓰는 정상 사용 전제.
계정 풀링/머신-투-머신엔 ApiBackend(API 키)를 써라.
"""

from __future__ import annotations

import json
import shutil
import subprocess

from hexaarch.llm.base import LLMError


class ClaudeSessionBackend:
    def __init__(self, *, claude_bin: str = "claude", timeout: int = 600):
        self.claude_bin = claude_bin
        self.timeout = timeout

    def complete(self, *, system: str, user: str,
                 json_schema: dict, model: str | None = None) -> dict:
        if shutil.which(self.claude_bin) is None:
            raise LLMError(
                f"'{self.claude_bin}' 실행파일을 찾을 수 없음. Claude Code 설치/로그인 필요.")
        cmd = [self.claude_bin, "-p", "--output-format", "json",
               "--json-schema", json.dumps(json_schema)]
        if system:
            cmd += ["--append-system-prompt", system]
        if model:
            cmd += ["--model", model]
        try:
            proc = subprocess.run(cmd, input=user, capture_output=True,
                                  text=True, timeout=self.timeout)
        except subprocess.TimeoutExpired as e:
            raise LLMError(f"claude 호출 타임아웃({self.timeout}s)") from e
        if proc.returncode != 0:
            raise LLMError(f"claude 호출 실패 (exit {proc.returncode}): "
                           f"{(proc.stderr or proc.stdout)[:800]}")
        try:
            env = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise LLMError(f"claude 출력 JSON 파싱 실패: {e}: {proc.stdout[:800]}") from e
        if env.get("is_error"):
            raise LLMError(f"claude 오류 응답: {env.get('result') or env}")
        out = env.get("structured_output")
        if out is None:
            raise LLMError("응답에 structured_output 없음 — 스키마 강제 실패")
        if not isinstance(out, dict):
            raise LLMError(f"structured_output가 객체가 아님: {type(out).__name__}")
        return out
