"""Fill every gate key POME did not measure (owner request 2026-11-23), never as `measured`.

Rules, applied only to keys that are still missing after build_evidence:
- quality: proxy = POME's measured value on the closest measured model (gapfill.yaml anchors);
- API latency: (TTFT + out_tokens / output speed) from published medians (not p95, not at peak);
- API throughput: published request limit, Gemini spend cap / cost per request, or Little's law;
- error rate: 100 - published uptime SLA, else the 95% Wilson upper bound of POME's own
  error share on a hosted API;
- self-host serving: memory-bandwidth decode model (docs/research/evidence-plan.md section B);
- deployment: vendor docs, or the self-host design assumption.
"""
import json
import math
from datetime import datetime
from pathlib import Path

import yaml

from pome.cost.model import api_monthly_cost
from pome.evidence.schema import EvidenceValue
from pome.profiles.loader import Profile
from pome.registry.loader import ConfigEntry

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "registry" / "gapfill.yaml"
QUALITY = ("intent.banking77.macro_f1", "oos.clinc150.recall", "oos.clinc150.precision",
           "faq.correct.en", "faq.correct.hi", "faq.correct.hinglish", "faq.declined.en",
           "faq.declined.hi", "faq.declined.hinglish", "intent.massive.macro_f1.en",
           "intent.massive.macro_f1.hi")
_DEPLOY = {"region": "deploy.region", "retention_days": "deploy.retention_days",
           "commercial_use": "deploy.commercial_use"}


def load_gapfill(path: Path = DEFAULT_PATH) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _modeled(value, unit: str, source: str, formula: str, at: datetime) -> EvidenceValue:
    return EvidenceValue(value=value, unit=unit, provenance="modeled", source=source,
                         retrieved_at=at, formula=formula)


def _error_share(root: Path, cid: str) -> tuple[int, int]:
    rows = [json.loads(line) for p in sorted((root / cid).glob("*_run0.jsonl"))
            for line in p.read_text(encoding="utf-8").splitlines() if line]
    return sum(r["status"] >= 300 for r in rows), len(rows)


def _wilson_upper(fail: int, n: int, z: float) -> float:
    p = fail / n
    centre = p + z * z / (2 * n)
    spread = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre + spread) / (1 + z * z / n)


def build_gap_evidence(registry: list[ConfigEntry], ev: dict[str, EvidenceValue],
                       profile: Profile, root: Path, data: dict | None = None
                       ) -> dict[str, EvidenceValue]:
    d = data if data is not None else load_gapfill()
    at = datetime.fromisoformat(d["retrieved_at"])
    out_tok, in_tok = d["out_tokens"], d["in_tokens"]
    out: dict[str, EvidenceValue] = {}

    def put(cid: str, key: str, make) -> None:
        full = f"{cid}.{key}"
        if full not in ev and full not in out:
            out[full] = make()

    fail, n = _error_share(Path(root), d["error_proxy"]["anchor"])
    err_proxy = round(100 * _wilson_upper(fail, n, d["error_proxy"]["z"]), 2) if n else None
    sh = d["selfhost"]

    for cfg in registry:
        cid = cfg.config_id
        # quality proxies
        for key in QUALITY:
            first = d["quality_anchor"].get(cid) if key.startswith("intent.banking77") else None
            anchor = next((a for a in (first, d["quality_default_anchor"])
                           if a and f"{a}.{key}" in ev), None)
            if anchor is None:
                continue
            src = ev[f"{anchor}.{key}"]
            kind = "POME measured run" if src.provenance == "measured" else f"{src.provenance} value"
            put(cid, key, lambda src=src, anchor=anchor, key=key, kind=kind: _modeled(
                src.value, src.unit, f"proxy: {kind} of {anchor} ({src.source})",
                f"value = {key} of {anchor} (proxy; this model was not run by POME)", at))

        # serving
        if cid in d["api_speed"]:
            s = d["api_speed"][cid]
            lat_s = s["ttft_s"] + out_tok / s["tok_s"]
            put(cid, "serving.p95_ms", lambda s=s, lat_s=lat_s: _modeled(
                round(lat_s * 1000), "ms", f"{s['url']} ({s['variant']})",
                f"(TTFT {s['ttft_s']} s + {out_tok} tok / {s['tok_s']} tok/s) * 1000; "
                "published medians, not p95 at peak", at))
            lim = d["api_limits"][cid]
            if lim["kind"] == "rpm":
                rps, f = lim["value"] / 60, f"{lim['value']} req/min / 60"
            elif lim["kind"] == "rps":
                rps, f = float(lim["value"]), f"{lim['value']} req/s published"
            elif lim["kind"] == "concurrency":
                rps, f = lim["value"] / lat_s, f"Little's law: {lim['value']} concurrent / {lat_s:.2f} s"
            else:
                p_in, p_out = cfg.pricing.input_per_1m, cfg.pricing.output_per_1m
                per_req = (in_tok * float(p_in.value) + out_tok * float(p_out.value)) / 1e6
                rps = lim["usd_per_10min"] / per_req / 600
                f = (f"spend cap ${lim['usd_per_10min']} per 10 min / ${per_req:.6f} per request "
                     f"({in_tok} in, {out_tok} out at list price) / 600 s")
            note = f"; {lim['note']}" if lim.get("note") else ""
            put(cid, "serving.sustainable_rps", lambda rps=rps, f=f, lim=lim, note=note:
                _modeled(round(rps, 2), "req_per_s", lim["url"], f + note, at))
            e = d["api_error"].get(cid)
            if e:
                put(cid, "serving.error_pct", lambda e=e: _modeled(
                    round(100 - e["sla_pct"], 2), "percent", e["url"],
                    f"100 - published uptime SLA {e['sla_pct']}%"
                    + (f"; {e['note']}" if e.get("note") else ""), at))
            elif err_proxy is not None:
                put(cid, "serving.error_pct", lambda: _modeled(
                    err_proxy, "percent", f"POME runs of {d['error_proxy']['anchor']}",
                    f"Wilson 95% upper bound of {fail} failed / {n} calls after retries "
                    "(proxy; provider publishes no SLA)", at))
        elif cid in sh["params_b"]:
            w_gb = sh["params_b"][cid] * 2
            t_step = w_gb / (sh["gpu_bw_tbps"] * 1000 * sh["eta"])
            e2e = sh["ttft_s"] + out_tok * t_step
            proxy = sh.get("proxy_of", {}).get(cid)
            base = ((f"proxy: modeled as {proxy} (same weights); " if proxy else "")
                    + f"1x A100 80GB bf16: weights {w_gb:.1f} GB / ({sh['gpu_bw_tbps']} TB/s x "
                    f"eta {sh['eta']}) = {t_step * 1000:.1f} ms per token")
            put(cid, "serving.p95_ms", lambda e2e=e2e, base=base: _modeled(
                round(e2e * 1000), "ms", sh["gpu_bw_url"],
                f"(TTFT {sh['ttft_s']} s + {out_tok} x t_step) * 1000; {base}; ±50%", at))
            put(cid, "serving.sustainable_rps", lambda e2e=e2e, base=base: _modeled(
                round(sh["concurrency"] / e2e, 2), "req_per_s", sh["gpu_bw_url"],
                f"Little's law: {sh['concurrency']} concurrent sequences (assumed) / "
                f"{e2e:.2f} s per request; {base}; ±50%", at))
            put(cid, "serving.error_pct", lambda: _modeled(
                round(100 - sh["vm_sla_pct"], 2), "percent", sh["vm_sla_url"],
                f"100 - single-VM uptime SLA {sh['vm_sla_pct']}% (serving errors ignored)", at))

        # cost for configs with a price but no cost yet, else a priced proxy
        p_in, p_out = cfg.pricing.input_per_1m, cfg.pricing.output_per_1m
        pp = d.get("price_proxy", {}).get(cid)
        cp = d.get("cost_proxy", {}).get(cid)
        if pp:
            b = api_monthly_cost(tickets=profile.volume_tickets_per_month,
                                 in_tokens_per_ticket=in_tok, out_tokens_per_ticket=out_tok,
                                 in_price_per_1m=pp["in"], out_price_per_1m=pp["out"])
            put(cid, "cost.monthly_usd", lambda b=b, pp=pp: _modeled(
                b.total, "usd_per_month", pp["url"],
                f"{b.formula} | proxy price: {pp['note']} | tokens assumed: {in_tok} in, "
                f"{out_tok} out", at))
        elif cp and f"{cp}.cost.monthly_usd" in ev:
            c = ev[f"{cp}.cost.monthly_usd"]
            put(cid, "cost.monthly_usd", lambda c=c, cp=cp: _modeled(
                c.value, c.unit, c.source,
                f"proxy: cost of {cp} (the deployment this config stands for): {c.formula}", at))
        elif p_in and p_out:
            b = api_monthly_cost(tickets=profile.volume_tickets_per_month,
                                 in_tokens_per_ticket=in_tok, out_tokens_per_ticket=out_tok,
                                 in_price_per_1m=float(p_in.value),
                                 out_price_per_1m=float(p_out.value))
            put(cid, "cost.monthly_usd", lambda b=b, src=p_in.source: _modeled(
                b.total, "usd_per_month", f"list price {src}; tokens assumed",
                f"{b.formula} | tokens per ticket assumed: {in_tok} in, {out_tok} out", at))

        # deployment
        facts = dict(d["deploy"].get(cid, {}))
        if cfg.host.startswith("self-hosted"):
            facts = {**d["selfhost_deploy"], **facts}
        for name, key in _DEPLOY.items():
            if name in facts:
                put(cid, key, lambda f=facts[name]: EvidenceValue(**f, retrieved_at=at))
    return out
