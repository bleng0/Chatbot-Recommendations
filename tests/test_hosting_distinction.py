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


def test_artificial_analysis_references_follow_hardware_and_stay_out_of_serving_gates():
    from pome.app.scenario import GPU_OPTIONS
    from pome.registry.loader import load_registry

    cfg = next(c for c in load_registry() if c.config_id == "gemma4-31b-vllm-in-bf16")
    gpu = "azure-ci-a100"
    plan = DeploymentPlan(gpu, 1, GPU_OPTIONS[gpu].vram_gb, 80, Estimate(1000, 100, 200),
                          "quote", "fixed", gpus_per_node=1)

    def evaluate(deployment):
        return decide(Scenario(), registry=[cfg], deployment_plans={cfg.config_id: deployment},
                      scope="rental", inr_per_usd=100)

    snapshot, decision = evaluate(plan)
    prefix = f"{cfg.config_id}.reference."
    first_answer = snapshot.values[prefix + "artificial_analysis.first_answer_s"]
    latency = snapshot.values[prefix + "performance_plan.request_ms"]
    rate = snapshot.values[prefix + "performance_plan.serial_rps"].value
    assert first_answer.value == 1.0 and first_answer.study
    assert latency.provenance == "modeled" and latency.value > 1000
    assert f"{cfg.config_id}.serving.p95_ms" not in snapshot.values
    assert decision.recommended is None

    scaled, _ = evaluate(replace(plan, nodes=2))
    assert scaled.values[prefix + "performance_plan.request_ms"].value == latency.value
    assert abs(scaled.values[prefix + "performance_plan.serial_rps"].value - 2 * rate) <= 0.001
    oversized, _ = evaluate(replace(plan, vram_gb=32))
    assert prefix + "performance_plan.request_ms" not in oversized.values


def test_hardware_selection_builds_only_fitting_rental_and_owned_candidates():
    app = AppTest.from_file(Path("pome/app/home.py").resolve(), default_timeout=20).run()

    def deployment_options():
        assert not app.exception
        return " ".join(app.selectbox(key="deployment_model").options)

    app.radio(key="hosting_scope").set_value("rental").run()
    app.selectbox(key="deployment_model").select("gemma4-31b-vllm-in-bf16").run()
    app.selectbox(key="rental_machine").select("aws-mum-4l40s").run()
    options = deployment_options()
    assert "gemma4-31b-vllm-in-bf16" not in options
    assert "gemma4-12b-vllm-in-w4a16" in options
    app.selectbox(key="deployment_model").select("gemma4-12b-vllm-in-w4a16").run()
    tab = next(tab for tab in app.tabs if tab.label == "Deployment variants")
    assert any("4 replica(s)" in caption.value for caption in tab.caption)
    assert any("Planning only" in item.value for item in tab.markdown)

    app.selectbox(key="rental_machine").select("custom").run()
    app.text_input(key="rental_custom_machine").set_value("Private cloud · Mumbai")
    app.number_input(key="rental_custom_vram").set_value(24)
    app.number_input(key="rental_custom_gpus").set_value(2)
    app.number_input(key="rental_hours").set_value(20)
    app.run()
    assert "gemma4-12b-vllm-in-bf16" not in deployment_options()
    app.selectbox(key="deployment_model").select("gemma4-12b-vllm-in-w4a16").run()
    tab = next(tab for tab in app.tabs if tab.label == "Deployment variants")
    assert any("complete monthly comparison is unavailable" in item.value for item in tab.markdown)
    app.number_input(key="rental_custom_rate").set_value(50.0).run()
    tab = next(tab for tab in app.tabs if tab.label == "Deployment variants")
    assert any("₹1,000" in item.value for item in tab.markdown)
    app.number_input(key="rental_custom_vram").set_value(8).run()
    assert not app.exception
    assert any("No rental configurations fit" in info.value for info in app.info)

    app.radio(key="hosting_scope").set_value("owned").run()
    app.selectbox(key="owned_hardware").select("production").run()
    assert "gemma4-31b-owned-bf16" in deployment_options()
    assert "sarvam30b-owned-bf16" in deployment_options()

    app.selectbox(key="owned_hardware").select("custom").run()
    app.text_input(key="custom_gpu_model").set_value("Test GPU")
    app.number_input(key="custom_vram").set_value(24)
    app.number_input(key="custom_gpus").set_value(2)
    app.number_input(key="custom_nodes").set_value(3)
    app.number_input(key="owned_custom_bandwidth").set_value(800.0)
    app.run()
    options = deployment_options()
    assert "llama31-8b-owned-bf16" in options
    assert "gemma4-12b-owned-bf16" not in options
    app.selectbox(key="deployment_model").select("llama31-8b-owned-bf16").run()
    tab = next(tab for tab in app.tabs if tab.label == "Deployment variants")
    assert any("Test GPU · 3 nodes · 2 GPU(s) per node · 24 GB" in item.value
               for item in tab.markdown)
    assert any("6 replica(s)" in caption.value for caption in tab.caption)
    assert any("Performance model" in caption.value for caption in tab.caption)
    assert any("Planning only" in item.value for item in tab.markdown)

    app.number_input(key="custom_vram").set_value(8).run()
    assert "llama31-8b-owned-bf16" not in deployment_options()
    assert "gemma4-12b-ollama-local-q4" in deployment_options()

    next(b for b in app.sidebar.button if b.label == "Reset to recommended").click().run()
    assert app.selectbox(key="owned_hardware").value == "pilot"
    assert app.selectbox(key="rental_machine").value == "azure-ci-a100"
    assert "gemma4-12b-owned-w4a16" in deployment_options()
