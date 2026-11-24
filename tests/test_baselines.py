"""Baselines (PLAN F8): what three simple rules would pick instead of the gates."""
from pome.app import render
from pome.app.scenario import Scenario, decide
from pome.app.views import baselines
from pome.registry.loader import load_registry


def _cards():
    snap, d = decide(Scenario())
    return d, baselines(d, snap, load_registry())


def test_four_cards_in_order_with_our_rule_first():
    d, cards = _cards()
    assert [c["title"] for c in cards] == [
        "Our rule", "Highest benchmark score", "Lowest price", "Self-host only"]
    assert cards[0]["config"] == d.recommended and cards[0]["fails"] == []
    assert cards[0]["delta_usd"] == 0


def test_lowest_price_is_the_cheapest_config_and_names_what_it_fails():
    d, cards = _cards()
    cheapest = min((v for v in d.verdicts if v.monthly_cost is not None),
                   key=lambda v: (v.monthly_cost, v.config_id))
    low = cards[2]
    assert low["config"] == cheapest.config_id
    assert low["delta_usd"] < 0 and low["fails"]  # cheaper than our pick, but fails something


def test_benchmark_card_uses_only_self_tested_quality():
    snap, d = decide(Scenario())
    best = baselines(d, snap, load_registry())[1]["config"]
    assert snap.values[f"{best}.intent.banking77.macro_f1"].provenance == "measured"


def test_self_host_card_is_a_rented_gpu_config():
    reg = {c.config_id: c for c in load_registry()}
    _, cards = _cards()
    assert reg[cards[3]["config"]].hosting_kind == "rental"


def test_baselines_are_pure_and_repeatable():
    snap, d = decide(Scenario())
    assert baselines(d, snap, load_registry()) == baselines(d, snap, load_registry())


def test_baseline_cards_render_cost_badge_delta_and_failures():
    html = render.baseline_cards([
        {"title": "Our rule", "rule": "r", "config": "a", "model": "m", "host": "h",
         "cost": "₹10", "badge": "MODELED", "delta": "", "delta_usd": 0, "fails": []},
        {"title": "Lowest price", "rule": "r", "config": "b<x", "model": "m", "host": "h",
         "cost": "₹5", "badge": "MODELED", "delta": "₹5 less a month than our pick",
         "delta_usd": -1, "fails": ["Error limit"]}])
    assert "Passes every gate" in html and "Fails 1 check" in html and "Error limit" in html
    assert "b&lt;x" in html and "MODELED" in html and "official" not in html.lower()
