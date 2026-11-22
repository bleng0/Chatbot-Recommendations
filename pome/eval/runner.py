"""Quality runner (PLAN F3): one task, one config, one run index.

Per item: build the fixed prompt -> cache hit? replay at $0 : ledger.ensure_room() ->
key pool -> Gemini -> ledger.record() -> cache.put(). Records come back in ITEM order
(asyncio.gather keeps order), so runs line up item by item for the bootstrap.
Non-2xx results after the pool's retries are errors: not billed, not cached.
offline=True: no API calls; returns records only for items already in the cache.
"""
import asyncio
from collections.abc import Sequence
from dataclasses import dataclass

from pome.eval.cache import ResponseCache
from pome.eval.tasks import intent_prompt, parse_label, prompt_sha256
from pome.providers.gemini import build_request, parse_response
from pome.providers.keypool import KeyPool, Transport
from pome.providers.spend import SpendLedger, estimate_run_cost

ERROR = "__error__"


@dataclass(frozen=True)
class Item:
    id: str
    text: str
    label: str


@dataclass(frozen=True)
class Record:
    task: str
    config_id: str
    run_idx: int
    item_id: str
    gold: str
    pred: str
    prompt_sha256: str
    temperature: float
    in_tokens: int
    out_tokens: int
    thought_tokens: int
    key_index: int
    retries: int
    status: int
    finish_reason: str
    cached: bool


async def run_task(*, task: str, items: Sequence[Item], labels: Sequence[str], allow_oos: bool,
                   config_id: str, model_id: str, temperature: float, run_idx: int,
                   in_price_per_1m: float, out_price_per_1m: float, pool: KeyPool,
                   transport: Transport, ledger: SpendLedger, cache: ResponseCache,
                   concurrency: int, tier: str = "paid", offline: bool = False
                   ) -> list[Record]:
    sem = asyncio.Semaphore(concurrency)

    def rec(item: Item, h: str, v: dict, *, cached: bool) -> Record:
        pred = (parse_label(v["text"], labels, allow_oos=allow_oos) if v["status"] < 300
                else ERROR)
        return Record(task, config_id, run_idx, item.id, item.label, pred, h, temperature,
                      v["in_tokens"], v["out_tokens"], v["thought_tokens"], v["key_index"],
                      v["retries"], v["status"], v["finish_reason"], cached)

    async def one(item: Item) -> Record | None:
        prompt = intent_prompt(item.text, labels, allow_oos=allow_oos)
        h = prompt_sha256(prompt)
        hit = cache.get(config_id, h, run_idx)
        if hit is not None:
            return rec(item, h, hit, cached=True)
        if offline:
            return None
        async with sem:
            ledger.ensure_room()
            res = await pool.request(transport, build_request(model_id, prompt,
                                                              temperature=temperature))
        if not res.ok:
            return rec(item, h, {"text": "", "in_tokens": 0, "out_tokens": 0,
                                 "thought_tokens": 0, "key_index": res.key_index,
                                 "retries": res.retries, "status": res.response.status,
                                 "finish_reason": ""}, cached=False)
        g = parse_response(res.response.body or {})
        ledger.record(config_id=config_id, run_id=f"{task}/run{run_idx}",
                      key_index=res.key_index, in_tokens=g.in_tokens, out_tokens=g.out_tokens,
                      in_price_per_1m=in_price_per_1m, out_price_per_1m=out_price_per_1m,
                      tier=tier)
        value = {"text": g.text, "in_tokens": g.in_tokens, "out_tokens": g.out_tokens,
                 "thought_tokens": g.thought_tokens, "key_index": res.key_index,
                 "retries": res.retries, "status": res.response.status,
                 "finish_reason": g.finish_reason, "model_version": g.model_version}
        cache.put(config_id, h, run_idx, value)
        return rec(item, h, value, cached=False)

    return [r for r in await asyncio.gather(*(one(i) for i in items)) if r is not None]


def estimate_from_records(records: Sequence[Record], *, calls: int, in_price_per_1m: float,
                          out_price_per_1m: float) -> float:
    """Scale the measured mean tokens of successful calls to a planned number of calls."""
    ok = [r for r in records if r.status < 300]
    if not ok:
        raise ValueError("no successful calls to estimate from")
    mean_in = sum(r.in_tokens for r in ok) / len(ok)
    mean_out = sum(r.out_tokens for r in ok) / len(ok)
    return estimate_run_cost(calls, mean_in, mean_out, in_price_per_1m, out_price_per_1m)
