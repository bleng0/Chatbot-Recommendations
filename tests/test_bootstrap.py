import random

import pytest

from pome.eval.bootstrap import bootstrap_ci, is_marginal, paired_bootstrap_diff
from pome.eval.metrics import macro_f1, proportion


def acc(items):
    return proportion(items)


def f1(items):
    t, p = zip(*items)
    return macro_f1(t, p)


def bern(n, p, seed):
    rng = random.Random(seed)
    return [rng.random() < p for _ in range(n)]


def test_same_seed_same_ci_and_different_seed_differs():
    runs = [bern(200, 0.8, s) for s in (1, 2, 3)]
    a = bootstrap_ci(acc, runs, seed=7, n_resamples=500)
    assert a == bootstrap_ci(acc, runs, seed=7, n_resamples=500)
    assert a != bootstrap_ci(acc, runs, seed=8, n_resamples=500)


def test_point_is_mean_of_per_run_metric_and_inside_ci():
    runs = [bern(200, 0.8, s) for s in (1, 2, 3)]
    ci = bootstrap_ci(acc, runs, seed=0, n_resamples=500)
    assert ci.point == pytest.approx(sum(proportion(r) for r in runs) / 3)
    assert ci.low <= ci.point <= ci.high
    assert ci.level == 0.95 and ci.n_resamples == 500 and ci.seed == 0


def test_constant_data_has_zero_width_ci():
    ci = bootstrap_ci(acc, [[True] * 50] * 3, seed=0, n_resamples=200)
    assert (ci.low, ci.point, ci.high) == (1.0, 1.0, 1.0)


def test_ci_width_matches_normal_approximation_for_a_proportion():
    # n=300, p~0.8: 95% half-width ~ 1.96*sqrt(.16/300) = 0.045
    ci = bootstrap_ci(acc, [bern(300, 0.8, 42)], seed=0, n_resamples=2000)
    assert 0.07 < ci.high - ci.low < 0.11


def test_works_with_macro_f1_items():
    run = [("a", "a"), ("a", "b"), ("b", "b"), ("b", "b")] * 10
    ci = bootstrap_ci(f1, [run, run], seed=0, n_resamples=200)
    assert ci.point == pytest.approx((2 / 3 + 0.8) / 2)


def test_runs_must_share_items():
    with pytest.raises(ValueError):
        bootstrap_ci(acc, [[True] * 5, [True] * 6])
    with pytest.raises(ValueError):
        bootstrap_ci(acc, [])


def test_paired_diff_identical_is_zero():
    runs = [bern(100, 0.7, s) for s in (1, 2, 3)]
    d = paired_bootstrap_diff(acc, runs, runs, seed=0, n_resamples=300)
    assert (d.low, d.point, d.high) == (0.0, 0.0, 0.0)


def test_paired_diff_all_right_vs_all_wrong_is_one():
    d = paired_bootstrap_diff(acc, [[True] * 40], [[False] * 40], seed=0, n_resamples=200)
    assert (d.low, d.point, d.high) == (1.0, 1.0, 1.0)


def test_paired_diff_requires_same_item_count():
    with pytest.raises(ValueError):
        paired_bootstrap_diff(acc, [[True] * 5], [[True] * 6])


def test_marginal_when_ci_crosses_threshold():
    ci = bootstrap_ci(acc, [bern(300, 0.8, 42)], seed=0, n_resamples=500)
    assert is_marginal(ci, ci.point)
    assert not is_marginal(ci, ci.high + 0.01)
    assert not is_marginal(ci, ci.low - 0.01)


def test_bias_corrected_ci_centres_small_class_macro_f1():
    # ~4 items/class: plain percentile CIs sit almost entirely below the point estimate.
    r = random.Random(0)
    labels = [f"l{i}" for i in range(77)]
    runs = [[(t, t if r.random() < 0.85 else r.choice(labels)) for t in (labels * 4)[:300]]
            for _ in range(3)]
    ci = bootstrap_ci(f1, runs, seed=0, n_resamples=400)
    assert ci.low < ci.point < ci.high
    assert 0.25 < (ci.point - ci.low) / (ci.high - ci.low) < 0.75


def test_stratified_resampling_keeps_every_class_and_centres_the_ci():
    r = random.Random(0)
    labels = [f"l{i}" for i in range(77)]
    truth = (labels * 4)[:300]
    runs = [[(t, t if r.random() < 0.85 else r.choice(labels)) for t in truth]
            for _ in range(3)]
    seen = []

    def spy(items):
        seen.append(len({t for t, _ in items}))
        return f1(items)

    ci = bootstrap_ci(spy, runs, strata=truth, seed=0, n_resamples=200)
    assert set(seen) == {77}
    assert 0.3 < (ci.point - ci.low) / (ci.high - ci.low) < 0.7


def test_strata_length_must_match_items():
    with pytest.raises(ValueError):
        bootstrap_ci(acc, [[True] * 5], strata=["a"] * 4)


def test_paired_diff_refuses_misaligned_item_ids():
    with pytest.raises(ValueError):
        paired_bootstrap_diff(acc, [[True, False]], [[True, False]],
                              ids_a=["u1", "u2"], ids_b=["u2", "u1"])
    d = paired_bootstrap_diff(acc, [[True, False]], [[True, False]],
                              ids_a=["u1", "u2"], ids_b=["u1", "u2"], n_resamples=50)
    assert d.point == 0.0
