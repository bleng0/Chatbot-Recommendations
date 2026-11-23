"""Pure table and chart data for the app (tested); the Streamlit page only renders them."""
from datetime import UTC, datetime

from pome.evidence.schema import EvidenceValue
from pome.evidence.snapshot import Snapshot
from pome.profiles.loader import Profile
from pome.registry.loader import ConfigEntry
from pome.selection.engine import CHECKS, Decision

BADGE = {"measured": "SELF-TESTED", "vendor-doc": "VENDOR-DOC", "modeled": "MODELED",
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
            f"{inr(v.monthly_cost)}/month (cost MODELED)")
        lead = ("Recommended on modeled evidence (not self-tested)" if d.recommended_is_modeled
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
        value, unit = str(e.value), e.unit
        if unit.startswith("usd_per") and isinstance(e.value, int | float):
            value, unit = inr(e.value, 2 if abs(e.value) < 100 else 0), unit.replace("usd", "inr")
        out.append({"config": cid, "metric": metric, "value": value, "unit": unit,
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


# Display currency (owner request 2026-11-23): the engine stays in USD; the UI shows INR.
USD_INR = EvidenceValue(
    value=92.7968, unit="inr_per_usd", provenance="vendor-doc",
    source="https://www.rbi.org.in/scripts/ReferenceRateArchive.aspx",
    retrieved_at=datetime(2026, 11, 23, 6, 30, tzinfo=UTC))


def inr(usd: float, decimals: int = 0) -> str:
    """USD amount shown as rupees with Indian digit grouping (₹1,39,195)."""
    amount = round(float(usd) * float(USD_INR.value), decimals)
    whole, _, frac = f"{abs(amount):.{decimals}f}".partition(".")
    head, tail = whole[:-3], whole[-3:]
    while len(head) > 2:
        tail = f"{head[-2:]},{tail}"
        head = head[:-2]
    grouped = f"{head},{tail}" if head else tail
    return ("-" if amount < 0 else "") + "₹" + grouped + (f".{frac}" if frac else "")


# One phrase per gate: what it checks, in the reviewer's words.
GATE_INFO = {
    "G1": "Understands which banking request the customer means",
    "G2": "Spots questions the bot must not answer",
    "G3": "Does not wrongly refuse real banking questions",
    "G4": "Answers FAQ questions correctly in every language",
    "G5": "Declines FAQ questions it cannot answer",
    "G6": "Hindi quality stays close to English",
    "G7": "Hinglish quality stays close to English",
    "G8": "Replies fast enough at peak load",
    "G9": "Keeps up with peak ticket traffic",
    "G10": "Rarely fails a request after retries",
    "G11": "Monthly cost stays within budget",
    "G12": "Customer data is processed in India",
    "G13": "Provider deletes customer data quickly",
    "G14": "Licence allows commercial use",
}
# Gates on screen are renumbered without gaps; G10 and G11 are sidebar settings instead.
SETTINGS = {"G10", "G11"}
SHOWN_GATES = ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9", "G14"]
_DISPLAY = {g: f"G{i}" for i, g in enumerate(SHOWN_GATES, 1)} | {
    "G10": "Error limit", "G11": "Budget"}


def display_gate(g: str) -> str:
    return _DISPLAY.get(g, g)


def relabel(text: str) -> str:
    """Swap internal gate ids in a sentence for the ids shown on screen."""
    import re
    return re.sub(r"\bG(\d+)\b", lambda m: display_gate(m.group(0)), text)


_UNIT_TXT = {"ratio": "", "ratio_gap": " gap", "ms": " ms", "req_per_s": " req/s",
             "percent": "%"}


def gate_info_rows(profile: Profile) -> list[dict[str, str]]:
    rows = []
    # G10 and G11 are sidebar settings (error limit, max spend), not gates on screen
    for g in sorted(set(profile.gates) - SETTINGS, key=lambda x: int(x[1:])):
        gate = profile.gates[g]
        if gate.op == "required":
            pass_if = "required"
        elif gate.unit == "usd_per_month":
            pass_if = f"{gate.op.replace('<=', '≤').replace('>=', '≥')} {inr(gate.value)} / month"
        else:
            num = f"{gate.value:,.0f}" if gate.unit == "ms" else (
                f"{gate.value:g}" if gate.unit in ("req_per_s", "percent") else f"{gate.value:.2f}")
            if gate.unit == "percent":
                num = f"{gate.value:.1f}"
            pass_if = (f"{gate.op.replace('<=', '≤').replace('>=', '≥')} {num}"
                       f"{_UNIT_TXT.get(gate.unit, '')}")
        rows.append({"gate": display_gate(g), "checks": GATE_INFO[g], "pass_if": pass_if})
    return rows
