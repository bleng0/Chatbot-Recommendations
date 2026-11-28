"""Requirements profile: loaded from YAML and hashed (PLAN F1)."""
import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

DEFAULT_PATH = Path(__file__).with_name("banking_mvp.yaml")


class Gate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    op: Literal[">=", "<=", "required"]
    value: float | bool
    unit: str


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    tasks: list[str]
    languages: list[str]
    volume_tickets_per_month: int
    peak_rps: float
    region: str
    gates: dict[str, Gate]
    # Identifies a session-derived profile. The profile loaded from disk has None.
    what_if_of: str | None = Field(default=None, min_length=1)


def load_profile(path: Path = DEFAULT_PATH) -> Profile:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if "what_if_of" in data:
        raise ValueError("a profile file cannot set what_if_of: use what_if_profile()")
    return Profile.model_validate(data)


def what_if_profile(base: Profile, off: Iterable[str],
                    thresholds: dict[str, float] | None = None) -> Profile:
    """Derive a profile from disabled gates and session-only threshold overrides."""
    off_sorted = sorted(set(off))
    moved = dict(sorted((thresholds or {}).items()))
    if not off_sorted and not moved:
        raise ValueError("a what-if needs at least one gate switched off or one threshold moved")
    unknown = [g for g in [*off_sorted, *moved] if g not in base.gates]
    if unknown:
        raise ValueError(f"{base.name} has no gates {unknown}")
    yes_no = [g for g in moved if base.gates[g].op == "required"]
    if yes_no:
        raise ValueError(f"yes/no gates have no threshold to move: {yes_no}")
    gates = {g: (v.model_copy(update={"value": float(moved[g])}) if g in moved else v)
             for g, v in base.gates.items() if g not in off_sorted}
    label = [f"{g} off" for g in off_sorted] + [f"{g}={v:g}" for g, v in moved.items()]
    return base.model_copy(update={
        "name": f"{base.name} what-if ({', '.join(label)})",
        "gates": gates,
        "what_if_of": base.name,
    })


def profile_hash(profile: Profile) -> str:
    # The marker is left out when unset, so the official profile hash is unchanged.
    data = profile.model_dump(mode="json",
                              exclude={"what_if_of"} if profile.what_if_of is None else None)
    canon = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()
