"""Hosted reference data and a short-text sizing model for self-managed plans."""
from datetime import datetime
from pathlib import Path

import yaml

from pome.evidence.gapfill import load_gapfill
from pome.evidence.schema import EvidenceValue

_CATALOG = Path(__file__).resolve().parents[1] / "registry" / "artificial_analysis.yaml"


def performance_reference(config_id: str, hardware: str, replicas: int, *,
                          memory_bandwidth_gb_s: float | None = None
                          ) -> dict[str, EvidenceValue]:
    catalog = yaml.safe_load(_CATALOG.read_text(encoding="utf-8"))
    rental_id = config_id.replace("-owned-", "-vllm-in-")
    endpoint = catalog["endpoints"].get(rental_id)
    gpu = catalog["hardware"].get(hardware)
    if memory_bandwidth_gb_s is not None:
        gpu = {"gb_s": memory_bandwidth_gb_s, "source": "Sidebar GPU memory bandwidth"}
    at = datetime.fromisoformat(catalog["retrieved_at"])
    values = {}
    if endpoint:
        conditions = {"provider": endpoint["provider"], "variant": endpoint["variant"],
                      "workload": "Artificial Analysis API performance v3"}
        for key, field, unit in (
            ("first_answer_s", "first_answer_s", "s"),
            ("endpoint_error_pct", "error_pct", "percent"),
        ):
            values[f"reference.artificial_analysis.{key}"] = EvidenceValue(
                value=endpoint[field], unit=unit, provenance="vendor-doc",
                source=endpoint["source"], retrieved_at=at, study=True,
                formula=f"Measurement scope and definitions: {catalog['methodology']}",
                measured_under=conditions,
            )
    if not gpu:
        return values

    inputs = load_gapfill()
    legacy = inputs["selfhost"]
    params = legacy["params_b"].get(rental_id)
    weights_gb = catalog["weight_sizes_gb"].get(rental_id, (params or 0) * 2)
    if not weights_gb:
        return values
    out_tokens = inputs["out_tokens"]
    first_answer = endpoint["first_answer_s"] if endpoint else legacy["ttft_s"]
    delay_basis = ("hosted first-answer time used as a transfer assumption"
                   if endpoint else "local first-token assumption from gapfill.yaml")
    decode_s = (out_tokens - 1) * weights_gb / (gpu["gb_s"] * legacy["eta"])
    request_s = first_answer + decode_s
    source = f"{endpoint['source']} · {gpu['source']}" if endpoint else gpu["source"]
    formula = (f"{first_answer:g} s first answer ({delay_basis}) + "
               f"({out_tokens} − 1) × {weights_gb:g} GB ÷ "
               f"({gpu['gb_s']} GB/s × {legacy['eta']:g}); one model copy per GPU")
    if gpu.get("note"):
        formula += f"; {gpu['note']}"
    for key, value, unit, basis in (
        ("request_ms", round(request_s * 1000), "ms", formula),
        ("serial_rps", round(replicas / request_s, 3), "req_per_s",
         f"{replicas} independent GPU replicas ÷ ({formula}); one active request per replica"),
    ):
        values[f"reference.performance_plan.{key}"] = EvidenceValue(
            value=value, unit=unit, provenance="modeled", source=source, retrieved_at=at,
            formula=basis, measured_under={"target_hardware": hardware, "replicas": replicas,
                                           "output_tokens": out_tokens},
        )
    return values
