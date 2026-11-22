"""Spend ledger (CONSTRAINTS B): one cap across ALL keys combined.

Append-only JSONL; one line per billed API call. Runs must:
  1. ledger.approve(estimate)  before starting (refuses if spent + estimate > cap)
  2. ledger.ensure_room()      before every call (hard stop once spent >= cap)
  3. ledger.record(...)        after every billed call (always persisted, even past the cap)
Cached responses cost $0 and are not recorded.

cost = in_tokens * in_price_per_1m / 1e6 + out_tokens * out_price_per_1m / 1e6
out_tokens must be the BILLED output count, thinking tokens included.
A token count of None (e.g. no candidates on a safety block) is recorded as 0, so the
billed input is never dropped. The total is counted in memory BEFORE the disk write, so a
failed write still blocks further calls in this process.

Trade-offs (accepted, see slice 6 doubt review):
- ensure_room() reserves nothing: in-flight calls can overshoot the cap by at most
  concurrency x one call's cost (32 x ~$0.001 here). Use ONE SpendLedger per process.
- Prompt caching, long-context (>200k) prices and tool fees are not modeled; none are used.
"""
import json
import math
import os
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

SPEND_CAP_USD = 20.00


class SpendCapExceeded(RuntimeError):
    """The run would exceed, or has reached, the spend cap."""


def _num(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be an int or float, got {value!r}")
    x = float(value)
    if not math.isfinite(x) or x < 0:
        raise ValueError(f"{name} must be finite and >= 0, got {value!r}")
    return x


def _tokens(name: str, value: object) -> int:
    if value is None:
        return 0
    x = _num(name, value)
    if x != int(x):
        raise ValueError(f"{name} must be a whole number, got {value!r}")
    return int(x)


def call_cost(in_tokens: float, out_tokens: float,
              in_price_per_1m: float, out_price_per_1m: float) -> float:
    return (_num("in_tokens", in_tokens) * _num("in_price_per_1m", in_price_per_1m)
            + _num("out_tokens", out_tokens) * _num("out_price_per_1m", out_price_per_1m)) / 1e6


def estimate_run_cost(calls: int, avg_in_tokens: float, avg_out_tokens: float,
                      in_price_per_1m: float, out_price_per_1m: float) -> float:
    return _num("calls", calls) * call_cost(avg_in_tokens, avg_out_tokens,
                                            in_price_per_1m, out_price_per_1m)


@dataclass(frozen=True)
class SpendEntry:
    config_id: str
    run_id: str
    key_index: int
    in_tokens: int
    out_tokens: int
    in_price_per_1m: float
    out_price_per_1m: float
    cost_usd: float
    recorded_at: str
    tier: str = "paid"
    unit: str = "usd"
    provenance: str = "measured"


class SpendLedger:
    def __init__(self, path: Path, *, cap_usd: float = SPEND_CAP_USD,
                 clock: Callable[[], datetime] = lambda: datetime.now(UTC)):
        self._path = Path(path)
        self._cap = _num("cap_usd", cap_usd)
        self._clock = clock
        self._lock = threading.Lock()
        self._spent = 0.0
        if self._path.exists():
            for n, line in enumerate(self._path.read_text(encoding="utf-8").splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    self._spent += _num("cost_usd", json.loads(line)["cost_usd"])
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    raise ValueError(f"spend ledger {self._path} line {n} is corrupt") from e

    @property
    def cap(self) -> float:
        return self._cap

    def spent(self) -> float:
        with self._lock:
            return self._spent

    def remaining(self) -> float:
        return max(self._cap - self.spent(), 0.0)

    def approve(self, estimate_usd: float) -> None:
        est = _num("estimate_usd", estimate_usd)
        spent = self.spent()
        if spent + est > self._cap + 1e-12:
            raise SpendCapExceeded(
                f"estimate ${est:.4f} + spent ${spent:.4f} > cap ${self._cap:.2f}")

    def ensure_room(self) -> None:
        spent = self.spent()
        if spent >= self._cap - 1e-9:
            raise SpendCapExceeded(f"spend cap reached: ${spent:.4f} of ${self._cap:.2f}")

    def record(self, *, config_id: str, run_id: str, key_index: int, in_tokens: int | None,
               out_tokens: int | None, in_price_per_1m: float, out_price_per_1m: float,
               tier: str = "paid") -> SpendEntry:
        if tier not in ("free", "paid"):
            raise ValueError(f"tier must be 'free' or 'paid', got {tier!r}")
        tin, tout = _tokens("in_tokens", in_tokens), _tokens("out_tokens", out_tokens)
        list_cost = call_cost(tin, tout, in_price_per_1m, out_price_per_1m)
        entry = SpendEntry(
            config_id=config_id, run_id=run_id, key_index=int(key_index),
            in_tokens=tin, out_tokens=tout,
            in_price_per_1m=in_price_per_1m, out_price_per_1m=out_price_per_1m,
            cost_usd=0.0 if tier == "free" else list_cost,
            recorded_at=self._clock().isoformat(), tier=tier,
        )
        line = json.dumps(asdict(entry), sort_keys=True) + "\n"
        with self._lock:
            self._spent += entry.cost_usd
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())
        return entry
