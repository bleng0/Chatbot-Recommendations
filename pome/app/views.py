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
        lead = ("Recommended from published vendor data" if d.recommended_is_modeled
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


def indian(n: float, decimals: int = 0) -> str:
    """Indian digit grouping: 100000 -> 1,00,000."""
    amount = round(float(n), decimals)
    whole, _, frac = f"{abs(amount):.{decimals}f}".partition(".")
    head, tail = whole[:-3], whole[-3:]
    while len(head) > 2:
        tail = f"{head[-2:]},{tail}"
        head = head[:-2]
    grouped = f"{head},{tail}" if head else tail
    return ("-" if amount < 0 else "") + grouped + (f".{frac}" if frac else "")


def inr(usd: float, decimals: int = 0) -> str:
    """USD amount shown as rupees with Indian digit grouping (₹1,39,195)."""
    amount = float(usd) * float(USD_INR.value)
    return ("-" if round(amount, decimals) < 0 else "") + "₹" + indian(abs(amount), decimals)


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
# Short names shown under each gate number (table head, sliders, sidebar toggles).
SHORT_NAME = {"G1": "Intent", "G2": "Out-of-scope", "G3": "No over-refusal", "G4": "FAQ accuracy",
              "G5": "FAQ decline", "G6": "Hindi gap", "G7": "Hinglish gap", "G8": "Latency",
              "G9": "Capacity", "G14": "Licence"}
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


def architecture_steps(cfg: ConfigEntry, gpu: str = "the GPU picked in the sidebar"
                       ) -> list[tuple[str, str]]:
    """How a bank would build this config: short title + one-line detail per step."""
    route = ("Classify each ticket into a banking intent, then answer FAQs from the bank's "
             "own approved text; send anything out of scope to a human agent.")
    if cfg.host.startswith("self-hosted"):
        return [
            ("Rent GPUs in India", f"Rent {gpu} in an India region for {cfg.model_id}."),
            ("Serve the model", (f"Run {cfg.serving} with {cfg.model_id} at {cfg.quant}, "
                                 "behind a private endpoint.")),
            ("Add a gateway", ("Put an API gateway and request queue in front; keep logs "
                               "off or redacted.")),
            ("Route tickets", route),
            ("Watch and scale", ("Track latency, errors and GPU load; add GPUs before peak "
                                 "hours.")),
        ]
    if cfg.provider == "ollama":
        return [
            ("Install Ollama", f"Install Ollama and pull {cfg.model_id} ({cfg.quant})."),
            ("Run locally", "Serve it on one machine for testing quality only."),
            ("Route test tickets", route),
            ("Move to a server", "For production, use the matching self-hosted GPU config."),
        ]
    provider = cfg.host.split(" (")[0]
    return [
        ("Open a provider account", f"Create a paid {provider} account and an API key."),
        ("Pick model and region", f"Call {cfg.model_id}; region: {cfg.region}."),
        ("Set data controls", ("Turn on zero data retention if offered; never send card or "
                               "account numbers.")),
        ("Route tickets", route),
        ("Watch cost and errors", "Set a monthly spend alert and retry failed calls once."),
    ]


def tickets_options() -> list[int]:
    """Log-spaced ticket volumes from 10,000 to 1 crore, rounded to tidy steps."""
    out = set()
    for i in range(61):
        v = 10 ** (4 + 3 * i / 60)
        step = 1_000 if v < 1e5 else 10_000 if v < 1e6 else 100_000
        out.add(int(round(v / step) * step))
    return sorted(out | {100_000})


def what_if_pick(wi: Decision, not_rec: dict[str, list[str]]) -> tuple[str | None, bool]:
    """The config a what-if suggests: the cheapest passing one that is valid at the
    recommended thresholds; only if none, the cheapest that passes only by loosening.
    Returns (config_id or None, picked_one_is_not_recommended)."""
    passing = [v for v in wi.verdicts if v.status.startswith("eligible")]
    cost = lambda v: (v.monthly_cost is None, v.monthly_cost or 0.0, v.config_id)
    valid = sorted((v for v in passing if v.config_id not in not_rec), key=cost)
    if valid:
        return valid[0].config_id, False
    flagged = sorted((v for v in passing if v.config_id in not_rec), key=cost)
    return (flagged[0].config_id, True) if flagged else (None, False)


_QUALITY_KEYS = {"G1": ("intent.banking77.macro_f1",), "G2": ("oos.clinc150.recall",),
                 "G3": ("oos.clinc150.precision",),
                 "G4": tuple(f"faq.correct.{lang}" for lang in ("en", "hi", "hinglish")),
                 "G5": tuple(f"faq.declined.{lang}" for lang in ("en", "hi", "hinglish"))}


def _quality(cid: str, snap: Snapshot) -> float:
    """Average of the G1-G5 scores (worst language for G4 and G5); a missing score counts 0."""
    total = 0.0
    for keys in _QUALITY_KEYS.values():
        vals = [float(e.value) for k in keys if (e := snap.values.get(f"{cid}.{k}")) is not None]
        total += min(vals) if vals else 0.0
    return total / len(_QUALITY_KEYS)


def baselines(d: Decision, snap: Snapshot, registry: list[ConfigEntry]) -> list[dict]:
    """PLAN F8: what three simple rules would pick instead of the gates, next to our pick.
    Highest benchmark score uses self-tested quality only (proxies copy another model's
    score); lowest price ignores every gate; self-host only is the cheapest rented-GPU config."""
    reg = {c.config_id: c for c in registry}
    by_id = {v.config_id: v for v in d.verdicts if v.config_id in reg}
    costed = [v for v in by_id.values() if v.monthly_cost is not None]
    key_cost = lambda v: (v.monthly_cost, v.config_id)
    self_tested = [v for v in costed
                   if (e := snap.values.get(f"{v.config_id}.intent.banking77.macro_f1"))
                   is not None and e.provenance == "measured"]
    picks = [
        ("Our rule", "Cheapest config that passes every gate", by_id.get(d.recommended or "")),
        ("Highest benchmark score", ("Best average of G1-G5 among the models we self-tested, "
                                     "cost ignored"), max(self_tested, key=lambda v: (_quality(v.config_id, snap),
                                                          -v.monthly_cost, v.config_id),
                             default=None)),
        ("Lowest price", "Cheapest monthly cost, gates ignored", min(costed, key=key_cost,
                                                                     default=None)),
        ("Self-host only", "Cheapest config on our own rented GPU in India, gates ignored",
         min((v for v in costed if reg[v.config_id].host.startswith("self-hosted")),
             key=key_cost, default=None)),
    ]
    ours = picks[0][2].monthly_cost if picks[0][2] and picks[0][2].monthly_cost is not None else None
    cards = []
    for title, rule, v in picks:
        if v is None:
            continue
        cfg = reg[v.config_id]
        e = snap.values.get(f"{v.config_id}.cost.monthly_usd")
        delta = 0.0 if ours is None else v.monthly_cost - ours
        if title == "Our rule" or ours is None:
            delta_txt = ""
        elif abs(delta * float(USD_INR.value)) < 0.5:
            delta_txt = "same cost as our pick"
        else:
            delta_txt = (f"{inr(abs(delta))} {'more' if delta > 0 else 'less'} a month "
                         "than our pick")
        fails = [f"{display_gate(g.gate)}{' ' + SHORT_NAME[g.gate] if g.gate in SHORT_NAME else ''}"
                 + (" (no evidence)" if g.status == "unverified" else "")
                 for g in sorted(v.gates, key=lambda g: int(g.gate[1:]))
                 if g.status in ("fail", "unverified")]
        cards.append({"title": title, "rule": rule, "config": v.config_id,
                      "model": cfg.model_id, "host": cfg.host.split(" (")[0],
                      "cost": inr(v.monthly_cost), "badge": badge(e) if e else "",
                      "delta": delta_txt, "delta_usd": round(delta, 6), "fails": fails})
    return cards
