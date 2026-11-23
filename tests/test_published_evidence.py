"""Published-study evidence (owner decision D1, 2026-11-23): vendor-doc + study flag."""
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from pome.app.scenario import Scenario, decide
from pome.evidence.schema import EvidenceValue
from pome.registry.loader import load_registry
from pome.selection.engine import select
from tests.test_selection import LENIENT, NOW, passing, snap

NEW_API = ["gpt54nano-api-global", "gpt54mini-api-global", "haiku55-api-global",
           "sonnet55-api-global", "gem35f-vertex-global", "mistralsmall4-api-global",
           "sarvam105b-api-in", "deepseekflash-api-global", "deepseekv41flash-sarvam-in"]
NEW_SELF = ["gemma4-31b-vllm-in-bf16", "gemma4-26b-vllm-in-bf16", "qwen38-27b-vllm-in-bf16",
            "llama31-8b-vllm-in-bf16", "sarvam30b-vllm-in-bf16", "museglimmer30b-vllm-in-bf16"]
UNDER = {"dataset": "BANKING77", "metric": "accuracy", "n": 500}


def study(value=0.9, **kw):
    base = {"value": value, "unit": "ratio", "provenance": "vendor-doc",
            "source": "https://arxiv.org/abs/2607.27421", "retrieved_at": NOW,
            "study": True, "measured_under": UNDER}
    return EvidenceValue(**(base | kw))


def test_study_defaults_to_false():
    e = EvidenceValue(value=1, unit="x", provenance="vendor-doc", source="https://a.b",
                      retrieved_at=NOW)
    assert e.study is False and e.measured_under is None


def test_study_value_is_vendor_doc_with_settings():
    assert study().study is True


@pytest.mark.parametrize("prov", ["measured", "modeled"])
def test_study_flag_only_on_vendor_doc(prov):
    extra = {"run_ids": ["r"]} if prov == "measured" else {"formula": "f"}
    with pytest.raises(ValidationError):
        study(provenance=prov, source="https://a.b", **extra)


@pytest.mark.parametrize("under", [None, {}])
def test_study_needs_reported_settings(under):
    with pytest.raises(ValidationError):
        study(measured_under=under)


def test_study_quality_evidence_gives_eligible_modeled_never_plain_eligible():
    s = snap(passing("a"), override={"a.intent.banking77.macro_f1": study(0.9)})
    v = select(s, LENIENT).verdicts[0]
    assert v.status == "eligible_modeled"
    assert select(s, LENIENT).recommended_is_modeled is True


def test_study_value_on_a_cost_gate_alone_does_not_flag():
    s = snap(passing("a"))
    assert select(s, LENIENT).verdicts[0].status == "eligible"


@pytest.fixture(scope="module")
def configs():
    return {c.config_id: c for c in load_registry()}


def test_fifteen_new_configs_exist(configs):
    assert set(NEW_API + NEW_SELF) <= set(configs)


@pytest.mark.parametrize("cid", NEW_API + NEW_SELF)
def test_new_configs_carry_no_measured_values(configs, cid):
    c = configs[cid]
    vals = [c.pricing.input_per_1m, c.pricing.output_per_1m, c.deployment.region_processing,
            c.deployment.retention_days, c.deployment.commercial_use]
    assert all(v.provenance != "measured" for v in vals if v)
    assert all(v.source.startswith("http") or v.provenance == "modeled" for v in vals if v)


@pytest.mark.parametrize("cid", NEW_API)
def test_new_api_configs_are_priced_only(configs, cid):
    assert configs[cid].evaluation_mode == "priced_only"
    assert configs[cid].pricing.input_per_1m is not None


@pytest.mark.parametrize("cid", NEW_SELF)
def test_new_self_hosted_configs_are_modeled_without_borrowed_quality(configs, cid):
    assert configs[cid].evaluation_mode == "modeled"
    assert configs[cid].quality_from is None


def test_every_variant_metric_is_a_study_value_with_settings(configs):
    n = 0
    for c in configs.values():
        for var in c.variants:
            for e in var.metrics.values():
                n += 1
                assert e.study and e.measured_under and e.provenance == "vendor-doc"
    assert n > 0


def test_llama_has_a_match_variant_and_every_match_states_token_lengths(configs):
    assert any(v.match == "MATCH" for v in configs["llama31-8b-vllm-in-bf16"].variants)
    for c in configs.values():
        for v in c.variants:
            if v.match == "MATCH":
                assert v.input_tokens and v.output_tokens


def test_new_api_configs_get_a_modeled_cost_from_the_stated_token_assumption():
    from pome.evidence.build import build_published_evidence
    from pome.profiles.loader import load_profile
    reg = [c for c in load_registry() if c.config_id == "gpt54mini-api-global"]
    ev = build_published_evidence(reg, load_profile(), datetime(2026, 11, 23, tzinfo=UTC))
    cost = ev["gpt54mini-api-global.cost.monthly_usd"]
    assert cost.provenance == "modeled" and "assumed" in cost.formula
    assert round(float(cost.value), 2) == 135.0  # 60M x 0.75 + 20M x 4.50 per 1M tokens


def test_new_configs_are_never_plain_eligible_and_only_recommended_as_modeled():
    # Owner 2026-11-23 replaced decision D2: unmeasured configs now get proxy evidence, so they
    # may be recommended, but only ever as modeled, never as plainly eligible.
    _, d = decide(Scenario())
    status = {v.config_id: v.status for v in d.verdicts}
    assert set(NEW_API + NEW_SELF) <= set(status)
    assert all(status[c] != "eligible" for c in NEW_API + NEW_SELF)
    if d.recommended in NEW_API + NEW_SELF:
        assert d.recommended_is_modeled
