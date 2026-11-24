import json
from dataclasses import replace
from pathlib import Path

from streamlit.testing.v1 import AppTest

from pome.app.scenario import (
    GPU_OPTIONS,
    SERVING_METRICS,
    DeploymentPlan,
    Scenario,
    decide,
    decide_what_if,
)
from pome.cost.infrastructure import Estimate, OwnedInputs, rental_estimate
from pome.profiles.loader import load_profile
from pome.registry.hosting import OWNED, owned_config
from tests.test_selection import ev


def test_node_billing_and_owned_cost_with_a_missing_quote():
    sku = GPU_OPTIONS["aws-mum-4l40s"]
    assert sku.gpus_per_node == 4
    rate = float(sku.price.value)
    assert rental_estimate(rate, 2, 730, ()).monthly == rate * 2 * 730
    owned = OwnedInputs(2, (("GPU", 360_000), ("UPS", None)), 0.5, 10, 1.2, 36, 730,
                        (("Connectivity", 1_000),))
    estimate = owned.estimate()
    assert estimate.upfront == 720_000
    assert estimate.operating == 9_760
    assert not estimate.complete and estimate.missing == ("UPS",)
    quoted = replace(owned, capex_lines=(("GPU", 360_000), ("UPS", 36_000))).estimate()
    assert quoted.complete and quoted.monthly == 31_760


def test_owned_requires_matching_hardware_evidence_even_with_serving_gates_off(tmp_path):
    cfg = owned_config(OWNED["pilot"])
    records = tmp_path / "records"
    serving = tmp_path / "serving"
    serving.mkdir()
    plan = DeploymentPlan("owned-pilot", 1, 32, 16, Estimate(1_000, 100, 200),
                          "docs/distinction.md", "test estimate")
    scenario = Scenario()
    off = tuple(g for g in load_profile().gates if g != "G11")
    tags = {
        "config_id": cfg.config_id, "hardware": plan.hardware, "nodes": 1, "gpus_per_node": 1,
        "runtime": cfg.serving, "precision": cfg.quant, "checkpoint": cfg.model_id,
        "input_tokens": 600, "output_tokens": 200, "max_model_len": 4096,
        "runtime_version": "test-runtime", "checkpoint_revision": "test-revision",
    }
    entries = {key: ev(value, unit=unit).model_copy(update={"measured_under": tags})
               .model_dump(mode="json")
               for (key, unit), value in zip(SERVING_METRICS.items(), (1500, 8, 0.5), strict=True)}
    file = serving / f"{cfg.config_id}.json"

    def evaluate(selected):
        snapshot, _ = decide(scenario, records, [cfg], deployment_plans={cfg.config_id: selected},
                             scope="owned", inr_per_usd=100)
        return snapshot, decide_what_if(snapshot, scenario, off)

    pending, result = evaluate(plan)
    assert result.recommended is None
    assert pending.values[f"{cfg.config_id}.cost.monthly_usd"].value == 2
    file.write_text(json.dumps(entries))
    mismatch, result = evaluate(replace(plan, nodes=2))
    assert result.recommended is None
    assert f"{cfg.config_id}.reference.curated.serving.p95_ms" in mismatch.values
    _, result = evaluate(plan)
    assert result.recommended == cfg.config_id
    _, result = evaluate(replace(plan, vram_gb=8))
    assert result.recommended is None and "Does not fit" in result.verdicts[0].reasons[-1]
    subtotal, result = evaluate(replace(plan, estimate=Estimate(1_000, 100, 200, ("UPS",))))
    assert result.recommended is None
    assert f"{cfg.config_id}.cost.monthly_usd" not in subtotal.values
    assert subtotal.values[f"{cfg.config_id}.cost.known_subtotal_inr"].value == 200


def test_hosting_filter_scopes_all_tabs():
    app = AppTest.from_file(Path("pome/app/home.py").resolve(), default_timeout=15).run()
    for scope, present, absent in (
        ("all", "gpt54nano-api-global", None),
        ("api", "gpt54nano-api-global", "gemma4-12b-owned-w4a16"),
        ("rental", "gemma4-12b-vllm-in-bf16", "gpt54nano-api-global"),
        ("owned", "gemma4-12b-owned-w4a16", "gpt54nano-api-global"),
    ):
        app.sidebar.radio[0].set_value(scope).run()
        assert not app.exception
        tabs = {tab.label: tab for tab in app.tabs}
        for name in ("Gates", "Evidence", "Configurations"):
            if name == "Gates":
                component, = tabs[name].get("component_instance")
                html = json.loads(component.proto.json_args)["table"]
            else:
                html = " ".join(item.proto.body for item in tabs[name].get("html"))
            assert present in html
            if absent:
                assert absent not in html
        assert present in tabs["Deployment variants"].selectbox[0].options[0] or any(
            present in option for option in tabs["Deployment variants"].selectbox[0].options
        )
        assert tabs["Cost"].dataframe
        assert tabs["Baselines"].get("html") or tabs["Baselines"].markdown
