from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError
from streamlit.testing.v1 import AppTest

from pome.app.scenario import GPU_OPTIONS, Scenario, decide, decide_what_if
from pome.evidence.compliance import (
    BuyerEvidence,
    build_compliance,
    load_buyer_evidence,
    load_catalog,
)
from pome.registry.loader import load_registry

NOW = date(2026, 11, 24)
SARVAM = "sarvam105b-api-in"
SELFHOST = "gemma4-12b-vllm-in-bf16"
GLOBAL = "gpt54nano-api-global"


def review(cid: str, **changes) -> dict:
    cfg = next(c for c in load_registry() if c.config_id == cid)
    identity = cfg.model_dump(include={"config_id", "model_id", "version", "host", "serving",
                                       "region", "quant"})
    return {
        **identity, "reference": "REVIEW-012", "scope": "Workspace text inference",
        "reviewed_on": "2026-11-01", "expires_on": "2026-12-01",
        "contract_verified": True, "configuration_verified": True,
        "facts": {"retention_days": 0, "storage_region": "No persistence",
                  "no_training": True, "no_prompt_logging": True},
        **changes,
    }


def evidence(*records, gpu="azure-ci-a100"):
    buyer = BuyerEvidence.model_validate({"records": records})
    return build_compliance(load_registry(), gpu, load_catalog(), buyer, NOW)


def status(decision, cid, gate):
    return next(g.status for v in decision.verdicts if v.config_id == cid
                for g in v.gates if g.gate == gate)


def test_catalog_covers_current_deployments_and_gpu_options():
    catalog = load_catalog()
    registry = load_registry()
    assert set(catalog.configurations) == {
        cfg.config_id for cfg in registry if cfg.hosting_kind != "rental"
    }
    assert set(catalog.gpu_options) == set(GPU_OPTIONS)


def test_india_and_zero_require_distinct_evidence():
    scenario = Scenario(compliance_gates=("G12", "G13", "G15"), retention_days=0)
    snapshot, d = decide(scenario)
    assert d.recommended is None
    assert status(d, GLOBAL, "G12") == "fail"
    assert status(d, "gem25f-api-global", "G13") == "fail"
    assert status(d, SARVAM, "G12") == "pass"
    assert status(d, SARVAM, "G13") == status(d, SARVAM, "G15") == "unverified"
    assert f"{SARVAM}.deploy.retention_days" not in snapshot.values
    assert f"{SELFHOST}.deploy.retention_days" not in snapshot.values


def test_loaded_buyer_review_supplies_each_fact_and_decisions_are_reproducible(tmp_path):
    path = tmp_path / "buyer.json"
    path.write_text(BuyerEvidence.model_validate({"records": [review(SARVAM)]}).model_dump_json())
    buyer = load_buyer_evidence(path)
    verified = build_compliance(load_registry(), "azure-ci-a100", load_catalog(), buyer, NOW)
    s = Scenario(compliance_gates=("G12", "G13", "G15", "G16", "G17", "G18", "G19"),
                 retention_days=0)
    snapshot, d = decide(s, compliance=verified)
    assert all(status(d, SARVAM, gate) == "pass" for gate in s.compliance_gates)
    assert decide_what_if(snapshot, s, ("G9", "G10")).recommended == SARVAM
    assert snapshot.values[f"{SARVAM}.deploy.retention_days"].provenance == "buyer-verified"
    assert decide(s, compliance=verified)[1].decision_hash == d.decision_hash
    assert decide(s)[1].decision_hash != d.decision_hash


@pytest.mark.parametrize("changes", [
    {"expires_on": "2026-11-23"}, {"version": "different-version"},
    {"reviewed_on": "2026-11-25"},
])
def test_invalid_scope_or_validity_leaves_buyer_facts_unknown(changes):
    checked = evidence(review(SARVAM, **changes))
    assert f"{SARVAM}.deploy.retention_days" not in checked.values
    assert f"{SARVAM}.deploy.contract_verified" not in checked.values
    assert SARVAM in checked.buyer_status


def test_buyer_record_cannot_relabel_globally_routed_endpoint_as_india():
    checked = evidence(review(GLOBAL, facts={"processing_region": "India"}))
    assert checked.values[f"{GLOBAL}.deploy.region"].value == "Global"
    assert f"{GLOBAL}.deploy.configuration_verified" not in checked.values


def test_gpu_switch_changes_evidence_and_invalidates_buyer_record():
    record = review(SELFHOST, gpu_option="azure-ci-a100",
                    facts={"processing_region": "India", "retention_days": 0})
    s = Scenario(compliance_gates=("G12", "G13"), retention_days=0)
    assert status(decide(s)[1], SELFHOST, "G12") == "unverified"
    _, azure = decide(s, compliance=evidence(record))
    _, e2e = decide(Scenario(gpu="e2e-a100", compliance_gates=s.compliance_gates, retention_days=0),
                    compliance=evidence(record, gpu="e2e-a100"))
    assert status(azure, SELFHOST, "G12") == status(azure, SELFHOST, "G13") == "pass"
    assert status(e2e, SELFHOST, "G12") == status(e2e, SELFHOST, "G13") == "unverified"


def test_known_training_or_logging_conflicts_fail():
    _, d = decide(Scenario(compliance_gates=("G16", "G17")))
    assert status(d, "gemma4-26b-api-global", "G16") == "fail"
    assert status(d, "gem25f-api-global", "G17") == "fail"


def test_malformed_buyer_file_is_rejected(tmp_path):
    path = tmp_path / "buyer.json"
    path.write_text('{"records": [{"facts": {"retention_days": false}}]}')
    with pytest.raises(ValidationError):
        load_buyer_evidence(path)


def test_streamlit_preset_preserves_other_controls_and_reset_clears_it(monkeypatch, tmp_path):
    invalid = tmp_path / "malformed.json"
    invalid.write_text("invalid")
    monkeypatch.setenv("POME_COMPLIANCE_EVIDENCE_FILE", str(invalid))
    app = AppTest.from_file(Path("pome/app/home.py").resolve(), default_timeout=15).run()
    assert not app.exception
    assert any("Using public evidence only" in warning.value for warning in app.warning)
    assert decide(Scenario())[1].recommended == GLOBAL
    app.sidebar.checkbox(key="compliance_G16").check().run()
    preset = next(b for b in app.sidebar.button if b.label == "Require India + zero provider retention")
    preset.click().run()
    assert not app.exception
    for gate in ("G12", "G13", "G16"):
        assert app.sidebar.checkbox(key=f"compliance_{gate}").value
    assert app.sidebar.number_input(key="compliance_retention").value == 0
    assert any("No configuration qualifies" in el.proto.body for el in app.get("html"))
    reset = next(b for b in app.sidebar.button if b.label == "Reset compliance filters")
    reset.click().run()
    assert not app.exception
    assert not app.sidebar.checkbox(key="compliance_G12").value
    assert not app.sidebar.checkbox(key="compliance_G16").value
    assert app.sidebar.number_input(key="compliance_retention").value == 30


def test_owned_controls_pass_compliance_without_changing_rented_deployments():
    from pome.registry.hosting import OWNED, owned_config

    registry = load_registry() + [owned_config(preset) for preset in OWNED.values()]
    gates = ("G12", "G13", "G15", "G16", "G17", "G18", "G19")
    compliance = build_compliance(registry, "azure-ci-a100", load_catalog(), None, NOW,
                                  assume_owned_controls=True)
    scenario = Scenario(compliance_gates=gates, retention_days=0)
    snapshot, decision = decide(scenario, registry=registry, compliance=compliance,
                                deployment_plans={})
    for preset in OWNED.values():
        assert all(status(decision, preset.id, gate) == "pass" for gate in (*gates, "G14"))
        assert snapshot.values[f"{preset.id}.deploy.contract_verified"].provenance == "operator-assumed"
        assert preset.id not in {item.config_id for item in decision.shortlist}
    assert status(decision, SELFHOST, "G12") == "unverified"
    assert status(decision, GLOBAL, "G12") == "fail"
