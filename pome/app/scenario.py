"""Pure scenario logic behind the app: inputs -> snapshot -> select() decision.

No clock: every value is dated EVIDENCE_AT (the day the evidence was gathered), so the same
inputs always give the same decision hash. GPU prices come from docs/research/evidence-plan.md.
"""
import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pome.cost.infrastructure import Estimate
from pome.cost.model import selfhost_monthly_cost
from pome.evidence.build import build_evidence, build_published_evidence
from pome.evidence.compliance import ComplianceEvidence, build_compliance, load_catalog
from pome.evidence.gapfill import build_gap_evidence
from pome.evidence.performance_reference import performance_reference
from pome.evidence.schema import EvidenceValue
from pome.evidence.snapshot import Snapshot, build_snapshot
from pome.profiles.loader import Gate, Profile, load_profile, what_if_profile
from pome.registry.hosting import PRICE_DATE
from pome.registry.loader import ConfigEntry, load_registry
from pome.selection.engine import COMPLIANCE_GATES, Decision, select

EVIDENCE_AT = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
RECORDS = Path(__file__).resolve().parents[2] / "runs" / "records"
SELFHOST = "gemma4-12b-vllm-in-bf16"


@dataclass(frozen=True)
class GpuOption:
    label: str
    note: str
    price: EvidenceValue
    vram_gb: int
    gpus_per_node: int = 1
    india_inr: float | None = None


def _price(v: float, src: str) -> EvidenceValue:
    return EvidenceValue(value=v, unit="usd_per_hour", provenance="vendor-doc", source=src,
                         retrieved_at=EVIDENCE_AT)


_AZURE = "https://prices.azure.com/api/retail/prices (filter: centralindia)"
_E2E = "https://www.e2enetworks.com/pricing"
_AWS = ("https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/"
        "ec2-ondemand-without-sec-sel/Asia%20Pacific%20(Mumbai)/Linux/index.json")
GPU_OPTIONS: dict[str, GpuOption] = {
    "azure-ci-a100": GpuOption("Azure Central India, 1x A100 80GB (NC24ads_A100_v4)",
                               "On-demand, Central India.", _price(5.142, _AZURE), 80),
    "e2e-a100": GpuOption("E2E Networks, 1x A100 80GB",
                          "Price excludes tax.",
                          _price(2.10, _E2E), 80, india_inr=189),
    "e2e-l40s": GpuOption("E2E Networks, 1x L40S 48GB",
                          "Price excludes tax.", _price(1.20, _E2E), 48, india_inr=102),
    "e2e-h100": GpuOption("E2E Networks, 1x H100 80GB",
                          "Price excludes tax.", _price(3.99, _E2E), 80, india_inr=379.05),
    "aws-mum-h100": GpuOption("AWS Mumbai, 1x H100 80GB (p5.4xlarge)",
                              "On-demand, Mumbai.", _price(8.256, _AWS), 80),
    "azure-ci-h100": GpuOption("Azure Central India, 1x H100 NVL 94GB (NC40ads_H100_v5)",
                               "On-demand, Central India.", _price(9.772, _AZURE), 94),
    "aws-mum-4l40s": GpuOption("AWS Mumbai, 4x L40S 48GB (g6e.12xlarge)",
                               "On-demand, Mumbai; 4 GPUs per machine.",
                               _price(12.601, _AWS), 48, gpus_per_node=4),
}


@dataclass(frozen=True)
class Scenario:
    volume: int = 100_000
    gpu: str = "azure-ci-a100"
    gpus: int = 1
    ops_monthly_usd: float = 0.0
    max_spend_usd: float = 1500.0  # the user's monthly budget; it is the G11 threshold
    max_error_pct: float = 1.0  # the user's error-rate limit; it is the G10 threshold
    compliance_gates: tuple[str, ...] = ()
    retention_days: int = 30
    disabled_gates: tuple[str, ...] = ()
    gate_thresholds: dict[str, float] = field(default_factory=dict)


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


def scenario_profile(s: Scenario) -> Profile:
    base = load_profile()
    gates = {**base.gates,
             "G11": base.gates["G11"].model_copy(update={"value": float(s.max_spend_usd)}),
             "G10": base.gates["G10"].model_copy(update={"value": float(s.max_error_pct)})}
    if set(s.compliance_gates) - COMPLIANCE_GATES:
        raise ValueError("unknown compliance gate")
    if "G13" in s.compliance_gates and (
        type(s.retention_days) is not int or s.retention_days < 0
    ):
        raise ValueError("retention cap must be a nonnegative number of whole days")
    for gid in s.compliance_gates:
        gates[gid] = (Gate(op="<=", value=s.retention_days, unit="days") if gid == "G13"
                      else Gate(op="required", value=True, unit="bool"))
    profile = base.model_copy(update={"volume_tickets_per_month": s.volume, "gates": gates})
    if s.disabled_gates or s.gate_thresholds:
        return what_if_profile(profile, s.disabled_gates, s.gate_thresholds)
    return profile


@dataclass(frozen=True)
class DeploymentPlan:
    hardware: str
    nodes: int
    vram_gb: int
    minimum_gb: int | None
    estimate: Estimate
    price_source: str
    cost_formula: str
    gpus_per_node: int = 1
    hours: int = 730
    priced_on: str = PRICE_DATE
    memory_bandwidth_gb_s: float | None = None


SERVING_METRICS = {"serving.p95_ms": "ms", "serving.sustainable_rps": "req_per_s",
                   "serving.error_pct": "percent"}


def serving_evidence(records: Path, cfg: ConfigEntry,
                     plan: DeploymentPlan) -> dict[str, EvidenceValue]:
    """Read curated serving evidence for the exact hardware and app workload."""
    file = records.parent / "serving" / f"{cfg.config_id}.json"
    if not file.is_file():
        return {}
    entries = json.loads(file.read_text(encoding="utf-8"))
    expected = {
        "config_id": cfg.config_id, "hardware": plan.hardware, "nodes": plan.nodes,
        "gpus_per_node": plan.gpus_per_node, "runtime": cfg.serving, "precision": cfg.quant,
        "checkpoint": cfg.model_id, "input_tokens": 600, "output_tokens": 200,
        "max_model_len": 4096,
    }
    result = {}
    versions = set()
    for metric, raw in entries.items():
        if metric not in SERVING_METRICS:
            raise ValueError(f"{file}: unexpected serving metric {metric}")
        item = EvidenceValue.model_validate(raw)
        tags = item.measured_under or {}
        value = item.value
        valid = (item.unit == SERVING_METRICS[metric]
                 and not isinstance(value, bool) and isinstance(value, int | float)
                 and math.isfinite(value) and value >= 0
                 and (metric != "serving.error_pct" or value <= 100))
        if valid and (item.provenance == "measured" or item.study) and all(
            tags.get(key) == value for key, value in expected.items()
        ) and tags.get("runtime_version") and tags.get("checkpoint_revision"):
            result[metric] = item
            versions.add((str(tags["runtime_version"]), str(tags["checkpoint_revision"])))
        else:
            result[f"reference.curated.{metric}"] = item
    if len(versions) > 1:
        return {key if key.startswith("reference.") else f"reference.curated.{key}": item
                for key, item in result.items()}
    return result


def _deployment_evidence(ev: dict[str, EvidenceValue], cfg: ConfigEntry,
                         plan: DeploymentPlan | None, records: Path) -> str | None:
    cid = cfg.config_id
    ev.pop(f"{cid}.cost.monthly_usd", None)
    for key in (f"{cid}.{metric}" for metric in SERVING_METRICS):
        if key in ev:
            ev[f"{cid}.reference.{key.split('.', 1)[1]}"] = ev.pop(key)
    if plan is None:
        return "Lab evidence only. No production infrastructure is assigned."
    if plan.minimum_gb is None or plan.vram_gb >= plan.minimum_gb:
        ev.update({f"{cid}.{key}": value for key, value in performance_reference(
            cid, plan.hardware, plan.nodes * plan.gpus_per_node,
            memory_bandwidth_gb_s=plan.memory_bandwidth_gb_s).items()})
    estimate = plan.estimate
    priced_at = datetime.fromisoformat(plan.priced_on).replace(tzinfo=UTC)
    ev[f"{cid}.deployment.plan"] = EvidenceValue(
        value=f"{plan.hardware} · {plan.nodes} nodes · {plan.gpus_per_node} GPU(s) per node",
        unit="plan", provenance="modeled", source=plan.price_source, retrieved_at=priced_at,
        formula=f"{plan.cost_formula}; missing: {', '.join(estimate.missing) or 'none'}")
    metric = "cost.monthly_usd" if estimate.complete else "cost.known_subtotal_inr"
    ev[f"{cid}.{metric}"] = EvidenceValue(
        value=estimate.monthly, unit="inr_per_month", provenance="modeled",
        source=plan.price_source, retrieved_at=priced_at, formula=plan.cost_formula)
    try:
        matching = serving_evidence(records, cfg, plan)
    except (OSError, ValueError, AttributeError):
        return "Planning only. The curated serving evidence file is unreadable or invalid."
    ev.update({f"{cid}.{key}": val for key, val in matching.items()})
    issues = []
    if plan.minimum_gb is not None and plan.vram_gb < plan.minimum_gb:
        issues.append("Does not fit the single-GPU memory plan.")
    if not estimate.complete:
        issues.append("Monthly cost incomplete. Supply the missing quotes.")
    if not SERVING_METRICS.keys() <= matching.keys():
        issues.append("Planning only. Applicable serving evidence is incomplete.")
    return " ".join(issues) or None


def decide(s: Scenario, records: Path = RECORDS,
           registry: list[ConfigEntry] | None = None, *,
           deployment_plans: dict[str, DeploymentPlan] | None = None,
           scope: str = "all", inr_per_usd: float = 1.0,
           compliance: ComplianceEvidence | None = None) -> tuple[Snapshot, Decision]:
    profile = scenario_profile(s)
    reg = registry if registry is not None else load_registry()
    ev = build_evidence(reg, records, profile, EVIDENCE_AT)
    ev |= build_published_evidence(reg, profile, EVIDENCE_AT)
    for c in reg:
        if c.hosting_kind == "rental" and deployment_plans is None:
            ev[f"{c.config_id}.cost.monthly_usd"] = _selfhost_cost(s, profile)
    ev |= build_gap_evidence(reg, ev, profile, records)
    blocks = {}
    if compliance is None:
        compliance = build_compliance(reg, s.gpu, load_catalog(), None, EVIDENCE_AT.date())
    ev.update(compliance.values)
    if deployment_plans is not None:
        for c in reg:
            if c.hosting_kind != "api" and (scope == "all" or c.hosting_kind == scope):
                reason = _deployment_evidence(ev, c, deployment_plans.get(c.config_id), records)
                if reason:
                    blocks[c.config_id] = reason
                    ev[f"{c.config_id}.deployment.block"] = EvidenceValue(
                        value=reason, unit="status", provenance="modeled",
                        source="docs/distinction.md", retrieved_at=EVIDENCE_AT,
                        formula="Deployment readiness rules",
                    )
                key = f"{c.config_id}.cost.monthly_usd"
                if key in ev:
                    ev[key] = ev[key].model_copy(update={
                        "value": float(ev[key].value) / inr_per_usd, "unit": "usd_per_month"})
        visible = {c.config_id for c in reg if scope == "all" or c.hosting_kind == scope}
        ev = {key: val for key, val in ev.items() if key.split(".", 1)[0] in visible}
    snap = build_snapshot(ev, EVIDENCE_AT)
    return snap, select(snap, profile, deployment_blocks=blocks)


def _recorded_blocks(snap: Snapshot) -> dict[str, str]:
    return {key.split(".", 1)[0]: str(item.value)
            for key, item in snap.values.items() if key.endswith(".deployment.block")}


def decide_what_if(snap: Snapshot, s: Scenario, off: tuple[str, ...]) -> Decision:
    """Rescore an existing snapshot with additional gates disabled."""
    return select(snap, what_if_profile(scenario_profile(s), off),
                  deployment_blocks=_recorded_blocks(snap))


def _looser(gate: Gate, value: float) -> bool:
    return value < gate.value if gate.op == ">=" else value > gate.value


def decide_sliders(snap: Snapshot, s: Scenario, off: tuple[str, ...],
                   thresholds: dict[str, float]) -> tuple[Decision, dict[str, list[str]]]:
    """What-if with per-gate threshold sliders. Returns the what-if decision and, per config,
    the loosened gates it passes only because of the slider ("Not recommended").
    Never the official recommendation."""
    base = scenario_profile(s)
    moved = {g: v for g, v in thresholds.items() if v != base.gates[g].value}
    blocks = _recorded_blocks(snap)
    wi = select(snap, what_if_profile(base, off, moved), deployment_blocks=blocks)
    loose = {g for g, v in moved.items() if _looser(base.gates[g], v)}
    if not loose:
        return wi, {}
    tight = {g: v for g, v in moved.items() if g not in loose}
    strict_profile = what_if_profile(base, off, tight) if (off or tight) else base
    strict = select(snap, strict_profile, deployment_blocks=blocks)
    failed = {v.config_id: [r.gate for r in v.gates if r.gate in loose and r.status == "fail"]
              for v in strict.verdicts}
    strict_ok = {v.config_id for v in strict.verdicts if v.status.startswith("eligible")}
    not_rec = {v.config_id: failed[v.config_id] for v in wi.verdicts
               if v.status.startswith("eligible") and v.config_id not in strict_ok
               and failed.get(v.config_id)}
    return wi, not_rec


def breakeven_tickets(*, api_cost_per_ticket: float, selfhost_monthly: float) -> int | None:
    """Monthly tickets above which a fixed self-host cost beats a per-ticket API cost."""
    if api_cost_per_ticket <= 0:
        return None
    return round(selfhost_monthly / api_cost_per_ticket)
