"""Turn the pinned sample files (slice 5) into runner items, label sets and bootstrap strata.

- banking77: 77 labels, out_of_scope offered (production ticket prompt, SPEC A4); an OOS
  answer scores as wrong. Strata = gold label.
- clinc150: label set = the 150 in-scope intents in the sample, out_of_scope offered;
  dataset label "oos" becomes out_of_scope. Strata = in-scope intent or "oos".
- massive_en / massive_hi: same utterance ids, same order (paired bootstrap for G6);
  no OOS option. Strata = gold label.
head=N (dry runs) keeps the first N items; for clinc150 half OOS, half in-scope.
"""
import json
from dataclasses import dataclass
from pathlib import Path

from pome.eval.runner import Item
from pome.eval.tasks import OOS

DATA = Path(__file__).resolve().parent.parent / "data"
TASKS = ("banking77", "clinc150", "massive_en", "massive_hi")


@dataclass(frozen=True)
class Task:
    name: str
    items: list[Item]
    labels: list[str]
    allow_oos: bool
    strata: list[str]


def _rows(name: str) -> list[dict]:
    return [json.loads(x) for x in (DATA / name).read_text(encoding="utf-8").splitlines() if x]


def load_task(name: str, head: int | None = None) -> Task:
    if name == "banking77":
        rows = _rows("banking77.jsonl")[:head]
        items = [Item(r["id"], r["text"], r["label"]) for r in rows]
        labels = sorted({r["label"] for r in _rows("banking77.jsonl")})
        return Task(name, items, labels, True, [i.label for i in items])
    if name == "clinc150":
        rows = _rows("clinc150.jsonl")
        labels = sorted({r["label"] for r in rows if not r["is_oos"]})
        if head is not None:
            rows = ([r for r in rows if r["is_oos"]][: head // 2]
                    + [r for r in rows if not r["is_oos"]][: head - head // 2])
        items = [Item(r["id"], r["text"], OOS if r["is_oos"] else r["label"]) for r in rows]
        return Task(name, items, labels, True, ["oos" if r["is_oos"] else r["label"] for r in rows])
    if name in ("massive_en", "massive_hi"):
        rows = _rows("massive.jsonl")
        labels = sorted({r["label"] for r in rows})
        en = sorted((r for r in rows if r["locale"] == "en-US"), key=lambda r: r["id"])
        by_id = {r["id"]: r for r in rows if r["locale"] == "hi-IN"}
        chosen = (en if name == "massive_en" else [by_id[r["id"]] for r in en])[:head]
        items = [Item(r["id"], r["text"], r["label"]) for r in chosen]
        return Task(name, items, labels, False, [i.label for i in items])
    raise ValueError(f"unknown task {name!r}; expected one of {TASKS}")
