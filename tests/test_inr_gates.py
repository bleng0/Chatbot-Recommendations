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
    assert rows["G14"]["pass_if"] == "required"


def test_more_self_host_gpu_options_each_with_a_sourced_price():
    assert len(GPU_OPTIONS) >= 7
    for o in GPU_OPTIONS.values():
        assert o.price.source.startswith("http") or "prices.azure.com" in o.price.source


def test_max_spend_sets_the_budget_gate_and_can_change_the_decision():
    from pome.app.scenario import Scenario, decide
    _, default = decide(Scenario())
    _, tight = decide(Scenario(max_spend_usd=10.0))
    assert default.recommended == "gpt54mini-api-global"   # ₹12,528 fits the default budget
    assert tight.recommended != "gpt54mini-api-global"     # ~₹928 cap rules it out
    assert default.decision_hash != tight.decision_hash


def test_gate_information_no_longer_lists_the_budget_gate():
    rows = [r["gate"] for r in gate_info_rows(load_profile())]
    assert "G11" not in rows
