"""본체 테스트 — 변경 게이트(§10). 가산=통과, 가드제거=거부, 조임=대안."""

import copy
import pathlib
import unittest

from hexaarch.gate import gate
from hexaarch.spec import Spec, load_spec

EXAMPLE = pathlib.Path(__file__).resolve().parent.parent / "examples" / "seoul-apt" / "domain-spec.yaml"


def _base() -> dict:
    return {
        "version": "0.1",
        "infrastructure": {"database": "pg", "messaging": "ev"},
        "contexts": [{
            "name": "c",
            "domains": {"A": {
                "kind": "aggregate",
                "states": ["X", "Y", "Z"],
                "transitions": {"X": ["Y"], "Y": ["Z"]},
                "guards": [{"edge": "X->Y", "id": "G1", "desc": "x→y 가드"}],
                "invariants": [{"id": "I1", "desc": "불변식"}],
            }},
        }],
    }


class GateNoChange(unittest.TestCase):
    def test_identical_spec_passes(self):
        spec = load_spec(EXAMPLE)
        report = gate(spec, spec)
        self.assertEqual(report.changes, [])
        self.assertTrue(report.passed)


class GatePass(unittest.TestCase):
    def test_adding_state_and_transition_passes(self):
        old = Spec.model_validate(_base())
        nd = _base()
        nd["contexts"][0]["domains"]["A"]["states"].append("W")
        nd["contexts"][0]["domains"]["A"]["transitions"]["Z"] = ["W"]
        report = gate(old, Spec.model_validate(nd))
        self.assertEqual(report.verdict, "pass")
        kinds = {c.kind for c in report.changes}
        self.assertIn("state.add", kinds)
        self.assertIn("transition.add", kinds)

    def test_adding_guard_passes(self):
        old = Spec.model_validate(_base())
        nd = _base()
        nd["contexts"][0]["domains"]["A"]["guards"].append(
            {"edge": "Y->Z", "id": "G2", "desc": "y→z 가드"})
        report = gate(old, Spec.model_validate(nd))
        self.assertEqual(report.verdict, "pass")


class GateReject(unittest.TestCase):
    def test_removing_guard_is_reject(self):
        old = Spec.model_validate(_base())
        nd = _base()
        nd["contexts"][0]["domains"]["A"]["guards"] = []
        report = gate(old, Spec.model_validate(nd))
        self.assertEqual(report.verdict, "reject")
        self.assertTrue(any(c.kind == "guard.remove" for c in report.changes))

    def test_removing_invariant_is_reject(self):
        old = Spec.model_validate(_base())
        nd = _base()
        nd["contexts"][0]["domains"]["A"]["invariants"] = []
        self.assertEqual(gate(old, Spec.model_validate(nd)).verdict, "reject")

    def test_removing_state_is_reject(self):
        old = Spec.model_validate(_base())
        nd = _base()
        nd["contexts"][0]["domains"]["A"]["states"] = ["X", "Y"]
        nd["contexts"][0]["domains"]["A"]["transitions"] = {"X": ["Y"]}
        report = gate(old, Spec.model_validate(nd))
        self.assertEqual(report.verdict, "reject")
        self.assertTrue(any(c.kind == "state.remove" for c in report.changes))

    def test_removing_context_is_reject(self):
        old = Spec.model_validate(_base())
        nd = _base()
        nd["contexts"] = []
        self.assertEqual(gate(old, Spec.model_validate(nd)).verdict, "reject")


class GateReview(unittest.TestCase):
    def test_removing_transition_is_review(self):
        # 전이 제거 = 상태머신 강화 → 대안(고립 인스턴스 확인 필요).
        old = Spec.model_validate(_base())
        nd = _base()
        nd["contexts"][0]["domains"]["A"]["transitions"] = {"X": ["Y"]}
        report = gate(old, Spec.model_validate(nd))
        self.assertEqual(report.verdict, "review")
        self.assertTrue(any(c.kind == "transition.remove" for c in report.changes))

    def test_rename_suggestion_on_state_swap(self):
        # 상태 동시 추가+제거면 rename 대안을 제시(판정은 안전하게 reject 유지).
        old = Spec.model_validate(_base())
        nd = _base()
        d = nd["contexts"][0]["domains"]["A"]
        d["states"] = ["X", "Y", "DONE"]            # Z→DONE rename 의도
        d["transitions"] = {"X": ["Y"], "Y": ["DONE"]}
        report = gate(old, Spec.model_validate(nd))
        rm = next(c for c in report.changes if c.kind == "state.remove")
        self.assertIn("rename", rm.suggestion)


if __name__ == "__main__":
    unittest.main()
