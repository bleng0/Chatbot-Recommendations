import pytest
import yaml

from pome.registry.loader import load_registry

PRICING = "https://aistudio.google.com/docs/pricing"


@pytest.fixture(scope="module")
def configs():
    return {c.config_id: c for c in load_registry()}


def test_registry_has_the_four_agreed_configs(configs):
    assert sorted(configs) == [
        "gem25f-api-global",
        "gem25fl-api-global",
        "gemma4-26b-api-global",
        "gemma4-26b-vllm-in-bf16",
    ]


def test_model_ids_match_verified_docs(configs):
    assert configs["gem25fl-api-global"].model_id == "gemini-2.5-flash-lite"
    assert configs["gem25f-api-global"].model_id == "gemini-2.5-flash"
    assert configs["gemma4-26b-api-global"].model_id == "gemma-4-26b-a4b-it"
    assert configs["gemma4-26b-vllm-in-bf16"].model_id == "gemma-4-26b-a4b-it"


@pytest.mark.parametrize(
    "cid,in_p,out_p",
    [
        ("gem25fl-api-global", 0.10, 0.40),
        ("gem25f-api-global", 0.30, 2.50),
    ],
)
def test_prices_match_dated_pricing_page(configs, cid, in_p, out_p):
    p = configs[cid].pricing
    assert p.input_per_1m.value == in_p and p.output_per_1m.value == out_p
    assert p.input_per_1m.provenance == "vendor-doc"
    assert p.input_per_1m.source == PRICING
    assert p.input_per_1m.retrieved_at.year == 2026


def test_gemma_api_has_no_paid_price(configs):
    p = configs["gemma4-26b-api-global"].pricing
    assert p.input_per_1m is None and p.output_per_1m is None


def test_hosted_gemini_retention_is_55_days_from_usage_policy(configs):
    r = configs["gem25fl-api-global"].deployment.retention_days
    assert r.value == 55 and r.provenance == "vendor-doc"
    assert r.source == "https://ai.google.dev/gemini-api/docs/usage-policies"


def test_missing_region_evidence_is_unverified_not_assumed(configs):
    for cid in ("gem25fl-api-global", "gem25f-api-global", "gemma4-26b-api-global"):
        assert configs[cid].deployment.region_processing is None


def test_registry_never_claims_measured(configs):
    for c in configs.values():
        for ev in (
            c.pricing.input_per_1m, c.pricing.output_per_1m,
            c.deployment.region_processing, c.deployment.retention_days,
            c.deployment.commercial_use,
        ):
            assert ev is None or ev.provenance in ("vendor-doc", "modeled")


def test_selfhost_deployment_values_are_modeled_or_vendor_doc(configs):
    d = configs["gemma4-26b-vllm-in-bf16"].deployment
    assert d.region_processing.provenance == "modeled"
    assert d.retention_days.provenance == "modeled"
    assert d.commercial_use.provenance == "vendor-doc"
    assert d.commercial_use.source.startswith("https://opensource.googleblog.com/")


def test_duplicate_config_id_is_rejected(tmp_path):
    p = tmp_path / "dup.yaml"
    entry = {
        "config_id": "x", "model_id": "m", "version": "1", "host": "h", "region": "r",
        "serving": "s", "quant": "none", "evaluation_mode": "measured",
        "pricing": {"input_per_1m": None, "output_per_1m": None},
        "deployment": {"region_processing": None, "retention_days": None, "commercial_use": None},
    }
    p.write_text(yaml.safe_dump({"configs": [entry, entry]}))
    with pytest.raises(ValueError, match="duplicate"):
        load_registry(p)
