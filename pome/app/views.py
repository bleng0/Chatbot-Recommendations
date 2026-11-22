"""Pure table and chart data for the app (tested); the Streamlit page only renders them."""
from pome.evidence.snapshot import Snapshot
from pome.selection.engine import Decision

BADGE = {"measured": "MEASURED", "vendor-doc": "VENDOR-DOC", "modeled": "MODELED"}
_SYMBOL = {"pass": "✓ pass", "fail": "✗ fail", "unverified": "? unverified",
           "not_tested": "– not tested"}
_STATUS = {"eligible": "Eligible", "eligible_modeled": "Eligible (modeled inputs)",
           "rejected": "Rejected", "unverified": "Unverified (evidence missing)"}


def status_label(status: str) -> str:
    return _STATUS[status]


def gate_matrix(d: Decision) -> list[dict[str, str]]:
    rows = []
    for v in d.verdicts:
        row = {"config": v.config_id, "status": status_label(v.status)}
        row |= {g.gate: _SYMBOL[g.status] for g in sorted(v.gates, key=lambda g: int(g.gate[1:]))}
        rows.append(row)
    return rows


def evidence_rows(snap: Snapshot) -> list[dict[str, str]]:
    out = []
    for key in sorted(snap.values):
        e = snap.values[key]
        cid, metric = key.split(".", 1)
        out.append({"config": cid, "metric": metric, "value": str(e.value), "unit": e.unit,
                    "provenance": BADGE[e.provenance], "source": e.source,
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
