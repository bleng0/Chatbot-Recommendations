import json
from datetime import UTC, datetime

import pytest

from pome.cost.model import api_monthly_cost
from pome.evidence.build import MIN_ITEMS, build_evidence
from pome.evidence.snapshot import build_snapshot
from pome.profiles.loader import load_profile
from pome.registry.loader import load_registry
from pome.selection.engine import select

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
FL, GEMMA, VLLM = "gem25f-api-global", "gemma4-26b-api-global", "gemma4-26b-vllm-in-bf16"


def write(root, cid, task, rows):
    d = root / cid
    d.mkdir(parents=True, exist_ok=True)
    with (d / f"{task}_run0.jsonl").open("w") as f:
        for i, (gold, pred, status) in enumerate(rows):
            f.write(json.dumps({"task": task, "config_id": cid, "run_idx": 0, "item_id": f"i{i}",
                                "gold": gold, "pred": pred, "in_tokens": 600, "out_tokens": 200,
                                "thought_tokens": 150, "status": status}) + "\n")


def rows_perfect(n, labels=("a", "b")):
    return [(labels[i % 2], labels[i % 2], 200) for i in range(n)]


@pytest.fixture
def reg():
    return load_registry()


def test_measured_quality_value_from_records(tmp_path, reg):
    rows = rows_perfect(MIN_ITEMS)
    rows[0] = ("a", "b", 200)  # one wrong
    write(tmp_path, FL, "banking77", rows)
    v = build_evidence(reg, tmp_path, load_profile(), NOW)[f"{FL}.intent.banking77.macro_f1"]
    assert v.provenance == "measured" and v.unit == "ratio" and 0 < v.value < 1
    assert "banking77_run0.jsonl" in v.source and f"n={MIN_ITEMS}" in v.source


def test_too_few_items_leaves_the_metric_unverified(tmp_path, reg):
    write(tmp_path, FL, "banking77", rows_perfect(MIN_ITEMS - 1))
    ev = build_evidence(reg, tmp_path, load_profile(), NOW)
    assert f"{FL}.intent.banking77.macro_f1" not in ev


def test_failed_calls_are_not_scored(tmp_path, reg):
    rows = rows_perfect(MIN_ITEMS) + [("a", "error", 429)] * 5
    write(tmp_path, FL, "banking77", rows)
    v = build_evidence(reg, tmp_path, load_profile(), NOW)[f"{FL}.intent.banking77.macro_f1"]
    assert v.value == 1.0 and f"n={MIN_ITEMS}" in v.source


def test_oos_recall_and_precision(tmp_path, reg):
    rows = [("out_of_scope", "out_of_scope", 200)] * 15 + [("a", "a", 200)] * 15
    write(tmp_path, FL, "clinc150", rows)
    ev = build_evidence(reg, tmp_path, load_profile(), NOW)
    assert ev[f"{FL}.oos.clinc150.recall"].value == 1.0
    assert ev[f"{FL}.oos.clinc150.precision"].value == 1.0


def test_api_cost_is_modeled_from_measured_tokens_and_listed_price(tmp_path, reg):
    write(tmp_path, FL, "banking77", rows_perfect(MIN_ITEMS))
    p = load_profile()
    v = build_evidence(reg, tmp_path, p, NOW)[f"{FL}.cost.monthly_usd"]
    cfg = next(c for c in reg if c.config_id == FL)
    want = api_monthly_cost(
        tickets=p.volume_tickets_per_month, in_tokens_per_ticket=600, out_tokens_per_ticket=200,
        in_price_per_1m=cfg.pricing.input_per_1m.value,
        out_price_per_1m=cfg.pricing.output_per_1m.value).total
    assert v.value == want and v.provenance == "modeled" and v.formula
    assert v.unit == "usd_per_month"


def test_no_cost_without_a_price_or_without_measured_tokens(tmp_path, reg):
    write(tmp_path, GEMMA, "banking77", rows_perfect(MIN_ITEMS))  # Gemma has no price
    ev = build_evidence(reg, tmp_path, load_profile(), NOW)
    assert f"{GEMMA}.cost.monthly_usd" not in ev
    assert f"{FL}.cost.monthly_usd" not in ev  # priced but nothing measured


def test_deployment_values_keep_registry_provenance(tmp_path, reg):
    ev = build_evidence(reg, tmp_path, load_profile(), NOW)
    assert ev[f"{FL}.deploy.retention_days"].provenance == "vendor-doc"
    assert ev[f"{VLLM}.deploy.retention_days"].provenance == "modeled"
    assert f"{FL}.deploy.region" not in ev and f"{FL}.deploy.commercial_use" not in ev


def test_selfhost_quality_is_carried_over_as_modeled(tmp_path, reg):
    write(tmp_path, GEMMA, "banking77", rows_perfect(MIN_ITEMS))
    ev = build_evidence(reg, tmp_path, load_profile(), NOW)
    own = ev[f"{GEMMA}.intent.banking77.macro_f1"]
    carried = ev[f"{VLLM}.intent.banking77.macro_f1"]
    assert own.provenance == "measured" and carried.provenance == "modeled"
    assert carried.value == own.value and GEMMA in carried.source
    assert f"{VLLM}.cost.monthly_usd" not in ev  # needs GPU price and throughput
    assert carried.formula and GEMMA in carried.formula
    build_snapshot(ev, NOW)  # every modeled value must validate (formula required)


def test_empty_records_dir_gives_only_registry_evidence(tmp_path, reg):
    ev = build_evidence(reg, tmp_path, load_profile(), NOW)
    assert all(".deploy." in k for k in ev)


def test_thin_evidence_never_yields_an_eligible_config_and_is_deterministic(tmp_path, reg):
    write(tmp_path, FL, "banking77", rows_perfect(MIN_ITEMS))
    p = load_profile()
    snap = build_snapshot(build_evidence(reg, tmp_path, p, NOW), NOW)
    d1, d2 = select(snap, p), select(snap, p)
    assert d1.decision_hash == d2.decision_hash
    assert all(v.status != "eligible" for v in d1.verdicts)
