"""Deployment-scoped governance evidence, assembled before selection."""
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StrictBool, StrictInt, model_validator

from pome.evidence.schema import EvidenceValue
from pome.registry.loader import ConfigEntry

CATALOG = Path(__file__).resolve().parents[1] / "registry" / "compliance.yaml"
FACTS = {
    "processing_region": ("deploy.region", "region"),
    "storage_region": ("deploy.storage_region", "region"),
    "retention_days": ("deploy.retention_days", "days"),
    "no_training": ("deploy.no_training", "bool"),
    "no_prompt_logging": ("deploy.no_prompt_logging", "bool"),
    "contract_verified": ("deploy.contract_verified", "bool"),
    "configuration_verified": ("deploy.configuration_verified", "bool"),
}
OWNED_OPERATOR_ASSUMPTIONS = {
    "processing_region": ("India", "Inference and fallback stay on the operator's India site."),
    "storage_region": ("No persistence", "No third-party provider persists prompt content."),
    "retention_days": (0, "No third-party provider retains prompts or responses."),
    "no_training": (True, "The operator runs frozen weights without a provider training pipeline."),
    "no_prompt_logging": (True, "Provider prompt logging is absent and operator content logs are disabled."),
    "contract_verified": (True, "Internal approval is assumed for the operator-owned deployment."),
    "configuration_verified": (True, "The operator is assumed to have reviewed these settings."),
}

REGION = Literal["India", "China", "United States", "EU", "Global"]


class Facts(BaseModel):
    model_config = ConfigDict(extra="forbid")
    processing_region: REGION | None = None
    storage_region: REGION | Literal["No persistence"] | None = None
    retention_days: StrictInt | None = Field(default=None, ge=0)
    no_training: StrictBool | None = None
    no_prompt_logging: StrictBool | None = None

    @model_validator(mode="after")
    def _consistent_persistence(self) -> "Facts":
        if self.storage_region == "No persistence" and (
            self.retention_days not in (None, 0) or self.no_prompt_logging is False
        ):
            raise ValueError("no persistence conflicts with retention or prompt logging")
        if self.retention_days == 0 and self.no_prompt_logging is False:
            raise ValueError("zero retention conflicts with persisted prompt logs")
        return self


class PublicRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: str = Field(min_length=1)
    reviewed_on: date
    sources: list[HttpUrl] = Field(min_length=1)
    facts: Facts = Field(default_factory=Facts)
    fact_sources: dict[str, HttpUrl] = Field(default_factory=dict)
    notes: str = Field(min_length=1)


class PublicCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")
    configurations: dict[str, PublicRecord]
    gpu_options: dict[str, PublicRecord]


class BuyerRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    config_id: str
    model_id: str
    version: str
    host: str
    serving: str
    region: str
    quant: str
    gpu_option: str | None = None
    reference: str = Field(min_length=1, max_length=160)
    scope: str = Field(min_length=1, max_length=500)
    reviewed_on: date
    expires_on: date | None = None
    facts: Facts = Field(default_factory=Facts)
    contract_verified: StrictBool | None = None
    configuration_verified: StrictBool | None = None

    @model_validator(mode="after")
    def _review_scope(self) -> "BuyerRecord":
        if self.expires_on is not None and self.expires_on < self.reviewed_on:
            raise ValueError("expiry precedes review")
        if not self.reference.strip() or not self.scope.strip():
            raise ValueError("reference and scope cannot be blank")
        if self.facts.model_dump(exclude_none=True) and self.configuration_verified is not True:
            raise ValueError("deployment facts require verified configuration settings")
        return self

    def matches(self, config: ConfigEntry, gpu_option: str | None) -> bool:
        return (self.config_id, self.model_id, self.version, self.host, self.serving,
                self.region, self.quant, self.gpu_option) == (config.config_id, config.model_id, config.version,
                                     config.host, config.serving, config.region, config.quant, gpu_option)


class BuyerEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    records: list[BuyerRecord]

    @model_validator(mode="after")
    def _unique_deployments(self) -> "BuyerEvidence":
        keys = [(record.config_id, record.gpu_option) for record in self.records]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate configuration and GPU option")
        return self


def load_catalog(path: Path = CATALOG) -> PublicCatalog:
    return PublicCatalog.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def load_buyer_evidence(path: Path) -> BuyerEvidence:
    return BuyerEvidence.model_validate_json(path.read_text(encoding="utf-8"))


@dataclass
class ComplianceEvidence:
    values: dict[str, EvidenceValue]
    public: dict[str, PublicRecord]
    buyer_status: dict[str, str]


def build_compliance(registry: list[ConfigEntry], gpu: str, catalog: PublicCatalog,
                     buyer: BuyerEvidence | None, review_date: date, *,
                     assume_owned_controls: bool = False) -> ComplianceEvidence:
    result = ComplianceEvidence({}, {}, {})
    records = {(record.config_id, record.gpu_option): record
               for record in buyer.records} if buyer else {}
    for config in registry:
        cid = config.config_id
        gpu_option = gpu if config.hosting_kind == "rental" else None
        public = (catalog.gpu_options.get(gpu_option) if gpu_option
                  else catalog.configurations.get(cid))
        if public:
            result.public[cid] = public
            for field, value in public.facts.model_dump(exclude_none=True).items():
                key, unit = FACTS[field]
                result.values[f"{cid}.{key}"] = EvidenceValue(
                    value=value, unit=unit, provenance="vendor-doc", source=str(public.fact_sources.get(field, public.sources[0])),
                    formula=public.scope, retrieved_at=datetime.combine(
                        public.reviewed_on, time.min, UTC))
        if assume_owned_controls and config.hosting_kind == "owned":
            for field, (value, basis) in OWNED_OPERATOR_ASSUMPTIONS.items():
                key, unit = FACTS[field]
                result.values.setdefault(f"{cid}.{key}", EvidenceValue(
                    value=value, unit=unit, provenance="operator-assumed",
                    source="docs/compliance.md#owned-self-hosting", formula=basis,
                    retrieved_at=datetime.combine(review_date, time.min, UTC),
                ))
            result.buyer_status[cid] = "Owned hosting uses the operator-control assumptions."
            continue
        record = records.get((cid, gpu_option))
        if record is None:
            continue
        if config.hosting_kind == "owned" and not config.lab_only:
            result.buyer_status[cid] = "Buyer evidence for configurable owned plans is not supported."
            continue
        if not record.matches(config, gpu_option):
            result.buyer_status[cid] = "Buyer record does not match this deployment."
            continue
        if record.reviewed_on > review_date or (
            record.expires_on is not None and record.expires_on < review_date
        ):
            result.buyer_status[cid] = "Buyer record is outside its review validity period."
            continue
        if (public and public.facts.processing_region and record.facts.processing_region
                and record.facts.processing_region != public.facts.processing_region):
            result.buyer_status[cid] = "Buyer processing claim conflicts with the catalog deployment."
            continue
        result.buyer_status[cid] = "Buyer record matched this deployment."
        facts = record.facts.model_dump(exclude_none=True)
        facts.update(contract_verified=record.contract_verified,
                     configuration_verified=record.configuration_verified)
        for field, value in facts.items():
            if value is None:
                continue
            key, unit = FACTS[field]
            result.values[f"{cid}.{key}"] = EvidenceValue(
                value=value, unit=unit, provenance="buyer-verified", source=record.reference,
                formula=record.scope, retrieved_at=datetime.combine(
                    record.reviewed_on, time.min, UTC))
    return result
