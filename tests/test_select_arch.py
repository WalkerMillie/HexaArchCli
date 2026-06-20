"""본체 테스트 — select-arch 파이프라인. FakeBackend로 오프라인·결정론."""

import unittest

from hexaarch.llm.base import LLMError
from hexaarch.select_arch import ArchProposal, build_schema, render_text, select_arch

VALID = {
    "alternatives": [
        {"name": "수집/판단/규제 분리", "summary": "기능 책임별 분해",
         "contexts": [{"name": "collection", "responsibility": "데이터 수집"},
                      {"name": "valuation", "responsibility": "판단/계산"}],
         "pros": ["관심사 분리 명확"], "cons": ["컨텍스트 간 동기 조회 필요"],
         "recommended": True},
        {"name": "사용자여정 중심", "summary": "여정 단계별 분해",
         "contexts": [{"name": "watchlist", "responsibility": "관심단지 관리"}],
         "pros": ["UX 정렬"], "cons": ["중복 로직 위험"], "recommended": False},
    ],
    "recommendation": "1번을 추천 — 변경 파급이 작다.",
}


class FakeBackend:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0
        self.last_schema = None

    def complete(self, *, system, user, json_schema, model=None):
        self.calls += 1
        self.last_schema = json_schema
        return self._responses[min(self.calls - 1, len(self._responses) - 1)]


class SelectArch(unittest.TestCase):
    def test_returns_validated_proposal(self):
        be = FakeBackend([VALID])
        p = select_arch("정책...", be, n=2)
        self.assertIsInstance(p, ArchProposal)
        self.assertEqual(len(p.alternatives), 2)
        self.assertEqual(be.calls, 1)

    def test_exactly_one_recommended(self):
        p = select_arch("정책...", FakeBackend([VALID]))
        self.assertEqual(sum(o.recommended for o in p.alternatives), 1)

    def test_repair_on_invalid_then_valid(self):
        be = FakeBackend([{"alternatives": "nope"}, VALID])   # 첫 출력 형태 오류
        p = select_arch("정책...", be, max_repair=1)
        self.assertIsInstance(p, ArchProposal)
        self.assertEqual(be.calls, 2)

    def test_gives_up_after_repair(self):
        be = FakeBackend([{"bad": 1}])
        with self.assertRaises(LLMError):
            select_arch("정책...", be, max_repair=1)
        self.assertEqual(be.calls, 2)

    def test_schema_passed_to_backend(self):
        be = FakeBackend([VALID])
        select_arch("정책...", be)
        self.assertIn("alternatives", be.last_schema["properties"])

    def test_render_text_marks_recommended(self):
        text = render_text(select_arch("정책...", FakeBackend([VALID])))
        self.assertIn("★추천", text)
        self.assertIn("추천:", text)


if __name__ == "__main__":
    unittest.main()
