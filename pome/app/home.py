"""POME decision-support app. Run: uv run streamlit run pome/app/home.py

Replays recorded evaluation results (runs/records); never calls an LLM API.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pome.app.scenario import GPU_OPTIONS, SELFHOST, Scenario, breakeven_tickets, decide
from pome.app.views import cost_curves, evidence_rows, gate_matrix, status_label
from pome.profiles.loader import load_profile
from pome.registry.loader import load_registry

# Categorical slots validated for colour-vision deficiency (dataviz validate_palette.js, light).
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]

st.set_page_config(page_title="POME: model and hosting selection", layout="wide")
profile = load_profile()
registry = {c.config_id: c for c in load_registry()}

with st.sidebar:
    st.header("Scenario")
    volume = st.slider("Tickets per month", 10_000, 1_000_000, profile.volume_tickets_per_month,
                       step=10_000, format="%d")
    gpu = st.selectbox("Self-host GPU (India price)", list(GPU_OPTIONS),
                       format_func=lambda k: GPU_OPTIONS[k].label)
    st.caption(GPU_OPTIONS[gpu].note)
    gpus = st.number_input("GPUs (assumption, not load-tested)", 1, 8, 1)
    ops = st.number_input("Self-host ops cost, USD/month (owner input)", 0.0, 50_000.0, 0.0,
                          step=100.0)
    if ops == 0:
        st.warning("Ops cost is $0: set it for a realistic self-host total.")

scenario = Scenario(volume=int(volume), gpu=gpu, gpus=int(gpus), ops_monthly_usd=float(ops))
snap, d = decide(scenario)

st.title("Which model and hosting option should a bank's support bot use?")
st.info("Replaying recorded evaluation results. No live API calls are made. "
        "Every number shows its provenance: MEASURED (we ran it), VENDOR-DOC (published by "
        "the provider), MODELED (formula with cited inputs).")

st.subheader("Recommendation")
if d.recommended:
    v = next(x for x in d.verdicts if x.config_id == d.recommended)
    c1, c2, c3 = st.columns(3)
    c1.metric("Recommended configuration", d.recommended)
    c2.metric("Monthly cost (MODELED)", f"${v.monthly_cost:,.2f}")
    c3.metric("Status", status_label(v.status))
    if v.not_tested:
        st.caption(f"Proof of concept: {', '.join(v.not_tested)} not load-tested.")
else:
    st.error("No feasible option: no configuration passes every gate with the evidence "
             "recorded so far. See the gate matrix for what is missing or failing.")
st.caption(f"Decision hash {d.decision_hash[:16]}…  ·  snapshot {d.snapshot_sha256[:16]}…  ·  "
           f"same inputs always give the same hash.")

tab_gates, tab_cost, tab_ev, tab_cfg = st.tabs(
    ["Gate matrix", "Cost and break-even", "Evidence", "Configurations"])

with tab_gates:
    st.dataframe(pd.DataFrame(gate_matrix(d)), hide_index=True, width="stretch")
    st.caption("✓ pass · ✗ fail · ? unverified (evidence missing or below 15 items) · "
               "– not tested (no load test; does not block). G12/G13 are not part of this "
               "proof-of-concept profile.")
    for v in d.verdicts:
        if v.reasons:
            with st.expander(f"{v.config_id}: {status_label(v.status)}"):
                for r in v.reasons:
                    st.write("- " + r)

with tab_cost:
    points = sorted({10_000, *range(50_000, 1_000_001, 50_000), int(volume)})
    curves = cost_curves(snap, volume=int(volume), points=points)
    if not curves:
        st.write("No configuration has a cost yet (needs measured tokens and a price).")
    else:
        fig = go.Figure()
        for i, (cid, ys) in enumerate(curves.items()):
            color = SERIES[i % len(SERIES)]
            fig.add_trace(go.Scatter(x=points, y=ys, mode="lines", name=cid,
                                     line={"width": 2, "color": color},
                                     hovertemplate="%{x:,} tickets: $%{y:,.0f}<extra>"
                                     + cid + "</extra>"))
            fig.add_annotation(x=points[-1], y=ys[-1], text=cid, showarrow=False,
                               xanchor="left", font={"size": 11})
        budget = float(profile.gates["G11"].value)
        fig.add_hline(y=budget, line={"dash": "dash", "width": 1, "color": "#888"},
                      annotation_text=f"G11 budget ${budget:,.0f}")
        fig.add_vline(x=int(volume), line={"width": 1, "color": "#bbb"},
                      annotation_text="selected volume")
        fig.update_layout(height=420, margin={"r": 180, "t": 30},
                          xaxis_title="Tickets per month", yaxis_title="USD per month (MODELED)",
                          hovermode="x unified", legend={"orientation": "h", "y": -0.2})
        fig.update_yaxes(rangemode="tozero", gridcolor="#eee")
        fig.update_xaxes(gridcolor="#eee")
        st.plotly_chart(fig, width="stretch")
        sh = snap.values.get(f"{SELFHOST}.cost.monthly_usd")
        for cid in curves:
            if cid == SELFHOST or sh is None:
                continue
            per_ticket = float(snap.values[f"{cid}.cost.monthly_usd"].value) / int(volume)
            be = breakeven_tickets(api_cost_per_ticket=per_ticket,
                                   selfhost_monthly=float(sh.value))
            if be:
                st.write(f"**{cid}** vs self-host: self-host is cheaper above "
                         f"**{be:,} tickets/month** (MODELED; API ${per_ticket:.6f}/ticket, "
                         f"self-host ${float(sh.value):,.0f}/month fixed).")
        st.dataframe(pd.DataFrame({"tickets": points, **curves}), hide_index=True)

with tab_ev:
    rows = evidence_rows(snap)
    prov = st.multiselect("Provenance", ["MEASURED", "VENDOR-DOC", "MODELED"],
                          default=["MEASURED", "VENDOR-DOC", "MODELED"])
    st.dataframe(pd.DataFrame([r for r in rows if r["provenance"] in prov]), hide_index=True,
                 width="stretch")

with tab_cfg:
    st.dataframe(pd.DataFrame([{
        "config": c.config_id, "model": c.model_id, "host": c.host, "region": c.region,
        "serving": c.serving, "quant": c.quant, "mode": c.evaluation_mode, "notes": c.notes,
    } for c in registry.values()]), hide_index=True, width="stretch")
