from pome.app.scenario import Scenario, decide
from pome.app.views import BADGE, cost_curves, evidence_rows, gate_matrix


def test_gate_matrix_has_one_row_per_config_and_text_symbols(tmp_path):
    _, d = decide(Scenario(), tmp_path)
    rows = gate_matrix(d)
    assert len(rows) == len(d.verdicts)
    cells = {v for r in rows for k, v in r.items() if k.startswith("G")}
    assert cells <= {"✓ pass", "✗ fail", "? unverified", "– not tested"}


def test_every_evidence_row_carries_a_provenance_badge(tmp_path):
    snap, _ = decide(Scenario(), tmp_path)
    rows = evidence_rows(snap)
    assert rows and all(r["provenance"] in BADGE.values() for r in rows)
    assert all(r["source"] for r in rows)


def test_cost_curves_api_is_linear_selfhost_flat(tmp_path):
    d = tmp_path / "gem25f-api-global"
    d.mkdir()
    (d / "banking77_run0.jsonl").write_text(
        '{"gold":"a","pred":"a","in_tokens":600,"out_tokens":200,"status":200}\n' * 20)
    snap, _ = decide(Scenario(volume=100_000), tmp_path)
    curves = cost_curves(snap, volume=100_000, points=[50_000, 100_000, 200_000])
    api, selfhost = curves["gem25f-api-global"], curves["gemma4-12b-vllm-in-bf16"]
    assert api[2] == 2 * api[1] and api[0] * 2 == api[1]
    assert len(set(selfhost)) == 1
