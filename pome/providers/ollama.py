"""Local Ollama transport, shaped like the Gemini transport so the runner is unchanged.

Fields from https://docs.ollama.com/api/chat (retrieved 2026-11-22): request model, messages,
stream, think, options.temperature; non-streaming reply message.content, done_reason,
prompt_eval_count, eval_count. Default base URL http://localhost:11434.
Thinking is turned off (think=false) to keep a laptop run short; output tokens = eval_count.
No API key is used; the pool's secret argument is ignored.
"""
from typing import Any

import httpx

from pome.providers.keypool import Response, Transport

BASE_URL = "http://localhost:11434"


def chat_body(payload: dict[str, Any], model: str) -> dict[str, Any]:
    body = payload["body"]
    return {
        "model": model,
        "messages": [{"role": "user", "content": body["contents"][0]["parts"][0]["text"]}],
        "stream": False,
        "think": False,
        "options": {"temperature": body["generationConfig"]["temperature"]},
    }


def to_gemini_body(reply: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidates": [{"content": {"parts": [{"text": (reply.get("message") or {})
                                                .get("content", "")}]},
                        "finishReason": str(reply.get("done_reason", ""))}],
        "usageMetadata": {"promptTokenCount": int(reply.get("prompt_eval_count") or 0),
                          "candidatesTokenCount": int(reply.get("eval_count") or 0)},
    }


def make_ollama_transport(client: httpx.AsyncClient, *, model: str, base_url: str = BASE_URL,
                          timeout: float = 600.0) -> Transport:
    async def send(secret: str, payload: dict[str, Any]) -> Response:
        try:
            r = await client.post(f"{base_url}/api/chat", json=chat_body(payload, model),
                                  timeout=timeout)
        except httpx.HTTPError:
            return Response(503)
        try:
            reply = r.json()
        except ValueError:
            return Response(r.status_code)
        return Response(r.status_code, to_gemini_body(reply) if r.status_code < 300 else reply)
    return send
