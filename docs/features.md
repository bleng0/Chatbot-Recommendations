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

1. Set monthly tickets and the maximum spend in the sidebar. If exploring self-managed hosting, choose a cloud GPU rental offering, quantity, and operating cost.
2. Read the official recommendation, configuration counts and the abbreviated decision hash at the top.
3. Open **Gates** to inspect the verdicts. Expand a configuration’s reasons to see what failed or lacked evidence.
4. Compare estimates in **Cost**, then trace any number to its **Source** and **Formula** in **Evidence**.
5. Use **Tweak mode** to switch off a requirement or move a threshold with the sliders in **Gates**. The app shows a separate result and keeps the recommendation at the top.

## Sidebar controls

| Control | How it affects the decision and main page |
|---|---|
| **Tickets per month** | One ticket represents one model call. Changing ticket volume changes estimated usage-priced API costs, cost bars, and budget verdicts. At a fixed rental quantity, the self-managed cloud GPU cost stays flat. |
| **Max monthly spend, INR** | Sets G11. It moves the budget line on the Cost chart and changes which candidates are over budget. The candidate cost estimates themselves stay the same. |
| **Self-host GPU (India price)** | Selects the recorded hourly price of a cloud GPU rental offering. Changing it updates self-hosted cost cells, chart bars, evidence entries, and the scenario estimate panel in Deployment variants. |
| **GPUs** | For pricing, this field acts as a rental **instance count**. A four-GPU offering at quantity 2 prices two machines, with eight GPUs in total. |
| **Self-host ops cost, INR/month** | Adds a fixed amount to each self-hosted estimate. It defaults to ₹0 and affects budget verdicts and break-even points. |
| **Max error rate after retries, %** | Sets the official G10 failure-rate limit. The verdicts and the error-rate display in **Gates** use it. |
| **Tweak mode** | Switching off a gate adds a separate what-if decision. The sliders in **Gates** adjust thresholds for that same what-if view. Candidates that pass only after a threshold is loosened are marked **Not recommended**. |

Cost and workload edits can change the official recommendation. They do not rerun the benchmarks or resize the serving model. The sidebar’s rental selection and quantity affect cost, while the modeled self-hosted performance continues to use its fixed A100 assumptions. [Dashboard implementation](../pome/app/home.py) · [Scenario implementation](../pome/app/scenario.py)

## What each tab shows

| Tab | What to look for |
|---|---|
| **Gates** | A side-by-side matrix of gate outcomes and costs, with expandable reasons for individual verdicts. When Tweak mode is active, the table also shows the what-if verdicts. |
| **Baselines** | Compares the recommendation with the app’s benchmark-score, lowest-price, and self-host-only rules. The gate descriptions and default targets appear in the sidebar’s toggle help. |
| **Cost** | Modeled monthly costs in INR, a budget line, a table at other ticket volumes, and interactive API cost curves and break-even estimates against the reference Gemma 4 12B self-hosted configuration. |
| **Evidence** | Expand a configuration to see its evidence grouped by quality, serving, cost, and deployment. Each metric includes provenance and source details, with formulas where available. |
| **Deployment variants** | Select a model to see its registered deployment, the sidebar-based rent estimate, and cards for published setups. Expand a card to see its source and conditions. |
| **Configurations** | The candidates in the registry, with model, host, region, serving software, and quantization. Browse the cards to see each configuration’s build steps. |

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
| **G12 · Data residency** | Customer data is processed in India. Optional and inactive in this prototype profile. |
| **G13 · Retention** | Provider retention **≤ 30 days**. Optional and inactive in this prototype profile. |
| **G14 · Commercial use** | The documented model licence or provider terms permit commercial use. |

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

**Self-managed cloud GPU rental.** Monthly cost is `rental instances × hourly price × 730 hours + monthly operating costs`, converted to INR for display using the app’s stored exchange rate. The app currently applies the same sidebar scenario across self-hosted entries. The four-L40S example is `1 × $12.601 × 730 × ₹92.7968/$ ≈ ₹8,53,613` before any operating costs.

Increasing quantity prices additional rental instances. Actual availability depends on account quota and capacity. Two one-GPU instances and one two-GPU instance have different interconnects and deployment requirements. Pricing a quantity does not verify that the model fits, can use the hardware together, or can sustain peak traffic.

**On-premises hosting** would require a separate cost model for hardware purchase amortization, power, and maintenance. The current app estimates cloud rental for its self-managed deployment scenarios. The break-even estimate divides fixed monthly self-hosted cost by the API price per ticket. It compares costs at the assumed capacity. [Cost formulas](../pome/cost/model.py) · [Cost and scenario inputs](../pome/app/scenario.py)

## How new evidence enters the dashboard

The evaluation CLI runs selected tasks for existing configuration IDs. It supports Gemini and local Ollama, cached replay, smaller samples, repeated runs, configurable concurrency, and spend controls for paid runs. It writes JSONL records under `runs/records/<configuration>/`, including predictions, token counts, retry counts, and final statuses. The evidence builder reads the recorded results, adds registry evidence and cost calculations, and fills configured gaps with modeled proxies. The selection engine evaluates that snapshot against the current profile and scenario. [Evaluation CLI](../pome/eval/cli.py) · [Evidence builder](../pome/evidence/build.py) · [Gap-fill implementation](../pome/evidence/gapfill.py)
