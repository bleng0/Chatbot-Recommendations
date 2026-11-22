"""Seeded bootstrap over ITEMS (CONSTRAINTS A: CIs shown, not gating).

All runs of a config score the same items, so each replicate draws one set of item
indices (with replacement) and applies it to every run; the replicate statistic is the
mean of the metric over runs. That matches the gate's point estimate (3-run mean) and
carries item-sampling uncertainty. Run-to-run spread is shown separately (per-run dots).

strata (optional, one key per item, e.g. the true intent or in-scope/OOS): resample WITHIN
each stratum, keeping per-class counts fixed as in the sampling design. Without it, ~1.4 of
77 intents vanish per replicate at ~4 items/class and the macro-F1 label set changes.

paired_bootstrap_diff checks ids_a == ids_b when given, and uses the SAME indices for A and B (same items, e.g. MASSIVE en-US vs
hi-IN on shared utterance IDs, or two configs on one sample) -> CI of mean(A) - mean(B).

Interval: bias-corrected (BC) percentile, Efron 1987. Plain percentile CIs for macro-F1
with ~4 items per class sit almost wholly below the point estimate, because resampling
duplicates items and F1 is non-linear. BC shifts the quantiles by
z0 = Phi^-1(share of replicates below the point, ties counted half):
  low/high = quantile(Phi(2*z0 -/+ z_{1-a/2})).
Default 2000 resamples, level 0.95, numpy default_rng(seed).
"""
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from statistics import NormalDist

import numpy as np

Metric = Callable[[Sequence], float]


@dataclass(frozen=True)
class CI:
    point: float
    low: float
    high: float
    level: float
    n_resamples: int
    seed: int


def _check(runs: Sequence[Sequence]) -> int:
    if not runs:
        raise ValueError("no runs")
    n = len(runs[0])
    if n == 0 or any(len(r) != n for r in runs):
        raise ValueError("every run must score the same, non-empty item list")
    return n


def _sampler(n: int, strata: Sequence | None, rng: np.random.Generator
             ) -> Callable[[], np.ndarray]:
    if strata is None:
        return lambda: rng.integers(0, n, n)
    if len(strata) != n:
        raise ValueError(f"strata has {len(strata)} keys for {n} items")
    groups: dict[str, list[int]] = {}
    for i, key in enumerate(strata):
        groups.setdefault(str(key), []).append(i)
    arrays = [np.asarray(groups[k]) for k in sorted(groups)]
    return lambda: np.concatenate([g[rng.integers(0, len(g), len(g))] for g in arrays])


def _mean_over_runs(metric: Metric, runs: Sequence[Sequence], idx: np.ndarray | None) -> float:
    vals = [metric(list(r) if idx is None else [r[i] for i in idx]) for r in runs]
    return float(sum(vals) / len(vals))


def _interval(point: float, reps: list[float], level: float, n_resamples: int,
              seed: int) -> CI:
    r = np.asarray(reps)
    if np.all(r == point):
        return CI(point, point, point, level, n_resamples, seed)
    nd = NormalDist()
    below = (np.sum(r < point) + 0.5 * np.sum(r == point)) / len(r)
    below = min(max(below, 0.5 / len(r)), 1 - 0.5 / len(r))
    z0, z = nd.inv_cdf(below), nd.inv_cdf(1 - (1 - level) / 2)
    low, high = np.quantile(r, [nd.cdf(2 * z0 - z), nd.cdf(2 * z0 + z)])
    return CI(point, float(low), float(high), level, n_resamples, seed)


def bootstrap_ci(metric: Metric, runs: Sequence[Sequence], *, strata: Sequence | None = None,
                 n_resamples: int = 2000, level: float = 0.95, seed: int = 0) -> CI:
    n = _check(runs)
    draw = _sampler(n, strata, np.random.default_rng(seed))
    reps = [_mean_over_runs(metric, runs, draw()) for _ in range(n_resamples)]
    return _interval(_mean_over_runs(metric, runs, None), reps, level, n_resamples, seed)


def paired_bootstrap_diff(metric: Metric, runs_a: Sequence[Sequence],
                          runs_b: Sequence[Sequence], *, ids_a: Sequence | None = None,
                          ids_b: Sequence | None = None, strata: Sequence | None = None,
                          n_resamples: int = 2000, level: float = 0.95, seed: int = 0) -> CI:
    n = _check(runs_a)
    if _check(runs_b) != n:
        raise ValueError("paired bootstrap needs the same items in A and B")
    if (ids_a is None) != (ids_b is None) or (ids_a is not None and list(ids_a) != list(ids_b)):
        raise ValueError("paired bootstrap: item ids of A and B differ or are not aligned")
    draw = _sampler(n, strata, np.random.default_rng(seed))
    reps = []
    for _ in range(n_resamples):
        idx = draw()
        reps.append(_mean_over_runs(metric, runs_a, idx) - _mean_over_runs(metric, runs_b, idx))
    point = _mean_over_runs(metric, runs_a, None) - _mean_over_runs(metric, runs_b, None)
    return _interval(point, reps, level, n_resamples, seed)


def is_marginal(ci: CI, threshold: float) -> bool:
    """CI crosses the gate threshold: shown as 'marginal', does not change pass/fail."""
    return ci.low <= threshold <= ci.high
