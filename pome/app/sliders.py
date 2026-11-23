"""Vertical per-gate threshold sliders: a what-if input only (CLAUDE.md section 3).
Values live in the browser session; they never touch CONSTRAINTS.md or the profile file."""
from pathlib import Path

from streamlit.components.v1 import declare_component

from pome.profiles.loader import Profile

_component = declare_component(
    "gate_sliders", path=str(Path(__file__).parent / "components" / "gate_sliders"))

# slider range per unit: (min, max, step)
_RANGE = {"ratio": (0.50, 1.00, 0.01), "ratio_gap": (0.0, 0.30, 0.01),
          "ms": (1000, 60000, 1000), "req_per_s": (1, 50, 1)}


def slider_specs(profile: Profile, gates: list[str], label) -> list[dict]:
    """One spec per gate that has a number to move (yes/no gates get no slider)."""
    out = []
    for g in gates:
        gate = profile.gates[g]
        if gate.op == "required" or gate.unit not in _RANGE:
            continue
        lo, hi, step = _RANGE[gate.unit]
        out.append({"id": g, "label": label(g), "min": lo, "max": hi, "step": step,
                    "official": float(gate.value), "op": gate.op, "unit": gate.unit})
    return out


def gate_sliders(specs: list[dict], key: str) -> dict[str, float]:
    value = _component(gates=specs, key=key, default=None)
    return {k: float(v) for k, v in (value or {}).items()}
