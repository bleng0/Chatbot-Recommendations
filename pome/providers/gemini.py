"""Gemini API REST transport for the key pool. Sources (retrieved 2026-11-22):
- endpoint, usageMetadata fields: https://ai.google.dev/api/generate-content
- x-goog-api-key header: https://ai.google.dev/gemini-api/docs/structured-output (REST example)
- thinking tokens billed as output: https://ai.google.dev/gemini-api/docs/thinking

Not sent (REST field names not confirmed in the docs): JSON-mode schema and thinking
controls. JSON is requested in the prompt instead; thinking stays at the model default and
its tokens are counted from thoughtsTokenCount.
The key goes only in the x-goog-api-key header, never in the URL or a log line.
"""
from dataclasses import dataclass
from typing import Any

import httpx

from pome.providers.keypool import Response, Transport

_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def build_request(model_id: str, prompt: str, *, temperature: float) -> dict[str, Any]:
    return {
        "url": _URL.format(model=model_id),
        "body": {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature},
        },
    }


@dataclass(frozen=True)
class GeminiResult:
    text: str
    in_tokens: int
    out_tokens: int  # billed output = candidates + thoughts
    thought_tokens: int
    finish_reason: str
    model_version: str


def parse_response(body: dict[str, Any]) -> GeminiResult:
    usage = body.get("usageMetadata") or {}
    thoughts = int(usage.get("thoughtsTokenCount") or 0)
    candidates = body.get("candidates") or []
    if candidates:
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        finish = str(candidates[0].get("finishReason", ""))
    else:
        text = ""
        finish = "BLOCKED:" + str((body.get("promptFeedback") or {}).get("blockReason", "UNKNOWN"))
    return GeminiResult(
        text=text,
        in_tokens=int(usage.get("promptTokenCount") or 0),
        out_tokens=int(usage.get("candidatesTokenCount") or 0) + thoughts,
        thought_tokens=thoughts,
        finish_reason=finish,
        model_version=str(body.get("modelVersion", "")),
    )


def make_transport(client: httpx.AsyncClient, *, timeout: float = 60.0) -> Transport:
    async def send(secret: str, payload: dict[str, Any]) -> Response:
        try:
            r = await client.post(payload["url"], json=payload["body"], timeout=timeout,
                                  headers={"x-goog-api-key": secret})
        except httpx.HTTPError:
            return Response(503)  # network failure: the pool cools the key and retries
        try:
            body = r.json()
        except ValueError:
            body = None
        return Response(r.status_code, body, dict(r.headers))
    return send
