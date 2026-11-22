import pytest

from pome.eval.metrics import (
    language_gap,
    macro_f1,
    oos_precision_recall,
    proportion,
    run_mean,
)


def test_macro_f1_hand_computed():
    # a: P=1 R=.5 F=2/3 ; b: P=2/3 R=1 F=.8 ; macro = (2/3 + .8) / 2
    assert macro_f1(["a", "a", "b", "b"], ["a", "b", "b", "b"]) == pytest.approx(
        (2 / 3 + 0.8) / 2)


def test_macro_f1_averages_over_true_labels_only():
    # An invented label is an error for "b", not an extra zero-F1 class.
    assert macro_f1(["a", "b"], ["a", "zzz"]) == pytest.approx(0.5)


def test_macro_f1_explicit_label_set():
    assert macro_f1(["a"], ["a"], labels=["a", "b"]) == pytest.approx(0.5)


def test_macro_f1_rejects_length_mismatch_and_empty():
    with pytest.raises(ValueError):
        macro_f1(["a"], ["a", "b"])
    with pytest.raises(ValueError):
        macro_f1([], [])


def test_oos_precision_recall_hand_computed():
    p, r = oos_precision_recall(["oos", "oos", "x", "y"], ["oos", "x", "oos", "y"],
                                oos_label="oos")
    assert (p, r) == (pytest.approx(0.5), pytest.approx(0.5))


def test_oos_precision_is_zero_when_nothing_flagged():
    p, r = oos_precision_recall(["oos", "x"], ["x", "x"], oos_label="oos")
    assert (p, r) == (0.0, 0.0)


def test_oos_recall_requires_oos_items():
    with pytest.raises(ValueError):
        oos_precision_recall(["x"], ["x"], oos_label="oos")


def test_proportion():
    assert proportion([True, True, False, True]) == 0.75
    with pytest.raises(ValueError):
        proportion([])


def test_language_gap_is_english_minus_other():
    assert language_gap(0.90, 0.78) == pytest.approx(0.12)


def test_run_mean():
    assert run_mean([0.8, 0.82, 0.84]) == pytest.approx(0.82)
    with pytest.raises(ValueError):
        run_mean([])


def test_run_mean_and_gap_drop_float_noise_at_thresholds():
    assert run_mean([0.7, 0.8, 0.9]) == 0.8
    assert language_gap(0.8, 0.7) == 0.1


def test_metrics_accept_numpy_arrays():
    import numpy as np
    assert macro_f1(np.array(["a", "b"]), np.array(["a", "b"])) == 1.0
    assert proportion(np.array([True, False])) == 0.5
