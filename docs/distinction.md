# Hosting distinction and infrastructure planning

## Who owns the hardware and runs inference

| Deployment | Hardware owner | Inference operator | Cost basis |
|---|---|---|---|
| Managed cloud API | API provider | API provider | Input and output tokens per ticket and the provider's rates |
| Rented cloud GPU | Infrastructure provider | Bank or its operator | Whole rented machine-hours plus storage, connectivity, and operations |
| Owned self-hosting | Bank or its operator | Bank or its operator | Purchased hardware, electricity, connectivity, backups, maintenance, staffing, and site costs |

A GPU VM running vLLM is a rented cloud deployment even when the bank manages the model. The
existing cloud-GPU configuration IDs remain stable so historical evidence still resolves. The
Ollama laptop record is owned lab evidence with no production cost or readiness claim. The
hosting selector defaults to all three types and scopes the recommendation and every tab.
A location shown for an owned plan is the intended site. Confirm where inference, backups,
logs, and the application gateway actually run.

## Owned presets and purchase inputs

References checked 24 November 2026. Prices are dated Indian listings, not purchase quotes.
Stock and checkout taxes can change. Conditional discounts and financing are excluded.
Numbers in the sidebar can be replaced with supplier quotes. All quantities are per node
unless otherwise indicated. The app uses the exact default BOM for each preset.

| Component | Pilot workstation, one node | Production candidate, two independent nodes |
|---|---:|---:|
| GPU | RTX 5090 32 GB, GV-N5090WF3OC-32GD, ₹4,13,000 | RTX PRO 6000 Blackwell Workstation 96 GB, 900-5G144-2500-000, ₹18,89,500 |
| CPU | AMD Ryzen 9 9950X, ₹59,500 | Same |
| Motherboard | MSI MAG X870E Tomahawk WiFi, ₹36,300 | Same |
| RAM | Corsair Vengeance DDR5 64 GB, ₹1,10,860 | Corsair Vengeance DDR5 128 GB, ₹2,52,890 |
| Storage | Samsung 990 Pro NVMe 2 TB, ₹43,500 | Same |
| PSU | Corsair HX1200i 1200 W, ₹26,860 | Same |
| CPU cooling | Arctic Liquid Freezer III 360, ₹11,699 | Same |
| Chassis and airflow | Integrator quote | Integrator quote |
| UPS | APC BVX2200LI-IN, ₹18,000, retail incl. tax | APC SUA2200UXI, ₹54,200 plus GST, external batteries and installation quoted separately |
| Networking | Private switch/firewall allocation and cabling, quote | Same, with redundancy sized to site requirements |

The pilot favors a repeatable short-context text workload and a smaller QAT checkpoint.
The production candidate uses a single 96 GB GPU per node to avoid model sharding for the
31B checkpoint. Two nodes are independent replicas. Verify failover and single-node load
capacity before treating them as redundant service. Ask the integrator to validate power and
connector specifications, card and radiator clearance, RAM compatibility, cooling under load,
and UPS runtime at measured draw. Verify site circuits, spare parts, procurement and support
terms as part of the quote. A workstation-class GPU does not establish an uptime target.

Purchase references. [RTX 5090, out of stock](https://www.vedantcomputers.com/gigabyte-rtx-5090-gv-n5090wf3oc-32gd) ·
[RTX PRO 6000, out of stock](https://www.vedantcomputers.com/index.php?route=extension/pc_builder/pc_builder_product&product_id=9556&pc_builder_component_id=3) ·
[CPU](https://mdcomputers.in/product/amd-ryzen-9-9950x-100-100001277wof-desktop-processor/processor/amd-processor) ·
[Motherboard](https://mdcomputers.in/catalog/msi-motherboard/msi-mag-motherboard) ·
[Memory](https://mdcomputers.in/?order=DESC&route=product%2Fsearch&search=Corsair+Vengeance&sort=p.price) ·
[NVMe](https://www.vedantcomputers.com/samsung-990-pro-2tb-mz-v9p2t0cw) ·
[Power supply](https://mdcomputers.in/product/corsair-hx1200i-platinum-modular-smps-cp-9020307-in) ·
[Cooler](https://mdcomputers.in/product/arctic-liquid-freezer-iii-360mm-white-liquid-cooler-acfre00152a) ·
[Chassis reference](https://mdcomputers.in/product/corsair-5000d-airflow-mid-tower-cabinet-cc-9011210-ww) ·
[Pilot UPS](https://mdcomputers.in/product/apc-ups-bvx2200li-in/peripherals/ups) ·
[Production UPS](https://eshop.se.com/in/apc-smart-ups-xl-2200va-230v-no-battery.html).

## Monthly cost

- API: monthly tickets × estimated token spend per ticket. Use the recorded token counts
  where available and label modeled workload inputs and pricing proxies.
- Rented: node-hour rate × number of nodes × billed hours plus storage and backup, network
  and egress, and operations. One AWS g6e.12xlarge node includes four L40S cards. Changing the
  node count does not multiply that rate again by the number of bundled GPUs.
- Owned: upfront hardware = node count × total cost per node. Monthly operating spend =
  nodes × average wall kW per node × powered hours × ₹/kWh × site energy multiplier
  + site-wide monthly recurring charges. Full monthly cost adds upfront hardware divided
  by the amortization months. Defaults are 730 hours, 36 months, ₹10/kWh, and 1.2× site
  energy, with illustrative average wall draw of 0.50 kW pilot and 0.65 kW production per
  node. Enter a facility tariff and metered draw to refine them. Enter 0 only for included
  or inapplicable costs. Taxes, site work, and shared infrastructure must be reflected in
  the relevant supplier or operating inputs.
- Missing line items produce a known-cost subtotal. A subtotal stays outside the budget
  gate and break-even charts. Break-even assumes the same workload, linear API token spend,
  and unchanged infrastructure size and charges over the plotted range. It is a cost
  calculation, not a capacity estimate.

E2E India on-demand rates used here are ₹102/h for L40S 48 GB, ₹189/h for A100 80 GB,
and ₹379.05/h for H100 80 GB before tax. Azure and AWS rates are the existing dated
USD references converted at the app's displayed RBI rate. Confirm the actual plan, region,
capacity, and billing terms. [E2E India GPU rate card](https://www.e2enetworks.com/gpu-cloud) ·
[Azure Retail Prices API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices) ·
[AWS Mumbai Linux on-demand rate card](https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ec2-ondemand-without-sec-sel/Asia%20Pacific%20(Mumbai)/Linux/index.json).

## Run and validate an owned deployment

The pilot uses `google/gemma-4-12B-it-qat-w4a16-ct`. Its 16 GB planning floor is a
conservative pilot assumption for the compressed-tensors checkpoint and short text context.
Google's 6.7 GB 12B Q4_0 figure is for a different quantization and is reference only.
The production plan uses `google/gemma-4-31B-it` at BF16. Google's 69.9 GB load estimate
informs the preliminary 80 GB single-GPU floor. These floors reserve space for the runtime
and KV cache and do not guarantee fit at all concurrency levels. Multiple GPUs or nodes do
not pool memory automatically. [Google model memory guidance](https://gemma.ai/models/gemma-4/) ·
[Google vLLM guide](https://gemma.ai/deployment/vllm/) ·
[vLLM memory guidance](https://docs.vllm.ai/en/stable/configuration/conserving_memory/) ·
[vLLM parallel serving](https://docs.vllm.ai/en/latest/serving/parallelism_scaling/).

1. Install a supported Linux distribution and the NVIDIA driver, Docker, and NVIDIA
   Container Toolkit, then verify the host and container can see the GPU. Keep model
   weights on the local NVMe volume. Choose the vLLM release documented to support
   the checkpoint and GPU, record its OCI image digest, and resolve the model revision
   to a full repository commit before deploying. [NVIDIA setup](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) ·
   [vLLM GPU setup](https://docs.vllm.ai/en/latest/getting_started/installation/gpu/).
2. Set `IMAGE` to the validated `vllm/vllm-openai@sha256:…` digest, `MODEL` to
   the checkpoint above, and `REVISION` to its exact commit. Supply `VLLM_API_KEY`
   through the deployment secret manager. For a single-node smoke test, bind the
   container port to loopback. Keep the checkpoint's declared quantization for the
   pilot and use BF16 for the production checkpoint.

   ```bash
   docker run --rm --gpus all --shm-size 2g -p 127.0.0.1:8000:8000 \
     --env VLLM_API_KEY -v /srv/pome/model-cache:/root/.cache/huggingface \
     "$IMAGE" --model "$MODEL" --revision "$REVISION" \
     --dtype bfloat16 --max-model-len 4096
   curl --fail --silent http://127.0.0.1:8000/v1/models \
     -H "Authorization: Bearer $VLLM_API_KEY"
   ```

3. Send a synthetic request to `/v1/chat/completions` and verify response shape, the
   model identifier, and rejection of missing credentials. Deploy replicas behind an
   authenticated private gateway with TLS, bounded queues, health checks and redacted
   logs. Keep real customer prompts out of diagnostics. Check GPU memory and temperature,
   request latency, retry failures, saturation, and failover at the gateway.
4. Replay the POME quality suite for the exact checkpoint and quantization. At 4,096 maximum
   context, benchmark a 600-input/200-output-token workload. Ramp concurrency around the
   expected peak. Record end-to-end p95 at the tested peak, the highest sustainable
   successful requests/second meeting the latency and error limits, and failures after the
   configured gateway retries. `vllm bench serve` can drive traffic. Collect post-retry
   errors at the gateway, where retries actually occur. [vLLM benchmark docs](https://docs.vllm.ai/en/stable/cli/index.html).

## Record evidence and qualify a plan

Record quality runs under `runs/records/<configuration-id>/`. Put reviewed serving evidence
in `runs/serving/<configuration-id>.json` as a mapping from `serving.p95_ms`,
`serving.sustainable_rps`, and `serving.error_pct` to the standard EvidenceValue objects
with units `ms`, `req_per_s`, and `percent` respectively. Include source, timestamp, run
IDs for self-tested measurements or a published study URL, and `measured_under` with
`config_id`, `hardware` (rental SKU key, `owned-pilot`, or `owned-production`),
`nodes`, `gpus_per_node`, `runtime`, `runtime_version`, `checkpoint`,
`checkpoint_revision`, `precision`, `input_tokens`, `output_tokens`, and
`max_model_len`. Capture the test duration, request distribution and retry policy in the
linked evidence. Retest after changes to the hardware, model, precision, runtime or service
settings and deploy the same revisions the evidence records. Confirm licence and other
required deployment evidence before promotion.

Gates shows actual values or compact verdicts with hosting and readiness always visible.
The sidebar gate help explains thresholds, and what-if sliders cannot override deployment
readiness. Baselines shows simple
rules scoped to the current filter. Cost groups the three pricing models. Evidence identifies
historical serving proxies as reference rather than using them for a different GPU.
Deployment variants and Configurations describe the actual selected hardware and operator.
Published or modeled proxies retain their historical provenance. An owned or rented plan
without applicable complete serving evidence remains planning only even with G8–G10 off.
