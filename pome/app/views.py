"""Pure table and chart data for the app (tested); the Streamlit page only renders them."""
from dataclasses import dataclass
from datetime import UTC, datetime

from pome.app.scenario import breakeven_tickets
from pome.evidence.schema import EvidenceValue
from pome.evidence.snapshot import Snapshot
from pome.profiles.loader import Profile
from pome.registry.loader import ConfigEntry
from pome.selection.engine import CHECKS, Decision, check_observation

BADGE = {"measured": "SELF-TESTED", "vendor-doc": "VENDOR-DOC", "modeled": "MODELED",
         "study": "PUBLISHED"}
_STATUS = {"eligible": "Eligible", "eligible_modeled": "Eligible (modeled inputs)",
           "rejected": "Rejected", "unverified": "Unverified (evidence missing)"}
# Gate matrix order: failing configs first, then missing evidence, then the ones that pass.
_ROW_ORDER = {"eligible": 0, "eligible_modeled": 1, "rejected": 2, "unverified": 3}
_METRIC_LABEL = {
    "throughput_tok_s_system": "tok/s (system)", "output_tok_s_per_gpu": "tok/s per GPU",
    "output_tok_s_per_user": "tok/s per user", "decode_tok_s_single_stream":
    "tok/s decode, 1 stream", "output_tok_s": "tok/s", "weights_memory_gb": "GB model weights",
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


GateValues = dict[str, list[tuple[str, str, tuple[str, ...]]]]
_LANGUAGE_LABELS = {"en": "English", "hi": "Hindi", "hinglish": "Hinglish"}
_GATE_VALUE_UNITS = {"ms": " ms", "req_per_s": " req/s"}


def gate_values(snap: Snapshot, config_id: str, gates: list[str]) -> GateValues:
    """One display line per check, with the provenance of the inputs it uses."""
    values: GateValues = {}
    for check in CHECKS:
        if check.gate not in gates:
            continue
        evidence = [snap.values[key] for metric in check.keys
                    if (key := f"{config_id}.{metric}") in snap.values]
        value = check_observation(check, evidence)
        label = ""
        if check.gate in {"G4", "G5"}:
            label = _LANGUAGE_LABELS[check.keys[0].rsplit(".", 1)[1]]
        elif check.kind == "gap":
            label = check.label.split(" ", 2)[2]

        provenance = ()
        if value is None:
            display = "Unavailable" if len(evidence) < len(check.keys) else "Invalid"
        else:
            provenance = tuple(dict.fromkeys(badge(item) for item in evidence))
            if check.kind == "gap":
                display = f"{float(value) * 100:+.2f} pp"
            elif isinstance(value, bool):
                display = "Yes" if value else "No"
            elif evidence[0].unit == "ratio":
                display = f"{float(value):.2%}"
            elif isinstance(value, (int, float)):
                display = f"{value:,.6g}{_GATE_VALUE_UNITS.get(evidence[0].unit, '')}"
            else:
                display = value
        values.setdefault(check.gate, []).append((label, display, provenance))
    return values


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


def variant_rows(cfg: ConfigEntry) -> list[dict]:
    """One published setup per row, with each result's own provenance and conditions."""
    rows = []
    for v in cfg.variants:
        conditions = []
        if v.batch_concurrency != "not stated":
            conditions.append(("Load / parallelism", v.batch_concurrency))
        if v.context != "not stated":
            conditions.append(("Context", v.context))
        if v.input_tokens or v.output_tokens:
            lengths = f"{v.input_tokens or 'n/s'} in / {v.output_tokens or 'n/s'} out"
            conditions.append(("Token lengths", lengths))
        results = []
        for key, e in v.metrics.items():
            value = f"{e.value:,}" if isinstance(e.value, int) else f"{e.value:,.4g}"
            unit = _METRIC_LABEL.get(key, f"{key} ({e.unit})")
            results.append({
                "figure": f"{value} {unit}",
                "badge": badge(e),
                "source": e.source,
                "retrieved": e.retrieved_at.date().isoformat(),
                "conditions": ", ".join(f"{k}: {val}" for k, val in (e.measured_under or {}).items()),
            })
        rows.append({
            "variant": v.variant_id,
            "stack": v.stack,
            "quant": v.quant,
            "hardware": f"{v.gpu_count} × {v.gpu}" if v.gpu_count else v.gpu,
            "match": v.match,
            "conditions": conditions,
            "results": results,
            "note": v.note,
        })
    return rows


# Insertion order is the reading order within each group.
_EVIDENCE_METRICS = {
    "Intent and out-of-scope detection": {
        "intent.banking77.macro_f1": ("BANKING77 intent macro-F1",
            "Balances precision and recall for each banking intent, giving every intent equal weight."),
        "oos.clinc150.recall": ("CLINC150 out-of-scope recall",
            "Share of out-of-scope requests the model correctly flags."),
        "oos.clinc150.precision": ("CLINC150 out-of-scope precision",
            "Share of flagged requests that are actually out of scope."),
        **{f"intent.massive.macro_f1.{code}": (f"MASSIVE intent macro-F1 ({language})",
            (f"Balances precision and recall for each intent in {language}, giving every intent "
            "equal weight.")) for code, language in (("en", "English"), ("hi", "Hindi"))},
    },
    "FAQ quality": {
        f"faq.{metric}.{code}": (f"{label} ({language})", description)
        for metric, label, description in (
            ("correct", "FAQ answer correctness", "Share of answerable FAQ questions answered correctly."),
            ("declined", "FAQ correct declines", "Share of unanswerable FAQ questions correctly declined."),
        )
        for code, language in (("en", "English"), ("hi", "Hindi"), ("hinglish", "Hinglish"))
    },
    "Serving performance": {
        "serving.p95_ms": ("p95 latency at peak load",
            "Time within which 95% of requests finish at peak load."),
        "serving.sustainable_rps": ("Sustainable throughput",
            "Requests per second the service can sustain within the latency and error limits."),
        "serving.error_pct": ("Error rate after retries",
            "Percentage of requests that still fail after retries at peak load."),
    },
    "Cost": {
        "cost.monthly_usd": ("Monthly cost",
            "Estimated monthly cost at the selected ticket volume and hosting settings."),
    },
    "Deployment": {
        "deploy.region": ("Processing region", "Where requests can be processed."),
        "deploy.retention_days": ("Data retention", "How long customer data can be retained."),
        "deploy.commercial_use": ("Commercial use", "Whether the license or terms allow commercial use."),
    },
}


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


def evidence_sections(
    snap: Snapshot, config_ids: set[str],
) -> dict[str, dict[str, list[dict[str, str]]]]:
    """Configuration sections containing only evidence present in the snapshot."""
    by_config: dict[str, dict] = {cid: {} for cid in sorted(config_ids)}
    for row in evidence_rows(snap):
        if row["config"] in by_config:
            by_config[row["config"]][row["metric"]] = row

    sections: dict[str, dict[str, list[dict[str, str]]]] = {}
    for cid, rows in by_config.items():
        groups: dict[str, list[dict[str, str]]] = {}
        for group, metrics in _EVIDENCE_METRICS.items():
            for key, (label, description) in metrics.items():
                if key not in rows:
                    continue
                row = rows.pop(key)
                row.update(label=label, description=description)
                value = snap.values[f"{cid}.{key}"].value
                if row["unit"] == "ratio" and isinstance(value, int | float) and not isinstance(value, bool):
                    row.update(value=f"{value:.2%}", unit="", raw=str(value))
                elif row["unit"] == "bool" and isinstance(value, bool):
                    row.update(value="Yes" if value else "No", unit="")
                groups.setdefault(group, []).append(row)
        if rows:
            for key, row in rows.items():
                recorded = snap.values[f"{cid}.{key}"]
                row.update(value=str(recorded.value), unit=recorded.unit)
            groups["Other evidence"] = list(rows.values())
        sections[cid] = groups
    return sections


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


@dataclass(frozen=True)
class ApiCostComparison:
    config_id: str
    usd_per_ticket: float
    breakeven: int | None


def api_cost_comparisons(
    costs: dict[str, EvidenceValue], *, volume: int, selfhost_monthly: float,
) -> list[ApiCostComparison]:
    """Compare ticket-priced costs to a fixed deployment cost, earliest crossover first."""
    rows = []
    for cid, cost in costs.items():
        # The API cost model starts with ticket volume. GPU deployments and their
        # local measurement proxies use fixed monthly cost formulas.
        if not (cost.formula or "").startswith("tickets *"):
            continue
        per_ticket = float(cost.value) / volume
        rows.append(ApiCostComparison(
            config_id=cid,
            usd_per_ticket=per_ticket,
            breakeven=breakeven_tickets(api_cost_per_ticket=per_ticket,
                                       selfhost_monthly=selfhost_monthly),
        ))
    return sorted(rows, key=lambda row: (row.breakeven is None, row.breakeven or 0, row.config_id))


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
