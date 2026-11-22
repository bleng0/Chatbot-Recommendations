import json

import pytest

from pome.eval import cli
from pome.providers.keypool import Response
from pome.providers.spend import SpendLedger


async def fake(secret, payload):
    text = json.dumps({"label": "out_of_scope"})
    return Response(200, {"candidates": [{"content": {"parts": [{"text": text}]},
                                          "finishReason": "STOP"}],
                          "usageMetadata": {"promptTokenCount": 800,
                                            "candidatesTokenCount": 6}})


def args(tmp_path, *extra):
    return ["--configs", "gem35fl-api-global", "--tasks", "banking77,clinc150", "--head", "4",
            "--out", str(tmp_path), *extra]


def test_worst_case_estimate_uses_prompt_length_and_max_output():
    # 2 calls, ~ (400 chars / 4) in, 1000 out, at 0.10 / 0.40
    assert cli.worst_case_cost(["x" * 400] * 2, 0.10, 0.40) == pytest.approx(
        2 * (100 * 0.10 + 1000 * 0.40) / 1e6)


def test_refuses_to_spend_without_flag(tmp_path, capsys):
    rc = cli.main(args(tmp_path), env={"LLM_API_KEY": "sk-test-AAAA"}, transport=fake)
    out = capsys.readouterr().out
    assert rc == 2 and "worst-case" in out and "--approve-spend" in out
    assert not (tmp_path / "spend_ledger.jsonl").exists()


def test_runs_records_spend_and_reports_measured_estimate(tmp_path, capsys):
    rc = cli.main(args(tmp_path, "--approve-spend"), env={"LLM_API_KEY": "sk-test-AAAA"},
                  transport=fake)
    out = capsys.readouterr().out
    assert rc == 0
    assert "sk-test-AAAA" not in out
    assert SpendLedger(tmp_path / "spend_ledger.jsonl").spent() == pytest.approx(
        8 * (800 * 0.30 + 6 * 2.50) / 1e6)  # gem35fl list price 0.30 / 2.50
    rows = (tmp_path / "records" / "gem35fl-api-global" / "banking77_run0.jsonl").read_text()
    assert len(rows.splitlines()) == 4
    assert "measured mean tokens" in out and "full plan" in out


def test_refuses_unpriced_configs(tmp_path, capsys):
    rc = cli.main(["--configs", "gemma4-26b-api-global", "--tasks", "banking77", "--head", "2",
                   "--out", str(tmp_path), "--approve-spend"],
                  env={"LLM_API_KEY": "k"}, transport=fake)
    assert rc == 2 and "no paid price" in capsys.readouterr().out


def test_free_tier_allows_unpriced_configs_and_charges_nothing(tmp_path, capsys):
    rc = cli.main(["--configs", "gemma4-26b-api-global,gem25f-api-global", "--tasks",
                   "banking77", "--head", "2", "--out", str(tmp_path), "--tier", "free",
                   "--approve-spend"], env={"LLM_API_KEY": "k"}, transport=fake)
    assert rc == 0
    rows = [json.loads(x) for x in (tmp_path / "spend_ledger.jsonl").read_text().splitlines()]
    assert len(rows) == 4 and {r["tier"] for r in rows} == {"free"}
    assert sum(r["cost_usd"] for r in rows) == 0.0
    assert "free tier: $0 charged" in capsys.readouterr().out
