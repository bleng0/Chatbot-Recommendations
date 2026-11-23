"""Pure scenario logic behind the app: inputs -> snapshot -> select() decision.

No clock: every value is dated EVIDENCE_AT (the day the evidence was gathered), so the same
inputs always give the same decision hash. GPU prices come from docs/research/evidence-plan.md.
"""
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pome.cost.model import selfhost_monthly_cost
from pome.evidence.build import build_evidence, build_published_evidence
from pome.evidence.gapfill import build_gap_evidence
from pome.evidence.schema import EvidenceValue
from pome.evidence.snapshot import Snapshot, build_snapshot
from pome.profiles.loader import Profile, load_profile, what_if_profile
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
_AWS = ("https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/"
        "ec2-ondemand-without-sec-sel/Asia%20Pacific%20(Mumbai)/Linux/index.json")
GPU_OPTIONS: dict[str, GpuOption] = {
    "azure-ci-a100": GpuOption("Azure Central India, 1x A100 80GB (NC24ads_A100_v4)",
                               "On-demand, Central India.", _price(5.142, _AZURE)),
    "e2e-a100": GpuOption("E2E Networks, 1x A100 80GB",
                          "Price excludes tax.",
                          _price(2.10, _E2E)),
    "e2e-l40s": GpuOption("E2E Networks, 1x L40S 48GB",
                          "Price excludes tax.", _price(1.20, _E2E)),
    "e2e-h100": GpuOption("E2E Networks, 1x H100 80GB",
                          "Price excludes tax.", _price(3.99, _E2E)),
    "aws-mum-h100": GpuOption("AWS Mumbai, 1x H100 80GB (p5.4xlarge)",
                              "On-demand, Mumbai.", _price(8.256, _AWS)),
    "azure-ci-h100": GpuOption("Azure Central India, 1x H100 NVL 94GB (NC40ads_H100_v5)",
                               "On-demand, Central India.", _price(9.772, _AZURE)),
    "aws-mum-4l40s": GpuOption("AWS Mumbai, 4x L40S 48GB (g6e.12xlarge)",
                               "On-demand, Mumbai; 4 GPUs per machine.",
                               _price(12.601, _AWS)),
}


@dataclass(frozen=True)
class Scenario:
    volume: int = 100_000
    gpu: str = "azure-ci-a100"
    gpus: int = 1
    ops_monthly_usd: float = 0.0
    max_spend_usd: float = 1500.0  # the user's monthly budget; it is the G11 threshold
    max_error_pct: float = 1.0  # the user's error-rate limit; it is the G10 threshold


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


def _profile(s: Scenario) -> Profile:
    base = load_profile()
    gates = {**base.gates,
             "G11": base.gates["G11"].model_copy(update={"value": float(s.max_spend_usd)}),
             "G10": base.gates["G10"].model_copy(update={"value": float(s.max_error_pct)})}
    return base.model_copy(update={"volume_tickets_per_month": s.volume, "gates": gates})


def decide(s: Scenario, records: Path = RECORDS,
           registry: list[ConfigEntry] | None = None) -> tuple[Snapshot, Decision]:
    profile = _profile(s)
    reg = registry if registry is not None else load_registry()
    ev = build_evidence(reg, records, profile, EVIDENCE_AT)
    ev |= build_published_evidence(reg, profile, EVIDENCE_AT)
    for c in reg:
        if c.host.startswith("self-hosted"):
            ev[f"{c.config_id}.cost.monthly_usd"] = _selfhost_cost(s, profile)
    ev |= build_gap_evidence(reg, ev, profile, records)
    snap = build_snapshot(ev, EVIDENCE_AT)
    return snap, select(snap, profile)


def decide_what_if(snap: Snapshot, s: Scenario, off: tuple[str, ...]) -> Decision:
    """The snapshot decide() built, judged against banking_mvp minus the gates in off.
    Exploration only: never the official recommendation. (Evidence depends only on volume,
    never on which gates are on, so the official snapshot is the right input.)"""
    return select(snap, what_if_profile(_profile(s), off))


def breakeven_tickets(*, api_cost_per_ticket: float, selfhost_monthly: float) -> int | None:
    """Monthly tickets above which a fixed self-host cost beats a per-ticket API cost."""
    if api_cost_per_ticket <= 0:
        return None
    return round(selfhost_monthly / api_cost_per_ticket)
