import pytest

from pome.eval.tasks import INVALID, OOS, intent_prompt, parse_label, prompt_sha256


def test_prompt_lists_every_label_and_oos_when_allowed():
    p = intent_prompt("where is my card?", ["card_arrival", "lost_card"], allow_oos=True)
    assert "card_arrival" in p and "lost_card" in p and OOS in p
    assert "where is my card?" in p
    assert OOS not in intent_prompt("x", ["a"], allow_oos=False)


def test_prompt_is_deterministic_and_hashable():
    a = intent_prompt("x", ["b", "a"], allow_oos=True)
    assert a == intent_prompt("x", ["a", "b"], allow_oos=True)  # labels sorted
    assert len(prompt_sha256(a)) == 64


@pytest.mark.parametrize("raw,expected", [
    ('{"label": "lost_card"}', "lost_card"),
    ('```json\n{"label": "lost_card"}\n```', "lost_card"),
    ('Sure! {"label":"out_of_scope"}', OOS),
    ('{"label": "made_up"}', INVALID),
    ("lost_card", INVALID),
    ("", INVALID),
    ('{"label": 3}', INVALID),
])
def test_parse_label(raw, expected):
    assert parse_label(raw, ["lost_card", "card_arrival"], allow_oos=True) == expected


def test_oos_is_invalid_when_not_allowed():
    assert parse_label('{"label": "out_of_scope"}', ["a"], allow_oos=False) == INVALID
