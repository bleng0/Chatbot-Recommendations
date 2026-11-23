"""Pure table and chart data for the app (tested); the Streamlit page only renders them."""
from pome.evidence.schema import EvidenceValue
from pome.evidence.snapshot import Snapshot
from pome.profiles.loader import Profile
from pome.registry.loader import ConfigEntry
from pome.selection.engine import CHECKS, Decision

BADGE = {"measured": "MEASURED", "vendor-doc": "VENDOR-DOC", "modeled": "MODELED",
         "study": "PUBLISHED"}
_STATUS = {"eligible": "Eligible", "eligible_modeled": "Eligible (modeled inputs)",
           "rejected": "Rejected", "unverified": "Unverified (evidence missing)"}
# Gate matrix order: failing configs first, then missing evidence, then the ones that pass.
_ROW_ORDER = {"eligible": 0, "eligible_modeled": 1, "rejected": 2, "unverified": 3}
_METRIC_LABEL = {
    "throughput_tok_s_system": "tok/s (system)", "output_tok_s_per_gpu": "tok/s per GPU",
    "output_tok_s_per_user": "tok/s per user", "decode_tok_s_single_stream":
    "tok/s decode, 1 stream", "output_tok_s": "tok/s", "weights_memory_gb": "GB weights",
    "quality_recovery_pct": "% quality kept", "mmlu_hindi_recovery_pct": "% Hindi MMLU kept",
    "weights_memory_reduction_pct": "% less weight memory",
}


def status_label(status: str) -> str:
    return _STATUS[status]


def badge(e: EvidenceValue) -> str:
    return BADGE["study"] if e.study else BADGE[e.provenance]


def gate_matrix(d: Decision) -> list[dict]:
    """One row per config: {config, status, gates: {G1: pass|fail|unverified|not_tested}}."""
    rows = [{"config": v.config_id, "status": v.status,
             "gates": {g.gate: g.status for g in sorted(v.gates, key=lambda g: int(g.gate[1:]))}}
            for v in d.verdicts]
    return sorted(rows, key=lambda r: (_ROW_ORDER[r["status"]], r["config"]))


def _fail_value(cid: str, gate: str, snap: Snapshot, profile: Profile) -> str | None:
    """'0.75 < 0.80' for a failing single-value gate; None when it is not one number."""
    for ch in CHECKS:
        if ch.gate != gate or ch.kind != "threshold":
            continue
        e = snap.values.get(f"{cid}.{ch.keys[0]}")
        if e is None:
            continue
        g = profile.gates[gate]
        v, t = float(e.value), float(g.value)
        if g.op == ">=" and v < t:
            return f"{v:.2f} < {t:.2f}"
        if g.op == "<=" and v > t:
            return f"{v:.2f} > {t:.2f}"
    return None


def answer_line(d: Decision, snap: Snapshot, profile: Profile) -> str:
    """The one sentence on top of the page."""
    if d.recommended:
        v = next(x for x in d.verdicts if x.config_id == d.recommended)
        cost = "no cost evidence" if v.monthly_cost is None else (
            f"${v.monthly_cost:,.0f}/month (cost MODELED)")
        lead = ("Recommended on modeled evidence (not measured)" if d.recommended_is_modeled
                else "Recommended")
        return f"{lead}: {d.recommended} at {cost}"
    parts = []
    missing = sum(v.status == "unverified" for v in d.verdicts)
    if missing:
        parts.append(f"{missing} lack evidence")
    by_gate: dict[str, list[str]] = {}
    for v in d.verdicts:
        if v.status == "rejected":
            first = next(g.gate for g in sorted(v.gates, key=lambda g: int(g.gate[1:]))
                         if g.status == "fail")
            by_gate.setdefault(first, []).append(v.config_id)
    for gate, cids in sorted(by_gate.items(), key=lambda kv: int(kv[0][1:])):
        values = {_fail_value(c, gate, snap, profile) for c in cids}
        detail = f" ({values.pop()})" if len(values) == 1 and None not in values else ""
        parts.append(f"{len(cids)} fail {gate}{detail}")
    return "No configuration qualifies yet: " + ", ".join(parts)


def split_configs(registry: list[ConfigEntry]) -> tuple[list[str], list[str]]:
    """(configs POME measured or carries POME measurements for, configs from published sources)."""
    measured = [c.config_id for c in registry
                if c.evaluation_mode == "measured" or c.quality_from]
    return measured, [c.config_id for c in registry if c.config_id not in measured]


def _figure(metrics: dict[str, EvidenceValue]) -> str:
    out = []
    for key, e in metrics.items():
        num = f"{e.value:,}" if isinstance(e.value, int) else f"{e.value:,.4g}"
        out.append(f"{num} {_METRIC_LABEL.get(key, f'{key} ({e.unit})')}")
    return "; ".join(out)


def variant_rows(cfg: ConfigEntry) -> list[dict[str, str]]:
    """One row per published deployment setting of an open-weight model."""
    rows = []
    for v in cfg.variants:
        gpu = f"{v.gpu_count}x {v.gpu}" if v.gpu_count else v.gpu
        settings = [v.stack, v.quant, gpu, v.batch_concurrency, v.context]
        if v.input_tokens or v.output_tokens:
            settings.append(f"{v.input_tokens or 'n/s'} in / {v.output_tokens or 'n/s'} out")
        first = next(iter(v.metrics.values()), None)
        rows.append({
            "variant": v.variant_id,
            "settings": " · ".join(s for s in settings if s and s != "not stated"),
            "figure": _figure(v.metrics), "badge": badge(first) if first else "",
            "match": v.match, "source": first.source if first else "",
            "retrieved": first.retrieved_at.date().isoformat() if first else "",
            "measured_under": first.measured_under if first else None, "note": v.note,
        })
    return rows


def evidence_rows(snap: Snapshot) -> list[dict[str, str]]:
    out = []
    for key in sorted(snap.values):
        e = snap.values[key]
        cid, metric = key.split(".", 1)
        out.append({"config": cid, "metric": metric, "value": str(e.value), "unit": e.unit,
                    "provenance": badge(e), "source": e.source,
                    "formula": e.formula or "", "retrieved": e.retrieved_at.date().isoformat()})
    return out


def cost_curves(snap: Snapshot, *, volume: int, points: list[int]) -> dict[str, list[float]]:
    """Monthly cost per config at each ticket volume. API cost scales with tickets (modeled per
    ticket from the current volume); self-host cost is fixed per month."""
    out: dict[str, list[float]] = {}
    for key, e in sorted(snap.values.items()):
        if not key.endswith(".cost.monthly_usd"):
            continue
        cid = key.split(".", 1)[0]
        fixed = "gpu_hourly" in (e.formula or "")
        per_ticket = float(e.value) / volume
        out[cid] = [round(float(e.value), 2) if fixed else round(per_ticket * n, 2)
                    for n in points]
    return out
