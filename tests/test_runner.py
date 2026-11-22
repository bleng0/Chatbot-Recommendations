import asyncio
import json

import pytest

from pome.eval.cache import ResponseCache
from pome.eval.runner import Item, estimate_from_records, run_task
from pome.providers.keypool import KeyPool, Response
from pome.providers.spend import SpendCapExceeded, SpendLedger

LABELS = ["lost_card", "card_arrival"]
ITEMS = [Item("i1", "lost my card", "lost_card"), Item("i2", "card not here", "card_arrival"),
         Item("i3", "weather?", "out_of_scope")]


def body(label, pin=100, pout=5):
    return {"candidates": [{"content": {"parts": [{"text": json.dumps({"label": label})}]},
                            "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": pin, "candidatesTokenCount": pout}}


class Fake:
    def __init__(self, answers, status=200):
        self.answers, self.status, self.calls = answers, status, 0

    async def __call__(self, secret, payload):
        self.calls += 1
        await asyncio.sleep(0)
        text = payload["body"]["contents"][0]["parts"][0]["text"]
        item = next(i for i in ITEMS if i.text in text)
        return Response(self.status, body(self.answers[item.id]) if self.status == 200 else {})


def run(tmp_path, transport, *, cap=1.0, run_idx=0):
    async def go():
        return await run_task(
            task="intent", items=ITEMS, labels=LABELS, allow_oos=True,
            config_id="cfg", model_id="m", temperature=1.0, run_idx=run_idx,
            in_price_per_1m=0.10, out_price_per_1m=0.40,
            pool=KeyPool({1: "k1", 2: "k2"}, sleep=lambda s: asyncio.sleep(0)),
            transport=transport, ledger=SpendLedger(tmp_path / "spend.jsonl", cap_usd=cap),
            cache=ResponseCache(tmp_path / "cache.jsonl"), concurrency=2)
    return asyncio.run(go())


ANS = {"i1": "lost_card", "i2": "lost_card", "i3": "out_of_scope"}


def test_records_predictions_in_item_order_and_bills_each_call(tmp_path):
    recs = run(tmp_path, Fake(ANS))
    assert [(r.item_id, r.gold, r.pred) for r in recs] == [
        ("i1", "lost_card", "lost_card"), ("i2", "card_arrival", "lost_card"),
        ("i3", "out_of_scope", "out_of_scope")]
    assert all(r.key_index in (1, 2) and not r.cached for r in recs)
    assert SpendLedger(tmp_path / "spend.jsonl").spent() == pytest.approx(
        3 * (100 * 0.10 + 5 * 0.40) / 1e6)


def test_rerun_is_served_from_cache_at_zero_cost(tmp_path):
    run(tmp_path, Fake(ANS))
    spent = SpendLedger(tmp_path / "spend.jsonl").spent()
    again = Fake(ANS)
    recs = run(tmp_path, again)
    assert again.calls == 0 and all(r.cached for r in recs)
    assert SpendLedger(tmp_path / "spend.jsonl").spent() == spent


def test_each_run_index_is_a_separate_call(tmp_path):
    run(tmp_path, Fake(ANS), run_idx=0)
    second = Fake(ANS)
    run(tmp_path, second, run_idx=1)
    assert second.calls == 3


def test_failed_calls_are_errors_not_billed_and_not_cached(tmp_path):
    recs = run(tmp_path, Fake(ANS, status=400))
    assert all(r.pred == "__error__" and r.status == 400 for r in recs)
    assert SpendLedger(tmp_path / "spend.jsonl").spent() == 0.0
    assert ResponseCache(tmp_path / "cache.jsonl").get("cfg", recs[0].prompt_sha256, 0) is None


def test_stops_when_cap_reached(tmp_path):
    with pytest.raises(SpendCapExceeded):
        run(tmp_path, Fake(ANS), cap=0.0)


def test_estimate_scales_measured_mean_tokens_to_planned_calls(tmp_path):
    recs = run(tmp_path, Fake(ANS))
    est = estimate_from_records(recs, calls=2820, in_price_per_1m=2.0, out_price_per_1m=10.0)
    assert est == pytest.approx(2820 * (100 * 2.0 + 5 * 10.0) / 1e6)
