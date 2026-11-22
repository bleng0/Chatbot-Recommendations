"""select(): gates -> min monthly cost -> tie-break. Five PLAN edge cases plus rules."""
import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pome.evidence.schema import EvidenceValue
from pome.evidence.snapshot import SnapshotHashMismatch, build_snapshot
from pome.profiles.loader import Gate, load_profile
from pome.selection.engine import InvalidProfile, required_keys, select

NOW = datetime(2026, 11, 22, 8, 0, tzinfo=UTC)
LENIENT = load_profile()  # banking_mvp as shipped: no G12/G13 (owner decision 2026-11-22)
# Strict profile = banking_mvp plus the optional deployment gates, for the full-gate rules below.
PROFILE = LENIENT.model_copy(update={"gates": {
    **LENIENT.gates,
    "G12": Gate(op="required", value=True, unit="bool"),
    "G13": Gate(op="<=", value=30, unit="days"),
}})


def ev(value, prov="measured", unit="ratio"):
    kw = {"value": value, "unit": unit, "provenance": prov, "retrieved_at": NOW}
    if prov == "measured":
        kw |= {"source": "eval/run", "run_ids": ["r1"]}
    elif prov == "vendor-doc":
        kw |= {"source": "https://example.com/doc"}
    else:
        kw |= {"source": "model", "formula": "f(x)"}
    return EvidenceValue(**kw)


def passing(cid, cost=1000.0, p95=1200.0, q=0.90, deploy_prov="vendor-doc"):
    """A config that passes every gate with quality score q everywhere."""
    v = {
        "intent.banking77.macro_f1": ev(q),
        "oos.clinc150.recall": ev(q),
        "oos.clinc150.precision": ev(q),
        "intent.massive.macro_f1.en": ev(q),
        "intent.massive.macro_f1.hi": ev(q),
        "serving.p95_ms": ev(p95, unit="ms"),
        "serving.sustainable_rps": ev(12.0, unit="req_per_s"),
        "serving.error_pct": ev(0.2, unit="percent"),
        "cost.monthly_usd": ev(cost, "modeled", unit="usd_per_month"),
        "deploy.region": ev("India", deploy_prov, unit="region"),
        "deploy.retention_days": ev(0 if deploy_prov == "modeled" else 7, deploy_prov, unit="days"),
        "deploy.commercial_use": ev(True, "vendor-doc", unit="bool"),
    }
    for lang in ("en", "hi", "hinglish"):
        v[f"faq.correct.{lang}"] = ev(q)
        v[f"faq.declined.{lang}"] = ev(q)
    return {f"{cid}.{k}": e for k, e in v.items()}


def snap(*parts, drop=(), override=None):
    values = {}
    for p in parts:
        values |= p
    for k in drop:
        values.pop(k)
    values |= override or {}
    return build_snapshot(values, created_at=NOW)


def verdict(decision, cid):
    return next(v for v in decision.verdicts if v.config_id == cid)


# ---- 1. budget ------------------------------------------------------------------------

def test_cost_exactly_at_budget_passes_and_one_cent_over_fails():
    d = select(snap(passing("a", cost=1500.0), passing("b", cost=1500.01)), PROFILE)
    assert verdict(d, "a").status == "eligible"
    vb = verdict(d, "b")
    assert vb.status == "rejected"
    assert [g.gate for g in vb.gates if g.status == "fail"] == ["G11"]


def test_cheapest_feasible_is_recommended_not_cheapest_overall():
    cheap_but_slow = passing("cheap", cost=100.0, p95=3500.0)
    d = select(snap(cheap_but_slow, passing("mid", cost=900.0), passing("dear", cost=1400.0)), PROFILE)
    assert (d.outcome, d.recommended) == ("recommended", "mid")
    assert [s.config_id for s in d.shortlist] == ["mid", "dear"]


# ---- 2. ties ----------------------------------------------------------------------------

def test_cost_tie_goes_to_larger_quality_margin():
    d = select(snap(passing("a", q=0.86), passing("b", q=0.95)), PROFILE)
    assert d.recommended == "b"


def test_cost_and_margin_tie_goes_to_lower_p95():
    d = select(snap(passing("a", p95=2000.0), passing("b", p95=900.0)), PROFILE)
    assert d.recommended == "b"


def test_quality_margin_outranks_p95_when_they_conflict():
    # same cost; "a" has the larger margin but the slower p95 -> margin decides
    d = select(snap(passing("a", q=0.95, p95=2500.0), passing("b", q=0.86, p95=500.0)), PROFILE)
    assert d.recommended == "a"


def test_full_tie_goes_to_config_id():
    d = select(snap(passing("zeta"), passing("alpha")), PROFILE)
    assert d.recommended == "alpha"


def test_quality_margin_is_the_tightest_slack_across_quality_gates():
    # all scores 0.95 except OOS recall 0.86: threshold 0.85 -> margin 0.01
    d = select(snap(passing("a", q=0.95), override={"a.oos.clinc150.recall": ev(0.86)}), PROFILE)
    assert verdict(d, "a").quality_margin == pytest.approx(0.01)


# ---- 3. no feasible option --------------------------------------------------------------

def test_no_feasible_option_is_a_valid_outcome():
    bad = passing("a")
    bad["a.deploy.retention_days"] = ev(55, "vendor-doc", unit="days")
    d = select(snap(bad), PROFILE)
    assert (d.outcome, d.recommended, d.shortlist) == ("no_feasible_option", None, [])
    reason = verdict(d, "a").reasons[0]
    assert "G13" in reason and "55" in reason


# ---- 4. unverified ----------------------------------------------------------------------

def test_missing_evidence_is_unverified_never_pass():
    d = select(snap(passing("a"), drop=["a.deploy.region"]), PROFILE)
    v = verdict(d, "a")
    assert v.status == "unverified"
    assert v.missing == ["a.deploy.region"]
    assert d.outcome == "no_feasible_option"


def test_a_fail_outranks_unverified():
    d = select(snap(passing("a", p95=5000.0), drop=["a.deploy.region"]), PROFILE)
    v = verdict(d, "a")
    assert v.status == "rejected"
    assert v.missing == ["a.deploy.region"]


def test_region_must_match_the_profile_region():
    d = select(snap(passing("a"), override={"a.deploy.region": ev("global", "vendor-doc", unit="region")}), PROFILE)
    assert [g.gate for g in verdict(d, "a").gates if g.status == "fail"] == ["G12"]


# ---- 5. determinism ---------------------------------------------------------------------

def test_same_snapshot_and_profile_give_the_same_decision_hash_twice():
    s = snap(passing("a"), passing("b", cost=800.0))
    d1, d2 = select(s, PROFILE), select(s, PROFILE)
    assert d1 == d2
    assert len(d1.decision_hash) == 64 and d1.decision_hash == d2.decision_hash


def test_decision_hash_changes_when_evidence_changes():
    a = select(snap(passing("a")), PROFILE)
    b = select(snap(passing("a", cost=1001.0)), PROFILE)
    assert a.decision_hash != b.decision_hash


def test_decision_records_snapshot_and_profile_hashes():
    s = snap(passing("a"))
    d = select(s, PROFILE)
    assert d.snapshot_sha256 == s.sha256 and len(d.profile_sha256) == 64


# ---- quality and language gates ---------------------------------------------------------

@pytest.mark.parametrize("lang", ["en", "hi", "hinglish"])
def test_faq_correctness_is_checked_per_language(lang):
    d = select(snap(passing("a"), override={f"a.faq.correct.{lang}": ev(0.79)}), PROFILE)
    assert "G4" in {g.gate for g in verdict(d, "a").gates if g.status == "fail"}


def test_hindi_gap_over_ten_points_fails_g6():
    d = select(snap(passing("a", q=0.95), override={"a.intent.massive.macro_f1.hi": ev(0.84)}), PROFILE)
    assert [g.gate for g in verdict(d, "a").gates if g.status == "fail"] == ["G6"]


def test_gap_of_exactly_ten_points_passes():
    d = select(snap(passing("a", q=0.95), override={"a.faq.correct.hinglish": ev(0.85)}), PROFILE)
    assert verdict(d, "a").status == "eligible"


def test_non_english_scoring_higher_is_not_a_gap():
    d = select(snap(passing("a", q=0.85), override={"a.faq.declined.hi": ev(0.99)}), PROFILE)
    assert verdict(d, "a").status == "eligible"


# ---- modeled evidence -------------------------------------------------------------------

def test_modeled_deployment_evidence_is_eligible_but_flagged():
    d = select(snap(passing("self", deploy_prov="modeled")), PROFILE)
    v = verdict(d, "self")
    assert v.status == "eligible_modeled"
    assert d.recommended == "self" and d.recommended_is_modeled


def test_cost_projection_alone_does_not_flag_a_config_as_modeled():
    d = select(snap(passing("api")), PROFILE)
    assert verdict(d, "api").status == "eligible" and not d.recommended_is_modeled


# ---- contract -----------------------------------------------------------------------------

def test_required_keys_cover_all_fourteen_gates():
    keys = required_keys("c")
    assert len(keys) == 18 and all(k.startswith("c.") for k in keys)


def test_verdicts_are_sorted_by_config_id():
    d = select(snap(passing("b"), passing("a"), passing("c")), PROFILE)
    assert [v.config_id for v in d.verdicts] == ["a", "b", "c"]


FORBIDDEN = {"os", "io", "pathlib", "random", "time", "datetime", "socket", "subprocess",
             "httpx", "requests", "uuid", "secrets", "asyncio", "threading", "yaml"}


def test_selection_package_is_pure():
    for path in Path("pome/selection").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [(node.module or "").split(".")[0]]
            elif isinstance(node, ast.Call) and getattr(node.func, "id", "") in ("open", "print", "input"):
                names = [node.func.id]
            else:
                continue
            assert not set(names) & (FORBIDDEN | {"open", "print", "input"}), (path, names)


# ---- adversarial review findings (doubt-driven, 2026-11-22) ------------------------------

@pytest.mark.parametrize("key,bad", [
    ("cost.monthly_usd", -5.0),
    ("cost.monthly_usd", float("-inf")),
    ("serving.p95_ms", -1.0),
    ("deploy.retention_days", -3),
    ("intent.banking77.macro_f1", 1.5),
    ("intent.banking77.macro_f1", float("nan")),
    ("serving.error_pct", 101.0),
])
def test_out_of_range_or_non_finite_evidence_is_invalid_not_pass(key, bad):
    unit = {"cost.monthly_usd": "usd_per_month", "serving.p95_ms": "ms",
            "deploy.retention_days": "days", "serving.error_pct": "percent"}.get(key, "ratio")
    d = select(snap(passing("a"), passing("b", cost=1400.0),
                    override={f"a.{key}": ev(bad, unit=unit)}), PROFILE)
    va = verdict(d, "a")
    assert va.status == "unverified" and any("invalid" in r for r in va.reasons)
    assert d.recommended == "b"


@pytest.mark.parametrize("key,bad,unit", [
    ("intent.banking77.macro_f1", True, "ratio"),
    ("deploy.retention_days", False, "days"),
    ("intent.banking77.macro_f1", "0.95", "ratio"),
    ("serving.p95_ms", "n/a", "ms"),
    ("deploy.commercial_use", 1, "bool"),
    ("deploy.region", 7, "region"),
])
def test_wrong_value_type_is_invalid_and_does_not_crash(key, bad, unit):
    d = select(snap(passing("a"), passing("b", cost=1400.0),
                    override={f"a.{key}": ev(bad, unit=unit)}), PROFILE)
    assert verdict(d, "a").status == "unverified"
    assert d.recommended == "b"


def test_huge_int_does_not_crash_select():
    d = select(snap(passing("a"), override={"a.serving.p95_ms": ev(10**400, unit="ms")}), PROFILE)
    assert verdict(d, "a").status == "unverified"


def test_wrong_unit_is_invalid():
    d = select(snap(passing("a"), override={"a.serving.p95_ms": ev(2.5, unit="s")}), PROFILE)
    v = verdict(d, "a")
    assert v.status == "unverified" and any("unit" in r for r in v.reasons)


@pytest.mark.parametrize("en,other", [(0.81, 0.71), (0.90, 0.80), (0.93, 0.83)])
def test_exact_ten_point_gap_passes_despite_float_rounding(en, other):
    d = select(snap(passing("a", q=en), override={"a.intent.massive.macro_f1.hi": ev(other)}), PROFILE)
    assert "G6" not in {g.gate for g in verdict(d, "a").gates if g.status == "fail"}


def test_profile_missing_a_gate_is_rejected_clearly():
    gates = dict(PROFILE.gates)
    del gates["G14"]
    with pytest.raises(InvalidProfile, match="G14"):
        select(snap(passing("a")), PROFILE.model_copy(update={"gates": gates}))


def test_profile_with_wrong_op_is_rejected_clearly():
    gates = dict(PROFILE.gates)
    gates["G1"] = gates["G14"]  # op 'required' on a threshold gate
    with pytest.raises(InvalidProfile, match="G1"):
        select(snap(passing("a")), PROFILE.model_copy(update={"gates": gates}))


def test_tampered_snapshot_values_are_detected():
    s = snap(passing("a"))
    s.values["a.cost.monthly_usd"] = ev(1.0, "modeled", unit="usd_per_month")
    with pytest.raises(SnapshotHashMismatch):
        select(s, PROFILE)


def test_empty_snapshot_is_an_error_not_a_decision():
    with pytest.raises(ValueError, match="empty"):
        select(build_snapshot({}, created_at=NOW), PROFILE)


def test_profile_region_whitespace_is_ignored():
    p = PROFILE.model_copy(update={"region": " India "})
    assert verdict(select(snap(passing("a")), p), "a").status == "eligible"


def test_profile_with_unknown_gate_is_rejected_clearly():
    gates = dict(PROFILE.gates) | {"G99": PROFILE.gates["G1"]}
    with pytest.raises(InvalidProfile, match="G99"):
        select(snap(passing("a")), PROFILE.model_copy(update={"gates": gates}))


def test_equal_margins_with_float_noise_still_fall_through_to_p95():
    # a: G1 0.90 -> slack 0.90-0.80 = 0.0999...; b: all 1.0, tightest slack is a gap 0.10
    a = passing("a", q=1.0, p95=500.0) | {"a.intent.banking77.macro_f1": ev(0.90)}
    b = passing("b", q=1.0, p95=2000.0)
    d = select(snap(a, b), PROFILE)
    assert verdict(d, "a").quality_margin == verdict(d, "b").quality_margin
    assert d.recommended == "a"


# ---- 6. proof-of-concept leniency (owner decision 2026-11-22) -------------------------

def test_shipped_profile_has_no_region_or_retention_gate():
    assert "G12" not in LENIENT.gates and "G13" not in LENIENT.gates


def test_without_g12_g13_global_region_and_55_day_retention_do_not_block():
    a = passing("a")
    a["a.deploy.region"] = ev("global", "vendor-doc", unit="region")
    a["a.deploy.retention_days"] = ev(55, "vendor-doc", unit="days")
    d = select(snap(a), LENIENT)
    assert d.recommended == "a" and verdict(d, "a").status == "eligible"
    assert {g.gate for g in verdict(d, "a").gates} == set(LENIENT.gates)


def test_profile_without_a_core_gate_is_still_rejected():
    gates = {k: v for k, v in LENIENT.gates.items() if k != "G1"}
    with pytest.raises(InvalidProfile, match="G1"):
        select(snap(passing("a")), LENIENT.model_copy(update={"gates": gates}))


SERVING = ["a.serving.p95_ms", "a.serving.sustainable_rps", "a.serving.error_pct"]


def test_missing_serving_evidence_is_not_tested_and_does_not_block():
    d = select(snap(passing("a"), drop=SERVING), LENIENT)
    v = verdict(d, "a")
    assert v.status == "eligible" and d.recommended == "a"
    assert {g.gate: g.status for g in v.gates}["G8"] == "not_tested"
    assert v.not_tested == ["G8", "G9", "G10"]
    assert v.missing == SERVING and v.p95_ms is None


def test_not_tested_config_ranks_after_equal_cost_config_with_serving_evidence():
    d = select(snap(passing("a"), passing("b"), drop=SERVING), LENIENT)
    assert d.recommended == "b"


def test_invalid_serving_evidence_is_still_unverified():
    d = select(snap(passing("a"), override={"a.serving.p95_ms": ev(-1.0, unit="ms")}), LENIENT)
    assert verdict(d, "a").status == "unverified"


def test_failing_serving_evidence_still_rejects():
    d = select(snap(passing("a", p95=5000.0)), LENIENT)
    assert verdict(d, "a").status == "rejected"
