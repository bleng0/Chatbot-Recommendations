# POME evidence plan (G1-G14): how to get honest numbers for free

Retrieved 2026-11-22 unless noted. No API was called and nothing was bought or signed up for. Tags: **M** = measured, **VD** = vendor-doc, **MOD** = modeled. Source numbers [Sx] refer to the list at the end.

**Main findings**
1. **Gemini Developer API (configs 1-3) fails G12 and G13 based on vendor docs alone.** On paid tier, Google may store or cache data in any country where it has facilities [S3]. Its usage policy keeps prompts and outputs for 55 days for abuse monitoring [S4], which is more than the 30 days G13 allows. On free tier, Google also uses the data to improve its products [S1][S3]. A configuration that can pass G12/G13 is **Vertex AI in asia-south1**. India ML processing is listed for `gemini-2.5-flash` (128k), `gemini-3.5-flash` and `gemini-3.5-flash-lite`. It is not listed for 2.5 Flash-Lite or 3.1 Flash-Lite [S6]. Proposal: add these as configs 1b/2b.
2. **The config-1 replacement is `gemini-3.5-flash-lite`.** Since 2026-09-18, the 2.5 models are available only to projects that have already used them, and Google recommends 3.5 Flash-Lite for new projects [S2][S2b]. It has a free tier, and its **Batch API is free on the free tier** [S1]. That is the cheapest way to score the full pilot sample.
3. **Self-hosting Gemma 4 24/7 in India fails G11 at every provider priced here** (cheapest is about $1,533/month). Whether G8 passes is uncertain (see B).

---

## A. Quality data without manual work

| Option | Limits (source) | Data / training terms | Counts as `measured` for our config? |
|---|---|---|---|
| Gemini API free tier, more projects | Limits apply **per project, not per key**. RPD resets at midnight Pacific. Per-model numbers are shown only in AI Studio [S5] | Free-tier data is used to improve products and may be reviewed by humans [S3] | Yes, same model ID. **Risk:** the Gemini terms do not mention multi-project quota stacking. The Google APIs ToS they incorporate were not checked. Ask before doing this. |
| **Batch API, free tier** | Free only for `gemini-3.5-flash-lite` and `gemini-3.1-flash-lite`. Not free for 2.5 Flash/Flash-Lite [S1]. Batch caps: 100 concurrent jobs, 2 GB input file [S5] | Same as free tier (public data only) | Yes for quality (G1-G7) of 3.5 Flash-Lite. **No** for latency. |
| Vertex AI $300 trial | Credits **cannot pay for the Gemini platform** if you sign up on or after 2026-11-16. No GPUs on a trial account [S10] | n/a | Not usable |
| OpenRouter `google/gemma-4-26b-a4b-it:free` | 20 RPM. 50 RPD, or 1,000 RPD after buying at least $10 of credits [S12]. The only free provider listed is Google AI Studio [S11] | Depends on provider; not stated on page | Yes, but it runs on the same Google backend, so expect the same 429/503 errors. Little gain. |
| **Cloudflare Workers AI** `@cf/google/gemma-4-26b-a4b-it` | 10,000 neurons/day free. Cost is 9,091 neurons per 1M input tokens and 27,273 per 1M output tokens [S13]. At 600 in / 200 out per request: (600x9,091 + 200x27,273)/1e6 = 10.9 neurons, so **about 915 requests/day** | No training on customer content. Inputs and outputs are not kept after the response [S14] | Yes for **model quality**. Record the host: precision is not disclosed [S15], so the scores may differ slightly from bf16. Needs a Cloudflare account, which the user must create. |
| HF Inference Providers | Free users get **$0** of credits. PRO gets $2/month [S16] | Depends on provider | Not free |
| Groq | No Gemma model is listed [S17] | n/a | n/a |
| NVIDIA build.nvidia.com | The model page exists, but its terms and limits could not be read [S18] | Unverified | Unverified |
| Kaggle/Colab GPUs | Kaggle's docs page did not render. A 2x T4 (16 GB each) limit is **UNVERIFIED** | n/a | Only a 4-bit model fits. That is a different artifact from bf16, so the result would be `measured` only for "Gemma 4 W4 on T4" and not for config 4. |

**Published benchmarks.** No primary source reports Gemma 4 or Gemini 2.5/3.5 scores on BANKING77, CLINC150 or MASSIVE. The Gemma 4 model card reports only general benchmarks, such as MMLU-Pro 82.6% [S7]. Those are `vendor-doc` but are not evidence for G1-G7. arXiv 2607.27421 (Ganesh et al., 2026) tests 41 open models on MASSIVE among other sets. Its abstract gives the model range as 135M-9B, so Gemma 4 26B is not covered [S19]. Use it only as literature context and do not substitute it for G1-G3.

**Sample size.** With n=30 and a true accuracy of 0.85, the Wilson 95% CI is about ±0.13, so G1-G7 decisions near the 0.80 threshold stay uncertain. With n=100 the CI is about ±0.07. Score the full pilot sample with Batch API (3.5 Flash-Lite) and Cloudflare (Gemma).

## B. Self-host inputs (config 4)

**Model facts** [S7]: 25.2B total parameters, 3.8B active, 128 experts (8 active plus 1 shared), 256K context, Apache 2.0. bf16 weights ≈ 25.2e9 x 2 B = **50.4 GB (MOD)**. vLLM support: requires vLLM ≥ 0.25.0, with an example of 1x A100/H100 bf16 at TP=1. No throughput numbers are published [S8].

**India GPU prices (on-demand, VD)**

| Provider / SKU | GPU | $/h | 730 h/month | Source |
|---|---|---|---|---|
| AWS ap-south-1 `p5.4xlarge` | 1x H100 80GB | 8.256 | 6,027 | [S20] (feed published 2026-11-21) |
| AWS ap-south-1/2 `g6e.12xlarge` | 4x L40S (no 2-GPU SKU exists) | 12.601 | 9,199 | [S20] |
| Azure Central India `NC40ads_H100_v5` (Linux) | 1x H100 NVL 94GB | 9.772 | 7,134 | [S21] |
| Azure Central India `NC24ads_A100_v4` (Linux) | 1x A100 80GB | 5.142 | 3,754 | [S21] |
| E2E Networks | 1x H100 / 1x A100 80GB / L40S | 3.99 / 2.10 / 1.20 | 2,913 / **1,533** / 1,752 (2x) | [S22] Page shows no region or date, and prices exclude tax |
| Yotta Shakti | 1x H100 SXM / 2x L40S | ₹596 / ₹593 | ₹435,080 / ₹432,890 | [S23] No date shown. Convert using a dated RBI rate (not retrieved). |
| GCP asia-south1 | a2-ultragpu-1g / a3 | not resolvable | - | The page shows only default-region prices, and a3 is 8-GPU only [S24] |

**G11 (MOD):** monthly cost = $/h x 730. Every 24/7 option costs more than $1,500. Running only during business hours (for example 12 h/day) roughly halves the cost, but then off-hours tickets cannot be served. This is an assumption the user needs to confirm.

**Throughput/latency model (MOD)**

Decode is memory-bandwidth-bound, so each decode step must read the weights it touches:
- `t_step ≈ (W_touched + KV_bytes) / (BW x η)`, with η = 0.6-0.8 (assumed, uncited).
- Expert fraction touched per layer at batch B: `f = 1 − (1 − 8/128)^B`. At B=24, f ≈ 0.79, so W_touched approaches the full 50.4 GB.
- On an H100 SXM (3.35 TB/s) [S25]: t_step ≈ 50.4/(3.35x0.7) ≈ **21 ms**. The band from η alone is 19-25 ms. On an H100 NVL (3.9 TB/s) it is about 18 ms. On an A100 (2.039 TB/s) [S26] it is about 35 ms.
- End-to-end latency `E2E ≈ TTFT + 200 x t_step` ≈ 0.2 + 4.2 = **~4.4 s on H100 bf16**, which would fail G8 (3,000 ms).
- Throughput by Little's law: concurrency N = λ x E2E = 8 x 4.4 ≈ 35. Output rate = N / t_step ≈ 1,600 tok/s, which is about 8 req/s. **G9 is borderline.**
- Prefill compute (2 x 3.8e9 x 4,800 tok/s ≈ 36 TFLOP/s) is small compared with H100 bf16 peak (1,979 TFLOPS, with sparsity [S25]).

**Error band: ±50% on t_step.** The split between attention/shared weights and expert weights is not published, η is assumed, and the model ignores scheduler overhead and prefill interference. The model is good enough to say G8 is at risk; it cannot decide G8. FP8 or TP=2 would roughly halve t_step, which brings G8 to a marginal pass. Assumption: thinking mode off, 200 output tokens.

**How to make it `measured`:** there is no free GPU with at least 52 GB. The cheapest real test is to rent **1 hour** of E2E H100 (about $4 plus tax) or AWS `p5.4xlarge` ($8.26). Then run `vllm bench serve --dataset-name random --random-input-len 600 --random-output-len 200 --request-rate 8`, which reports TTFT, TPOT, ITL and end-to-end latency [S27]. This spends money, so it needs approval.

## C. API serving metrics (G8-G10)

- **What can be measured on free tier:** only **unloaded single-request latency**, collected alongside quality calls. Quantile CI uses order-statistic ranks `n·q ± 1.96·√(n·q(1−q))`. At n=100, p95 lies between the 91st and 99th values. At n=300, it lies between ranks 278 and 292. Running 8 req/s (480 RPM) for G9 is far above free limits, so **G8 at peak and G9 cannot be measured on free tier**. Label any free-tier p95 as `measured (unloaded, free tier)`.
- **What Google publishes (VD):** Vertex AI online inference SLA is 99.5% monthly uptime. "Downtime" means a server-side 5xx rate above 5% sustained for at least 5 minutes [S28]. This does **not** support G10 (≤1% errors). The only latency SLO requires Provisioned Throughput on the global endpoint: p50 of 80 TPS for 2.5 Flash and 110 TPS for 2.5 Flash-Lite [S28]. A 200-token response at 80 TPS takes about 2.5 s plus TTFT (MOD, ±30%). Paid tiers 1-3 are defined by spend [S5]. Per-model RPM numbers appear only in AI Studio.

## D. Deployment evidence (G11-G14)

| Item | Value | Tag | Source |
|---|---|---|---|
| Gemini API paid: data use | Not used for training. Data may be cached in any country | VD | [S3] |
| Gemini API: retention | 55 days (abuse monitoring) → **G13 fail** | VD | [S4] |
| Gemini API free: data use | Used to improve products, human review possible | VD | [S1][S3] |
| Vertex India processing | asia-south1 supported: 2.5 Flash (128k), 3.5 Flash, 3.5 Flash-Lite. Not supported: 2.5 Flash-Lite, 3.1 Flash-Lite. The `global` endpoint gives no residency guarantee | VD | [S6] (updated 2026-11-20) |
| Vertex ZDR | No training. Implicit cache in memory only, deleted within 24 h. Abuse logging may apply under the GCP ToS, so confirm an exception for G13 | VD | [S9] |
| Vertex prices ($/1M in/out) | 2.5 Flash 0.30/2.50. 3.5 Flash-Lite 0.33/2.75 non-global (0.30/2.50 global). Gemma 4 26B 0.15/0.60 (region not confirmed) | VD | [S29] |
| G11 API (MOD) | Volume: 100k tickets x 600 in / 200 out = 60M in + 20M out tokens. Costs: 2.5 Flash **$68**; 2.5 Flash-Lite $14; 3.5 Flash-Lite on Vertex India **$74.80**. One call per ticket, thinking tokens excluded (they are billed as output [S1]) | MOD | [S1][S29] |
| Gemma 4 licence | Apache 2.0, no field-of-use limit → **G14 pass** | VD | [S7][S30] |

## E. Citation check

| Ref | Verdict |
|---|---|
| [1] Brynjolfsson, Li, Raymond, QJE 140(2):889-942, 2025 | **Correct.** The DOI resolves. The abstract says **5,172** agents [S31] |
| [2] FrugalGPT, Chen, Zaharia, Zou | **Correct.** TMLR (12/2024), and the PDF resolves [S32] |
| arXiv 2005.11401 | RAG, Lewis et al., NeurIPS 2020. Correct [S33] |
| arXiv 2309.06180 | vLLM/PagedAttention, Kwon et al., SOSP 2023. Correct [S33] |
| arXiv 2204.08582 | MASSIVE, FitzGerald et al., 2022. About 1M utterances, 51 languages, 60 intents. Cite the arXiv year unless the deck says ACL 2023 (not verified here) [S33] |
| naacl-main.239 | **Yes, it is ABCD** (Chen et al., NAACL-HLT 2021, pp. 3002-3017; 10K+ dialogues, 55 intents) [S34] |
| arXiv 2003.04807 | BANKING77: **13,083 examples, 77 intents, correct**. Its peer-reviewed venue is the **NLP4ConvAI workshop 2020** (pp. 38-45). Cite that venue and do not call it a main-conference paper [S33][S34] |
| D19-1131 | CLINC150, Larson et al., EMNLP-IJCNLP 2019 (pp. 1311-1316); 150 intents, 10 domains, plus OOS. Correct [S34] |

No errors found. One clarification: BANKING77 is a workshop paper.

## F. Accuracy honesty

None of these models can claim "99% accuracy". Every modeled value needs its error band and what would turn it into a measurement:

| Value | Band | What makes it `measured` |
|---|---|---|
| Self-host t_step / G8 / G9 | ±50% | 1 h paid GPU + `vllm bench serve` |
| Self-host G11 | ±10% (price drift, tax, FX) | A dated invoice or quote |
| API G11 | ±25% (real token counts, thinking tokens) | Usage metadata from the pilot calls |
| API p95 at peak | Unknown (free tier only gives unloaded latency) | A paid-tier load test (needs approval) |
| Quality at n=30 | ±0.13 | n ≥ 100 using Batch/Cloudflare |

---

## Ranked actions (cheapest and most reliable first)

| # | Action | Effort | Yields | Risks |
|---|---|---|---|---|
| 1 | Record G12/G13/G14 for all configs from [S3][S4][S6][S9][S30] | 20 min | VD | Terms change. Store the retrieval date. |
| 2 | Fix the deck: BANKING77 venue; switch config 1 to `gemini-3.5-flash-lite` | 10 min | - | None |
| 3 | Batch API (free) on `gemini-3.5-flash-lite` for the full pilot sample | 60 min | M (quality) | Free-tier data is used for training, so public data only. Batch turnaround up to about 24 h. |
| 4 | User creates a Cloudflare account, then Gemma 4 quality on the full sample (~915 req/day) | 90 min | M (quality, host-labelled) | Precision undisclosed. The account step is the user's. |
| 5 | Log latency on every free call, report p95 at n ≥ 100 | 15 min | M (unloaded only) | Do not present it as peak p95. |
| 6 | 2.5 Flash: continue ~20/day/project until each metric has at least 30 items | days | M | Multi-project stacking: ask the user first (ToS not checked) |
| 7 | Encode the B formula and the G11 formulas with cited inputs | 45 min | MOD | Error band ±50% |
| 8 | (Needs approval) 1 h H100 + `vllm bench serve` | 90 min, about $4-9 | M (G8-G10, config 4) | Spends money. Results are specific to that GPU and provider. |
| 9 | Ask the user: add Vertex asia-south1 configs (2.5 Flash, 3.5 Flash-Lite) | 5 min | - | Scope change |

## Sources (all retrieved 2026-11-22)

- S1 https://ai.google.dev/gemini-api/docs/pricing
- S2 https://ai.google.dev/gemini-api/docs/models
- S2b https://ai.google.dev/gemini-api/docs/changelog
- S3 https://ai.google.dev/gemini-api/terms (updated 2026-04-28)
- S4 https://ai.google.dev/gemini-api/docs/usage-policies (updated 2026-06-09)
- S5 https://ai.google.dev/gemini-api/docs/rate-limits (updated 2026-10-28)
- S6 https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/data-residency (HTML table parsed)
- S7 https://ai.google.dev/gemma/docs/core/model_card_4 (updated 2026-07-30)
- S8 https://recipes.vllm.ai/Google/gemma-4-26B-A4B-it
- S9 https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/zero-data-retention
- S10 https://docs.cloud.google.com/free/docs/free-cloud-features (updated 2026-11-13)
- S11 https://openrouter.ai/models/google/gemma-4-26b-a4b-it%3Afree
- S12 https://openrouter.ai/docs/api/reference/limits
- S13 https://developers.cloudflare.com/workers-ai/platform/pricing/
- S14 https://developers.cloudflare.com/workers-ai/platform/data-usage/
- S15 https://developers.cloudflare.com/workers-ai/models/gemma-4-26b-a4b-it/
- S16 https://huggingface.co/docs/inference-providers/pricing
- S17 https://console.groq.com/docs/models
- S18 https://build.nvidia.com/google/gemma-4-26b-a4b-it
- S19 https://arxiv.org/abs/2607.27421
- S20 https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ec2-ondemand-without-sec-sel/Asia%20Pacific%20(Mumbai)/Linux/index.json (and the Hyderabad file)
- S21 https://prices.azure.com/api/retail/prices (filter: centralindia)
- S22 https://www.e2enetworks.com/pricing
- S23 https://shakticloud.ai/pricing.html
- S24 https://cloud.google.com/products/compute/pricing/accelerator-optimized
- S25 https://www.nvidia.com/en-us/data-center/h100/
- S26 https://www.nvidia.com/en-us/data-center/a100/
- S27 https://docs.vllm.ai/en/latest/benchmarking/cli/
- S28 https://cloud.google.com/vertex-ai/generative-ai/sla (modified 2026-06-30)
- S29 https://cloud.google.com/vertex-ai/generative-ai/pricing
- S30 https://ai.google.dev/gemma/docs/gemma_4_license (updated 2026-04-01)
- S31 https://api.crossref.org/works/10.1093/qje/qjae044
- S32 https://lingjiaochen.com/papers/2024_FrugalGPT_TMLR.pdf
- S33 https://export.arxiv.org/api/query?id_list=2005.11401,2309.06180,2204.08582,2003.04807
- S34 https://aclanthology.org/2021.naacl-main.239/ , https://aclanthology.org/D19-1131/ , https://aclanthology.org/2020.nlp4convai-1.5/
