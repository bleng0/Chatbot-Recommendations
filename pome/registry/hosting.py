"""Dated India planning references. Prices are INR unless the rate card says otherwise."""
from dataclasses import dataclass
from datetime import UTC, datetime

from pome.evidence.schema import EvidenceValue
from pome.registry.loader import ConfigEntry, Deployment, Pricing

PRICE_DATE = "2026-11-24"
RENTAL_SOURCE = "https://www.e2enetworks.com/gpu-cloud"
HOSTING = {
    "all": "All hosting types",
    "api": "Managed cloud API",
    "rental": "Rented cloud GPU",
    "owned": "Owned self-hosting",
}
RESPONSIBILITY = {
    "api": "The provider owns the hardware and runs inference.",
    "rental": "The provider owns the hardware. Your team runs inference on the rented nodes.",
    "owned": "Your team owns the hardware and runs inference.",
}


@dataclass(frozen=True)
class Part:
    name: str
    inr: int | None
    source: str = ""
    stock: str = "Check listing"
    tax: str = "Verify at checkout"


@dataclass(frozen=True)
class Preset:
    id: str
    label: str
    checkpoint: str
    precision: str
    vram_gb: int
    # Planning minimum including a reserve for short-context text inference.
    minimum_gb: int
    nodes: int
    kw: float
    parts: tuple[Part, ...]


_COMMON = (
    Part("CPU · Ryzen 9 9950X (100-100001277WOF)", 59500,
         "https://mdcomputers.in/product/amd-ryzen-9-9950x-100-100001277wof-desktop-processor/processor/amd-processor",
         "Listed in stock"),
    Part("Motherboard · MSI MAG X870E Tomahawk WiFi", 36300,
         "https://mdcomputers.in/catalog/msi-motherboard/msi-mag-motherboard"),
    Part("NVMe · Samsung 990 Pro 2 TB (MZ-V9P2T0CW)", 43500,
         "https://www.vedantcomputers.com/samsung-990-pro-2tb-mz-v9p2t0cw", "Listed in stock"),
    Part("PSU · Corsair HX1200i (CP-9020307-IN)", 26860,
         "https://mdcomputers.in/product/corsair/corsair-hx1200i-platinum-modular-smps-cp-9020307-in",
         "Listed in stock"),
    Part("CPU cooler · Arctic Liquid Freezer III 360 (ACFRE00152A)", 11699,
         "https://mdcomputers.in/product/arctic-liquid-freezer-iii-360mm-white-liquid-cooler-acfre00152a"),
    Part("Chassis · Corsair 5000D Airflow or integrator-approved equivalent", None,
         "https://mdcomputers.in/product/corsair-5000d-airflow-mid-tower-cabinet-cc-9011210-ww",
         "Quote required"),
    Part("Network · switch, firewall allocation and cabling per node", None, stock="Quote required"),
)
_UPS = Part("UPS · APC BVX2200LI-IN", 18000,
            "https://mdcomputers.in/product/apc-ups-bvx2200li-in/peripherals/ups",
            "Listed in stock", "Retail inclusive")
_RAM = "https://mdcomputers.in/?route=product%2Fsearch&search=Corsair+Vengeance"
OWNED = {
    "pilot": Preset("gemma4-12b-owned-w4a16", "Pilot workstation", "google/gemma-4-12B-it-qat-w4a16-ct",
                    "W4A16 QAT", 32, 16, 1, 0.5, (
                        Part("GPU · RTX 5090 32 GB (GV-N5090WF3OC-32GD)", 413000,
                             "https://www.vedantcomputers.com/gigabyte-rtx-5090-gv-n5090wf3oc-32gd",
                             "Out-of-stock reference"),
                        Part("RAM · Corsair Vengeance DDR5 64 GB", 110860, _RAM),
                        _UPS, *_COMMON,
                    )),
    "production": Preset("gemma4-31b-owned-bf16", "Production candidate",
                         "google/gemma-4-31B-it", "BF16", 96, 80, 2, 0.65, (
                             Part("GPU · RTX PRO 6000 96 GB (900-5G144-2500-000)", 1889500,
                                  "https://www.vedantcomputers.com/index.php?route=extension/pc_builder/pc_builder_product&product_id=9556&pc_builder_component_id=3",
                                  "Out-of-stock reference"),
                             Part("RAM · Corsair Vengeance DDR5 128 GB", 252890, _RAM),
                             Part("UPS · APC SUA2200UXI, external battery separate", 54200,
                                  "https://eshop.se.com/in/apc-smart-ups-xl-2200va-230v-no-battery.html",
                                  "Delivery subject to listing", "GST excluded"),
                             Part("UPS battery bank and installation", None, stock="Quote required"),
                             *_COMMON,
                         )),
}


def owned_config(preset: Preset) -> ConfigEntry:
    licence = EvidenceValue(
        value=True, unit="bool", provenance="vendor-doc",
        source=f"https://huggingface.co/{preset.checkpoint}",
        retrieved_at=datetime(2026, 11, 24, tzinfo=UTC),
    )
    return ConfigEntry(
        config_id=preset.id, model_id=preset.checkpoint, version=preset.precision,
        host="Customer-owned GPU", region="Customer site (confirm location)", serving="vLLM",
        quant=preset.precision, evaluation_mode="measured", provider="none", hosting_kind="owned",
        pricing=Pricing(input_per_1m=None, output_per_1m=None),
        deployment=Deployment(region_processing=None, retention_days=None, commercial_use=licence),
    )


# Short-context, single-GPU planning floors. For Qwen, Sarvam and Muse-Glimmer
# the floor rounds up BF16 weights plus 20% overhead and 8 GB runtime reserve
# using the parameter counts in gapfill.yaml.
RENTAL_MIN_VRAM_GB = {
    "gemma4-12b-vllm-in-bf16": 36,
    "gemma4-26b-vllm-in-bf16": 68,
    "gemma4-31b-vllm-in-bf16": 80,
    "qwen38-27b-vllm-in-bf16": 80,
    "llama31-8b-vllm-in-bf16": 24,
    "sarvam30b-vllm-in-bf16": 96,
    "museglimmer30b-vllm-in-bf16": 80,
    "gemma4-12b-vllm-in-w4a16": OWNED["pilot"].minimum_gb,
}


def rental_candidates(registry: list[ConfigEntry]) -> list[tuple[ConfigEntry, int]]:
    """Build rental candidates with an explicit per-GPU planning floor."""
    qat = owned_config(OWNED["pilot"]).model_copy(update={
        "config_id": "gemma4-12b-vllm-in-w4a16",
        "host": "rented cloud GPU (India region)",
        "region": "India",
        "hosting_kind": "rental",
    })
    candidates = {cfg.config_id: cfg for cfg in registry if cfg.hosting_kind == "rental"}
    candidates.setdefault(qat.config_id, qat)
    return [(cfg, RENTAL_MIN_VRAM_GB[cid]) for cid, cfg in candidates.items()
            if cid in RENTAL_MIN_VRAM_GB]


def owned_candidates(rentals: list[tuple[ConfigEntry, int]]) -> list[tuple[ConfigEntry, int]]:
    """Reuse checkpoints and precision options across hosting types."""
    existing = {
        "gemma4-12b-vllm-in-w4a16": OWNED["pilot"],
        "gemma4-31b-vllm-in-bf16": OWNED["production"],
    }
    candidates = []
    for cfg, minimum in rentals:
        preset = existing.get(cfg.config_id)
        if preset:
            owned = owned_config(preset).model_copy(update={"variants": cfg.variants})
        else:
            owned = cfg.model_copy(update={
                "config_id": cfg.config_id.replace("-vllm-in-", "-owned-"),
                "host": "Customer-owned GPU",
                "region": "Customer site (confirm location)",
                "hosting_kind": "owned",
            })
        candidates.append((owned, minimum))
    return candidates


def fitting_candidates(candidates: list[tuple[ConfigEntry, int]], vram_gb: int
                       ) -> list[tuple[ConfigEntry, int]]:
    """Replicas fit independently; the plan never pools VRAM across GPUs."""
    return [(cfg, floor) for cfg, floor in candidates if floor <= vram_gb]
