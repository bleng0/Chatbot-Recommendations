"""Requirements profile: loaded from YAML and hashed (PLAN F1)."""
import hashlib
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

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


def load_profile(path: Path = DEFAULT_PATH) -> Profile:
    return Profile.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def profile_hash(profile: Profile) -> str:
    canon = json.dumps(profile.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()
