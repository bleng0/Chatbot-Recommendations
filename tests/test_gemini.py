import asyncio

import httpx

from pome.providers.gemini import build_request, make_transport, parse_response

BODY = {
    "candidates": [{"content": {"parts": [{"text": '{"label": "card_arrival"}'}]},
                    "finishReason": "STOP"}],
    "usageMetadata": {"promptTokenCount": 900, "candidatesTokenCount": 8,
                      "thoughtsTokenCount": 40, "totalTokenCount": 948},
    "modelVersion": "gemini-2.5-flash-lite-001",
}


def test_build_request_targets_generate_content_and_records_temperature():
    req = build_request("gemini-2.5-flash-lite", "hello", temperature=1.0)
    assert req["url"] == ("https://generativelanguage.googleapis.com/v1beta/models/"
                          "gemini-2.5-flash-lite:generateContent")
    assert req["body"]["contents"] == [{"role": "user", "parts": [{"text": "hello"}]}]
    assert req["body"]["generationConfig"] == {"temperature": 1.0}


def test_parse_response_bills_thinking_tokens_as_output():
    r = parse_response(BODY)
    assert r.text == '{"label": "card_arrival"}'
    assert (r.in_tokens, r.out_tokens, r.thought_tokens) == (900, 48, 40)
    assert r.finish_reason == "STOP" and r.model_version == "gemini-2.5-flash-lite-001"


def test_parse_response_without_candidates_still_counts_input():
    r = parse_response({"promptFeedback": {"blockReason": "SAFETY"},
                        "usageMetadata": {"promptTokenCount": 50}})
    assert (r.text, r.in_tokens, r.out_tokens) == ("", 50, 0)
    assert r.finish_reason == "BLOCKED:SAFETY"


def test_transport_sends_key_in_header_not_url():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["key"] = str(request.url), request.headers["x-goog-api-key"]
        return httpx.Response(429, json={"error": {}}, headers={"Retry-After": "7"})

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await make_transport(client)("sk-test-XYZ",
                                                build_request("m", "p", temperature=0.0))

    resp = asyncio.run(go())
    assert resp.status == 429 and resp.headers["retry-after"] == "7"
    assert seen["key"] == "sk-test-XYZ" and "sk-test-XYZ" not in seen["url"]


def test_transport_maps_network_errors_to_503():
    def handler(request):
        raise httpx.ConnectError("boom")

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await make_transport(client)("k", build_request("m", "p", temperature=0.0))

    assert asyncio.run(go()).status == 503
