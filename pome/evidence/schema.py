"""Evidence value: every number in the app is one of these (CLAUDE.md section 2)."""
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, field_validator, model_validator

Provenance = Literal["measured", "vendor-doc", "modeled"]


class EvidenceValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: float | int | str | bool
    unit: str
    provenance: Provenance
    source: str
    retrieved_at: AwareDatetime
    run_ids: list[str] = []
    key_index: int | None = None
    formula: str | None = None
    study: bool = False  # published third-party figure (decision D1): never `measured`
    measured_under: dict[str, str | int | float] | None = None  # settings the study reported

    @field_validator("unit", "source")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v

    @model_validator(mode="after")
    def _provenance_rules(self) -> "EvidenceValue":
        if self.provenance == "measured" and not self.run_ids:
            raise ValueError("measured evidence needs at least one run_id")
        if self.provenance == "vendor-doc" and not self.source.startswith(("http://", "https://")):
            raise ValueError("vendor-doc evidence needs a URL source")
        if self.provenance == "modeled" and not (self.formula and self.formula.strip()):
            raise ValueError("modeled evidence needs a stated formula")
        if self.study:
            if self.provenance != "vendor-doc":
                raise ValueError("study evidence must be vendor-doc")
            if not self.measured_under:
                raise ValueError("study evidence needs the settings it was reported under")
        return self
