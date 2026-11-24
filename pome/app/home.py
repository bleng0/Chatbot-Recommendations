"""POME decision-support app. Run: uv run python -m streamlit run pome/app/home.py

Replays recorded evaluation results (runs/records); never calls an LLM API.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pome.app import cost_charts, render
from pome.app.hosting_controls import owned_plans, rented_plans
from pome.app.scenario import (
    GPU_OPTIONS,
    SERVING_METRICS,
    Scenario,
    decide,
    decide_sliders,
)
from pome.app.sliders import current, gate_sliders, slider_specs
from pome.app.views import (
    SHORT_NAME,
    SHOWN_GATES,
    USD_INR,
    answer_line,
    architecture_steps,
    baselines,
    cost_curves,
    display_gate,
    evidence_sections,
    gate_info_rows,
    gate_matrix,
    gate_values,
    indian,
    inr,
    relabel,
    status_label,
    tickets_options,
    variant_rows,
    what_if_pick,
)
from pome.profiles.loader import load_profile, what_if_profile
from pome.registry.hosting import HOSTING, OWNED, RESPONSIBILITY, owned_config
from pome.registry.loader import load_registry

st.set_page_config(page_title="Model and hosting selection", layout="wide")
T = render.TOKENS["light"]
st.html(render.css("light"))

profile = load_profile()
catalog = load_registry() + [owned_config(preset) for preset in OWNED.values()]
# G10 (error limit) and G11 (budget) are sidebar settings; the rest are gates, numbered 1-10
GATES = SHOWN_GATES
RATE = float(USD_INR.value)

with st.sidebar:
    st.header("Scenario")
    volume = st.select_slider("Tickets per month", tickets_options(),
                              value=profile.volume_tickets_per_month, format_func=indian)
    st.caption("1 ticket = 1 customer question.")
    max_spend_inr = st.number_input(
        "Max monthly spend, INR", 0, 10_00_00_000,
        round(float(profile.gates["G11"].value) * RATE), step=5_000,
        help="Configs costing more are rejected.")
    max_error = st.number_input(
        "Max error rate after retries, %", 0.0, 100.0, float(profile.gates["G10"].value),
        step=0.1, format="%.1f", help="Configs failing more requests are rejected.")
    scope = st.radio("Hosting scope", list(HOSTING), format_func=HOSTING.get)
    with st.expander("Rented cloud GPU"):
        gpu = st.selectbox("Rental machine", list(GPU_OPTIONS),
                           format_func=lambda k: GPU_OPTIONS[k].label)
        st.caption(GPU_OPTIONS[gpu].note)
        gpus = st.number_input("Rental nodes", 1, 64, 1,
                               help="Number of whole rental machines, including bundled GPUs.")
        ops_inr = st.number_input("Rented GPU operations, ₹/month", 0, 10_00_00_000, 0,
                                  step=10_000)
        plans = rented_plans(catalog, gpu, gpus, ops_inr, RATE)
    st.subheader("Owned self-hosting")
    plans.update(owned_plans())
    ops = float(ops_inr) / RATE
    st.header("Tweak mode")
    st.caption("Switch a gate off to see a what-if view; the recommendation is unchanged.")
    info = dict(zip(GATES, gate_info_rows(profile), strict=True))
    off = tuple(g for g, row in info.items()
                if not st.toggle(f"{row['gate']} · {SHORT_NAME[g]}", value=True, key=f"gate_{g}",
                                 help=f"{row['checks']}. Passes if {row['pass_if']}."))

default_usd = float(profile.gates["G11"].value)
# the default INR budget maps back to the exact banking_mvp value, so the decision hash holds
max_spend_usd = (default_usd if max_spend_inr == round(default_usd * RATE)
                 else float(max_spend_inr) / RATE)
scenario = Scenario(volume=int(volume), gpu=gpu, gpus=int(gpus), ops_monthly_usd=float(ops),
                    max_spend_usd=max_spend_usd, max_error_pct=float(max_error))
snap, d = decide(scenario, registry=catalog, deployment_plans=plans,
                 scope=scope, inr_per_usd=RATE)
registry = [c for c in catalog if scope == "all" or scope == c.hosting_kind]
by_id = {c.config_id: c for c in registry}


def hosting_label(cid: str) -> str:
    cfg = by_id[cid]
    return HOSTING[cfg.hosting_kind] + (" · lab only" if cfg.lab_only else "")


def readiness(cid: str) -> str:
    cfg = by_id[cid]
    if cfg.hosting_kind == "api":
        return "Provider-operated"
    plan = plans.get(cid)
    if plan is None:
        return "Lab evidence only"
    if plan.minimum_gb is not None and plan.vram_gb < plan.minimum_gb:
        return "Does not fit"
    if all(f"{cid}.{metric}" in snap.values for metric in SERVING_METRICS):
        return "Serving evidence available"
    return "Planning only · needs validation"



st.html('<h1 class="q">Which <span class="k">model</span> and <span class="k">hosting plan</span> '
        'should you use?</h1>')
for column, kind in zip(st.columns(3), RESPONSIBILITY, strict=True):
    column.markdown(f"**{HOSTING[kind]}**")
    column.caption(RESPONSIBILITY[kind])
st.caption(f"Comparing {HOSTING[scope].lower()}.")

passing = sum(v.status.startswith("eligible") for v in d.verdicts)
if d.recommended:
    rec_cfg, rec_v = by_id[d.recommended], next(v for v in d.verdicts
                                                if v.config_id == d.recommended)
    st.html(render.answer_card(
        model=rec_cfg.model_id, config=d.recommended,
        host=f"{hosting_label(rec_cfg.config_id)} · {rec_cfg.host}", region=rec_cfg.region.split(" (")[0],
        cost="no cost evidence" if rec_v.monthly_cost is None else inr(rec_v.monthly_cost),
        modeled=rec_v.monthly_cost is not None, passing=passing, total=len(d.verdicts),
        decision_hash=d.decision_hash[:12],
        source="From published vendor data" if d.recommended_is_modeled else ""))
else:
    st.html(render.answer(relabel(answer_line(d, snap, profile)), recommended=False))
    st.html(render.stats([("configurations", len(d.verdicts)),
                          ("rejected", sum(v.status == "rejected" for v in d.verdicts))]))
    st.html(f'<p class="hash">decision {d.decision_hash[:12]}… · same inputs, same hash</p>')

wi_box = st.container()  # filled once the sliders in the Gates tab are read

ids = {c.config_id for c in registry}

tab_gates, tab_base, tab_cost, tab_ev, tab_var, tab_cfg = st.tabs(
    ["Gates", "Baselines", "Cost", "Evidence", "Deployment variants", "Configurations"])

with tab_base:
    st.html('<p class="one">What simple selection rules would pick instead of the gates, at the '
            'settings in the sidebar.</p>')
    cards = baselines(d, snap, registry, by_hosting=True)
    if cards:
        st.html(render.baseline_cards(cards))
    else:
        st.write("No complete priced candidates for these comparison rules.")
    if d.recommended and by_id[d.recommended].hosting_kind == "api":
        st.html('<p class="bl-note">An API-only rule picks the same config as ours, because '
                'our pick is already an API.</p>')

with tab_gates:
    st.html('<p class="one">Slide a gate to explore. Configs that pass only because a gate is '
            'looser than recommended are marked <b>Not recommended</b>; the recommendation above '
            'never changes.</p>')
    moved = {g: v for g, v in current("gate_sliders").items()
             if g not in off and v != float(profile.gates[g].value)}
    wi, not_rec = (decide_sliders(snap, scenario, off, moved) if off or moved else (None, {}))
    if wi:
        parts = [f"{display_gate(g)} off" for g in off] + [
            f"{display_gate(g)} moved" for g in moved]
        pick, flagged = what_if_pick(wi, not_rec)
        cost_of = {v.config_id: v.monthly_cost for v in wi.verdicts}
        if pick is None:
            line = render.answer(relabel(answer_line(wi, snap, what_if_profile(profile, off, moved))),
                                 recommended=False, what_if=True)
        else:
            c = cost_of[pick]
            line = render.answer(f"Cheapest passing: {pick} at "
                                 f"{'no cost evidence' if c is None else inr(c) + '/month'}",
                                 recommended=True, what_if=True)
        why = ""
        if flagged:
            gs = ", ".join(f"{display_gate(g)} (recommended {info[g]['pass_if']})"
                           for g in not_rec[pick])
            why = (f'<p class="nr">Not recommended: {pick} passes only because {gs} was '
                   f'loosened.</p>')
        wi_box.html(
            f'<div class="wi"><h3>What-if ({", ".join(parts)}): '
            f'<span class="muted">not the recommendation</span></h3>{line}{why}'
            f'<p class="hash">what-if decision {wi.decision_hash[:12]}…</p></div>')
    sort_by = st.segmented_control(
        "Sort by", ["Status", "Monthly cost", "Error rate"], default="Status")
    order = st.segmented_control("Order", ["Ascending", "Descending"], default="Ascending")
    show_gate_values = st.toggle(
        "Show gate values", key="show_gate_values",
        help="Show the evidence used by each gate, including modeled values and language gaps.",
    )
    rows = [r for r in gate_matrix(d) if r["config"] in ids]
    observations = ({row["config"]: gate_values(snap, row["config"], GATES) for row in rows}
                    if show_gate_values else None)
    wi_status = ({v.config_id: ("not_recommended" if v.config_id in not_rec else v.status)
                  for v in wi.verdicts} if wi else None)
    nr_notes = {cid: "; ".join(f"{display_gate(g)} recommended {info[g]['pass_if']}" for g in gs)
                for cid, gs in not_rec.items()}
    budget_usd = max_spend_usd

    def _val(cid: str, metric: str) -> float | None:
        e = snap.values.get(f"{cid}.{metric}")
        return float(e.value) if e is not None and isinstance(e.value, int | float) else None

    cost_cells = {cid: (inr(v), v > budget_usd) for r in rows
                  if (v := _val(cid := r["config"], "cost.monthly_usd")) is not None}
    error_cells = {cid: (f"{v:.2f}%", v > float(max_error)) for r in rows
                   if (v := _val(cid := r["config"], "serving.error_pct")) is not None}
    inf = float("inf")
    if sort_by == "Monthly cost":
        rows.sort(key=lambda r: _val(r["config"], "cost.monthly_usd") or inf)
    elif sort_by == "Error rate":
        rows.sort(key=lambda r: _val(r["config"], "serving.error_pct") or inf)
    if order == "Descending":
        rows.reverse()
    gate_sliders(slider_specs(profile, GATES, display_gate, SHORT_NAME),
                 render.gate_table(rows, GATES, set(off), wi_status, cost=cost_cells,
                                   labels={g: display_gate(g) for g in GATES},
                                   short=SHORT_NAME,
                                   error=error_cells, notes=nr_notes, values=observations,
                                   deployment={cid: (hosting_label(cid), readiness(cid))
                                               for cid in ids}),
                 render.css("light"), key="gate_sliders")
    no_ev = sorted(ids - {r["config"] for r in rows})
    if no_ev:
        st.html(f'<p class="one">No evidence recorded yet: {", ".join(no_ev)}</p>')
    st.caption("Failing first, then missing evidence, then passing. Unverified: evidence missing "
               "or under 15 scored items. GPU deployments need matching serving evidence to qualify.")
    for v in d.verdicts:
        if v.config_id in ids and v.reasons:
            with st.expander(f"{v.config_id}: {status_label(v.status)}"):
                st.markdown("\n".join(f"- {relabel(r)}" for r in v.reasons))

with tab_cost:
    costs = {k.split(".", 1)[0]: e for k, e in snap.values.items()
             if k.endswith(".cost.monthly_usd") and k.split(".", 1)[0] in ids}
    st.caption("Monthly figures use prices as entered. Check quoted taxes and add-ons before "
               "comparing a budget or purchasing hardware.")
    for kind in RESPONSIBILITY:
        group = [c for c in registry if c.hosting_kind == kind]
        if not group:
            continue
        st.subheader(HOSTING[kind])
        rows = []
        for c in group:
            plan = plans.get(c.config_id)
            cost = costs.get(c.config_id)
            estimate = plan.estimate if plan else None
            rows.append({
                "Configuration": c.config_id,
                "Upfront hardware": ("₹" + indian(estimate.upfront)) if kind == "owned"
                and estimate else "—",
                "Operating per month": ("₹" + indian(estimate.operating)) if estimate else "—",
                "Monthly comparison": inr(float(cost.value)) if cost else "Unavailable",
                "Pricing notes": (
                    f"Known-cost subtotal ₹{indian(estimate.monthly)}/month. "
                    f"Missing: {', '.join(estimate.missing)}"
                    if estimate and not estimate.complete else readiness(c.config_id)
                ),
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True)
    if not costs:
        st.write("No configuration has a cost yet.")
    else:
        budget = max_spend_usd * RATE
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
        infrastructure = [c.config_id for c in registry if c.hosting_kind != "api"
                          and c.config_id in costs and readiness(c.config_id) != "Does not fit"]
        api_costs = {cid: cost for cid, cost in costs.items() if by_id[cid].hosting_kind == "api"}
        if infrastructure and api_costs:
            compared = st.selectbox("Infrastructure plan to compare", infrastructure,
                                    format_func=lambda cid: f"{hosting_label(cid)} · {cid}")
            cost_charts.show_api_comparison(
                {**api_costs, compared: costs[compared]}, volume=int(volume),
                baseline_id=compared, baseline_label=hosting_label(compared),
            )
        with st.expander("Cost at other volumes (table)"):
            points = sorted({10_000, *range(100_000, 1_000_001, 100_000), int(volume)})
            curves = {k: v for k, v in cost_curves(snap, volume=int(volume),
                                                   points=points).items() if k in ids}
            inr_curves = {k: [round(v * RATE) for v in vs] for k, vs in curves.items()}
            st.caption("INR per month")
            st.dataframe(pd.DataFrame({"tickets": points, **inr_curves}), hide_index=True)

with tab_ev:
    for kind in RESPONSIBILITY:
        group_ids = {c.config_id for c in registry if c.hosting_kind == kind}
        if group_ids:
            st.subheader(HOSTING[kind])
            st.html(render.evidence_display(evidence_sections(snap, group_ids)))

with tab_var:
    selected = st.selectbox("Deployment to inspect", list(by_id), key="deployment_model",
                            format_func=lambda cid: f"{hosting_label(cid)} · {cid}")
    c = by_id[selected]
    plan = plans.get(selected)
    st.subheader(hosting_label(selected))
    st.caption(RESPONSIBILITY[c.hosting_kind])
    st.write(f"{c.model_id} · {c.serving} · {c.quant} · {readiness(selected)}")
    cost = snap.values.get(f"{selected}.cost.monthly_usd")
    st.write(f"Monthly comparison: {inr(float(cost.value))}" if cost else
             "A complete monthly comparison is unavailable.")
    if plan:
        hardware = GPU_OPTIONS[gpu].label if c.hosting_kind == "rental" else next(
            preset.parts[0].name for preset in OWNED.values() if preset.id == selected)
        st.write(f"{hardware} · {plan.nodes} nodes · "
                 f"{plan.gpus_per_node} GPU(s) per node · {plan.vram_gb} GB per GPU")
        if plan.minimum_gb is not None:
            st.caption(f"Planning floor: {plan.minimum_gb} GB per GPU at short context.")
        else:
            st.caption("A verified memory requirement is unavailable for this checkpoint.")
        serving = snap.values.get(f"{selected}.serving.p95_ms")
        if serving and serving.measured_under:
            tags = serving.measured_under
            st.caption(f"Serving evidence · runtime {tags['runtime_version']} · "
                       f"checkpoint revision {tags['checkpoint_revision']} · "
                       f"{tags['input_tokens']} input / {tags['output_tokens']} output tokens")
    if c.variants:
        st.caption("Published variants below describe their own test hardware and workload.")
        st.html(render.deployment_evidence(variant_rows(c)))
    for title, detail in architecture_steps(c, gpu=hardware if plan else ""):
        st.markdown(f"**{title}** · {detail}")

with tab_cfg:
    st.html(render.config_table([{
        "config": c.config_id, "model": c.model_id, "host": f"{hosting_label(c.config_id)} · {c.host}",
        "region": c.region.split(" (")[0].split(";")[0], "serving": c.serving,
        "quant": c.quant.split(" (")[0]} for c in registry if c.config_id in ids]))
    status = {v.config_id: v.status for v in d.verdicts}
    order = [r["config"] for r in gate_matrix(d)]
    gpu_label = f"{GPU_OPTIONS[gpu].label} · {gpus} billed nodes"
    fan_items = []
    for cid in order:
        c = by_id[cid]
        cost = snap.values.get(f"{cid}.cost.monthly_usd")
        fan_items.append({
            "config": cid, "model": c.model_id, "host": f"{hosting_label(c.config_id)} · {c.host}",
            "status": status[cid], "cost": f"{inr(float(cost.value))}/mo" if cost else "—",
            "steps": architecture_steps(c, gpu=gpu_label)})
    st.caption("Scroll the list on the right or use the arrows; the middle card's build steps "
               "show on the left.")
    if order:
        st.html(render.config_fan(fan_items, focus=d.recommended or order[0]),
                unsafe_allow_javascript=True)

st.html(f'<p class="foot">All costs are shown in INR. Conversion: US$1 = '
        f'₹{RATE:.4f} (RBI reference rate, {USD_INR.retrieved_at.date().isoformat()}). '
        f'Prices published in USD were converted at this rate.</p>')

# Last element, so the rows and answers above exist when the motion script runs.
st.html(render.MOTION, unsafe_allow_javascript=True)
