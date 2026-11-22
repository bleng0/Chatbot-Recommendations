"""Frozen evidence snapshot: canonical JSON + SHA256 (PLAN F6)."""
import hashlib
import json
from datetime import UTC
from pathlib import Path

from pydantic import AwareDatetime, BaseModel, ConfigDict

from pome.evidence.schema import EvidenceValue

SCHEMA_VERSION = "1"


class SnapshotHashMismatch(ValueError):
    """The stored hash does not match the content (file edited or corrupted)."""


def _ts(dt: AwareDatetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _canonical(schema_version: str, created_at: AwareDatetime,
               values: dict[str, EvidenceValue]) -> str:
    payload = {
        "schema_version": schema_version,
        "created_at": _ts(created_at),
        "values": {
            key: {**v.model_dump(mode="python"), "retrieved_at": _ts(v.retrieved_at)}
            for key, v in values.items()
        },
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(schema_version: str, created_at: AwareDatetime,
          values: dict[str, EvidenceValue]) -> str:
    return hashlib.sha256(_canonical(schema_version, created_at, values).encode()).hexdigest()


def content_hash(snapshot: "Snapshot") -> str:
    """Recompute the SHA256 of a snapshot's content (ignores the stored sha256 field)."""
    return _hash(snapshot.schema_version, snapshot.created_at, snapshot.values)


class Snapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    created_at: AwareDatetime
    values: dict[str, EvidenceValue]
    sha256: str


def build_snapshot(values: dict[str, EvidenceValue], created_at: AwareDatetime) -> Snapshot:
    return Snapshot(
        schema_version=SCHEMA_VERSION,
        created_at=created_at,
        values=dict(values),
        sha256=_hash(SCHEMA_VERSION, created_at, values),
    )


def save_snapshot(snapshot: Snapshot, path: Path) -> None:
    path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")


def load_snapshot(path: Path) -> Snapshot:
    snap = Snapshot.model_validate_json(Path(path).read_text(encoding="utf-8"))
    actual = _hash(snap.schema_version, snap.created_at, snap.values)
    if actual != snap.sha256:
        raise SnapshotHashMismatch(f"stored {snap.sha256[:12]}... != computed {actual[:12]}...")
    return snap
