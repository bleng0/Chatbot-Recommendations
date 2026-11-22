"""Fixed intent-classification prompt (PLAN F3) and a lenient JSON label parser.

Labels are sorted so the prompt, and therefore its cache key, does not depend on input
order. Any reply that is not one of the offered labels parses to INVALID (scored as wrong).
"""
import hashlib
import json
import re
from collections.abc import Sequence

OOS = "out_of_scope"
INVALID = "__invalid__"
_OBJ = re.compile(r"\{[^{}]*\}")


def intent_prompt(text: str, labels: Sequence[str], *, allow_oos: bool) -> str:
    options = sorted(labels) + ([OOS] if allow_oos else [])
    oos_rule = f'If the message matches none of the intents, answer "{OOS}".\n' if allow_oos else ""
    return ("You are an intent classifier for a bank's customer-care assistant.\n"
            "Choose exactly one intent for the customer message from this list:\n"
            + "\n".join(options) + "\n" + oos_rule
            + 'Reply with JSON only, in the form {"label": "<intent>"}.\n\n'
            + f"Customer message: {text}")


def prompt_sha256(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def parse_label(raw: str, labels: Sequence[str], *, allow_oos: bool) -> str:
    match = _OBJ.search(raw or "")
    if not match:
        return INVALID
    try:
        label = json.loads(match.group(0)).get("label")
    except (json.JSONDecodeError, AttributeError):
        return INVALID
    if isinstance(label, str) and (label in labels or (allow_oos and label == OOS)):
        return label
    return INVALID
