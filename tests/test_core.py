"""Core smoke tests — domain-agnostic."""
import os, sys, tempfile, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cge1 import (ObjectiveSpec, GateSet, MetricThreshold,
                   ShrinkageScorer, ConstraintLedger, Observation)


def test_gate_pass():
    gs = GateSet(gates=(MetricThreshold("acc", 0.75),))
    ok, fails = gs.check({"acc": 0.80})
    assert ok and not fails

def test_gate_fail():
    gs = GateSet(gates=(MetricThreshold("acc", 0.75),))
    ok, _ = gs.check({"acc": 0.60})
    assert not ok

def test_beats():
    gs = GateSet(gates=(MetricThreshold("a", 0.5),))
    assert gs.beats({"a": 0.9}, {"a": 0.8})
    assert not gs.beats({"a": 0.7}, {"a": 0.8})

def test_shrinkage():
    sc = ShrinkageScorer(prior_mean=0.45, prior_weight=6.0)
    r = sc.evaluate([0.8, 0.9, 0.7])
    assert 0.5 < r.score < 0.9
    r_empty = sc.evaluate([])
    assert r_empty.score == 0.45
    r_single = sc.evaluate([0.9])
    assert r_single.score > 0.4  # above prior but pulled toward it

def test_constraints():
    path = os.path.join(tempfile.mkdtemp(), "ledger.json")
    cl = ConstraintLedger(path)
    can, _ = cl.can_attempt("test", "abc")
    assert can
    cl.register_attempt("test", "abc")
    cl.burn("test", "abc", reason="test")
    can2, reason2 = cl.can_attempt("test", "abc")
    assert not can2 and "burned" in reason2
    cl.record_null()
    s = cl.stats()
    assert s["nulls"] == 1 and s["burned"] == 1

def test_spec_roundtrip():
    spec = ObjectiveSpec(
        name="my_optimisation",
        primary_metric="accuracy",
        gates=GateSet(gates=(MetricThreshold("accuracy", 0.75),)),
        search_space={"lr": [0.01, 0.1]},
    )
    d = spec.to_dict()
    assert d["name"] == "my_optimisation"
    assert d["family"] == "generic"

if __name__ == "__main__":
    test_gate_pass()
    print("gate_pass OK"); test_gate_fail(); print("gate_fail OK")
    test_beats(); print("beats OK")
    test_shrinkage(); print("shrinkage OK")
    test_constraints(); print("constraints OK")
    test_spec_roundtrip(); print("spec roundtrip OK")
    print("\nALL TESTS PASS")
