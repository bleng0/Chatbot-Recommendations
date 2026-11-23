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


def slider_specs(profile: Profile, gates: list[str], label, short: dict[str, str] | None = None
                 ) -> list[dict]:
    """One spec per gate that has a number to move (yes/no gates get no slider)."""
    out = []
    for g in gates:
        gate = profile.gates[g]
        if gate.op == "required" or gate.unit not in _RANGE:
            continue
        lo, hi, step = _RANGE[gate.unit]
        out.append({"id": g, "label": label(g), "short": (short or {}).get(g, ""), "min": lo, "max": hi, "step": step,
                    "official": float(gate.value), "op": gate.op, "unit": gate.unit})
    return out


def gate_sliders(specs: list[dict], table_html: str, css: str, key: str) -> dict[str, float]:
    """The gate table with one vertical slider in each gate column's header."""
    import streamlit as st
    prev = st.session_state.get(key) or {}
    value = _component(gates=specs, table=table_html, css=css, value=prev, key=key, default=None)
    return {k: float(v) for k, v in (value or {}).items()}


def current(key: str) -> dict[str, float]:
    """Slider values from the last interaction, read before the table is built."""
    import streamlit as st
    return {k: float(v) for k, v in (st.session_state.get(key) or {}).items()}
