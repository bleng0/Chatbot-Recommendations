"""Quality metrics (CONSTRAINTS A, G1-G7). Pure functions, no I/O.

macro_f1: unweighted mean F1 over the TRUE label set (or `labels` if given). A predicted
  label outside that set counts as an error for the true class, not as an extra class.
oos_precision_recall: out-of-scope is the positive class (G2 recall, G3 precision).
  Precision is 0.0 when nothing is flagged OOS (fail-safe for the gate).
proportion: share of True flags (FAQ correctness G4, decline rate G5).
language_gap: english - other (G6, G7; positive means the other language is worse).
run_mean: mean point estimate over runs (gates compare this, CONSTRAINTS A).
run_mean and language_gap round to 9 decimals (as selection/engine.py does for gaps), so
float noise like 0.7999999999999999 cannot flip a gate at its threshold.
"""
import math
from collections.abc import Sequence

from sklearn.metrics import f1_score


def _pair(y_true: Sequence, y_pred: Sequence) -> None:
    if len(y_true) != len(y_pred):
        raise ValueError(f"length mismatch: {len(y_true)} true vs {len(y_pred)} predicted")
    if len(y_true) == 0:
        raise ValueError("no items")


def macro_f1(y_true: Sequence[str], y_pred: Sequence[str],
             labels: Sequence[str] | None = None) -> float:
    _pair(y_true, y_pred)
    labels = sorted(set(y_true)) if labels is None else list(labels)
    return float(f1_score(list(y_true), list(y_pred), labels=labels,
                          average="macro", zero_division=0))


def oos_precision_recall(y_true: Sequence[str], y_pred: Sequence[str], *,
                         oos_label: str) -> tuple[float, float]:
    _pair(y_true, y_pred)
    tp = sum(t == oos_label and p == oos_label for t, p in zip(y_true, y_pred))
    flagged = sum(p == oos_label for p in y_pred)
    actual = sum(t == oos_label for t in y_true)
    if actual == 0:
        raise ValueError(f"no '{oos_label}' items: recall is undefined")
    return (tp / flagged if flagged else 0.0), tp / actual


def proportion(flags: Sequence[bool]) -> float:
    if len(flags) == 0:
        raise ValueError("no items")
    return sum(bool(f) for f in flags) / len(flags)


def language_gap(english: float, other: float) -> float:
    return round(english - other, 9)


def run_mean(values: Sequence[float]) -> float:
    if len(values) == 0:
        raise ValueError("no runs")
    return round(math.fsum(values) / len(values), 9)
