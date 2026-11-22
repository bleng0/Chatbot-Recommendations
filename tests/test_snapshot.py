import hashlib
import json
import re
from datetime import UTC, datetime

import pytest

from pome.evidence.schema import EvidenceValue
from pome.evidence.snapshot import (
    SnapshotHashMismatch,
    build_snapshot,
    load_snapshot,
    save_snapshot,
)

NOW = datetime(2026, 11, 22, 8, 0, tzinfo=UTC)


def price(v=0.1, prov="vendor-doc"):
    return EvidenceValue(
        value=v, unit="usd_per_1m_tokens", provenance=prov,
        source="https://example.com/p", retrieved_at=NOW,
    )


def test_hash_is_64_lowercase_hex():
    snap = build_snapshot({"a.b": price()}, created_at=NOW)
    assert re.fullmatch(r"[0-9a-f]{64}", snap.sha256)


def test_golden_hash_matches_independent_canonical_form():
    snap = build_snapshot({"a.b": price()}, created_at=NOW)
    expected = (
        '{"created_at":"2026-11-22T08:00:00Z","schema_version":"1","values":{"a.b":'
        '{"formula":null,"key_index":null,"provenance":"vendor-doc",'
        '"retrieved_at":"2026-11-22T08:00:00Z","run_ids":[],'
        '"source":"https://example.com/p","unit":"usd_per_1m_tokens","value":0.1}}}'
    )
    assert snap.sha256 == hashlib.sha256(expected.encode()).hexdigest()


def test_same_input_gives_same_hash_twice():
    a = build_snapshot({"x": price(), "y": price(0.2)}, created_at=NOW)
    b = build_snapshot({"x": price(), "y": price(0.2)}, created_at=NOW)
    assert a.sha256 == b.sha256


def test_insertion_order_does_not_change_hash():
    a = build_snapshot({"x": price(), "y": price(0.2)}, created_at=NOW)
    b = build_snapshot({"y": price(0.2), "x": price()}, created_at=NOW)
    assert a.sha256 == b.sha256


def test_changed_value_changes_hash():
    a = build_snapshot({"x": price(0.1)}, created_at=NOW)
    b = build_snapshot({"x": price(0.2)}, created_at=NOW)
    assert a.sha256 != b.sha256


def test_changed_provenance_changes_hash():
    modeled = EvidenceValue(
        value=0.1, unit="usd_per_1m_tokens", provenance="modeled",
        source="https://example.com/p", retrieved_at=NOW, formula="f",
    )
    a = build_snapshot({"x": price()}, created_at=NOW)
    b = build_snapshot({"x": modeled}, created_at=NOW)
    assert a.sha256 != b.sha256


def test_save_then_load_round_trips_with_same_hash(tmp_path):
    snap = build_snapshot({"x": price(), "y": price(0.2)}, created_at=NOW)
    path = tmp_path / "snap.json"
    save_snapshot(snap, path)
    loaded = load_snapshot(path)
    assert loaded.sha256 == snap.sha256
    assert loaded.values == snap.values


def test_tampered_file_is_rejected(tmp_path):
    snap = build_snapshot({"x": price(0.1)}, created_at=NOW)
    path = tmp_path / "snap.json"
    save_snapshot(snap, path)
    data = json.loads(path.read_text())
    data["values"]["x"]["value"] = 0.2
    path.write_text(json.dumps(data))
    with pytest.raises(SnapshotHashMismatch):
        load_snapshot(path)
