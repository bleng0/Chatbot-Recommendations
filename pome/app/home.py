"""POME decision-support app. Run: uv run python -m streamlit run pome/app/home.py

Replays recorded evaluation results (runs/records); never calls an LLM API.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pome.app import render
from pome.app.scenario import (
    GPU_OPTIONS,
    SELFHOST,
    Scenario,
    breakeven_tickets,
    decide,
    decide_what_if,
)
from pome.app.views import (
    SHOWN_GATES,
    USD_INR,
    answer_line,
    architecture_steps,
    cost_curves,
    display_gate,
    evidence_rows,
    gate_info_rows,
    gate_matrix,
    inr,
    relabel,
    status_label,
    variant_rows,
)
from pome.profiles.loader import load_profile, what_if_profile
from pome.registry.loader import load_registry

st.set_page_config(page_title="Model and hosting selection", layout="wide")
T = render.TOKENS["light"]
st.html(render.css("light"))

profile = load_profile()
registry = load_registry()
by_id = {c.config_id: c for c in registry}
# G10 (error limit) and G11 (budget) are sidebar settings; the rest are gates, numbered 1-10
GATES = SHOWN_GATES
RATE = float(USD_INR.value)

with st.sidebar:
    st.header("Scenario")
    volume = st.slider("Tickets per month", 10_000, 10_000_000,
                       profile.volume_tickets_per_month, step=10_000, format="%d")
    st.caption("1 ticket = 1 customer question.")
    max_spend_inr = st.number_input(
        "Max monthly spend, INR", 0, 10_00_00_000,
        round(float(profile.gates["G11"].value) * RATE), step=5_000,
        help="Configs costing more are rejected.")
    max_error = st.number_input(
        "Max error rate after retries, %", 0.0, 100.0, float(profile.gates["G10"].value),
        step=0.1, format="%.1f", help="Configs failing more requests are rejected.")
    gpu = st.selectbox("Self-host GPU (India price)", list(GPU_OPTIONS),
                       format_func=lambda k: GPU_OPTIONS[k].label)
    st.caption(GPU_OPTIONS[gpu].note)
    gpus = st.number_input("GPUs", 1, 64, 1, help="GPUs rented for self-hosting.")
    ops_inr = st.number_input("Self-host ops cost, INR/month", 0, 10_00_00_000, 0,
                              step=10_000, help="Staff and tooling to run your own GPUs.")
    ops = float(ops_inr) / float(USD_INR.value)
    st.header("Tweak mode")
    kept = st.pills("Gates to check against", GATES, selection_mode="multi", default=GATES,
                    format_func=display_gate, help="Off = what-if view; official result unchanged.")
    st.caption("Click a gate to switch it off.")
    off = tuple(g for g in GATES if g not in (kept or []))

default_usd = float(profile.gates["G11"].value)
# the default INR budget maps back to the exact banking_mvp value, so the official hash holds
max_spend_usd = (default_usd if max_spend_inr == round(default_usd * RATE)
                 else float(max_spend_inr) / RATE)
scenario = Scenario(volume=int(volume), gpu=gpu, gpus=int(gpus), ops_monthly_usd=float(ops),
                    max_spend_usd=max_spend_usd, max_error_pct=float(max_error))
snap, d = decide(scenario)
wi = decide_what_if(snap, scenario, off) if off else None

st.title("Which model and hosting should a bank's support bot use?")
st.html(f'<p class="note">{render.icon("info")}Replaying recorded evaluation results. No live '
        f'API calls are made. Every number carries its provenance badge.</p>')
st.html(render.answer(relabel(answer_line(d, snap, profile)), recommended=bool(d.recommended)))
counts = [("configurations", len(d.verdicts)),
          ("eligible" if any(v.status == "eligible" for v in d.verdicts)
           else "eligible (modeled)", sum(v.status.startswith("eligible") for v in d.verdicts)),
          ("rejected", sum(v.status == "rejected" for v in d.verdicts)),
          ("gates checked", len(GATES))]
st.html(render.stats(counts))
st.html(f'<p class="hash">decision {d.decision_hash[:12]}… · snapshot '
        f'{d.snapshot_sha256[:12]}… · profile banking_mvp · same inputs, same hash</p>')

if wi:
    names = ", ".join(display_gate(g) for g in off)
    st.html(f'<div class="wi"><h3>What-if ({names} off): <span class="muted">not the official '
            f'decision</span></h3>'
            + render.answer(relabel(answer_line(wi, snap, what_if_profile(profile, off))),
                            recommended=bool(wi.recommended), what_if=True)
            + f'<p class="hash">what-if decision {wi.decision_hash[:12]}… · thresholds of the '
              f'gates kept are unchanged</p></div>')

ids = {c.config_id for c in registry}

tab_gates, tab_info, tab_cost, tab_ev, tab_var, tab_cfg = st.tabs(
    ["Gates", "Gate information", "Cost", "Evidence", "Deployment variants", "Configurations"])

with tab_info:
    st.html(render.gate_info_table(gate_info_rows(profile)))

with tab_gates:
    rows = [r for r in gate_matrix(d) if r["config"] in ids]
    wi_status = {v.config_id: v.status for v in wi.verdicts} if wi else None
    budget_usd = max_spend_usd
    cost_cells = {k.split(".", 1)[0]: (inr(float(e.value)), float(e.value) > budget_usd)
                  for k, e in snap.values.items() if k.endswith(".cost.monthly_usd")}
    st.html(render.gate_table(rows, GATES, set(off), wi_status, cost=cost_cells,
                              labels={g: display_gate(g) for g in GATES}))
    no_ev = sorted(ids - {r["config"] for r in rows})
    if no_ev:
        st.html(f'<p class="one">No evidence recorded yet: {", ".join(no_ev)}</p>')
    st.caption("Failing first, then missing evidence, then passing. Unverified: evidence missing "
               "or under 15 scored items. Not tested: no load test run; does not block.")
    for v in d.verdicts:
        if v.config_id in ids and v.reasons:
            with st.expander(f"{v.config_id}: {status_label(v.status)}"):
                st.markdown("\n".join(f"- {relabel(r)}" for r in v.reasons))

with tab_cost:
    costs = {k.split(".", 1)[0]: e for k, e in snap.values.items()
             if k.endswith(".cost.monthly_usd") and k.split(".", 1)[0] in ids}
    if not costs:
        st.write("No configuration has a cost yet.")
    else:
        budget = float(max_spend_inr)
        items = sorted(costs.items(), key=lambda kv: float(kv[1].value))
        names_ = [cid for cid, _ in items]
        vals = [float(e.value) * RATE for _, e in items]
        colors = [T["coral"] if v > budget else T["line"] if v == 0 else T["teal"]
                  for v in vals]
        fig = go.Figure(go.Bar(
            x=vals, y=names_, orientation="h", marker={"color": colors, "cornerradius": 4},
            text=[inr(v / RATE) + (" over budget" if v > budget else "") for v in vals],
            textposition="outside", cliponaxis=False,
            hovertemplate="%{y}: ₹%{x:,.0f}/month (MODELED)<extra></extra>"))
        fig.add_vline(x=budget, line={"dash": "dash", "width": 1.5, "color": T["coral"]},
                      annotation_text=f"Your max spend {inr(budget / RATE)}",
                      annotation_position="top", annotation_font_color=T["coraltext"])
        fig.update_layout(
            height=60 + 34 * len(vals), margin={"l": 10, "r": 90, "t": 36, "b": 30},
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", bargap=0.35,
            font={"family": "Fira Sans, sans-serif", "color": T["text"], "size": 13},
            xaxis={"title": f"INR per month at {int(volume):,} tickets (MODELED)",
                   "gridcolor": T["line"], "zeroline": False, "linecolor": T["grey"],
                   "tickfont": {"color": T["muted"]}, "tickprefix": "₹",
                   "range": [0, max(budget, *vals) * 1.18]},
            yaxis={"autorange": "reversed",
                   "tickfont": {"family": "Fira Code, monospace", "color": T["muted"]}},
            hoverlabel={"font": {"family": "Fira Sans, sans-serif", "color": T["text"]},
                        "bgcolor": T["panel"], "bordercolor": T["teal"]})
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        sh = snap.values.get(f"{SELFHOST}.cost.monthly_usd")
        for cid in names_:
            if cid == SELFHOST or sh is None:
                continue
            per_ticket = float(costs[cid].value) / int(volume)
            be = breakeven_tickets(api_cost_per_ticket=per_ticket,
                                   selfhost_monthly=float(sh.value))
            if be:
                st.markdown(f"`{cid}` vs self-host: self-host is cheaper above **{be:,} tickets"
                            f"/month** (MODELED; API {inr(per_ticket, 4)}/ticket, self-host "
                            f"{inr(float(sh.value))}/month fixed).")
        with st.expander("Cost at other volumes (table)"):
            points = sorted({10_000, *range(100_000, 1_000_001, 100_000), int(volume)})
            curves = {k: v for k, v in cost_curves(snap, volume=int(volume),
                                                   points=points).items() if k in ids}
            inr_curves = {k: [round(v * RATE) for v in vs] for k, vs in curves.items()}
            st.caption("INR per month")
            st.dataframe(pd.DataFrame({"tickets": points, **inr_curves}), hide_index=True)

with tab_ev:
    st.html(render.evidence_table([r for r in evidence_rows(snap) if r["config"] in ids]))

with tab_var:
    shown = [c for c in registry if c.config_id in ids and c.variants]
    if not shown:
        st.write("No open-weight model lists published deployment settings.")
    for c in shown:
        rows = variant_rows(c)
        cost = snap.values.get(f"{c.config_id}.cost.monthly_usd")
        cost_txt = (f" · modeled cost {inr(float(cost.value))}/month {render.badge('MODELED')}"
                    if cost else " · no modeled monthly cost yet")
        if not any(r["figure"] for r in rows):
            st.html(f'<p class="one"><code>{c.config_id}</code>: {len(rows)} published '
                    f'settings, none with a figure{cost_txt}</p>')
            continue
        st.html(f'<h3 class="vh"><code>{c.config_id}</code>{cost_txt}</h3>'
                + render.variant_table(rows))

with tab_cfg:
    status = {v.config_id: v.status for v in d.verdicts}
    order = [r["config"] for r in gate_matrix(d)]
    gpu_label = GPU_OPTIONS[gpu].label + (f" x{int(gpus)}" if int(gpus) > 1 else "")
    fan_items = []
    for cid in order:
        c = by_id[cid]
        cost = snap.values.get(f"{cid}.cost.monthly_usd")
        fan_items.append({
            "config": cid, "model": c.model_id, "host": c.host.split(" (")[0],
            "status": status[cid], "cost": f"{inr(float(cost.value))}/mo" if cost else "—",
            "steps": architecture_steps(c, gpu=gpu_label)})
    st.caption("Scroll or use the arrows; the card in the middle shows its build steps.")
    st.html(render.config_fan(fan_items, focus=d.recommended or order[0]),
            unsafe_allow_javascript=True)
    with st.expander("All configuration details (table)"):
        st.dataframe(pd.DataFrame([{
            "config": c.config_id, "model": c.model_id, "host": c.host, "region": c.region,
            "serving": c.serving, "quant": c.quant, "mode": c.evaluation_mode, "notes": c.notes,
        } for c in registry if c.config_id in ids]), hide_index=True, width="stretch")

st.html(f'<p class="foot">All costs are shown in INR. Conversion: US$1 = '
        f'₹{RATE:.4f} (RBI reference rate, {USD_INR.retrieved_at.date().isoformat()}). '
        f'Prices published in USD were converted at this rate.</p>')

# Last element, so the rows and answers above exist when the motion script runs.
st.html(render.MOTION, unsafe_allow_javascript=True)
