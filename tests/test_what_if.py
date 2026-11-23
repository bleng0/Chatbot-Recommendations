"""What-if profiles (CONSTRAINTS.md section A): banking_mvp minus switched-off gates.

Exploration only. The official decision always uses banking_mvp as written; a what-if never
edits a threshold and never changes the official decision hash.
"""
import pytest

from pome.app.scenario import Scenario, decide, decide_what_if
from pome.profiles.loader import Profile, load_profile, profile_hash, what_if_profile
from pome.selection.engine import select
from tests.test_selection import LENIENT, ev, passing, snap, verdict


def test_kept_gates_keep_identical_thresholds():
    base = load_profile()
    wi = what_if_profile(base, ["G1", "G11"])
    assert set(wi.gates) == set(base.gates) - {"G1", "G11"}
    assert all(wi.gates[g] == base.gates[g] for g in wi.gates)
    assert wi.what_if_of == base.name


def test_unknown_or_empty_switch_off_is_rejected():
    with pytest.raises(ValueError, match="G99"):
        what_if_profile(load_profile(), ["G99"])
    with pytest.raises(ValueError, match="at least one"):
        what_if_profile(load_profile(), [])


def test_official_profile_hash_ignores_the_what_if_marker():
    base = load_profile()
    assert base.what_if_of is None
    assert "what_if_of" not in base.model_dump(exclude={"what_if_of"})
    assert profile_hash(base) != profile_hash(what_if_profile(base, ["G1"]))


def test_what_if_never_changes_the_official_decision_hash(tmp_path):
    snap, before = decide(Scenario(), tmp_path)
    wi = decide_what_if(snap, Scenario(), ("G1",))
    _, after = decide(Scenario(), tmp_path)
    assert before.decision_hash == after.decision_hash
    assert wi.decision_hash != before.decision_hash


def test_same_what_if_twice_gives_the_same_hash(tmp_path):
    snap, _ = decide(Scenario(), tmp_path)
    a = decide_what_if(snap, Scenario(), ("G1", "G11"))
    b = decide_what_if(snap, Scenario(), ("G11", "G1"))
    assert a.decision_hash == b.decision_hash


def test_a_profile_file_cannot_declare_itself_a_what_if(tmp_path):
    text = (load_profile.__defaults__[0]).read_text(encoding="utf-8")
    f = tmp_path / "p.yaml"
    f.write_text(text + "what_if_of: banking_mvp\n", encoding="utf-8")
    with pytest.raises(ValueError, match="what_if_of"):
        load_profile(f)


def test_empty_what_if_marker_is_rejected():
    data = LENIENT.model_dump() | {"what_if_of": ""}
    with pytest.raises(ValueError, match="what_if_of"):
        Profile.model_validate(data)


def test_switching_off_the_only_failing_gate_makes_a_config_eligible():
    s = snap(passing("a", q=0.85), override={"a.intent.banking77.macro_f1": ev(0.70)})
    official = select(s, LENIENT)
    assert verdict(official, "a").status == "rejected" and official.recommended is None
    wi = select(s, what_if_profile(LENIENT, ["G1"]))
    assert wi.recommended == "a"
    assert "G1" not in {g.gate for g in verdict(wi, "a").gates}


def test_what_if_without_cost_or_quality_gates_still_ranks_without_crashing():
    quality = ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G11"]
    s = snap(passing("a"), passing("b", cost=500.0), drop=["a.cost.monthly_usd"])
    d = select(s, what_if_profile(LENIENT, quality))
    assert d.recommended == "b"  # a config with no cost ranks after one with a cost
    assert [v.config_id for v in d.shortlist] == ["b", "a"]
