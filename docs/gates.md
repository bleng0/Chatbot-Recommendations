# How POME models serving gates G8–G10

POME uses estimates to fill missing serving metrics. It combines values saved from external sources, project assumptions, and a reference evaluation run. The examples below reproduce the values in the repository, so they use the stored inputs even if a provider has since changed its rates or benchmark results.

| Gate | What a peak-load test would measure | Target |
|---|---|---|
| G8 | End-to-end latency at the 95th percentile | At most 20,000 ms |
| G9 | Sustainable request rate while meeting G8 and G10 | At least 5 requests per second |
| G10 | Share of original requests that still fail after the retry policy runs | At most 1% |

POME compares the three stored values separately. A modeled pass can contribute to a recommendation marked **Eligible (modeled)**. Missing serving evidence is marked **Not tested** and does not block selection in this prototype. Verifying all three targets requires measuring them on the same deployment, with the same request mix and retry policy, at the same sustained load. [Gate requirements](../CONSTRAINTS.md#a-decision-gates-product-bar-profile-banking_mvp) · [Selection engine](../pome/selection/engine.py)

## Inputs and provenance

The application reads [gapfill.yaml](../pome/registry/gapfill.yaml), which records values, model or tier labels, and source URLs. It uses **600 input tokens** and **200 output tokens** as fixed workload assumptions for these serving formulas. The values are curated in the repository and reused at runtime. The [gap-fill implementation](../pome/evidence/gapfill.py) adds each serving estimate only when that metric is missing. In the app, the **Evidence** tab displays the metric’s **Source** and **Formula**.

## G8 · Response time

### Managed API

```text
T = time_to_first_token_seconds + output_tokens / generation_tokens_per_second
G8 = round(1,000 × T) milliseconds
```

Dividing tokens by tokens per second gives the estimated decode time in seconds. POME adds time to first token (TTFT) and uses all 200 output tokens in the division. This is a POME approximation based on two published inputs. It assumes the speed input represents generation after the first token. If the source’s speed already covers the full request, adding TTFT counts some of that time twice. In particular, Artificial Analysis’s current methodology describes its output speed as covering the full request. The repo describes its stored inputs as published medians. Combining headline figures does not produce a p95 at peak load. [POME formula](../pome/evidence/gapfill.py#L88) · [Artificial Analysis methodology](https://artificialanalysis.ai/methodology/performance-benchmarking)

**GPT-5.4 Mini example.** Stored TTFT is 1.18 s and stored speed is 125 tokens/s. Decode time is `200 / 125 = 1.60 s`. Then `1.18 + 1.60 = 2.78 s`, stored as **2,780 ms**. [Stored inputs](../pome/registry/gapfill.yaml#L29) · [Benchmark source recorded in the repo](https://artificialanalysis.ai/models/gpt-5-4-mini)

### Historical rented-GPU reference

```text
weights_GB = parameters_in_billions × 2
effective_bandwidth_GB_per_second = bandwidth_TB_per_second × 1,000 × efficiency
decode_seconds_per_token = weights_GB / effective_bandwidth_GB_per_second
T = assumed_time_to_first_token_seconds + output_tokens × decode_seconds_per_token
G8 = round(1,000 × T) milliseconds
```

BF16 uses 16 bits, or two bytes, per parameter. POME estimates each decode step as one read of the modeled weight footprint. The implementation uses one A100 80 GB with **1.935 TB/s** of nominal bandwidth and project assumptions of **70%** bandwidth efficiency and **0.2 s** TTFT. It uses total configured parameters and ignores factors such as attention cache traffic, queueing, and how batching changes latency. The source note’s **±50%** is an uncertainty annotation. The app retains this estimate as reference evidence. The selected GPU plan needs applicable serving evidence for its own verdict. See [Hosting distinction](distinction.md). [POME evidence plan, section B](research/evidence-plan.md#b-self-host-inputs-config-4) · [NVIDIA A100 specs](https://www.nvidia.com/en-us/data-center/a100/) · [vLLM technical report on the weight-read bandwidth limit](https://www2.eecs.berkeley.edu/Pubs/TechRpts/2025/Archive/EECS-2025-192.pdf) · [POME implementation](../pome/evidence/gapfill.py#L122)

**Gemma 4 12B BF16 example.** The modeled weights are `12 × 2 = 24 GB`. Effective bandwidth is `1.935 × 1,000 × 0.70 = 1,354.5 GB/s`. A decode step takes `24 / 1,354.5 ≈ 0.01772 s`. Adding TTFT gives `0.2 + 200 × (24 / 1,354.5) ≈ 3.74374 s`, stored as **3,744 ms**. The same serving proxy is used for the local Ollama 12B quality configuration. [Stored self-hosting inputs](../pome/registry/gapfill.yaml#L70)

## G9 · Sustainable throughput

POME chooses the API calculation from the quota type in the repository. The stored result is rounded to two decimal places. [API quota inputs](../pome/registry/gapfill.yaml#L43) · [Calculation branches](../pome/evidence/gapfill.py#L94)

| Quota type | Calculation | Worked example and input source |
|---|---|---|
| Requests per minute | Divide the limit by 60 seconds per minute. | GPT-5.4 Mini Tier 1: `500 / 60 = 8.33 req/s`. [OpenAI model documentation](https://developers.openai.com/api/docs/models/gpt-5.4-mini) |
| Requests per second | Use the published limit directly. | Mistral Small 4 uses a free-tier proxy of **1 req/s**. [Mistral free-tier limits](https://help.mistral.ai/en/articles/225174-what-are-the-limits-of-the-free-tier) |
| Maximum concurrent requests | Divide the concurrent request limit by the G8 estimate in seconds, before millisecond rounding. | DeepSeek Flash: `2,500 / (0.78 + 200 / 227) ≈ 1,505.07 req/s` after rounding. [DeepSeek rate limits](https://api-docs.deepseek.com/quick_start/rate_limit) · [Stored speed inputs](../pome/registry/gapfill.yaml#L29) |
| Spend per 10 minutes | Divide the cap in dollars by estimated dollars per request, then by 600 seconds. | Gemini 2.5 Flash: `(600 × $0.30 + 200 × $2.50) / 1,000,000 = $0.00068/request`. Then `$10 / $0.00068 / 600 = 24.51 req/s` after rounding. [Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) · [Stored prices](../pome/registry/configs.yaml) |

The concurrency formula comes from **Little’s law**, `L = λ × W`. In a stable system, the average number of requests in the system equals the average request rate times the average time a request spends in the system. Rearranging gives `λ = L / W`. POME substitutes a maximum or assumed concurrency for the average number of requests and the G8 estimate for average request time. That makes the result a planning estimate. A single quota or spend cap can also overstate throughput when another limit binds. [Little (1961), original proof](https://pubsonline.informs.org/doi/10.1287/opre.9.3.383)

**Historical rented-GPU example.** POME uses **32 concurrent sequences** as a project assumption. Using the unrounded Gemma 4 12B latency gives `32 / 3.74374 ≈ 8.55 req/s`. This estimate exceeds the default 5 req/s floor. The same configuration’s G8 estimate would exceed a tighter 3-second target. [Self-hosting inputs](../pome/registry/gapfill.yaml#L70) · [Self-hosting calculation](../pome/evidence/gapfill.py#L130)

## G10 · Request failures after retries

### Uptime SLA proxy

```text
G10 = round(100 − uptime_SLA_percent, 2)
```

This complement converts an uptime percentage into the share of time outside the uptime commitment. POME uses that as a proxy for request failures. It does not account for how traffic is distributed during outages, what retries recover, or what failures occur while the service is available. For GPT-5.4 Mini, the stored **Scale Tier** SLA gives `100 − 99.9 = 0.10%`. The G9 example uses a **Tier 1** quota. For the historical rental proxy, the same calculation uses a **99.9% single-VM** SLA and does not include failures in the model server. [POME formula](../pome/evidence/gapfill.py#L111) · [OpenAI Scale Tier](https://openai.com/api-scale-tier) · [Microsoft cloud service SLAs](https://www.microsoft.com/licensing/docs/view/Service-Level-Agreements-SLA-for-Online-Services)

### Saved-run proxy for APIs without a configured SLA

POME reads the `*_run0.jsonl` files for its configured reference, `gem25f-api-global`. It counts each record’s final HTTP status of **300 or higher** as a failure. Let `n` be the number of records, `f` the number of failures, and `p = f / n` the observed fraction. POME uses the upper endpoint of a two-sided Wilson score interval with `z = 1.96` (approximately 95% confidence).

```text
centre = p + z² / (2n)
spread = z × sqrt(p × (1 − p) / n + z² / (4n²))
upper = (centre + spread) / (1 + z² / n)
G10 = round(100 × upper, 2)
```

In the saved reference run there are **0 failures in 108 records**. The point estimate is **0%**, while the upper endpoint is about **3.43%**. POME reuses that upper endpoint as the modeled value for API entries with configured speed inputs and without a configured SLA. The interval reflects sample uncertainty for the reference run. Transferring it to another API or to peak traffic adds uncertainty that the interval does not quantify. If there are no reference records, POME cannot use this fallback. [Wilson (1927), original score interval](https://www.jstor.org/stable/2276774) · [POME implementation](../pome/evidence/gapfill.py#L43) · [Saved reference records](../runs/records/gem25f-api-global)
