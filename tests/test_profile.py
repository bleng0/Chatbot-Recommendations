import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from pome.profiles.loader import load_profile, profile_hash

ROOT = Path(__file__).resolve().parent.parent
GATE_ROW = re.compile(r"^\|\s*(G\d+)\s*\|(.*)$")


def constraints_section_a():
    """gate id -> (op, value) parsed from the Threshold column of CONSTRAINTS.md section A."""
    out = {}
    for line in (ROOT / "CONSTRAINTS.md").read_text(encoding="utf-8").splitlines():
        m = GATE_ROW.match(line)
        if not m:
            continue
        cells = [c.strip() for c in m.group(2).split("|")]
        threshold = cells[1]  # cells: gate, threshold, evidence, why
        if threshold.lower().startswith("required"):
            out[m.group(1)] = ("required", True)
            continue
        op = re.search(r"([≥≤])", threshold).group(1)
        num = re.search(r"[≥≤]\s*\$?([\d,]+(?:\.\d+)?)", threshold).group(1).replace(",", "")
        out[m.group(1)] = (">=" if op == "≥" else "<=", float(num))
    return out


def test_profile_gates_equal_constraints_md_section_a():
    expected = constraints_section_a()
    assert len(expected) == 12  # G12, G13 dropped for the proof of concept
    profile = load_profile()
    assert set(profile.gates) == set(expected)
    for gid, (op, val) in expected.items():
        g = profile.gates[gid]
        assert (g.op, float(g.value) if op != "required" else g.value) == (op, val), gid


def test_profile_basics():
    p = load_profile()
    assert p.name == "banking_mvp"
    assert p.volume_tickets_per_month == 100_000
    assert p.peak_rps == 5  # owner 2026-11-23 (was 8)
    assert p.region == "India"
    assert p.languages == ["en", "hi", "hinglish"]


def test_profile_hash_is_stable_and_sensitive():
    a, b = load_profile(), load_profile()
    assert profile_hash(a) == profile_hash(b)
    changed = a.model_copy(update={"peak_rps": 9})
    assert profile_hash(changed) != profile_hash(a)


def test_loading_a_profile_with_unknown_field_fails(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("name: x\nsurprise: 1\n")
    with pytest.raises(ValidationError):
        load_profile(p)
