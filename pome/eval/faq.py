"""FAQ scoring (G4, G5). Pure.

Gold is an approved-answer id (F01..) or NONE for a question no approved answer covers.
correct = share of answerable items where the predicted id equals the gold id (G4).
decline = share of unanswerable items where the model answered NONE (G5).
Per-language gaps (G6, G7) use metrics.language_gap on these two numbers.
"""
from collections.abc import Sequence

from pome.eval.metrics import proportion
from pome.eval.tasks import NONE


def faq_scores(gold: Sequence[str], pred: Sequence[str]) -> tuple[float, float]:
    if len(gold) != len(pred):
        raise ValueError(f"length mismatch: {len(gold)} gold vs {len(pred)} predicted")
    ans = [(g, p) for g, p in zip(gold, pred, strict=True) if g != NONE]
    una = [(g, p) for g, p in zip(gold, pred, strict=True) if g == NONE]
    if not ans or not una:
        raise ValueError("need both answerable and unanswerable items")
    return proportion([g == p for g, p in ans]), proportion([p == NONE for _, p in una])
