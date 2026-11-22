import asyncio
import json

import httpx

from pome.eval import cli
from pome.providers.gemini import build_request, parse_response
from pome.providers.keypool import Response
from pome.providers.ollama import chat_body, make_ollama_transport, to_gemini_body


def test_chat_body_carries_prompt_temperature_and_disables_streaming_and_thinking():
    p = build_request("ignored", "hello", temperature=0.7)
    assert chat_body(p, "gemma4:26b") == {
        "model": "gemma4:26b", "messages": [{"role": "user", "content": "hello"}],
        "stream": False, "think": False, "options": {"temperature": 0.7}}


def test_ollama_reply_reads_like_a_gemini_reply():
    g = parse_response(to_gemini_body({"message": {"content": '{"label": "a"}'},
                                       "done_reason": "stop", "prompt_eval_count": 600,
                                       "eval_count": 9}))
    assert (g.text, g.in_tokens, g.out_tokens, g.thought_tokens) == ('{"label": "a"}', 600, 9, 0)
    assert g.finish_reason == "stop"


def run(handler):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            send = make_ollama_transport(c, model="gemma4:26b")
            return await send("unused", build_request("x", "hi", temperature=1.0))
    return asyncio.run(go())


def test_transport_posts_to_local_chat_endpoint():
    seen = {}

    def handler(req):
        seen["url"], seen["body"] = str(req.url), json.loads(req.content)
        return httpx.Response(200, json={"message": {"content": "ok"}, "done_reason": "stop",
                                         "prompt_eval_count": 3, "eval_count": 1})
    r = run(handler)
    assert seen["url"] == "http://localhost:11434/api/chat"
    assert seen["body"]["model"] == "gemma4:26b" and "x-goog-api-key" not in seen
    assert r.status == 200 and parse_response(r.body).text == "ok"


def test_server_error_status_is_passed_through_and_network_failure_is_503():
    assert run(lambda req: httpx.Response(500, json={"error": "boom"})).status == 500

    def down(req):
        raise httpx.ConnectError("refused")
    assert run(down).status == 503


async def fake_ollama(secret, payload):
    return Response(200, to_gemini_body({"message": {"content": '{"label": "out_of_scope"}'},
                                         "done_reason": "stop", "prompt_eval_count": 500,
                                         "eval_count": 7}))


def test_cli_ollama_needs_no_keys_and_no_spend_approval_and_records_zero_cost(tmp_path, capsys):
    rc = cli.main(["--configs", "gemma4-12b-ollama-local-q4", "--provider", "ollama",
                   "--tasks", "banking77", "--head", "3", "--out", str(tmp_path)],
                  env={}, transport=fake_ollama)
    assert rc == 0
    rows = (tmp_path / "records" / "gemma4-12b-ollama-local-q4" / "banking77_run0.jsonl"
            ).read_text().splitlines()
    assert len(rows) == 3
    spent = [json.loads(x)["cost_usd"] for x in
             (tmp_path / "spend_ledger.jsonl").read_text().splitlines()]
    assert spent == [0.0, 0.0, 0.0]


def test_cli_refuses_ollama_for_a_hosted_config(tmp_path, capsys):
    rc = cli.main(["--configs", "gem25f-api-global", "--provider", "ollama", "--tasks",
                   "banking77", "--head", "1", "--out", str(tmp_path)], env={},
                  transport=fake_ollama)
    assert rc == 2 and "ollama" in capsys.readouterr().out.lower()
