"""Pinned public-benchmark loaders, seeded sampling and the manifest.

Only public benchmark data is read and written here. Sources are downloaded from the Hugging
Face hub at a pinned commit; the manifest records the revisions, the source file hashes, the
seed and the SHA256 of every sample file.
"""
from __future__ import annotations

import hashlib
import json
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from pome.data.sampler import stratified_sample

DEFAULT_SEED = 20261122
SIZES = {"banking77": 300, "clinc_in": 150, "clinc_oos": 100, "massive": 150}

# Revisions looked up on 2026-11-22 from https://huggingface.co/api/datasets/<repo>.
# MASSIVE only ships a loading script on main, so its parquet comes from the hub's
# auto-converted branch (refs/convert/parquet); main was ff6bd8e4b27c3543e4f8fe2108f32bb95a6f8740.
PINS: dict[str, dict[str, Any]] = {
    "banking77": {
        "repo": "PolyAI/banking77", "revision": "1846984189f2bc0ac51c6fc3a600fa9e1714e0c6",
        "licence": "cc-by-4.0", "files": {"b77": "data/test-00000-of-00001.parquet"},
    },
    "clinc150": {
        "repo": "clinc/clinc_oos", "revision": "155b9c710419136e17307b80d0a13e68cd46b4ec",
        "licence": "cc-by-3.0", "files": {"clinc": "plus/test-00000-of-00001.parquet"},
    },
    "massive": {
        "repo": "AmazonScience/massive", "revision": "ed58ac423a2f4121720918bf5301577edce4ffd3",
        "licence": "cc-by-4.0",
        "files": {"en": "en-US/test/0000.parquet", "hi": "hi-IN/test/0000.parquet"},
    },
}
_KEY_TO_DATASET = {k: d for d, p in PINS.items() for k in p["files"]}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch_pinned(cache_dir: Path) -> Callable[[str], Path]:
    """Return a fetch(key) that downloads a pinned source file once into cache_dir."""
    def fetch(key: str) -> Path:
        pin = PINS[_KEY_TO_DATASET[key]]
        rel = pin["files"][key]
        dest = cache_dir / f"{key}-{pin['revision'][:12]}.parquet"
        if not dest.exists():
            cache_dir.mkdir(parents=True, exist_ok=True)
            url = f"https://huggingface.co/datasets/{pin['repo']}/resolve/{pin['revision']}/{rel}"
            with urllib.request.urlopen(url, timeout=120) as resp:
                dest.write_bytes(resp.read())
        return dest
    return fetch


def read_parquet_rows(path: Path) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    """Rows plus the class-label names stored in the parquet's Hugging Face metadata."""
    table = pq.read_table(path)
    meta = (table.schema.metadata or {}).get(b"huggingface", b"{}")
    feats = json.loads(meta).get("info", {}).get("features", {})
    names = {k: v["names"] for k, v in feats.items() if "names" in v}
    return table.to_pylist(), names


def _jsonl(rows: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in rows)


def build_samples(
    fetch: Callable[[str], Path], out_dir: Path, *, seed: int = DEFAULT_SEED,
    sizes: dict[str, int] | None = None, retrieved_at: str,
) -> dict[str, Any]:
    sizes = sizes or SIZES
    out_dir.mkdir(parents=True, exist_ok=True)
    sources = {k: fetch(k) for k in _KEY_TO_DATASET}

    rows, names = read_parquet_rows(sources["b77"])
    lab = names["label"]
    b77 = [{"id": f"b77-{i}", "text": r["text"], "label": lab[r["label"]]} for i, r in enumerate(rows)]
    b77 = stratified_sample(b77, "label", sizes["banking77"], seed=seed)

    rows, names = read_parquet_rows(sources["clinc"])
    lab = names["intent"]
    clinc = [{"id": f"clinc-{i}", "text": r["text"], "label": lab[r["intent"]],
              "is_oos": lab[r["intent"]] == "oos"} for i, r in enumerate(rows)]
    clinc_in = stratified_sample([r for r in clinc if not r["is_oos"]], "label",
                                 sizes["clinc_in"], seed=seed)
    clinc_oos = stratified_sample([r for r in clinc if r["is_oos"]], "label",
                                  sizes["clinc_oos"], seed=seed)

    en_rows, en_names = read_parquet_rows(sources["en"])
    hi_rows, hi_names = read_parquet_rows(sources["hi"])
    hi_by_id = {r["id"]: r for r in hi_rows}
    lab = en_names["intent"]
    shared = [{"id": r["id"], "locale": "en-US", "text": r["utt"], "label": lab[r["intent"]]}
              for r in en_rows if r["id"] in hi_by_id]
    en_pick = stratified_sample(shared, "label", sizes["massive"], seed=seed)
    hi_pick = [{"id": r["id"], "locale": "hi-IN", "text": hi_by_id[r["id"]]["utt"],
                "label": hi_names["intent"][hi_by_id[r["id"]]["intent"]]} for r in en_pick]
    if any(h["label"] != e["label"] for e, h in zip(en_pick, hi_pick, strict=True)):
        raise ValueError("MASSIVE en-US and hi-IN labels disagree for a shared id")

    files = {"banking77.jsonl": b77, "clinc150.jsonl": clinc_in + clinc_oos,
             "massive.jsonl": en_pick + hi_pick}
    manifest: dict[str, Any] = {
        "seed": seed, "retrieved_at": retrieved_at, "sizes": sizes,
        "datasets": {d: {k: p[k] for k in ("repo", "revision", "licence")}
                     | {"source_sha256": {k: _sha256(sources[k]) for k in p["files"]}}
                     for d, p in PINS.items()},
        "samples": {},
    }
    for name, data in files.items():
        text = _jsonl(data)
        (out_dir / name).write_text(text, encoding="utf-8")
        manifest["samples"][name] = {"rows": len(data),
                                     "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def verify_manifest(out_dir: Path) -> None:
    man = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    for name, info in man["samples"].items():
        data = (out_dir / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != info["sha256"] or data.count(b"\n") != info["rows"]:
            raise ValueError(f"{name} does not match manifest.json")


if __name__ == "__main__":  # pragma: no cover  (python -m pome.data.loaders)
    from datetime import UTC, datetime
    here = Path(__file__).parent
    build_samples(fetch_pinned(here / ".cache"), here,
                  retrieved_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
