"""INR display, gate information phrases, GPU options (owner request 2026-11-23)."""
from pome.app.scenario import GPU_OPTIONS
from pome.app.views import GATE_INFO, USD_INR, gate_info_rows, inr
from pome.profiles.loader import load_profile


def test_inr_uses_indian_digit_grouping_and_the_dated_rate():
    assert USD_INR.value == 92.7968 and USD_INR.provenance == "vendor-doc"
    assert inr(1500) == "₹1,39,195"        # 1500 * 92.7968 = 139,195.2
    assert inr(12.5) == "₹1,160"
    assert inr(0) == "₹0"


def test_every_profile_gate_has_a_one_phrase_criterion():
    gates = load_profile().gates
    assert set(GATE_INFO) >= set(gates)
    for g in gates:
        phrase = GATE_INFO[g]
        assert phrase and "." not in phrase.rstrip(".") and len(phrase.split()) <= 9, g


def test_gate_info_rows_show_the_threshold_with_budget_in_inr():
    rows = {r["gate"]: r for r in gate_info_rows(load_profile())}
    assert rows["G1"]["pass_if"] == "≥ 0.80"
    assert rows["G10"]["pass_if"] == "required"


def test_more_self_host_gpu_options_each_with_a_sourced_price():
    assert len(GPU_OPTIONS) >= 7
    for o in GPU_OPTIONS.values():
        assert o.price.source.startswith("http") or "prices.azure.com" in o.price.source


def test_max_spend_sets_the_budget_gate_and_can_change_the_decision():
    from pome.app.scenario import Scenario, decide
    _, default = decide(Scenario())
    rec = next(v for v in default.verdicts if v.config_id == default.recommended)
    _, tight = decide(Scenario(max_spend_usd=rec.monthly_cost - 0.01))  # just under its cost
    assert default.recommended and tight.recommended != default.recommended
    assert default.decision_hash != tight.decision_hash


def test_gate_information_no_longer_lists_the_budget_gate():
    rows = [r["gate"] for r in gate_info_rows(load_profile())]
    assert "G11" not in rows


def test_owner_thresholds_2026_11_23_g8_20_seconds_g9_5_per_second():
    gates = load_profile().gates
    assert gates["G8"].value == 20000 and gates["G9"].value == 5


def test_no_visible_text_says_pome_tested_it():
    from pome.app.scenario import Scenario, decide
    from pome.app.views import BADGE, evidence_rows
    from pome.registry.loader import load_registry
    snap, _ = decide(Scenario())
    shown = " ".join(r["source"] + r["formula"] for r in evidence_rows(snap))
    shown += " ".join(c.notes for c in load_registry()) + " ".join(BADGE.values())
    assert "POME" not in shown and "MEASURED" not in BADGE.values()
    assert "self-tested" in shown.lower()


def test_shown_gates_are_numbered_without_gaps():
    from pome.app.views import SHOWN_GATES, display_gate, relabel
    assert [display_gate(g) for g in SHOWN_GATES] == [f"G{i}" for i in range(1, 11)]
    assert display_gate("G14") == "G10"
    assert relabel("G14 licence: fail; G10 error rate; G11 cost") == (
        "G10 licence: fail; Error limit error rate; Budget cost")


def test_error_limit_is_a_user_setting_and_peak_is_5():
    from pome.app.scenario import Scenario, decide
    p = load_profile()
    assert p.peak_rps == 5
    rows = [r["gate"] for r in gate_info_rows(p)]
    assert "G10" in rows and len(rows) == 10          # display ids, G14 shown as G10
    _, strict = decide(Scenario(max_error_pct=0.0))
    _, default = decide(Scenario())
    assert strict.decision_hash != default.decision_hash
