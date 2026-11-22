"""Seeded stratified sampler. Pure: no I/O, no clock, no global random state."""
from __future__ import annotations

import json
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

Row = Mapping[str, Any]


def _canon(row: Row) -> str:
    return json.dumps(row, sort_keys=True, ensure_ascii=False, default=str)


def stratified_sample(rows: Sequence[Row], key: str, n: int, *, seed: int) -> list[Row]:
    """Pick exactly n rows, balanced across the values of `key` to within one row.

    A stratum smaller than its quota is taken whole and the shortfall is shared by the others.
    The result is sorted canonically, so it does not depend on the input order.
    """
    if isinstance(n, bool) or not isinstance(n, int) or n <= 0:
        raise ValueError(f"n must be a positive int, got {n!r}")
    if n > len(rows):
        raise ValueError(f"cannot sample {n} rows from {len(rows)}")

    strata: dict[Any, list[Row]] = defaultdict(list)
    for r in rows:
        strata[r[key]].append(r)
    for v in strata.values():
        v.sort(key=_canon)

    quota: dict[Any, int] = {}
    active = sorted(strata, key=str)
    remaining = n
    while True:
        base = remaining // len(active)
        small = [s for s in active if len(strata[s]) <= base]
        if not small:
            break
        for s in small:
            quota[s] = len(strata[s])
            remaining -= quota[s]
        active = [s for s in active if s not in small]
        if not active:
            break
    if active:
        base, extra = divmod(remaining, len(active))
        bonus = set(random.Random(f"{seed}|extra").sample(active, extra))
        for s in active:
            quota[s] = base + (1 if s in bonus else 0)

    out: list[Row] = []
    for s in sorted(quota, key=str):
        out.extend(random.Random(f"{seed}|{s}").sample(strata[s], quota[s]))
    out.sort(key=_canon)
    return out
