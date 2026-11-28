"""Sidebar inputs for rented and owned infrastructure."""
from dataclasses import asdict, replace
from datetime import UTC, datetime
from json import dumps

import streamlit as st

from pome.app.scenario import GPU_OPTIONS, DeploymentPlan
from pome.app.views import indian
from pome.cost.infrastructure import OwnedInputs, rental_estimate
from pome.registry.hosting import OWNED, PRICE_DATE, RENTAL_SOURCE, Part, fitting_candidates
from pome.registry.loader import ConfigEntry


def rented_plans(candidates: list[tuple[ConfigEntry, int]], rate_inr: float
                 ) -> tuple[str, str, dict[str, DeploymentPlan]]:
    with st.expander("Rented cloud GPU"):
        labels = {key: opt.label for key, opt in GPU_OPTIONS.items()}
        labels["custom"] = "Other cloud GPU machine"
        gpu = st.selectbox("Rental machine", list(labels), format_func=labels.get,
                           key="rental_machine")
        opt = GPU_OPTIONS.get(gpu)
        bandwidth = None
        if opt:
            label = opt.label
            vram = opt.vram_gb
            gpu_count = opt.gpus_per_node
            rate = opt.india_inr if opt.india_inr is not None else float(opt.price.value) * rate_inr
            source = RENTAL_SOURCE if opt.india_inr is not None else opt.price.source
            priced_on = (PRICE_DATE if opt.india_inr is not None
                         else opt.price.retrieved_at.date().isoformat())
            st.caption(opt.note)
            st.caption(f"₹{indian(rate, 2)}/node-hour · {gpu_count} GPU(s) per node")
            st.caption(f"Price reference: {priced_on} · check taxes and region.")
            st.markdown(f"[Rate source]({source.split(' (filter:')[0]})")
        else:
            label = st.text_input("Provider, region and machine", key="rental_custom_machine").strip()
            vram = st.number_input("VRAM per GPU, GB", 1, 512, 48, key="rental_custom_vram")
            gpu_count = st.number_input("GPUs per node", 1, 16, 1, key="rental_custom_gpus")
            rate = st.number_input("Rate, ₹ per node-hour", min_value=0.0, value=None,
                                   key="rental_custom_rate", placeholder="Enter cloud quote")
            bandwidth = st.number_input("GPU memory bandwidth, GB/s", min_value=1.0, value=None,
                                        key="rental_custom_bandwidth", placeholder="Optional")
            gpu = f"rental-custom:{label}:{vram}gb"
            label = label or "Custom cloud GPU"
            source = "User-entered rental quote"
            priced_on = datetime.now(UTC).date().isoformat()
        nodes = st.number_input("Rental nodes", 1, 64, 1, key="rental_nodes",
                                help="Number of whole rental machines, including bundled GPUs.")
        ops = st.number_input("Rented GPU operations, ₹/month", 0, 10_00_00_000, 0,
                              step=10_000, key="rental_ops")
        hours = st.number_input("Billed hours per month", 1, 744, 730, key="rental_hours")
        storage = st.number_input("Storage and backup, ₹/month", min_value=0, value=0,
                                  key="rental_storage")
        network = st.number_input("Network and egress, ₹/month", min_value=0, value=0,
                                  key="rental_network")
        st.caption("Enter separate charges when they apply. The default assumes none.")
        recurring = (("Operations", ops), ("Storage and backup", storage), ("Network", network))
        if rate is None:
            recurring += (("Node-hour quote", None),)
        estimate = rental_estimate(rate or 0.0, nodes, hours, recurring)
        fitted = fitting_candidates(candidates, vram)
        st.caption(f"{len(fitted)} configurations fit this GPU.")
    return gpu, label, {
        cfg.config_id: DeploymentPlan(
            hardware=gpu, nodes=nodes, vram_gb=vram,
            minimum_gb=floor, estimate=estimate, price_source=source,
            cost_formula=(f"{'Quote required' if rate is None else f'₹{rate:.4f}/node-hour'}"
                          f" × {nodes} nodes × {hours} hours"
                          f" + ₹{ops} ops + ₹{storage} storage + ₹{network} network"),
            gpus_per_node=gpu_count, hours=hours, priced_on=priced_on,
            memory_bandwidth_gb_s=bandwidth,
        )
        for cfg, floor in fitted
    }


def owned_plans(candidates: list[tuple[ConfigEntry, int]]
                ) -> tuple[str, dict[str, DeploymentPlan]]:
    labels = {"pilot": "RTX 5090 · 32 GB", "production": "RTX PRO 6000 · 96 GB",
              "custom": "Other NVIDIA GPU"}
    with st.expander("Owned hardware"):
        key = st.selectbox("GPU in your machine", list(labels), format_func=labels.get,
                           key="owned_hardware")
        preset = OWNED.get(key)
        bandwidth = None
        if preset:
            label = labels[key]
            vram = preset.vram_gb
            gpu_count = st.number_input("GPUs per node", 1, 16, 1, key=f"{key}_gpus")
            parts = preset.parts if gpu_count == 1 else (
                replace(preset.parts[0], name=f"All {gpu_count} GPUs",
                        inr=preset.parts[0].inr * gpu_count), *preset.parts[1:])
        else:
            model = st.text_input("GPU model", key="custom_gpu_model").strip()
            label = model or "Custom NVIDIA GPU"
            vram = st.number_input("VRAM per GPU, GB", 1, 512, 24, key="custom_vram")
            gpu_count = st.number_input("GPUs per node", 1, 16, 1, key="custom_gpus")
            bandwidth = st.number_input("GPU memory bandwidth, GB/s", min_value=1.0, value=None,
                                        key="owned_custom_bandwidth", placeholder="Optional")
            parts = (Part("Total hardware", None, stock="Enter actual hardware cost"),)
        st.caption("Each GPU hosts one model replica. Candidates are sized at 4,096 tokens.")
        nodes = st.number_input("Nodes", 1, 64, preset.nodes if preset else 1, key=f"{key}_nodes")
        capex = []
        for idx, part in enumerate(parts):
            value = st.number_input(
                f"{part.name}, ₹ per node", min_value=0, value=part.inr,
                key=f"{key}_part_{gpu_count}_{idx}", placeholder="Enter quote",
            )
            capex.append((part.name, value))
            detail = f"{part.stock} · {part.tax} · {PRICE_DATE}"
            if part.source:
                st.markdown(f"{detail} · [Price source]({part.source})")
            else:
                st.caption(detail)
        power_default = preset.kw if preset and gpu_count == 1 else None
        kw = st.number_input("Average wall draw, kW/node", 0.0, 20.0, power_default,
                             key=f"{key}_kw_{gpu_count}", placeholder="Enter measured or estimated draw")
        tariff = st.number_input("Electricity, ₹/kWh", 0.0, 100.0, 10.0, key=f"{key}_tariff")
        cooling = st.number_input("Site energy multiplier", 1.0, 5.0, 1.2,
                                  key=f"{key}_cooling")
        months = st.number_input("Amortization months", 1, 120, 36, key=f"{key}_months")
        hours = st.number_input("Powered hours/month", 1, 744, 730, key=f"{key}_hours")
        st.caption("Enter 0 for costs already covered.")
        recurring = tuple((name, st.number_input(f"{name}, ₹/month", min_value=0,
                                                value=None, key=f"{key}_op_{i}"))
                          for i, name in enumerate(("Connectivity", "Backups", "Maintenance",
                                                   "Staffing", "Site or colocation")))
        if kw is None:
            recurring += (("Average wall draw", None),)
        inputs = OwnedInputs(nodes, tuple(capex), kw or 0.0, tariff, cooling, months, hours, recurring)
        estimate = inputs.estimate()
        hardware = f"owned-{key}" if preset else f"owned-custom:{model}:{vram}gb"
        return label, {
            cfg.config_id: DeploymentPlan(
                hardware, nodes, vram, floor, estimate, "docs/distinction.md",
                dumps(asdict(inputs), ensure_ascii=False), gpus_per_node=gpu_count, hours=hours,
                memory_bandwidth_gb_s=bandwidth,
            )
            for cfg, floor in fitting_candidates(candidates, vram)
        }
