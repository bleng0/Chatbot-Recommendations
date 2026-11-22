import json
import re
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parent.parent / "pome" / "data" / "faq_pilot.jsonl"
LANGS = ("en", "hi", "hinglish")
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
HOSTS = ("sbi.co.in", "sbi.bank.in", "hdfc.bank.in", "hdfcbank.com", "rbi.org.in",
         "icici.bank.in", "icicibank.com")


@pytest.fixture(scope="module")
def rows():
    return [json.loads(x) for x in PATH.read_text(encoding="utf-8").splitlines() if x.strip()]


def test_30_questions_24_answerable_6_unanswerable(rows):
    assert len(rows) == 30 and len({r["id"] for r in rows}) == 30
    assert sum(r["answerable"] for r in rows) == 24
    assert sum(not r["answerable"] for r in rows) == 6


def test_answerable_items_have_unique_faq_ids_answer_and_dated_source(rows):
    ans = [r for r in rows if r["answerable"]]
    assert sorted(r["faq_id"] for r in ans) == [f"F{i:02d}" for i in range(1, 25)]
    for r in ans:
        assert 20 <= len(r["answer"]) <= 400
        assert r["source_url"].startswith("https://") and any(h in r["source_url"] for h in HOSTS)
        assert r["retrieved_at"] == "2026-11-22" and "paraphrased" in r["licence"]


def test_unanswerable_items_carry_no_faq_id_answer_or_source(rows):
    for r in (r for r in rows if not r["answerable"]):
        assert r["faq_id"] is None and r["answer"] is None and r["source_url"] is None


def test_every_question_exists_in_all_three_languages(rows):
    for r in rows:
        assert set(r["q"]) == set(LANGS)
        assert all(r["q"][lang].strip().endswith("?") for lang in LANGS)


def test_hindi_is_devanagari_and_hinglish_is_latin_script(rows):
    for r in rows:
        assert DEVANAGARI.search(r["q"]["hi"])
        assert not DEVANAGARI.search(r["q"]["hinglish"]) and not DEVANAGARI.search(r["q"]["en"])
        assert r["q"]["hinglish"] != r["q"]["en"]


def test_questions_are_distinct(rows):
    for lang in LANGS:
        qs = [r["q"][lang] for r in rows]
        assert len(set(qs)) == 30
