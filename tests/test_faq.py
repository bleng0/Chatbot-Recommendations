import asyncio
import json

import pytest

from pome.eval.cache import ResponseCache
from pome.eval.datasets import FAQ_TASKS, load_task
from pome.eval.faq import faq_scores
from pome.eval.runner import run_task
from pome.eval.tasks import INVALID, NONE, faq_prompt, parse_label
from pome.providers.keypool import KeyPool, Response
from pome.providers.spend import SpendLedger

KB = [("F01", "Block it right away at a branch."), ("F02", "Never share your PIN.")]


def test_faq_prompt_lists_every_approved_answer_and_the_none_option():
    p = faq_prompt("मेरा कार्ड खो गया?", KB)
    assert "F01: Block it right away at a branch." in p and "F02: Never share your PIN." in p
    assert 'faq_id' in p and NONE in p and "मेरा कार्ड खो गया?" in p
    assert p == faq_prompt("मेरा कार्ड खो गया?", KB)


def test_parse_label_can_read_the_faq_id_key():
    labels = ["F01", "F02", NONE]
    assert parse_label('{"faq_id": "F02"}', labels, allow_oos=False, key="faq_id") == "F02"
    assert parse_label('{"faq_id": "none"}', labels, allow_oos=False, key="faq_id") == NONE
    assert parse_label('{"faq_id": "F99"}', labels, allow_oos=False, key="faq_id") == INVALID
    assert parse_label('{"label": "F02"}', labels, allow_oos=False, key="faq_id") == INVALID


def test_faq_scores_split_answerable_correctness_from_decline_rate():
    gold = ["F01", "F02", "F03", NONE, NONE]
    pred = ["F01", "F03", "F03", NONE, "F01"]
    assert faq_scores(gold, pred) == (pytest.approx(2 / 3), pytest.approx(0.5))


def test_faq_scores_need_both_kinds_of_item():
    with pytest.raises(ValueError):
        faq_scores(["F01"], ["F01"])
    with pytest.raises(ValueError):
        faq_scores([NONE], [NONE])


def test_faq_tasks_share_ids_and_labels_across_languages():
    en, hi, hg = (load_task(n) for n in FAQ_TASKS)
    assert FAQ_TASKS == ("faq_en", "faq_hi", "faq_hinglish")
    assert [i.id for i in en.items] == [i.id for i in hi.items] == [i.id for i in hg.items]
    assert [i.label for i in en.items] == [i.label for i in hi.items]
    assert len(en.items) == 30 and [i.label for i in en.items].count(NONE) == 6
    assert en.labels == [f"F{i:02d}" for i in range(1, 25)] + [NONE]
    assert en.label_key == "faq_id" and not en.allow_oos


def test_faq_prompt_for_an_item_carries_the_whole_knowledge_base_and_the_question():
    t = load_task("faq_hi")
    prompt = t.build_prompt(t.items[0])
    assert t.items[0].text in prompt and "F24:" in prompt and "F01:" in prompt


def test_faq_head_keeps_unanswerable_items():
    t = load_task("faq_en", head=10)
    assert len(t.items) == 10 and [i.label for i in t.items].count(NONE) == 2


def test_runner_uses_a_custom_prompt_builder_and_label_key(tmp_path):
    t = load_task("faq_en", head=5)
    gold = {i.text: i.label for i in t.items}

    async def transport(secret, payload):
        text = payload["body"]["contents"][0]["parts"][0]["text"]
        label = next(g for q, g in gold.items() if q in text)
        body = {"candidates": [{"content": {"parts": [{"text": json.dumps({"faq_id": label})}]},
                                "finishReason": "STOP"}],
                "usageMetadata": {"promptTokenCount": 900, "candidatesTokenCount": 5}}
        return Response(200, body)

    async def go():
        return await run_task(
            task=t.name, items=t.items, labels=t.labels, allow_oos=False, config_id="cfg",
            model_id="m", temperature=1.0, run_idx=0, in_price_per_1m=0.1, out_price_per_1m=0.4,
            pool=KeyPool({1: "k"}), transport=transport,
            ledger=SpendLedger(tmp_path / "s.jsonl"), cache=ResponseCache(tmp_path / "c.jsonl"),
            concurrency=2, build_prompt=t.build_prompt, label_key=t.label_key)

    recs = asyncio.run(go())
    assert [r.pred for r in recs] == [r.gold for r in recs] and len(recs) == 5
