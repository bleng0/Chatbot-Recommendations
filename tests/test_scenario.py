import pytest

from pome.app.scenario import GPU_OPTIONS, Scenario, breakeven_tickets, decide

VLLM = "gemma4-12b-vllm-in-bf16"


def test_gpu_options_are_cited_vendor_prices():
    assert GPU_OPTIONS
    for o in GPU_OPTIONS.values():
        assert o.price.provenance == "vendor-doc" and o.price.source.startswith("https://")
        assert o.price.unit == "usd_per_hour" and o.price.value > 0


def test_selfhost_cost_is_modeled_from_gpu_price_hours_and_ops(tmp_path):
    name = next(iter(GPU_OPTIONS))
    snap, _ = decide(Scenario(gpu=name, gpus=1, ops_monthly_usd=100.0), tmp_path)
    v = snap.values[f"{VLLM}.cost.monthly_usd"]
    assert v.provenance == "modeled"
    assert v.value == pytest.approx(GPU_OPTIONS[name].price.value * 730 + 100.0, abs=0.01)
    assert "730" in v.formula


def test_volume_changes_api_cost_but_not_selfhost_cost(tmp_path):
    # needs measured tokens for the API config: write a minimal Flash record file
    d = tmp_path / "gem25f-api-global"
    d.mkdir()
    (d / "banking77_run0.jsonl").write_text("".join(
        '{"gold":"a","pred":"a","in_tokens":600,"out_tokens":200,"status":200}\n'
        for _ in range(20)))
    s1, _ = decide(Scenario(volume=100_000), tmp_path)
    s2, _ = decide(Scenario(volume=200_000), tmp_path)
    a1, a2 = (s.values["gem25f-api-global.cost.monthly_usd"].value for s in (s1, s2))
    assert a2 == pytest.approx(2 * a1, rel=1e-6)
    assert s1.values[f"{VLLM}.cost.monthly_usd"] == s2.values[f"{VLLM}.cost.monthly_usd"]


def test_same_scenario_gives_same_decision_hash(tmp_path):
    _, d1 = decide(Scenario(), tmp_path)
    _, d2 = decide(Scenario(), tmp_path)
    assert d1.decision_hash == d2.decision_hash


def test_breakeven_is_fixed_cost_over_per_ticket_cost():
    assert breakeven_tickets(api_cost_per_ticket=0.001, selfhost_monthly=1000.0) == 1_000_000
    assert breakeven_tickets(api_cost_per_ticket=0.0, selfhost_monthly=1000.0) is None
