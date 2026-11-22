"""Slice 5: seeded stratified sampler, pinned loaders, manifest. All offline (synthetic parquet)."""
import hashlib
import json
from collections import Counter

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from pome.data.loaders import (
    PINS,
    SIZES,
    build_samples,
    read_parquet_rows,
    verify_manifest,
)
from pome.data.sampler import stratified_sample

# ---------------------------------------------------------------- sampler

def _rows(per_label, labels):
    return [{"id": f"{l}-{i}", "label": l} for l in labels for i in range(per_label)]


def test_sampler_is_deterministic_for_same_seed():
    rows = _rows(20, "abcdefg")
    assert stratified_sample(rows, "label", 30, seed=7) == stratified_sample(rows, "label", 30, seed=7)


def test_sampler_changes_with_seed():
    rows = _rows(20, "abcdefg")
    assert stratified_sample(rows, "label", 30, seed=1) != stratified_sample(rows, "label", 30, seed=2)


def test_sampler_seed_changes_choice_within_strata_even_with_no_remainder():
    rows = _rows(20, "abcdefg")
    assert stratified_sample(rows, "label", 28, seed=1) != stratified_sample(rows, "label", 28, seed=2)


def test_sampler_independent_of_input_order():
    rows = _rows(20, "abcdefg")
    assert stratified_sample(rows, "label", 30, seed=3) == stratified_sample(rows[::-1], "label", 30, seed=3)


def test_sampler_balanced_to_within_one_per_label_and_exact_size():
    out = stratified_sample(_rows(20, "abcdefg"), "label", 30, seed=0)  # 30 = 7*4 + 2
    counts = Counter(r["label"] for r in out)
    assert len(out) == 30 and set(counts) == set("abcdefg")
    assert max(counts.values()) - min(counts.values()) <= 1


def test_sampler_no_duplicates():
    out = stratified_sample(_rows(20, "abcdefg"), "label", 100, seed=0)
    assert len({r["id"] for r in out}) == len(out) == 100


def test_sampler_small_stratum_redistributes_the_shortfall():
    rows = _rows(1, "a") + _rows(50, "bc")
    out = stratified_sample(rows, "label", 30, seed=0)
    counts = Counter(r["label"] for r in out)
    assert len(out) == 30 and counts["a"] == 1


def test_sampler_rejects_impossible_sizes():
    rows = _rows(2, "ab")
    with pytest.raises(ValueError):
        stratified_sample(rows, "label", 5, seed=0)
    with pytest.raises(ValueError):
        stratified_sample(rows, "label", 0, seed=0)
    with pytest.raises(ValueError):
        stratified_sample(rows, "label", True, seed=0)


def test_sampler_does_not_use_global_random_state():
    import random
    rows = _rows(20, "abcdefg")
    random.seed(1)
    a = stratified_sample(rows, "label", 30, seed=5)
    random.seed(999)
    assert a == stratified_sample(rows, "label", 30, seed=5)


# ---------------------------------------------------------------- loaders / manifest

def _write(path, table_cols, names):
    t = pa.table(table_cols)
    meta = {"info": {"features": {k: {"names": v} for k, v in names.items()}}}
    t = t.replace_schema_metadata({"huggingface": json.dumps(meta)})
    pq.write_table(t, path)


@pytest.fixture
def sources(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    b_names = [f"intent_{i}" for i in range(5)]
    _write(src / "b77.parquet",
           {"text": [f"b{i}" for i in range(100)], "label": [i % 5 for i in range(100)]},
           {"label": b_names})
    c_names = [f"c_{i}" for i in range(4)] + ["oos"]
    ci = [i % 4 for i in range(80)] + [4] * 30
    _write(src / "clinc.parquet", {"text": [f"c{i}" for i in range(110)], "intent": ci},
           {"intent": c_names})
    m_names = [f"m_{i}" for i in range(3)]
    ids = [str(i) for i in range(60)]
    for loc, f in (("en-US", "en"), ("hi-IN", "hi")):
        _write(src / f"{f}.parquet",
               {"id": ids if f == "en" else ids[::-1],  # different order on purpose
                "locale": [loc] * 60,
                "utt": [f"{f}{i}" for i in (range(60) if f == "en" else range(59, -1, -1))],
                "intent": [int(i) % 3 for i in (ids if f == "en" else ids[::-1])]},
               {"intent": m_names})
    files = {"b77": "b77.parquet", "clinc": "clinc.parquet", "en": "en.parquet", "hi": "hi.parquet"}

    def fetch(key):
        return src / files[key]
    return fetch


SMALL = {"banking77": 20, "clinc_in": 8, "clinc_oos": 6, "massive": 12}


def test_read_parquet_rows_returns_rows_and_label_names(sources):
    rows, names = read_parquet_rows(sources("b77"))
    assert len(rows) == 100 and names["label"][0] == "intent_0"


def test_build_samples_writes_expected_sizes_and_labels(sources, tmp_path):
    out = tmp_path / "out"
    build_samples(sources, out, seed=11, sizes=SMALL, retrieved_at="2026-11-22T00:00:00Z")
    b = [json.loads(l) for l in (out / "banking77.jsonl").read_text().splitlines()]
    assert len(b) == 20 and {r["label"] for r in b} <= {f"intent_{i}" for i in range(5)}
    c = [json.loads(l) for l in (out / "clinc150.jsonl").read_text().splitlines()]
    assert Counter(r["is_oos"] for r in c) == {False: 8, True: 6}
    assert all(r["label"] == "oos" for r in c if r["is_oos"])
    assert all(r["label"] != "oos" for r in c if not r["is_oos"])


def test_massive_en_and_hi_share_the_same_ids_with_matching_labels(sources, tmp_path):
    out = tmp_path / "out"
    build_samples(sources, out, seed=11, sizes=SMALL, retrieved_at="2026-11-22T00:00:00Z")
    m = [json.loads(l) for l in (out / "massive.jsonl").read_text().splitlines()]
    en = {r["id"]: r for r in m if r["locale"] == "en-US"}
    hi = {r["id"]: r for r in m if r["locale"] == "hi-IN"}
    assert len(en) == len(hi) == 12 and en.keys() == hi.keys()
    assert all(en[i]["label"] == hi[i]["label"] for i in en)
    assert all(hi[i]["text"] == f"hi{i}" and en[i]["text"] == f"en{i}" for i in en)


def test_build_is_byte_identical_across_runs(sources, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for d in (a, b):
        build_samples(sources, d, seed=5, sizes=SMALL, retrieved_at="2026-11-22T00:00:00Z")
    for name in ("banking77.jsonl", "clinc150.jsonl", "massive.jsonl", "manifest.json"):
        assert (a / name).read_bytes() == (b / name).read_bytes()


def test_manifest_records_pins_seed_and_sample_hashes(sources, tmp_path):
    out = tmp_path / "out"
    build_samples(sources, out, seed=5, sizes=SMALL, retrieved_at="2026-11-22T00:00:00Z")
    man = json.loads((out / "manifest.json").read_text())
    assert man["seed"] == 5 and man["retrieved_at"] == "2026-11-22T00:00:00Z"
    assert man["datasets"]["banking77"]["revision"] == PINS["banking77"]["revision"]
    f = man["samples"]["banking77.jsonl"]
    assert f["sha256"] == hashlib.sha256((out / "banking77.jsonl").read_bytes()).hexdigest()
    assert f["rows"] == 20
    verify_manifest(out)


def test_verify_manifest_detects_tampering(sources, tmp_path):
    out = tmp_path / "out"
    build_samples(sources, out, seed=5, sizes=SMALL, retrieved_at="2026-11-22T00:00:00Z")
    p = out / "banking77.jsonl"
    p.write_text(p.read_text().replace("b", "x", 1))
    with pytest.raises(ValueError, match="banking77.jsonl"):
        verify_manifest(out)


def test_pins_are_full_commit_hashes_with_licence():
    for name, pin in PINS.items():
        assert len(pin["revision"]) == 40 and set(pin["revision"]) <= set("0123456789abcdef"), name
        assert pin["licence"] and pin["repo"], name


def test_default_sizes_match_plan():
    assert SIZES == {"banking77": 300, "clinc_in": 150, "clinc_oos": 100, "massive": 150}


def test_build_rejects_oversized_requests(sources, tmp_path):
    with pytest.raises(ValueError):
        build_samples(sources, tmp_path / "o", seed=1, sizes={**SMALL, "clinc_oos": 999},
                      retrieved_at="2026-11-22T00:00:00Z")


def test_sampler_can_take_every_row():
    rows = _rows(3, "ab")
    assert len(stratified_sample(rows, "label", 6, seed=0)) == 6


def test_fetch_pinned_downloads_once_from_the_pinned_url(tmp_path, monkeypatch):
    import io

    import pome.data.loaders as L
    urls = []

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(url, timeout):
        urls.append(url)
        return Resp(b"parquet-bytes")

    monkeypatch.setattr(L.urllib.request, "urlopen", fake_urlopen)
    fetch = L.fetch_pinned(tmp_path / "cache")
    p1, p2 = fetch("hi"), fetch("hi")
    assert p1 == p2 and p1.read_bytes() == b"parquet-bytes" and len(urls) == 1
    rev = PINS["massive"]["revision"]
    assert urls[0] == f"https://huggingface.co/datasets/AmazonScience/massive/resolve/{rev}/hi-IN/test/0000.parquet"


def test_build_rejects_en_hi_label_disagreement(sources, tmp_path):
    src = tmp_path / "bad"
    src.mkdir()
    ids = [str(i) for i in range(60)]
    for f in ("en", "hi"):
        _write(src / f"{f}.parquet",
               {"id": ids, "locale": ["x"] * 60, "utt": [f"{f}{i}" for i in ids],
                "intent": [i % 3 if f == "en" else (i + 1) % 3 for i in range(60)]},
               {"intent": ["a", "b", "c"]})

    def fetch(key):
        return src / f"{key}.parquet" if key in ("en", "hi") else sources(key)
    with pytest.raises(ValueError, match="labels disagree"):
        build_samples(fetch, tmp_path / "o", seed=1, sizes=SMALL, retrieved_at="2026-11-22T00:00:00Z")
