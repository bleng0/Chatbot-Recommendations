"""Pure scenario logic behind the app: inputs -> snapshot -> select() decision.

No clock: every value is dated EVIDENCE_AT (the day the evidence was gathered), so the same
inputs always give the same decision hash. GPU prices come from docs/research/evidence-plan.md.
"""
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pome.cost.model import selfhost_monthly_cost
from pome.evidence.build import build_evidence
from pome.evidence.schema import EvidenceValue
from pome.evidence.snapshot import Snapshot, build_snapshot
from pome.profiles.loader import Profile, load_profile
from pome.registry.loader import ConfigEntry, load_registry
from pome.selection.engine import Decision, select

EVIDENCE_AT = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
RECORDS = Path(__file__).resolve().parents[2] / "runs" / "records"
SELFHOST = "gemma4-12b-vllm-in-bf16"


@dataclass(frozen=True)
class GpuOption:
    label: str
    note: str
    price: EvidenceValue


def _price(v: float, src: str) -> EvidenceValue:
    return EvidenceValue(value=v, unit="usd_per_hour", provenance="vendor-doc", source=src,
                         retrieved_at=EVIDENCE_AT)


_AZURE = "https://prices.azure.com/api/retail/prices (filter: centralindia)"
_E2E = "https://www.e2enetworks.com/pricing"
GPU_OPTIONS: dict[str, GpuOption] = {
    "azure-ci-a100": GpuOption("Azure Central India, 1x A100 80GB (NC24ads_A100_v4)",
                               "On-demand Linux; India region confirmed.", _price(5.142, _AZURE)),
    "e2e-a100": GpuOption("E2E Networks, 1x A100 80GB",
                          "Page shows no region or date; price excludes tax.",
                          _price(2.10, _E2E)),
    "e2e-l40s": GpuOption("E2E Networks, 1x L40S 48GB",
                          "Page shows no region or date; price excludes tax. Fits the 12B at "
                          "bf16 (Google lists ~26.7 GB to load the weights).", _price(1.20, _E2E)),
}


@dataclass(frozen=True)
class Scenario:
    volume: int = 100_000
    gpu: str = "azure-ci-a100"
    gpus: int = 1
    ops_monthly_usd: float = 0.0


def _selfhost_cost(s: Scenario, profile: Profile) -> EvidenceValue:
    opt = GPU_OPTIONS[s.gpu]
    # gpus is an owner assumption (not load-tested): model it as peak / (peak / gpus) instances
    b = selfhost_monthly_cost(peak_rps=profile.peak_rps,
                              sustainable_rps_per_instance=profile.peak_rps / s.gpus,
                              gpu_hourly_usd=float(opt.price.value),
                              ops_monthly_usd=s.ops_monthly_usd)
    return EvidenceValue(
        value=b.total, unit="usd_per_month", provenance="modeled",
        source=f"{opt.label}: {opt.price.source}. GPU count is an assumption, not load-tested.",
        retrieved_at=EVIDENCE_AT, formula=b.formula)


def decide(s: Scenario, records: Path = RECORDS,
           registry: list[ConfigEntry] | None = None) -> tuple[Snapshot, Decision]:
    base = load_profile()
    profile = base.model_copy(update={"volume_tickets_per_month": s.volume})
    reg = registry if registry is not None else load_registry()
    ev = build_evidence(reg, records, profile, EVIDENCE_AT)
    if any(c.config_id == SELFHOST for c in reg):
        ev[f"{SELFHOST}.cost.monthly_usd"] = _selfhost_cost(s, profile)
    snap = build_snapshot(ev, EVIDENCE_AT)
    return snap, select(snap, profile)


def breakeven_tickets(*, api_cost_per_ticket: float, selfhost_monthly: float) -> int | None:
    """Monthly tickets above which a fixed self-host cost beats a per-ticket API cost."""
    if api_cost_per_ticket <= 0:
        return None
    return round(selfhost_monthly / api_cost_per_ticket)
