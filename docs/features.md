# POME evaluator guide

POME is a decision-support prototype for choosing a model and hosting setup for a bank’s customer-support bot. It compares candidate configurations against a common set of requirements, then recommends the lowest estimated monthly cost among eligible options. Reviewers can inspect the evidence behind the recommendation and see how it changes with workload, budget, or a different set of requirements.

With the bundled evidence and default scenario of **100,000 tickets per month** and **₹1,39,195/month** maximum spend, POME evaluates **20 configurations**. It recommends **`gpt54nano-api-global` at ₹3,433/month**. Three entries are eligible on modeled evidence. The recommended entry relies on estimates or proxies beyond cost.

## Run and review the app

From the repository root:

```bash
uv sync
uv run python -m streamlit run pome/app/home.py
```

Open [localhost:8501](http://localhost:8501). The dashboard reads the bundled records and recalculates the evidence snapshot and decision as inputs change. It needs no API key and makes no live model calls. The repository also includes a separate Next.js scaffold with a health endpoint. The evaluation dashboard runs in Streamlit. [Project README](../README.md)

1. Set monthly tickets and the maximum spend in the sidebar. If exploring self-managed hosting, choose a rental machine or enter your owned GPU and costs.
2. Read the recommendation, configuration counts and the abbreviated decision hash at the top.
3. Open **Gates** to inspect the verdicts. Expand a configuration’s reasons to see what failed or lacked evidence.
4. Compare estimates in **Cost**, then trace any number to its **Source** and **Formula** in **Evidence**.
5. Use **Tweak mode** to switch off a requirement or move a threshold with the sliders in **Gates**. The app shows a separate result and keeps the recommendation at the top.

## Sidebar controls

| Control | How it affects the decision |
|---|---|
| **Tickets per month** | Changes usage-priced API estimates. Rental and ownership estimates stay fixed for the selected infrastructure. |
| **Hosting scope** | Filters the recommendation and tabs to managed cloud APIs, rented cloud GPUs, or owned self-hosting. |
| **Rented cloud GPU** | Accepts a listed or quoted cloud machine, filters by VRAM per GPU, and prices billed hours and operating add-ons. |
| **Owned self-hosting** | Accepts a known or custom NVIDIA GPU, filters by VRAM per GPU, and models the shared hardware and operating costs. |
| **Budget and error limit** | Set the recommendation's G11 and G10 limits. |
| **Eligibility settings** | Gate switches and threshold sliders update the recommendation. Reset to recommended restores all app settings. |

## What each tab shows

| Tab | What to look for |
|---|---|
| **Gates** | Hosting type, readiness and verdict per configuration, with a toggle for actual values. |
| **Baselines** | Alternative selection rules scoped to the current deployment filter. |
| **Cost** | Upfront and monthly costs by hosting type, budget and break-even comparisons for complete estimates. |
| **Evidence** | Metric provenance, test settings, formulas and serving references excluded from the current plan. |
| **Deployment variants** | The selected candidate's infrastructure, serving steps and distinct published setups. |
| **Configurations** | Model, hosting, runtime, region and build steps for the filtered candidates. |

### Configurations, variants, and evidence

A **configuration** is a candidate POME can evaluate. The candidates are curated in [the configuration registry](../pome/registry/configs.yaml). Each has a unique ID and specifies a model/version, host, region, serving software, weight format, and available pricing and deployment evidence. The [registry loader](../pome/registry/loader.py) checks the schema and rejects duplicate IDs. To add a candidate, add a registry entry and supply the evidence needed to judge it.

For example, `gemma4-12b-ollama-local-q4` identifies a local 4-bit Ollama setup used to measure quality. `gemma4-12b-vllm-in-bf16` identifies a proposed India-region cloud GPU setup using vLLM and BF16. The vLLM entry explicitly borrows quality evidence from the local run, so the borrowed values are modeled for that deployment.

A **deployment variant** is a published way to run a model. A row can specify serving software, precision, GPU type and count, batching or concurrency, context limits, and test token counts. `MATCH` indicates that the registry considers the setting close enough to the target workload to inform a modeled estimate. `REFERENCE` provides context. To receive its own verdict, a variant needs its own configuration entry.

Read each published figure alongside the hardware, precision, and workload on its own card. For Gemma 4 31B, the BF16 vLLM row describes two A100/H100 GPUs with tensor parallelism of two and has **no published figure** recorded. The separate Ollama 4-bit row shows **20 GB weights**. This is the approximate footprint of the model parameters in that format. If all the weights reside on the GPU they occupy VRAM. CPU execution uses system RAM, and some setups split the weights across both. Inference needs additional memory for active request state and runtime buffers.

The upper panel identifies the **parent configuration** and separately labels the **monthly estimate from sidebar settings**. For example, **₹8,53,613/month** corresponds to one AWS Mumbai four-L40S instance at the stored hourly price with zero added operating cost. The two-A100/H100 card describes a separate published setup and has no rental estimate of its own. [Deployment entries](../pome/registry/configs.yaml) · [Rendering code](../pome/app/home.py)

**Evidence** is the information POME uses to judge configurations. **Measured** values come from saved POME runs. **Published** values come from a vendor or study. **Modeled** values come from formulas or proxies, including quality borrowed from a reference model, costs computed from prices and usage, and serving estimates. The evaluation mode in the registry describes how an entry is intended to be evaluated. Inspect its evidence rows to see what was actually collected.

## The banking MVP gates

`banking_mvp` is the acceptance profile for the minimum viable banking support bot. It covers recognition of banking requests, correct FAQ handling, and appropriate refusals in English, Hindi, and Hinglish, alongside serving, cost, and licence requirements. [Profile](../pome/profiles/banking_mvp.yaml) · [Constraints](../CONSTRAINTS.md)

| Gate | Passing requirement |
|---|---|
| **G1 · Banking intent recognition** | BANKING77 macro-F1 **≥ 0.80**. Macro-F1 weights all intent labels equally. |
| **G2 · Out-of-scope recall** | Flag **≥ 85%** of genuinely out-of-scope questions. |
| **G3 · Out-of-scope precision** | **≥ 80%** of the questions flagged out of scope actually are out of scope. |
| **G4 · FAQ accuracy** | Select the correct answer for **≥ 80%** of answerable FAQs in each language. |
| **G5 · Appropriate FAQ refusal** | Decline **≥ 80%** of unanswerable FAQs in each language. |
| **G6 · Hindi quality gap** | Hindi trails English by at most **10 percentage points** on each of intent macro-F1, FAQ accuracy, and FAQ refusal. |
| **G7 · Hinglish quality gap** | Hinglish trails English by at most **10 percentage points** on each of FAQ accuracy and FAQ refusal. |
| **G8 · Latency at peak** | End-to-end p95 **≤ 20,000 ms**. |
| **G9 · Sustainable throughput** | Sustain **≥ 5 requests/second** while meeting G8 and G10. |
| **G10 · Failure rate after retries** | **≤ 1%** of requests still fail after retries at the target load. |
| **G11 · Monthly budget** | Estimated monthly cost is at or below the sidebar’s maximum. |
| **G12 · Data residency** | Inference processing stays in India. Available as an opt-in filter. |
| **G13 · Retention** | Provider prompt and response retention stays within the selected cap. Available as an opt-in filter. |
| **G14 · Commercial use** | The documented model licence or provider terms permit commercial use. |
| **G15–G19 · Governance** | Optional India-only storage, no training, no prompt logging, buyer-reviewed contract, and buyer-verified settings. |

The [compliance decision record](compliance.md) describes how deployment-specific facts and
unknowns feed these filters.

G2 starts with all genuinely out-of-scope questions. G3 starts with all questions the model flagged. If it catches 17 of 20 out-of-scope questions and wrongly flags 5 legitimate ones, its recall is **85%**, while its precision is **17 ÷ 22 ≈ 77%**. It passes G2 and fails G3.

A failed gate rejects a candidate. Missing or invalid required evidence yields **Unverified** when there is no failure. G8–G10 have an explicit exception for missing serving evidence, shown as **Not tested**, which does not block selection. When a candidate qualifies using modeled evidence beyond cost, POME flags its eligibility as modeled. It ranks eligible candidates by monthly cost, then favors serving evidence, larger quality margin, lower p95, and finally configuration ID. If nothing qualifies, it reports no feasible option. Content hashes identify the evidence snapshot, profile, and decision so the result can be reproduced from the same inputs. [Selection engine](../pome/selection/engine.py)

## Quality benchmarks and saved runs

| Benchmark | Bundled sample and scoring | Gates |
|---|---|---|
| **BANKING77** | 300 requests spanning 77 banking intents. Score intent macro-F1. | G1 |
| **CLINC150** | 150 in-scope and 100 out-of-scope requests. Score out-of-scope recall and precision. | G2, G3 |
| **Amazon MASSIVE** | 150 matched English/Hindi examples, 300 inputs in total. Compare intent macro-F1 across languages. | G6 |
| **Banking FAQ pilot** | 30 questions each available in English, Hindi, and Hinglish. Select an approved answer ID or signal that the question cannot be answered. Score correct selections and correct declines separately. | G4, G5 and the FAQ parts of G6 and G7 |

The saved results cover BANKING77, CLINC150, and both MASSIVE languages for Gemini 2.5 Flash, Gemma 4 26B via API, and Gemma 4 12B via Ollama. The FAQ pilot has saved results only for local Gemma 4 12B, with 15 requests per language. Bundled sample sizes describe what is available to run. The prototype uses the point estimate from the saved run for each quality gate and requires at least 15 scored items to use a quality metric. [Dataset manifest](../pome/data/manifest.json) · [Task loader](../pome/eval/datasets.py) · [Saved runs](../runs/records)

## How serving performance is modeled

POME has no peak-load benchmark for G8–G10. For entries with configured inputs, the app fills missing values with the following proxies. The stored reference workload uses 600 input tokens and 200 output tokens.

| Gate | Managed API | Self-managed cloud GPU |
|---|---|---|
| **G8** | Estimate time to first token plus output tokens divided by published generation speed. GPT-5.4 Mini gives `1.18 + 200 / 125 = 2.78 s`. | Estimate a BF16 weight read per generated token. Divide weight GB by effective GPU bandwidth, multiply by output tokens, and add assumed time to first token. A 12B model gives about **3.74 s** with the stored A100 assumptions. |
| **G9** | Convert the published requests-per-minute limit, use a published requests-per-second limit, divide concurrent requests by estimated latency, or divide a spend cap by modeled cost per request and the time window. For GPT-5.4 Mini the stored quota gives `500 / 60 = 8.33 req/s`. | Divide the assumed 32 concurrent sequences by estimated response time. The 12B example gives about **8.55 req/s** under the fixed bandwidth and concurrency assumptions. |
| **G10** | Subtract a documented uptime SLA from 100%, or use the upper endpoint of a Wilson interval on a saved reference run’s failure share. For GPT-5.4 Mini the Scale Tier SLA proxy gives **0.10%**. | Subtract the stored single-VM uptime SLA from 100%. This leaves out model-serving failures while the VM is available. |

The G8 estimate uses headline benchmark inputs, the G9 quota describes permitted traffic, and the G10 SLA describes availability. A peak-load test on the exact deployment is needed to measure all three together. [Detailed formulas, assumptions, examples, and sources](gates.md) · [Stored model inputs](../pome/registry/gapfill.yaml)

## Cost and hosting assumptions

**Managed model API.** Monthly cost is estimated as `tickets × (input tokens per ticket × input price per million + output tokens per ticket × output price per million) / 1,000,000`. POME uses measured average token counts where available for the cost calculation, and modeled token counts or proxy prices where configured.

**Rented cloud GPU and owned self-hosting.** Rentals are billed per node-hour and
include operator-entered add-ons. Owned estimates amortize the component bill and add power
and recurring operating costs. A valid serving test must match the selected deployment.
See the bills of materials, prices and runbooks in [Hosting distinction](distinction.md).

## How new evidence enters the dashboard

The evaluation CLI runs selected tasks for existing configuration IDs. It supports Gemini and local Ollama, cached replay, smaller samples, repeated runs, configurable concurrency, and spend controls for paid runs. It writes JSONL records under `runs/records/<configuration>/`, including predictions, token counts, retry counts, and final statuses. The evidence builder reads the recorded results, adds registry evidence and cost calculations, and fills configured gaps with modeled proxies. The selection engine evaluates that snapshot against the current profile and scenario. [Evaluation CLI](../pome/eval/cli.py) · [Evidence builder](../pome/evidence/build.py) · [Gap-fill implementation](../pome/evidence/gapfill.py)
