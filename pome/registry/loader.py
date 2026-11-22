"""Configuration registry: config_id -> model, host, region, serving, quant (PLAN F2)."""
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from pome.evidence.schema import EvidenceValue

DEFAULT_PATH = Path(__file__).with_name("configs.yaml")


class Pricing(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    input_per_1m: EvidenceValue | None
    output_per_1m: EvidenceValue | None


class Deployment(BaseModel):
    """None means the evidence is missing: shown as 'unverified', never assumed to pass."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    region_processing: EvidenceValue | None
    retention_days: EvidenceValue | None
    commercial_use: EvidenceValue | None


class ConfigEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    config_id: str
    model_id: str
    version: str
    host: str
    region: str
    serving: str
    quant: str
    evaluation_mode: Literal["measured", "priced_only", "modeled"]
    provider: Literal["gemini", "ollama", "none"] = "gemini"
    quality_from: str | None = None  # modeled configs: config whose measured quality is carried
    pricing: Pricing
    deployment: Deployment
    notes: str = ""


class _RegistryFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    configs: list[ConfigEntry]

    @model_validator(mode="after")
    def _unique_ids(self) -> "_RegistryFile":
        ids = [c.config_id for c in self.configs]
        dups = sorted({i for i in ids if ids.count(i) > 1})
        if dups:
            raise ValueError(f"duplicate config_id: {dups}")
        return self


def load_registry(path: Path = DEFAULT_PATH) -> list[ConfigEntry]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return _RegistryFile.model_validate(raw).configs
