"""Sidebar inputs for rented and owned infrastructure."""
from dataclasses import asdict
from json import dumps

import streamlit as st

from pome.app.scenario import GPU_OPTIONS, DeploymentPlan
from pome.app.views import indian
from pome.cost.infrastructure import OwnedInputs, rental_estimate
from pome.registry.hosting import OWNED, PRICE_DATE, RENTAL_SOURCE
from pome.registry.loader import ConfigEntry

_RENTAL_MIN = {
    "gemma4-12b-vllm-in-bf16": 36,
    "gemma4-26b-vllm-in-bf16": 68,
    "gemma4-31b-vllm-in-bf16": 80,
    "llama31-8b-vllm-in-bf16": 24,
}


def rented_plans(registry: list[ConfigEntry], gpu: str, nodes: int, ops: float,
                 rate_inr: float) -> dict[str, DeploymentPlan]:
    opt = GPU_OPTIONS[gpu]
    hr_rate = opt.india_inr if opt.india_inr is not None else float(opt.price.value) * rate_inr
    source = RENTAL_SOURCE if opt.india_inr is not None else opt.price.source
    st.caption(f"₹{indian(hr_rate, 2)}/node-hour · {opt.gpus_per_node} GPU(s) per node")
    priced_on = PRICE_DATE if opt.india_inr is not None else opt.price.retrieved_at.date().isoformat()
    st.caption(f"Price reference: {priced_on} · check taxes and region.")
    st.markdown(f"[Rate source]({source.split(' (filter:')[0]})")
    hours = st.number_input("Billed hours per month", 1, 744, 730, key="rental_hours")
    storage = st.number_input("Storage and backup, ₹/month", min_value=0, value=0,
                              key="rental_storage")
    network = st.number_input("Network and egress, ₹/month", min_value=0, value=0,
                              key="rental_network")
    st.caption("Enter separate charges when they apply. The default assumes none.")
    recurring = (("Operations", ops), ("Storage and backup", storage), ("Network", network))
    estimate = rental_estimate(hr_rate, nodes, hours, recurring)
    return {
        c.config_id: DeploymentPlan(
            hardware=gpu, nodes=nodes, vram_gb=opt.vram_gb,
            minimum_gb=_RENTAL_MIN.get(c.config_id), estimate=estimate, price_source=source,
            cost_formula=(f"₹{hr_rate:.4f}/node-hour × {nodes} nodes × {hours} hours"
                          f" + ₹{ops} ops + ₹{storage} storage + ₹{network} network"),
            gpus_per_node=opt.gpus_per_node, hours=hours, priced_on=priced_on,
        )
        for c in registry if c.hosting_kind == "rental"
    }


def owned_plans() -> dict[str, DeploymentPlan]:
    plans = {}
    for key, preset in OWNED.items():
        with st.expander(preset.label):
            st.caption(f"{preset.checkpoint} · {preset.precision} · {preset.vram_gb} GB GPU")
            nodes = st.number_input("Nodes", 1, 64, preset.nodes, key=f"{key}_nodes")
            parts = []
            for idx, part in enumerate(preset.parts):
                value = st.number_input(
                    f"{part.name}, ₹ per node", min_value=0, value=part.inr,
                    key=f"{key}_part_{idx}", placeholder="Enter quote",
                )
                parts.append((part.name, value))
                detail = f"{part.stock} · {part.tax} · {PRICE_DATE}"
                if part.source:
                    st.markdown(f"{detail} · [Price source]({part.source})")
                else:
                    st.caption(detail)
            kw = st.number_input("Average wall draw, kW/node", 0.0, 20.0, preset.kw,
                                 key=f"{key}_kw")
            tariff = st.number_input("Electricity, ₹/kWh", 0.0, 100.0, 10.0, key=f"{key}_tariff")
            cooling = st.number_input("Site energy multiplier", 1.0, 5.0, 1.2,
                                      key=f"{key}_cooling")
            months = st.number_input("Amortization months", 1, 120, 36, key=f"{key}_months")
            hours = st.number_input("Powered hours/month", 1, 744, 730, key=f"{key}_hours")
            st.caption("Power and site defaults are planning assumptions. Enter 0 for included costs.")
            recurring = tuple((label, st.number_input(f"{label}, ₹/month", min_value=0,
                                                     value=None, key=f"{key}_op_{i}"))
                              for i, label in enumerate(("Connectivity", "Backups", "Maintenance",
                                                         "Staffing", "Site or colocation")))
            inputs = OwnedInputs(nodes, tuple(parts), kw, tariff, cooling, months, hours, recurring)
            plans[preset.id] = DeploymentPlan(
                f"owned-{key}", nodes, preset.vram_gb, preset.minimum_gb, inputs.estimate(),
                "docs/distinction.md", dumps(asdict(inputs), ensure_ascii=False), hours=hours,
            )
    return plans
