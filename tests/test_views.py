from pathlib import Path

from streamlit.testing.v1 import AppTest

from pome.app.scenario import Scenario, decide
from pome.app.views import (
    BADGE,
    answer_line,
    cost_curves,
    evidence_rows,
    gate_matrix,
    split_configs,
    variant_rows,
)
from pome.profiles.loader import load_profile
from pome.registry.loader import load_registry
from pome.selection.engine import select
from tests.test_selection import LENIENT, ev, passing, snap

STATUSES = {"pass", "fail", "unverified", "not_tested"}


def test_gate_matrix_has_one_row_per_config_and_status_keys(tmp_path):
    _, d = decide(Scenario(), tmp_path)
    rows = gate_matrix(d)
    assert len(rows) == len(d.verdicts)
    assert {c for r in rows for c in r["gates"].values()} <= STATUSES


def test_gate_matrix_sorts_eligible_then_failing_then_unverified():
    # design pass 2026-11-23: the reviewer's question is "which one qualifies", so it leads
    s = snap(passing("ok"), passing("bad", q=0.5), passing("gap"),
             drop=["gap.oos.clinc150.recall"])
    rows = gate_matrix(select(s, LENIENT))
    assert [r["config"] for r in rows] == ["ok", "bad", "gap"]


def test_answer_line_flags_a_recommendation_built_on_modeled_evidence():
    snap_, d = decide(Scenario())
    assert d.recommended_is_modeled
    assert answer_line(d, snap_, load_profile()).startswith(
        f"Recommended from published vendor data: {d.recommended} at ₹")


def test_answer_line_for_a_recommendation_states_config_and_modeled_cost():
    s = snap(passing("a", cost=1234.6))
    assert answer_line(select(s, LENIENT), s, LENIENT) == (
        "Recommended: a at ₹1,14,567/month (cost MODELED)")


def test_answer_line_omits_the_value_when_failing_configs_differ():
    s = snap(passing("a"), passing("b"), override={
        "a.intent.banking77.macro_f1": ev(0.70), "b.intent.banking77.macro_f1": ev(0.60)})
    assert answer_line(select(s, LENIENT), s, LENIENT) == (
        "No configuration qualifies yet: 2 fail G1")


def test_split_puts_pome_measured_configs_apart_from_published_ones():
    measured, published = split_configs(load_registry())
    assert len(measured) == 5 and len(published) == 15
    assert "gemma4-12b-vllm-in-bf16" in measured  # carries POME-measured quality
    assert not set(measured) & set(published)


def test_variant_rows_carry_settings_figure_badge_and_match():
    cfg = next(c for c in load_registry() if c.config_id == "llama31-8b-vllm-in-bf16")
    rows = variant_rows(cfg)
    assert len(rows) == len(cfg.variants)
    first = rows[0]
    assert first["match"] == "MATCH" and first["results"][0]["badge"] == "PUBLISHED"
    assert ("Token lengths", "778 in / 73 out") in first["conditions"]
    assert first["hardware"] == "8 × B300-SXM-270GB"
    assert first["results"][0]["figure"] == "173,950 tok/s (system)"


def test_variant_without_a_figure_says_so():
    cfg = next(c for c in load_registry() if c.config_id == "gemma4-31b-vllm-in-bf16")
    row = next(r for r in variant_rows(cfg) if r["variant"] == "vllm-bf16-2gpu")
    assert row["hardware"] == "2 × A100/H100" and row["results"] == []


def test_deployment_tab_keeps_scenario_cost_separate_from_published_setups():
    home = Path(__file__).resolve().parents[1] / "pome/app/home.py"
    app = AppTest.from_file(home, default_timeout=15).run()
    tab = next(tab for tab in app.tabs if tab.label == "Deployment variants")
    assert not app.exception
    app.selectbox(key="deployment_model").select("gemma4-31b-vllm-in-bf16").run()
    tab = next(tab for tab in app.tabs if tab.label == "Deployment variants")
    assert not app.exception
    evidence = tab.get("html")[0].proto.body
    assert any("₹3,48,328" in entry.value for entry in tab.markdown)
    assert "₹3,48,328" not in evidence
    assert "Published variants" in tab.caption[-1].value

    app.selectbox(key="deployment_model").select("llama31-8b-vllm-in-bf16").run()
    tab = next(tab for tab in app.tabs if tab.label == "Deployment variants")
    assert not app.exception
    evidence = tab.get("html")[0].proto.body
    assert "POME workload matches" in evidence and "173,950 tok/s (system)" in evidence


def test_every_evidence_row_carries_a_provenance_badge(tmp_path):
    snap_, _ = decide(Scenario(), tmp_path)
    rows = evidence_rows(snap_)
    assert rows and all(r["provenance"] in BADGE.values() for r in rows)
    assert all(r["source"] for r in rows)


def test_study_evidence_is_badged_published_not_vendor_doc():
    e = ev(0.9, "vendor-doc").model_copy(update={"study": True, "measured_under": {"x": 1}})
    rows = evidence_rows(build := snap(override={"c.intent.banking77.macro_f1": e}))
    assert build and rows[0]["provenance"] == "PUBLISHED"


def test_cost_curves_api_is_linear_selfhost_flat(tmp_path):
    d = tmp_path / "gem25f-api-global"
    d.mkdir()
    (d / "banking77_run0.jsonl").write_text(
        '{"gold":"a","pred":"a","in_tokens":600,"out_tokens":200,"status":200}\n' * 20)
    snap_, _ = decide(Scenario(volume=100_000), tmp_path)
    curves = cost_curves(snap_, volume=100_000, points=[50_000, 100_000, 200_000])
    api, selfhost = curves["gem25f-api-global"], curves["gemma4-12b-vllm-in-bf16"]
    assert api[2] == 2 * api[1] and api[0] * 2 == api[1]
    assert len(set(selfhost)) == 1


def test_evidence_sections_cover_current_snapshot_and_keep_unknown_metrics():
    from pome.app.views import evidence_sections

    snapshot, _ = decide(Scenario())
    ids = {c.config_id for c in load_registry()}
    sections = evidence_sections(snapshot, ids)
    rows = [r for groups in sections.values() for group in groups.values() for r in group]
    assert list(sections) == sorted(ids)
    assert len(sections) == 20
    assert len(rows) == len(snapshot.values) == 360
    assert {f"{r['config']}.{r['metric']}" for r in rows} == set(snapshot.values)
    assert {r["metric"] for r in rows if r["description"]} == {
        key.split(".", 1)[1] for key in snapshot.values
    }
    assert len({r["metric"] for r in rows}) == 18
    ratio = next(r for r in rows if "raw" in r)
    assert ratio["value"] == f"{float(ratio['raw']):.2%}"

    unknown = evidence_sections(
        snap(override={"present.future.metric": ev(0.5)}), {"present", "empty"})
    assert unknown["empty"] == {}
    assert unknown["present"]["Other evidence"][0]["metric"] == "future.metric"
