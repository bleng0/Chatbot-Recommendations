"""Decision engine (PLAN F7). PURE: no I/O, no randomness, no clock.

select(snapshot, profile) -> Decision
  1. every gate per config: pass | fail | unverified (evidence key missing)
  2. config status: any fail -> rejected; else any unverified -> unverified;
     else eligible, or eligible_modeled if any non-cost gate used modeled evidence
  3. among eligible*: min monthly cost, then larger quality margin, then lower p95,
     then config_id

Evidence keys are "<config_id>.<metric>" (config_id contains no dots).
The monthly cost (G11) is always a projection, so its provenance does not flag a config;
the cost value carries its own badge in the UI.

Evidence that is present but unusable (wrong unit, wrong type, NaN/inf, out of range)
makes that check "unverified (invalid)": never a pass, never a crash.
Known trade-off: languages are fixed to en/hi/hinglish (frozen banking_mvp profile);
profile-driven languages are deferred to the profile builder (slice 10).
"""
import hashlib
import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

from pome.evidence.schema import EvidenceValue
from pome.evidence.snapshot import Snapshot, SnapshotHashMismatch, content_hash
from pome.profiles.loader import Profile, profile_hash

LANGS_NON_EN = ("hi", "hinglish")
QUALITY_GATES = {"G1", "G2", "G3", "G4", "G5", "G6", "G7"}
GATE_OPS = {
    "G1": ">=", "G2": ">=", "G3": ">=", "G4": ">=", "G5": ">=", "G6": "<=", "G7": "<=",
    "G8": "<=", "G9": ">=", "G10": "<=", "G11": "<=", "G12": "required", "G13": "<=",
    "G14": "required",
}
# metric suffix -> (expected unit, (min, max) allowed range for numbers)
_RATIO = ("ratio", (0.0, 1.0))
METRIC_SPEC: dict[str, tuple[str, tuple[float, float] | None]] = {
    "serving.p95_ms": ("ms", (0.0, math.inf)),
    "serving.sustainable_rps": ("req_per_s", (0.0, math.inf)),
    "serving.error_pct": ("percent", (0.0, 100.0)),
    "cost.monthly_usd": ("usd_per_month", (0.0, math.inf)),
    "deploy.retention_days": ("days", (0.0, math.inf)),
    "deploy.region": ("region", None),
    "deploy.commercial_use": ("bool", None),
}


class InvalidProfile(ValueError):
    """The profile does not define gates G1-G14 with the expected operators."""


@dataclass(frozen=True)
class _Check:
    gate: str
    label: str
    keys: tuple[str, ...]
    kind: Literal["threshold", "gap", "region", "true"]


def _checks() -> tuple[_Check, ...]:
    c = [
        _Check("G1", "intent macro-F1 (BANKING77)", ("intent.banking77.macro_f1",), "threshold"),
        _Check("G2", "OOS recall (CLINC150)", ("oos.clinc150.recall",), "threshold"),
        _Check("G3", "OOS precision (CLINC150)", ("oos.clinc150.precision",), "threshold"),
    ]
    for lang in ("en", *LANGS_NON_EN):
        c.append(_Check("G4", f"FAQ correctness [{lang}]", (f"faq.correct.{lang}",), "threshold"))
    for lang in ("en", *LANGS_NON_EN):
        c.append(_Check("G5", f"FAQ unanswerable declined [{lang}]",
                        (f"faq.declined.{lang}",), "threshold"))
    c += [
        _Check("G6", "gap en-hi intent macro-F1 (MASSIVE)",
               ("intent.massive.macro_f1.en", "intent.massive.macro_f1.hi"), "gap"),
        _Check("G6", "gap en-hi FAQ correctness", ("faq.correct.en", "faq.correct.hi"), "gap"),
        _Check("G6", "gap en-hi FAQ declined", ("faq.declined.en", "faq.declined.hi"), "gap"),
        _Check("G7", "gap en-hinglish FAQ correctness",
               ("faq.correct.en", "faq.correct.hinglish"), "gap"),
        _Check("G7", "gap en-hinglish FAQ declined",
               ("faq.declined.en", "faq.declined.hinglish"), "gap"),
        _Check("G8", "p95 latency at peak", ("serving.p95_ms",), "threshold"),
        _Check("G9", "sustainable throughput", ("serving.sustainable_rps",), "threshold"),
        _Check("G10", "error rate after retries", ("serving.error_pct",), "threshold"),
        _Check("G11", "monthly cost", ("cost.monthly_usd",), "threshold"),
        _Check("G12", "in-region data processing", ("deploy.region",), "region"),
        _Check("G13", "provider retention", ("deploy.retention_days",), "threshold"),
        _Check("G14", "licence permits commercial use", ("deploy.commercial_use",), "true"),
    ]
    return tuple(c)


CHECKS = _checks()


def required_keys(config_id: str) -> list[str]:
    keys = dict.fromkeys(k for ch in CHECKS for k in ch.keys)
    return [f"{config_id}.{k}" for k in keys]


GateStatus = Literal["pass", "fail", "unverified"]
ConfigStatus = Literal["eligible", "eligible_modeled", "rejected", "unverified"]


class GateResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    gate: str
    status: GateStatus
    detail: list[str]


class Verdict(BaseModel):
    model_config = ConfigDict(frozen=True)
    config_id: str
    status: ConfigStatus
    gates: list[GateResult]
    reasons: list[str]
    missing: list[str]
    monthly_cost: float | None
    quality_margin: float | None
    p95_ms: float | None


class Decision(BaseModel):
    model_config = ConfigDict(frozen=True)
    outcome: Literal["recommended", "no_feasible_option"]
    recommended: str | None
    recommended_is_modeled: bool
    shortlist: list[Verdict]
    verdicts: list[Verdict]
    snapshot_sha256: str
    profile_sha256: str
    decision_hash: str


_OPS: dict[str, Callable[[float, float], bool]] = {
    ">=": lambda v, t: v >= t,
    "<=": lambda v, t: v <= t,
}


def _invalid(metric: str, e: EvidenceValue) -> str | None:
    """Why this evidence value is unusable, or None if it is fine."""
    unit, rng = METRIC_SPEC.get(metric, _RATIO)
    if e.unit != unit:
        return f"unit {e.unit!r}, expected {unit!r}"
    v = e.value
    if unit == "region":
        return None if isinstance(v, str) and v.strip() else f"value {v!r} is not a region name"
    if unit == "bool":
        return None if isinstance(v, bool) else f"value {v!r} is not true/false"
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return f"value {v!r} is not a number"
    try:
        x = float(v)
    except OverflowError:
        return "value is too large"
    if not math.isfinite(x):
        return f"value {v!r} is not finite"
    lo, hi = rng
    if not lo <= x <= hi:
        return f"value {v!r} outside [{lo}, {hi}]"
    return None


def _validate_profile(profile: Profile) -> None:
    for gid, op in GATE_OPS.items():
        g = profile.gates.get(gid)
        if g is None:
            raise InvalidProfile(f"profile has no gate {gid}")
        if g.op != op:
            raise InvalidProfile(f"gate {gid} must use op {op!r}, got {g.op!r}")
    extra = sorted(set(profile.gates) - set(GATE_OPS))
    if extra:
        raise InvalidProfile(f"profile has unknown gates {extra}")


def _evaluate_check(ch: _Check, ev: list[EvidenceValue], profile: Profile
                    ) -> tuple[bool, str, float | None]:
    """-> (passed, detail, quality slack or None). Evidence is already validated."""
    if ch.kind == "region":
        val = ev[0].value
        ok = val.strip().lower() == profile.region.strip().lower()
        return ok, f"{ch.label}: {val!r} vs required {profile.region.strip()!r}", None
    if ch.kind == "true":
        ok = ev[0].value is True
        return ok, f"{ch.label}: {ev[0].value!r} vs required True", None
    g = profile.gates[ch.gate]
    if ch.kind == "gap":
        en, other = float(ev[0].value), float(ev[1].value)
        gap = round(en - other, 9)  # 0.81 - 0.71 must count as exactly 0.10
        ok = _OPS[g.op](gap, float(g.value))
        return ok, f"{ch.label}: {gap:+.3f} vs required {g.op} {g.value}", float(g.value) - gap
    val = float(ev[0].value)
    thr = float(g.value)
    ok = _OPS[g.op](val, thr)
    slack = (val - thr) if g.op == ">=" else (thr - val)
    unit = f" {ev[0].unit}" if ev[0].unit else ""
    return ok, f"{ch.label}: {ev[0].value}{unit} vs required {g.op} {g.value}", slack


def _verdict(cid: str, values: dict[str, EvidenceValue], profile: Profile) -> Verdict:
    per_gate: dict[str, dict[str, list[str]]] = {}
    fails, unverified, missing = [], [], []
    slacks: list[float] = []
    modeled = False
    for ch in CHECKS:
        slot = per_gate.setdefault(ch.gate, {"fail": [], "unverified": [], "pass": []})
        full = [f"{cid}.{k}" for k in ch.keys]
        absent = [k for k in full if k not in values]
        if absent:
            missing += [k for k in absent if k not in missing]
            msg = f"{ch.gate} {ch.label}: evidence missing (unverified)"
            slot["unverified"].append(msg)
            unverified.append(msg)
            continue
        evs = [values[k] for k in full]
        bad = [f"{k}: {why}" for k, e in zip(full, evs, strict=True)
               if (why := _invalid(k.split(".", 1)[1], e))]
        if bad:
            msg = f"{ch.gate} {ch.label}: evidence invalid ({'; '.join(bad)}) (unverified)"
            slot["unverified"].append(msg)
            unverified.append(msg)
            continue
        ok, detail, slack = _evaluate_check(ch, evs, profile)
        if ch.gate != "G11" and any(e.provenance == "modeled" for e in evs):
            modeled = True
        if ch.gate in QUALITY_GATES and slack is not None:
            slacks.append(slack)
        slot["pass" if ok else "fail"].append(detail)
        if not ok:
            fails.append(f"{ch.gate} {detail}")

    gates = []
    for gid, slot in per_gate.items():
        status: GateStatus = ("fail" if slot["fail"] else
                              "unverified" if slot["unverified"] else "pass")
        gates.append(GateResult(gate=gid, status=status,
                                detail=slot["fail"] + slot["unverified"] + slot["pass"]))

    if fails:
        status_c: ConfigStatus = "rejected"
    elif unverified:
        status_c = "unverified"
    else:
        status_c = "eligible_modeled" if modeled else "eligible"

    def num(key: str) -> float | None:
        e = values.get(f"{cid}.{key}")
        if e is None or _invalid(key, e):
            return None
        return float(e.value)

    return Verdict(
        config_id=cid, status=status_c, gates=gates, reasons=fails + unverified,
        missing=missing, monthly_cost=num("cost.monthly_usd"),
        quality_margin=round(min(slacks), 9) if slacks and not unverified else None,
        p95_ms=num("serving.p95_ms"),
    )


def _hash(payload: dict) -> str:
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canon.encode()).hexdigest()


def select(snapshot: Snapshot, profile: Profile) -> Decision:
    if not snapshot.values:
        raise ValueError("snapshot is empty: nothing was evaluated")
    if content_hash(snapshot) != snapshot.sha256:
        raise SnapshotHashMismatch("snapshot content does not match its recorded sha256")
    _validate_profile(profile)
    config_ids = sorted({key.split(".", 1)[0] for key in snapshot.values})
    verdicts = [_verdict(cid, snapshot.values, profile) for cid in config_ids]
    feasible = sorted(
        (v for v in verdicts if v.status in ("eligible", "eligible_modeled")),
        key=lambda v: (v.monthly_cost, -v.quality_margin, v.p95_ms, v.config_id),
    )
    best = feasible[0] if feasible else None
    body = {
        "outcome": "recommended" if best else "no_feasible_option",
        "recommended": best.config_id if best else None,
        "recommended_is_modeled": bool(best and best.status == "eligible_modeled"),
        "shortlist": feasible,
        "verdicts": verdicts,
        "snapshot_sha256": snapshot.sha256,
        "profile_sha256": profile_hash(profile),
    }
    dumped = {k: ([v.model_dump(mode="json") for v in val] if isinstance(val, list) else val)
              for k, val in body.items()}
    return Decision(**body, decision_hash=_hash(dumped))
