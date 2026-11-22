"""Build evidence values from the registry and recorded eval runs (no I/O beyond reading files).

Quality: scored from runs/records/<config>/<task>_run<k>.jsonl, successful calls only, and only
when a task has at least MIN_ITEMS scored items (otherwise the metric stays unverified).
Cost: modeled = list price (registry) x measured mean tokens per call x profile volume, one call
per ticket. Self-hosted configs carry quality over from the hosted copy of the same weights, as
`modeled` (SPEC A7). Latency, throughput and error rate are not produced here.
"""
import json
import math
from datetime import datetime
from pathlib import Path

from pome.cost.model import api_monthly_cost
from pome.eval.faq import faq_scores
from pome.eval.metrics import macro_f1, oos_precision_recall
from pome.eval.tasks import OOS
from pome.evidence.schema import EvidenceValue
from pome.profiles.loader import Profile
from pome.registry.loader import ConfigEntry

MIN_ITEMS = 30
LANGS = ("en", "hi", "hinglish")
_DEPLOY = {"region_processing": "deploy.region", "retention_days": "deploy.retention_days",
           "commercial_use": "deploy.commercial_use"}


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return [r for r in rows if r["status"] < 300]


def _ev(value: float, source: str, now: datetime, path: Path) -> EvidenceValue:
    return EvidenceValue(value=value, unit="ratio", provenance="measured", source=source,
                         retrieved_at=now, run_ids=[path.name])


def _quality(cid: str, root: Path, now: datetime) -> dict[str, EvidenceValue]:
    out: dict[str, EvidenceValue] = {}

    def task(name: str):
        path = root / cid / f"{name}_run0.jsonl"
        rows = _load(path)
        if len(rows) < MIN_ITEMS:
            return None, None, None
        return [r["gold"] for r in rows], [r["pred"] for r in rows], (path, len(rows))

    def src(meta) -> str:
        return f"{meta[0].parent.name}/{meta[0].name} (n={meta[1]}, successful calls only)"

    gold, pred, meta = task("banking77")
    if meta:
        out[f"{cid}.intent.banking77.macro_f1"] = _ev(macro_f1(gold, pred), src(meta), now, meta[0])
    gold, pred, meta = task("clinc150")
    if meta and OOS in gold:
        prec, rec = oos_precision_recall(gold, pred, oos_label=OOS)
        out[f"{cid}.oos.clinc150.recall"] = _ev(rec, src(meta), now, meta[0])
        out[f"{cid}.oos.clinc150.precision"] = _ev(prec, src(meta), now, meta[0])
    for lang in ("en", "hi"):
        gold, pred, meta = task(f"massive_{lang}")
        if meta:
            out[f"{cid}.intent.massive.macro_f1.{lang}"] = _ev(
                macro_f1(gold, pred), src(meta), now, meta[0])
    for lang in LANGS:
        gold, pred, meta = task(f"faq_{lang}")
        if meta and any(g == "none" for g in gold) and any(g != "none" for g in gold):
            correct, declined = faq_scores(gold, pred)
            out[f"{cid}.faq.correct.{lang}"] = _ev(correct, src(meta), now, meta[0])
            out[f"{cid}.faq.declined.{lang}"] = _ev(declined, src(meta), now, meta[0])
    return out


def _mean_tokens(cid: str, root: Path) -> tuple[float, float, int] | None:
    rows = [r for p in sorted((root / cid).glob("*_run0.jsonl")) for r in _load(p)]
    if len(rows) < MIN_ITEMS:
        return None
    n = len(rows)
    return (math.fsum(r["in_tokens"] for r in rows) / n,
            math.fsum(r["out_tokens"] for r in rows) / n, n)


def build_evidence(registry: list[ConfigEntry], root: Path, profile: Profile, now: datetime
                   ) -> dict[str, EvidenceValue]:
    root = Path(root)
    ev: dict[str, EvidenceValue] = {}
    for cfg in registry:
        cid = cfg.config_id
        for field, suffix in _DEPLOY.items():
            val = getattr(cfg.deployment, field)
            if val is not None:
                ev[f"{cid}.{suffix}"] = val
        if cfg.evaluation_mode == "measured":
            ev.update(_quality(cid, root, now))
            tok = _mean_tokens(cid, root)
            p_in, p_out = cfg.pricing.input_per_1m, cfg.pricing.output_per_1m
            if tok and p_in and p_out:
                tin, tout, n = tok
                b = api_monthly_cost(
                    tickets=profile.volume_tickets_per_month, in_tokens_per_ticket=tin,
                    out_tokens_per_ticket=tout, in_price_per_1m=float(p_in.value),
                    out_price_per_1m=float(p_out.value))
                ev[f"{cid}.cost.monthly_usd"] = EvidenceValue(
                    value=b.total, unit="usd_per_month", provenance="modeled",
                    source=(f"list price {p_in.source}; mean tokens from {n} measured calls "
                            f"(in {tin:.0f}, out {tout:.0f} incl. thinking); one call per ticket"),
                    retrieved_at=now, formula=b.formula)
    hosted = {c.model_id: c.config_id for c in registry if c.evaluation_mode == "measured"}
    for cfg in registry:
        if cfg.evaluation_mode != "modeled" or cfg.model_id not in hosted:
            continue
        src_id = hosted[cfg.model_id]
        for key, v in list(ev.items()):
            if key.startswith(f"{src_id}.") and ".deploy." not in key and ".cost." not in key:
                ev[f"{cfg.config_id}.{key.removeprefix(src_id + '.')}"] = v.model_copy(update={
                    "provenance": "modeled",
                    "source": f"carried over from hosted copy {src_id} (same weights): {v.source}"})
    return ev
