"""본체 테스트 — extract 파이프라인. FakeBackend로 오프라인·결정론 검증.

(라이브 `claude -p` 경로는 사용자 인증/비결정 출력이라 단위테스트가 아니라 CLI 시연으로 확인.)
"""

import pathlib
import tempfile
import unittest

import yaml

from hexaarch.extract import build_schema, extract, spec_to_yaml
from hexaarch.llm.base import LLMError
from hexaarch.spec import Spec, load_spec

VALID = {
    "version": "0.1",
    "infrastructure": {"database": "pg", "messaging": "ev"},
    "contexts": [{
        "name": "c",
        "domains": {"A": {"kind": "aggregate", "states": ["X", "Y"],
                          "transitions": {"X": ["Y"]}}},
    }],
}
INVALID = {  # 자기 전이 — 스키마는 통과하나 의미 검증에서 실패
    "version": "0.1",
    "infrastructure": {"database": "pg", "messaging": "ev"},
    "contexts": [{
        "name": "c",
        "domains": {"A": {"kind": "aggregate", "states": ["X"],
                          "transitions": {"X": ["X"]}}},
    }],
}


class FakeBackend:
    """순서대로 미리 정한 응답을 돌려주는 백엔드. complete 호출수를 센다."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0
        self.last_user = None

    def complete(self, *, system, user, json_schema, model=None):
        self.calls += 1
        self.last_user = user
        return self._responses[min(self.calls - 1, len(self._responses) - 1)]


class ExtractPipeline(unittest.TestCase):
    def test_returns_validated_spec(self):
        be = FakeBackend([VALID])
        spec = extract("정책...", be)
        self.assertIsInstance(spec, Spec)
        self.assertEqual(be.calls, 1)
        self.assertEqual(spec.contexts[0].name, "c")

    def test_repair_loop_recovers(self):
        be = FakeBackend([INVALID, VALID])     # 첫 출력 실패 → 복구 후 성공
        spec = extract("정책...", be, max_repair=2)
        self.assertIsInstance(spec, Spec)
        self.assertEqual(be.calls, 2)
        self.assertIn("의미 검증에서 실패", be.last_user)   # 오류를 되먹였는지

    def test_gives_up_after_max_repair(self):
        be = FakeBackend([INVALID])            # 늘 실패
        with self.assertRaises(LLMError):
            extract("정책...", be, max_repair=2)
        self.assertEqual(be.calls, 3)          # 1 + 2회 재시도

    def test_yaml_roundtrips_through_validation(self):
        spec = extract("정책...", FakeBackend([VALID]))
        text = spec_to_yaml(spec)
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "domain-spec.yaml"
            p.write_text(text, encoding="utf-8")
            reloaded = load_spec(p)            # 재검증 통과해야
        self.assertEqual(reloaded.contexts[0].name, "c")
        self.assertEqual(yaml.safe_load(text)["version"], "0.1")

    def test_schema_describes_contexts(self):
        schema = build_schema()
        self.assertIn("contexts", schema["properties"])


if __name__ == "__main__":
    unittest.main()
