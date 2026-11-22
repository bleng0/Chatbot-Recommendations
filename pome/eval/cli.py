"""Run quality evals: python -m pome.eval.cli --configs ID[,ID] [--tasks ...] [--head N]
                                             [--runs R] [--approve-spend]

Without --approve-spend it prints a worst-case estimate and exits (rc 2) without calling
the API. With it, the ledger refuses the run if spent + worst case > cap. After running it
prints measured mean tokens and the cost of the full plan (all items x 1 run).
Worst case = ceil(prompt chars / 4) input tokens + 1000 output tokens per call.
Keys come from .env via the key pool; only key indices are ever printed.
--tier free: Google charges nothing, so the ledger records $0 (tokens and list price kept)
and configs without a paid price (Gemma) are allowed.
"""
import argparse
import asyncio
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from pathlib import Path

import httpx

from pome.eval.cache import ResponseCache
from pome.eval.datasets import FAQ_TASKS, TASKS, load_task
from pome.eval.runner import Record, estimate_from_records, run_task
from pome.providers.gemini import make_transport
from pome.providers.keypool import KeyPool, Transport, load_keys, read_dotenv
from pome.providers.spend import SpendLedger, call_cost

ROOT = Path(__file__).resolve().parent.parent.parent
WORST_OUT_TOKENS = 1000
FULL_RUNS = 1  # CONSTRAINTS A: one run per config (owner decision 2026-11-22)


def worst_case_cost(prompts: Sequence[str], in_price: float, out_price: float) -> float:
    return sum(call_cost(math.ceil(len(p) / 4), WORST_OUT_TOKENS, in_price, out_price)
               for p in prompts)


def main(argv: Sequence[str] | None = None, *, env: Mapping[str, str] | None = None,
         transport: Transport | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", required=True)
    ap.add_argument("--tasks", default=",".join(TASKS + FAQ_TASKS))
    ap.add_argument("--head", type=int)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--concurrency", type=int, default=7)
    ap.add_argument("--out", type=Path, default=ROOT / "runs")
    ap.add_argument("--approve-spend", action="store_true")
    ap.add_argument("--tier", choices=("paid", "free"), default="paid")
    ap.add_argument("--cached-only", action="store_true",
                    help="no API calls: write records for items already in the cache")
    a = ap.parse_args(argv)

    from pome.registry.loader import load_registry
    registry = {c.config_id: c for c in load_registry()}
    configs = [registry[c] for c in a.configs.split(",")]
    def price(ev) -> float:
        return 0.0 if ev is None else ev.value

    for c in configs:
        if a.tier == "paid" and (c.pricing.input_per_1m is None or c.pricing.output_per_1m is None):
            print(f"{c.config_id}: no paid price in the registry; refusing (spend unverifiable)")
            return 2
    tasks = [load_task(t, a.head) for t in a.tasks.split(",")]
    prompts = [t.build_prompt(i) for t in tasks for i in t.items] * a.runs
    ledger = SpendLedger(a.out / "spend_ledger.jsonl")
    worst = {c.config_id: 0.0 if a.tier == "free" else
             worst_case_cost(prompts, price(c.pricing.input_per_1m), price(c.pricing.output_per_1m))
             for c in configs}
    print(f"{len(prompts)} calls per config; worst-case ${sum(worst.values()):.4f} "
          f"({', '.join(f'{k} ${v:.4f}' for k, v in worst.items())}); "
          f"ledger spent ${ledger.spent():.4f} of ${ledger.cap:.2f}")
    if a.tier == "free":
        print("free tier: $0 charged; ledger keeps tokens and list prices")
    if not a.approve_spend and not a.cached_only:
        print("dry estimate only: re-run with --approve-spend to call the API")
        return 2
    if not a.cached_only:
        ledger.approve(sum(worst.values()))

    keys = load_keys(env if env is not None else read_dotenv(ROOT / ".env"))
    # Free-tier limits reset every minute: cap cooldowns at 60 s so the pool never stalls.
    pool = KeyPool(keys, base_cooldown=15.0, max_cooldown=60.0)
    print(f"key pool: {pool!r}")
    cache = ResponseCache(a.out / "cache.jsonl")
    full_calls = sum(len(load_task(t).items) for t in TASKS + FAQ_TASKS) * FULL_RUNS

    async def go(send: Transport) -> None:
        for c in configs:
            pin, pout = price(c.pricing.input_per_1m), price(c.pricing.output_per_1m)
            recs: list[Record] = []
            for t in tasks:
                for run_idx in range(a.runs):
                    rs = await run_task(
                        task=t.name, items=t.items, labels=t.labels, allow_oos=t.allow_oos,
                        config_id=c.config_id, model_id=c.model_id,
                        temperature=a.temperature, run_idx=run_idx, in_price_per_1m=pin,
                        out_price_per_1m=pout, pool=pool, transport=send, ledger=ledger,
                        cache=cache, concurrency=a.concurrency, tier=a.tier,
                        offline=a.cached_only, build_prompt=t.build_prompt,
                        label_key=t.label_key)
                    path = a.out / "records" / c.config_id / f"{t.name}_run{run_idx}.jsonl"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("".join(json.dumps(asdict(r), ensure_ascii=False) + "\n"
                                            for r in rs), encoding="utf-8")
                    recs += rs
            ok = [r for r in recs if r.status < 300]
            errors = len(recs) - len(ok)
            if ok:
                mi = sum(r.in_tokens for r in ok) / len(ok)
                mo = sum(r.out_tokens for r in ok) / len(ok)
                mt = sum(r.thought_tokens for r in ok) / len(ok)
                full = estimate_from_records(recs, calls=full_calls, in_price_per_1m=pin,
                                             out_price_per_1m=pout)
                print(f"{c.config_id}: {len(ok)} ok, {errors} errors; measured mean tokens "
                      f"in {mi:.0f} / out {mo:.0f} (thinking {mt:.0f}); full plan "
                      f"{full_calls} calls = ${full:.2f} at list ${pin}/{pout} per 1M")
            else:
                print(f"{c.config_id}: 0 ok, {errors} errors")

    if transport is not None:
        asyncio.run(go(transport))
    else:
        async def live() -> None:
            async with httpx.AsyncClient() as client:
                await go(make_transport(client))
        asyncio.run(live())
    print(f"ledger spent ${ledger.spent():.4f} of ${ledger.cap:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
