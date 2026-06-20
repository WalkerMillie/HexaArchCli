"""HexaArch 본체 테스트 — 스펙 검증(§16.5) + 스펙레벨 충돌 판정(§10.3 맛보기)."""

import pathlib
import unittest

from pydantic import ValidationError

from hexaarch.spec import Spec, load_spec

EXAMPLE = pathlib.Path(__file__).resolve().parent.parent / "examples" / "seoul-apt" / "domain-spec.yaml"


def _spec_with(transitions, guards=None):
    return {
        "version": "0.1",
        "infrastructure": {"database": "pg", "messaging": "ev"},
        "contexts": [{
            "name": "c",
            "domains": {"A": {
                "kind": "aggregate",
                "states": ["X", "Y"],
                "transitions": transitions,
                "guards": guards or [],
            }},
        }],
    }


class SpecValidation(unittest.TestCase):
    def test_example_spec_loads(self):
        spec = load_spec(EXAMPLE)
        self.assertEqual({c.name for c in spec.contexts}, {"valuation", "regulation", "collection"})

    def test_valid_minimal(self):
        Spec.model_validate(_spec_with({"X": ["Y"]}))   # 통과해야

    def test_self_transition_rejected(self):
        with self.assertRaises(ValidationError):
            Spec.model_validate(_spec_with({"X": ["X"]}))

    def test_unknown_target_state_rejected(self):
        with self.assertRaises(ValidationError):
            Spec.model_validate(_spec_with({"X": ["Z"]}))   # Z는 states에 없음

    def test_guard_without_matching_transition_rejected(self):
        with self.assertRaises(ValidationError):
            Spec.model_validate(_spec_with({"X": ["Y"]}, guards=[{"edge": "X->Z", "id": "G1", "desc": "x"}]))

    def test_calculation_requires_formulas(self):
        bad = {
            "version": "0.1",
            "infrastructure": {"database": "pg", "messaging": "ev"},
            "contexts": [{"name": "c", "domains": {"B": {"kind": "calculation"}}}],
        }
        with self.assertRaises(ValidationError):
            Spec.model_validate(bad)

    def test_relation_to_unknown_context_rejected(self):
        bad = {
            "version": "0.1",
            "infrastructure": {"database": "pg", "messaging": "ev"},
            "contexts": [{
                "name": "c",
                "domains": {"A": {"kind": "aggregate", "states": ["X", "Y"], "transitions": {"X": ["Y"]}}},
                "relations": [{"to": "nope", "via": "event", "event": "E"}],
            }],
        }
        with self.assertRaises(ValidationError):
            Spec.model_validate(bad)


if __name__ == "__main__":
    unittest.main()
