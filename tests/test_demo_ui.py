"""The approved refinements demo (2026-11-23), as app behaviour."""
from pome.app import render
from pome.app.scenario import Scenario, decide, decide_sliders
from pome.app.views import SHORT_NAME, indian, tickets_options, what_if_pick


def test_tickets_options_are_log_spaced_and_keep_the_profile_volume():
    opts = tickets_options()
    assert opts[0] == 10_000 and opts[-1] == 10_000_000 and 100_000 in opts
    assert opts == sorted(set(opts))
    assert 30 <= len(opts) <= 80


def test_indian_grouping():
    assert indian(100000) == "1,00,000"
    assert indian(10_000_000) == "1,00,00,000"
    assert indian(950) == "950"


def test_every_shown_gate_has_a_short_name():
    assert SHORT_NAME["G8"] == "Latency" and SHORT_NAME["G14"] == "Licence"
    assert len(SHORT_NAME) == 10


def test_what_if_prefers_the_cheapest_valid_config_over_a_not_recommended_one():
    snap, _ = decide(Scenario())
    wi, not_rec = decide_sliders(snap, Scenario(), (), {"G9": 1.0})
    pick, flagged = what_if_pick(wi, not_rec)
    assert pick is not None and not flagged and pick not in not_rec
    assert not_rec, "G9 at 1/s must let a cheaper config pass only by loosening"


def test_what_if_falls_back_to_a_flagged_pick_when_nothing_valid_passes():
    snap, _ = decide(Scenario())
    wi, not_rec = decide_sliders(snap, Scenario(), (), {"G9": 1.0, "G1": 0.99})
    pick, flagged = what_if_pick(wi, not_rec)
    assert pick is None or flagged == (pick in not_rec)


def test_answer_card_names_model_and_hosting_plan_with_modeled_badge():
    html = render.answer_card(model="gpt-5.4-nano", config="gpt54nano-api-global",
                              host="OpenAI API", region="global endpoint", cost="₹3,433",
                              modeled=True, passing=3, total=20, decision_hash="e9ad4c71d6a2")
    for s in ("Model", "Hosting plan", "gpt-5.4-nano", "OpenAI API", "MODELED", "3", "20",
              "e9ad4c71d6a2"):
        assert s in html
    assert "official" not in html.lower()


def test_answer_text_turns_cost_modeled_into_a_badge():
    html = render.answer("Recommended: a at ₹1/month (cost MODELED)", recommended=True)
    assert "(cost MODELED)" not in html and 'class="bdg' in html


def test_gate_table_says_recommended_not_official_and_shows_short_names():
    html = render.gate_table([{"config": "a", "status": "rejected", "gates": {"G8": "pass"}}],
                             ["G8"], set(), {"a": "eligible"}, labels={"G8": "G8"},
                             short={"G8": "Latency"})
    assert "official" not in html.lower() and "Recommended status" in html and "Latency" in html
