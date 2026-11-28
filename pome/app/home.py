"""POME decision-support app. Run: uv run python -m streamlit run pome/app/home.py

Replays recorded evaluation results (runs/records); never calls an LLM API.
"""
from datetime import UTC, datetime
from os import environ
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from pydantic import ValidationError

from pome.app import cost_charts, render
from pome.app.hosting_controls import owned_plans, rented_plans
from pome.app.scenario import (
    SERVING_METRICS,
    Scenario,
    decide,
    scenario_profile,
)
from pome.app.sliders import current, gate_sliders, slider_specs
from pome.app.views import (
    COMPLIANCE_SHORT,
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
)
from pome.evidence.compliance import build_compliance, load_buyer_evidence, load_catalog
from pome.profiles.loader import load_profile
from pome.registry.hosting import HOSTING, RESPONSIBILITY, owned_candidates, rental_candidates
from pome.registry.loader import load_registry

st.set_page_config(page_title="Model and hosting selection", layout="wide")
T = render.TOKENS["light"]
st.html(render.css("light"))

profile = load_profile()
base_registry = load_registry()
rentals = rental_candidates(base_registry)
owned = owned_candidates(rentals)
# G10 (error limit) and G11 (budget) are sidebar settings; the rest are gates, numbered 1-10
GATES = SHOWN_GATES
COMPLIANCE_CONTROLS = {
    "G12": "Require India-only inference",
    "G13": "Limit provider prompt retention",
    "G15": "Require India-only prompt storage",
    "G16": "Exclude provider model training",
    "G17": "Exclude provider prompt logging",
    "G18": "Require a buyer-reviewed contract",
    "G19": "Require buyer-verified settings",
}
TABLE_GATES = [*GATES, *COMPLIANCE_CONTROLS]
RATE = float(USD_INR.value)


def reset_to_recommended() -> None:
    next_revision = st.session_state.get("reset_revision", 0) + 1
    for key in list(st.session_state):
        del st.session_state[key]
    # A fresh component key remounts the iframe and discards its local slider state.
    st.session_state["reset_revision"] = next_revision


def reset_compliance() -> None:
    key = "compliance"
    for gate in COMPLIANCE_CONTROLS:
        st.session_state[f"{key}_{gate}"] = False
    st.session_state[f"{key}_retention"] = 30


def apply_india_preset(key: str) -> None:
    st.session_state[f"{key}_G12"] = True
    st.session_state[f"{key}_G13"] = True
    st.session_state[f"{key}_retention"] = 0


with st.sidebar:
    st.header("Scenario")
    st.button("Reset to recommended", on_click=reset_to_recommended)
    volume = st.select_slider("Tickets per month", tickets_options(),
                              value=profile.volume_tickets_per_month, format_func=indian, key="volume")
    st.caption("1 ticket = 1 customer question.")
    max_spend_inr = st.number_input(
        "Max monthly spend, INR", 0, 10_00_00_000,
        round(float(profile.gates["G11"].value) * RATE), step=5_000, key="max_spend",
        help="Configs costing more are rejected.")
    max_error = st.number_input(
        "Max error rate after retries, %", 0.0, 100.0, float(profile.gates["G10"].value),
        step=0.1, format="%.1f", key="max_error", help="Configs failing more requests are rejected.")
    scope = st.radio("Hosting scope", list(HOSTING), format_func=HOSTING.get, key="hosting_scope")
    gpu, rental_label, plans = rented_plans(rentals, RATE)
    st.subheader("Owned self-hosting")
    owned_label, owned_deployments = owned_plans(owned)
    plans.update(owned_deployments)
    st.caption(f"{len(owned_deployments)} configurations fit your GPU.")
    st.header("Eligibility gates")
    st.caption("Enabled gates determine which configurations qualify.")
    info = dict(zip(GATES, gate_info_rows(profile), strict=True))
    off = tuple(g for g, row in info.items()
                if not st.toggle(f"{row['gate']} · {SHORT_NAME[g]}", value=True, key=f"gate_{g}",
                                 help=f"{row['checks']}. Recommended threshold: {row['pass_if']}."))

    with st.expander("Compliance filters"):
        st.caption("Owned self-hosting uses the operator-control assumptions described in Evidence. "
                   "Other deployments require applicable records for enabled filters.")
        compliance_key = "compliance"
        st.button("Require India + zero provider retention", on_click=apply_india_preset,
                  args=(compliance_key,))
        st.button("Reset compliance filters", on_click=reset_compliance)
        compliance_gates = tuple(
            gid for gid, label in COMPLIANCE_CONTROLS.items()
            if st.checkbox(f"{gid} {label}", key=f"{compliance_key}_{gid}")
        )
        retention_days = st.number_input(
            "Max provider retention (days)", min_value=0, value=30, step=1,
            key=f"{compliance_key}_retention", disabled="G13" not in compliance_gates,
            help="Maximum retention of prompts and responses. Zero requires documented no persistence.")


slider_key = f'gate_sliders_{st.session_state.get("reset_revision", 0)}'
thresholds = {g: v for g, v in current(slider_key).items()
              if g not in off and v != float(profile.gates[g].value)}

default_usd = float(profile.gates["G11"].value)
# the default INR budget maps back to the exact banking_mvp value, so the decision hash holds
max_spend_usd = (default_usd if max_spend_inr == round(default_usd * RATE)
                 else float(max_spend_inr) / RATE)
scenario = Scenario(volume=int(volume), gpu=gpu,
                    max_spend_usd=max_spend_usd, max_error_pct=float(max_error),
                    compliance_gates=compliance_gates, retention_days=retention_days,
                    disabled_gates=off, gate_thresholds=thresholds)
catalog = [cfg for cfg in base_registry if cfg.hosting_kind != "rental"]
catalog.extend(cfg.model_copy(update={"host": "Rented cloud GPU", "region": "Confirm region"})
               if gpu.startswith("rental-custom:") and cfg.hosting_kind == "rental" else cfg
               for cfg, _ in [*rentals, *owned] if cfg.config_id in plans)
if scope == "rental" and not any(cfg.hosting_kind == "rental" for cfg in catalog):
    st.info("No rental configurations fit the selected GPU. Choose another rental machine "
            "or increase VRAM per GPU to see compatible configurations.")
    st.stop()
buyer = None
buyer_path = environ.get("POME_COMPLIANCE_EVIDENCE_FILE")
if buyer_path:
    try:
        buyer = load_buyer_evidence(Path(buyer_path))
    except ValidationError as error:
        st.warning("The local buyer evidence file is invalid. Using public evidence only.")
        problems = error.errors(include_input=False, include_context=False, include_url=False)
        for problem in problems[:5]:
            location = ".".join(map(str, problem["loc"])) or "file"
            st.text(f"{location}: {problem['type']}")
    except (OSError, UnicodeError):
        st.warning("The local buyer evidence file could not be read as UTF-8. Using public "
                   "evidence only. Check its path and permissions.")
compliance = build_compliance(catalog, gpu, load_catalog(), buyer, datetime.now(UTC).date(),
                              assume_owned_controls=True)
effective_profile = scenario_profile(scenario)
snap, d = decide(scenario, registry=catalog, deployment_plans=plans,
                 scope=scope, inr_per_usd=RATE, compliance=compliance)
registry = [c for c in catalog if scope == "all" or scope == c.hosting_kind]
by_id = {c.config_id: c for c in registry}


def hosting_label(cid: str) -> str:
    cfg = by_id[cid]
    return HOSTING[cfg.hosting_kind] + (" · lab only" if cfg.lab_only else "")


def deployment_hardware(cid: str) -> str:
    if cid not in plans:
        return ""
    return rental_label if by_id[cid].hosting_kind == "rental" else owned_label


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
    st.html(render.answer(relabel(answer_line(d, snap, effective_profile)), recommended=False))
    st.html(render.stats([("configurations", len(d.verdicts)),
                          ("rejected", sum(v.status == "rejected" for v in d.verdicts))]))
    st.html(f'<p class="hash">decision {d.decision_hash[:12]}… · same inputs, same hash</p>')

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
    sort_by = st.segmented_control(
        "Sort by", ["Status", "Monthly cost", "Error rate"], default="Status", key="gate_sort")
    order = st.segmented_control(
        "Order", ["Ascending", "Descending"], default="Ascending", key="gate_order")
    show_gate_values = st.toggle(
        "Show gate values", key="show_gate_values",
        help="Show the evidence used by each gate, including modeled values and language gaps.",
    )
    rows = [r for r in gate_matrix(d) if r["config"] in ids]
    for row in rows:
        if by_id[row["config"]].hosting_kind == "owned":
            for gid in COMPLIANCE_CONTROLS:
                row["gates"].setdefault(gid, "pass")
    observations = ({row["config"]: gate_values(snap, row["config"], TABLE_GATES) for row in rows}
                    if show_gate_values else None)
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
                 render.gate_table(rows, TABLE_GATES,
                                   set(off) | (COMPLIANCE_CONTROLS.keys() - set(compliance_gates)),
                                   cost=cost_cells,
                                   labels={g: display_gate(g) for g in TABLE_GATES},
                                   short={**SHORT_NAME, **COMPLIANCE_SHORT},
                                   error=error_cells, values=observations,
                                   deployment={cid: (hosting_label(cid), readiness(cid))
                                               for cid in ids}),
                 render.css("light"), key=slider_key)
    with st.expander("Compliance gate information"):
        st.dataframe(gate_info_rows(effective_profile, compliance_only=True), hide_index=True)
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
                                    key="comparison_plan",
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

    with st.expander("Compliance sources and verification gaps"):
        st.caption("Public policies and buyer reviews support screening. See docs/compliance.md "
                   "for applicability and evidence scope.")
        for cid in sorted(ids):
            st.markdown(f"**{cid}**")
            public = compliance.public.get(cid)
            if public is not None:
                st.text(f"{public.scope} Reviewed {public.reviewed_on}. {public.notes}")
                for index, source in enumerate(public.sources, 1):
                    st.markdown(f"[Source {index}]({source})")
            st.caption(compliance.buyer_status.get(cid, "No matching buyer review supplied."))

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
        hardware = deployment_hardware(selected)
        st.write(f"{hardware} · {plan.nodes} nodes · "
                 f"{plan.gpus_per_node} GPU(s) per node · {plan.vram_gb} GB per GPU")
        replicas = plan.nodes * plan.gpus_per_node
        st.caption(f"Deployment plan · {replicas} replica(s) · 1 GPU per replica · "
                   "4,096-token context limit")
        if plan.minimum_gb is not None:
            st.caption(f"Planning floor: {plan.minimum_gb} GB per GPU at short context.")
        else:
            st.caption("A verified memory requirement is unavailable for this checkpoint.")
        request = snap.values.get(f"{selected}.reference.performance_plan.request_ms")
        throughput = snap.values.get(f"{selected}.reference.performance_plan.serial_rps")
        if request and throughput:
            st.caption(f"Performance model · {int(request.value):,} ms/request · "
                       f"{float(throughput.value):g} requests/s with one active request per GPU. "
                       "See Evidence for sources and calculations.")
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
    fan_items = []
    for cid in order:
        c = by_id[cid]
        cost = snap.values.get(f"{cid}.cost.monthly_usd")
        fan_items.append({
            "config": cid, "model": c.model_id, "host": f"{hosting_label(c.config_id)} · {c.host}",
            "status": status[cid], "cost": f"{inr(float(cost.value))}/mo" if cost else "—",
            "steps": architecture_steps(c, gpu=deployment_hardware(cid))})
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
