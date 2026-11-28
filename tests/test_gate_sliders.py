"""Threshold sliders, session profiles, and the live gate table."""
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

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


def test_relaxed_capacity_updates_the_main_recommendation_and_eligibility():
    default_snapshot, default = decide(Scenario())
    snapshot, edited = decide(Scenario(gate_thresholds={"G9": 1.0}))
    assert snapshot.sha256 == default_snapshot.sha256
    assert edited.decision_hash != default.decision_hash
    assert edited.recommended != default.recommended
    previous = {v.config_id: v for v in default.verdicts}[edited.recommended]
    assert any(g.gate == "G9" and g.status == "fail" for g in previous.gates)
    assert edited.shortlist[0].status.startswith("eligible")


def test_streamlit_live_gate_edits_and_reset():
    home = Path(__file__).resolve().parents[1] / "pome/app/home.py"
    app = AppTest.from_file(home, default_timeout=20).run()

    def outputs():
        assert not app.exception
        component, = app.get("component_instance")
        table = json.loads(component.proto.json_args)["table"]
        answer = next(item.proto.body for item in app.get("html")
                      if 'class="ac"' in item.proto.body or 'class="ans"' in item.proto.body)
        return answer, table, component.proto.id

    original_answer, original_table, original_component = outputs()
    app.session_state["gate_sliders_0"] = {"G9": 1.0}
    app.run()
    live_answer, live_table, _ = outputs()
    _, edited = decide(Scenario(gate_thresholds={"G9": 1.0}))
    assert edited.recommended in live_answer and live_answer != original_answer
    assert live_table != original_table and "What-if" not in live_table

    app.toggle(key="gate_G9").set_value(False).run()
    disabled_answer, disabled_table, _ = outputs()
    assert disabled_answer != live_answer and "Capacity</span><small>off</small>" in disabled_table

    app.select_slider(key="volume").set_value(200_000)
    app.number_input(key="max_spend").set_value(10_000)
    app.number_input(key="max_error").set_value(2.0)
    app.radio(key="hosting_scope").set_value("rental")
    app.selectbox(key="rental_machine").set_value("e2e-h100")
    app.number_input(key="rental_nodes").set_value(2)
    app.number_input(key="rental_hours").set_value(500)
    app.number_input(key="rental_storage").set_value(500)
    owned_input = next(widget for widget in app.number_input if widget.key.endswith("_tariff"))
    owned_input.set_value(12.0)
    app.checkbox(key="compliance_G16").check()
    app.toggle(key="show_gate_values").set_value(True)
    app.run()
    assert outputs()[:2] != (original_answer, original_table)

    next(b for b in app.sidebar.button if b.label == "Reset to recommended").click().run()
    answer, table, component = outputs()
    assert (answer, table) == (original_answer, original_table)
    assert component != original_component
    assert app.number_input(key=owned_input.key).value == 10.0
    assert app.number_input(key="rental_hours").value == 730
    assert app.number_input(key="rental_storage").value == 0
    assert not app.checkbox(key="compliance_G16").value
    app.run()
    assert outputs() == (answer, table, component)


def test_gate_values_toggle_shows_evidence_in_the_slider_table():
    home = Path(__file__).resolve().parents[1] / "pome/app/home.py"
    app = AppTest.from_file(home, default_timeout=20).run()

    def table():
        assert not app.exception
        component, = app.get("component_instance")
        return json.loads(component.proto.json_args)["table"]

    def nano_row(html):
        return next(row for row in html.split("</tr>") if 'title="gpt54nano-api-global"' in row)

    initial = table()
    assert "gate-value" not in initial
    assert "st-pass" in nano_row(initial)

    app.toggle(key="show_gate_values").set_value(True).run()
    row = nano_row(table())
    assert "st-pass" in row and "81.25%" in row and "3,207 ms" in row
    assert "MODELED" in row and "Hinglish" in row and " pp" in row

    app.toggle(key="gate_G1").set_value(False).run()
    row = nano_row(table())
    assert '<td class="g off">' in row and "81.25%" in row

    app.toggle(key="gate_G1").set_value(True).run()
    app.toggle(key="show_gate_values").set_value(False).run()
    assert table() == initial
