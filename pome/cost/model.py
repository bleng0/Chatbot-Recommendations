"""Cost model (PLAN F5). Pure: no I/O, no clock.

A "ticket" is one classification call plus one grounded FAQ answer call (SPEC A4), so the
per-ticket token figures are the SUM over both calls, measured from the eval runs.

API:       monthly = tickets * (in_tok * in_price + out_tok * out_price) / 1e6 * (1 + retry_rate)
Self-host: instances = ceil(peak_rps / sustainable_rps_per_instance)
           monthly   = instances * gpu_hourly * 730 + ops_monthly

Retry overhead is a conservative assumption: retried calls are treated as billed.
Totals are rounded ONCE, to 6 decimals, after the exact arithmetic; items are for display.
Instances use exact arithmetic on each float's shortest decimal form (no tolerance), so
1.1 / 0.1 is exactly 11 instances and 7.0000000004 / 1 is 8.
Only Python int and float inputs are accepted (not Decimal, Fraction or numpy types).
Results that overflow raise ValueError instead of returning nan or inf.
"""
import math
from datetime import datetime
from fractions import Fraction

from pydantic import BaseModel, ConfigDict

from pome.evidence.schema import EvidenceValue

HOURS_PER_MONTH = 730


class CostBreakdown(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: tuple[tuple[str, float], ...]
    total: float
    formula: str
    instances: int | None = None


def _num(name: str, value: object, *, positive: bool = False, integer: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be an int or float, got {value!r}")  # noqa: TRY004 - contract: ValueError for every bad input
    try:
        x = float(value)
    except OverflowError:
        raise ValueError(f"{name} is too large: {value!r}") from None
    if not math.isfinite(x):
        raise ValueError(f"{name} must be finite, got {value!r}")
    if x < 0 or (positive and x == 0):
        raise ValueError(f"{name} must be {'> 0' if positive else '>= 0'}, got {value!r}")
    if integer and x != int(x):
        raise ValueError(f"{name} must be a whole number, got {value!r}")
    return x


def _r(x: float) -> float:
    return round(x, 6)


def _fmt(x: float) -> str:
    return str(int(x)) if x == int(x) and abs(x) < 1e15 else repr(x)


def _finite(name: str, x: float) -> float:
    if not math.isfinite(x):
        raise ValueError(f"{name} overflows: inputs are too large")
    return x


def api_monthly_cost(
    *,
    tickets: int,
    in_tokens_per_ticket: float,
    out_tokens_per_ticket: float,
    in_price_per_1m: float,
    out_price_per_1m: float,
    retry_rate: float = 0.0,
) -> CostBreakdown:
    _num("tickets", tickets, integer=True)
    n = int(tickets)
    tin = _num("in_tokens_per_ticket", in_tokens_per_ticket)
    tout = _num("out_tokens_per_ticket", out_tokens_per_ticket)
    pin = _num("in_price_per_1m", in_price_per_1m)
    pout = _num("out_price_per_1m", out_price_per_1m)
    retry = _num("retry_rate", retry_rate)
    inp_raw = _finite("input cost", n * tin * pin / 1e6)
    out_raw = _finite("output cost", n * tout * pout / 1e6)
    total = _r(_finite("total", (inp_raw + out_raw) * (1 + retry)))
    inp, out = _r(inp_raw), _r(out_raw)
    formula = (
        f"tickets * (in_tok * in_price + out_tok * out_price) / 1e6 * (1 + retry_rate) = "
        f"{n} * ({_fmt(tin)} * {_fmt(pin)} + {_fmt(tout)} * {_fmt(pout)}) / 1e6 "
        f"* (1 + {_fmt(retry)})"
    )
    return CostBreakdown(
        items=(("input_tokens", inp), ("output_tokens", out),
               ("retry_overhead", _r(total - inp - out))),
        total=total,
        formula=formula,
    )


def selfhost_monthly_cost(
    *,
    peak_rps: float,
    sustainable_rps_per_instance: float,
    gpu_hourly_usd: float,
    ops_monthly_usd: float,
) -> CostBreakdown:
    """ops_monthly_usd has no default on purpose: it is an explicit owner input."""
    peak = _num("peak_rps", peak_rps, positive=True)
    per = _num("sustainable_rps_per_instance", sustainable_rps_per_instance, positive=True)
    gpu_h = _num("gpu_hourly_usd", gpu_hourly_usd)
    ops = _num("ops_monthly_usd", ops_monthly_usd)
    instances = math.ceil(Fraction(repr(peak)) / Fraction(repr(per)))
    try:
        gpu_raw = _finite("gpu cost", instances * gpu_h * HOURS_PER_MONTH)
    except OverflowError:
        raise ValueError("gpu cost overflows: inputs are too large") from None
    total = _r(_finite("total", gpu_raw + ops))
    formula = (
        f"ceil(peak_rps / rps_per_instance) * gpu_hourly * {HOURS_PER_MONTH} + ops_monthly = "
        f"ceil({_fmt(peak)} / {_fmt(per)}) * {_fmt(gpu_h)} * {HOURS_PER_MONTH} + {_fmt(ops)}"
    )
    return CostBreakdown(
        items=(("gpu", _r(gpu_raw)), ("ops", _r(ops))),
        total=total,
        formula=formula,
        instances=instances,
    )


def cost_per_ticket(monthly_total: float, tickets: int) -> float:
    """Unrounded on purpose: per-ticket costs are tiny (e.g. 0.000189 USD)."""
    total = _num("monthly_total", monthly_total)
    n = _num("tickets", tickets, positive=True, integer=True)
    return total / n


def cost_evidence(breakdown: CostBreakdown, *, source: str, retrieved_at: datetime
                  ) -> EvidenceValue:
    """Wrap a total as `modeled` evidence: a projection from a stated formula and inputs."""
    return EvidenceValue(
        value=breakdown.total, unit="usd_per_month", provenance="modeled",
        source=source, retrieved_at=retrieved_at, formula=breakdown.formula,
    )
