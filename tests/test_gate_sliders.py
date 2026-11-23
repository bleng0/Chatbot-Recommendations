"""Per-gate threshold sliders (CLAUDE.md section 3 exception): session-only what-if."""
import pytest

from pome.app.scenario import Scenario, decide, decide_sliders
from pome.profiles.loader import load_profile, profile_hash, what_if_profile

SLIDER_GATES = ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9"]
LOOSE = {"G1": 0.0, "G2": 0.0, "G3": 0.0, "G4": 0.0, "G5": 0.0,
         "G6": 1.0, "G7": 1.0, "G8": 10_000_000, "G9": 0.0}


def test_threshold_override_moves_only_that_gate_and_leaves_the_official_profile_alone():
    base = load_profile()
    before = profile_hash(base)
    wi = what_if_profile(base, (), thresholds={"G8": 30000})
    assert wi.gates["G8"].value == 30000
    assert wi.gates["G9"] == base.gates["G9"]
    assert profile_hash(base) == before
    assert wi.what_if_of == base.name


def test_threshold_override_refuses_unknown_and_yes_no_gates():
    base = load_profile()
    with pytest.raises(ValueError):
        what_if_profile(base, (), thresholds={"G99": 1.0})
    with pytest.raises(ValueError):
        what_if_profile(base, (), thresholds={"G14": 0.5})


def test_sliders_never_change_the_official_decision_hash():
    snap, d = decide(Scenario())
    decide_sliders(snap, Scenario(), (), LOOSE)
    assert decide(Scenario())[1].decision_hash == d.decision_hash


def test_loosened_passes_are_labelled_not_recommended_with_the_gate():
    snap, d = decide(Scenario())
    wi, not_rec = decide_sliders(snap, Scenario(), (), LOOSE)
    assert not_rec, "loosening every slider must let at least one rejected config pass"
    status = {v.config_id: v.status for v in wi.verdicts}
    official = {v.config_id: v.status for v in d.verdicts}
    for cid, gates in not_rec.items():
        assert status[cid].startswith("eligible")
        assert not official[cid].startswith("eligible")
        assert gates and set(gates) <= set(SLIDER_GATES)


def test_stricter_sliders_keep_normal_labels():
    snap, _ = decide(Scenario())
    strict = {"G1": 0.95, "G8": 1000}
    _, not_rec = decide_sliders(snap, Scenario(), (), strict)
    assert not_rec == {}


def test_slider_specs_cover_number_gates_only_with_official_inside_the_range():
    from pome.app.sliders import slider_specs
    specs = slider_specs(load_profile(), [*SLIDER_GATES, "G14"], str)
    assert [s["id"] for s in specs] == SLIDER_GATES
    assert all(s["min"] <= s["official"] <= s["max"] for s in specs)


def test_not_recommended_chip_and_note_render_in_the_what_if_column():
    from pome.app import render
    html = render.gate_table([{"config": "a", "status": "rejected", "gates": {}}], [], set(),
                             {"a": "not_recommended"}, notes={"a": "G8 official ≤ 20,000 ms"})
    assert "Not recommended" in html and "G8 official" in html
