"""Gap fill: every config gets a value for every gate key, never as `measured`."""
from pome.app.scenario import Scenario, decide
from pome.registry.loader import load_registry
from pome.selection.engine import required_keys


def _snap():
    return decide(Scenario())[0]


def test_every_config_has_every_required_key():
    snap = _snap()
    missing = [k for c in load_registry() for k in required_keys(c.config_id)
               if k not in snap.values]
    assert missing == []


def test_gap_fill_never_claims_measured():
    snap = _snap()
    measured = {k for k, v in snap.values.items() if v.provenance == "measured"}
    # only values built from recorded runs are measured: their run file is named in run_ids
    assert all(snap.values[k].run_ids for k in measured)
    assert "gpt54mini-api-global.intent.banking77.macro_f1" not in measured


def test_gap_fill_keeps_existing_measured_value():
    snap = _snap()
    v = snap.values["gem25f-api-global.intent.banking77.macro_f1"]
    assert v.provenance == "measured"


def test_proxy_quality_names_its_anchor():
    v = _snap().values["sonnet55-api-global.faq.correct.hinglish"]
    assert v.provenance == "modeled"
    assert "gemma4-12b-ollama-local-q4" in v.formula


def test_api_latency_formula_uses_published_speed():
    v = _snap().values["gpt54mini-api-global.serving.p95_ms"]
    assert v.provenance == "modeled"
    assert v.value == 2780  # (1.18 s + 200 / 125 tok/s) * 1000


def test_selfhost_configs_all_get_a_cost():
    snap = _snap()
    for c in load_registry():
        if c.host.startswith("self-hosted"):
            assert snap.values[f"{c.config_id}.cost.monthly_usd"].provenance == "modeled"


def test_decision_is_deterministic():
    a = decide(Scenario())[1].decision_hash
    b = decide(Scenario())[1].decision_hash
    assert a == b
