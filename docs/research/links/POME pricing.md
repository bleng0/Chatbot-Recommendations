# LLM API and Hosting Pricing Sources for PME Project

| Category                  | What you need to collect                                      | Priority                                |
| ------------------------- | ------------------------------------------------------------- | --------------------------------------- |
| LLM APIs                  | Input/output token prices, caching, batch discounts           | Essential                               |
| Managed inference         | Hosted endpoint prices, dedicated capacity                    | Essential                               |
| Self-hosting              | GPU/CPU prices, instance specifications, uptime               | Essential                               |
| Supporting infrastructure | Storage, networking, databases, monitoring                    | Essential for production cost estimates |
| Enterprise requirements   | Support contracts, region-specific pricing, security services | Important                               |
| Financial adjustments     | INR conversion, taxes, discounts, utilization                 | Essential for fair comparisons          |

## 1. Official LLM API pricing

|Provider|Official pricing source|What to extract|
|---|---|---|
|OpenAI|[OpenAI API pricing](https://developers.openai.com/api/docs/pricing?utm_source=chatgpt.com)|Input/output tokens, cached input, Batch/Flex, service tiers and tool charges|
|Anthropic|[Claude API pricing](https://platform.claude.com/docs/en/about-claude/pricing?utm_source=chatgpt.com)|Input/output tokens, prompt caching, batch processing|
|Google Gemini|[Gemini Developer API pricing](https://ai.google.dev/gemini-api/docs/pricing?utm_source=chatgpt.com)|Standard, Batch, Flex, context caching, grounding|
|Mistral AI|[Mistral API pricing](https://mistral.ai/pricing/api/?utm_source=chatgpt.com)|Multilingual models, input/output, batch, regional processing|
|Cohere|[Cohere pricing](https://cohere.com/pricing?utm_source=chatgpt.com)|Command models, Aya multilingual models, embeddings, reranking|
|Together AI|[Together AI pricing](https://www.together.ai/pricing?utm_source=chatgpt.com)|Open-model serverless inference, provisioned capacity, dedicated deployments|
|Fireworks AI|[Fireworks AI pricing](https://fireworks.ai/pricing?utm_source=chatgpt.com)|Serverless inference, GPU-based deployments, tuning|
|OpenRouter|[OpenRouter pricing](https://openrouter.ai/pricing?utm_source=chatgpt.com)|Multi-provider model access and additional platform fees|

### Enterprise cloud API pricing


|Cloud platform|Official pricing|
|---|---|
|Amazon Bedrock|[Amazon Bedrock pricing](https://aws.amazon.com/bedrock/pricing/?utm_source=chatgpt.com)|
|Azure OpenAI|[Azure OpenAI pricing](https://azure.microsoft.com/en-us/pricing/details/azure-openai/?utm_source=chatgpt.com)|
|Google Cloud Agent Platform / Vertex AI generative models|[Google Cloud generative AI pricing](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing?utm_source=chatgpt.com)|


## 2. Managed model hosting and inference endpoints


|Platform|Official pricing|Billing model|
|---|---|---|
|Hugging Face Inference Endpoints|[Instance pricing](https://huggingface.co/docs/inference-endpoints/pricing?utm_source=chatgpt.com)|Hourly/minute-based CPU or GPU endpoint|
|AWS SageMaker AI|[SageMaker pricing](https://aws.amazon.com/sagemaker/ai/pricing/?utm_source=chatgpt.com)|Real-time inference instances and related usage|
|Microsoft Foundry|[Microsoft Foundry pricing](https://azure.microsoft.com/en-us/pricing/details/microsoft-foundry/?utm_source=chatgpt.com)|Model inference and managed AI services|
|Together AI|[Dedicated inference and provisioned throughput](https://www.together.ai/pricing?utm_source=chatgpt.com)|Dedicated GPUs or reserved inference capacity|
|Fireworks AI|[On-demand GPU deployments](https://fireworks.ai/pricing?utm_source=chatgpt.com)|GPU-time-based inference|
|Amazon Bedrock|[Provisioned throughput and model import](https://aws.amazon.com/bedrock/pricing/?utm_source=chatgpt.com)|Token-based, reserved and model-hosting options|


### B. Specialized GPU cloud providers

| Provider  | Official source                                                              | What it is useful for                          |
| --------- | ---------------------------------------------------------------------------- | ---------------------------------------------- |
| RunPod    | [RunPod GPU pricing](https://www.runpod.io/pricing?utm_source=chatgpt.com)   | On-demand GPUs, serverless workers, storage    |
| Lambda    | [Lambda GPU cloud pricing](https://lambda.ai/pricing?utm_source=chatgpt.com) | Dedicated GPU instances                        |
| CoreWeave | [CoreWeave pricing](https://coreweave.com/pricing?utm_source=chatgpt.com)    | Production GPU deployments and larger clusters |
| Vast.ai   | [Vast.ai GPU marketplace](https://vast.ai/pricing?utm_source=chatgpt.com)    | Market-priced GPU instances                    |
### C. India-focused infrastructure providers


[E2E Networks GPU Cloud](https://www.e2enetworks.com/gpu-cloud?utm_source=chatgpt.com)



[Yotta Shakti Cloud](https://shakticloud.ai/pricing/?utm_source=chatgpt.com)



[Neysa Velocis](https://neysa.ai/pricing?utm_source=chatgpt.com)




### Indicative GPU prices from official rate cards


|Provider|GPU|Advertised price|
|---|---|---|
|E2E Networks|NVIDIA L4 24 GB|₹49/hour|
|E2E Networks|NVIDIA L40S 48 GB|₹102/hour|
|E2E Networks|NVIDIA A100 80 GB|₹189/hour|
|Yotta Shakti Cloud|NVIDIA L40S on-demand VM|₹137/hour|
|Yotta Shakti Cloud|NVIDIA H100 on-demand VM|₹356/hour|


## 4. Additional infrastructure prices you should not ignore

|Expense|Official source|When it matters|
|---|---|---|
|Model weights and ticket storage|[Amazon S3 pricing](https://aws.amazon.com/s3/pricing/?utm_source=chatgpt.com)|Storing models, datasets, conversation records|
|GPU VM disk storage|[Amazon EBS pricing](https://aws.amazon.com/ebs/pricing/?utm_source=chatgpt.com)|Persistent volumes and model checkpoints|
|Google Cloud storage|[Cloud Storage pricing](https://cloud.google.com/storage/pricing?utm_source=chatgpt.com)|Alternative storage pricing and locations|
|Internet data transfer|[Google network pricing](https://cloud.google.com/network-tiers/pricing?utm_source=chatgpt.com)|Traffic entering/leaving customer-service infrastructure|
|Load balancing|[AWS load balancer pricing](https://aws.amazon.com/elasticloadbalancing/pricing/?utm_source=chatgpt.com)|Production API endpoints, multiple replicas|
|Monitoring and logs|[CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/?utm_source=chatgpt.com)|Logs, metrics, tracing, alerting|
|Encryption keys|[AWS KMS pricing](https://aws.amazon.com/kms/pricing/?utm_source=chatgpt.com)|Customer-managed encryption keys|
|Vector search|[OpenSearch pricing](https://aws.amazon.com/opensearch-service/pricing/?utm_source=chatgpt.com)|RAG-based customer-support assistants|
|Managed vector database|[Pinecone pricing](https://www.pinecone.io/pricing/?utm_source=chatgpt.com)|Retrieval over company knowledge bases|


## 5. Cloud pricing calculators


![](https://www.google.com/s2/favicons?domain=https://aws.amazon.com&sz=32)

[AWS Pricing Calculator](https://calculator.aws/?utm_source=chatgpt.com#/)

Configure instance type, region, operating hours, storage and associated services.

![](https://www.google.com/s2/favicons?domain=https://azure.microsoft.com&sz=32)

[Azure Pricing Calculator](https://azure.microsoft.com/en-us/pricing/calculator/?utm_source=chatgpt.com)

Compare virtual machines, AI services, storage and contracted pricing.

![](https://www.google.com/s2/favicons?domain=https://cloud.google.com&sz=32)

[Google Cloud Pricing Calculator](https://cloud.google.com/products/calculator?utm_source=chatgpt.com)


## 6. Machine-readable pricing sources for your actual tool

This is especially important. Instead of manually updating hundreds of prices, you can use existing pricing catalogs and APIs.

|Source|Link|Best use|
|---|---|---|
|LiteLLM model cost map|[LiteLLM pricing documentation](https://docs.litellm.ai/docs/proxy/model_cost_map?utm_source=chatgpt.com)|Unified model pricing across numerous providers|
|LiteLLM model catalog|[LiteLLM models and prices](https://models.litellm.ai/?utm_source=chatgpt.com)|Browse supported models, prices and context lengths|
|Azure Retail Prices API|[Azure pricing API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices?utm_source=chatgpt.com)|Retrieve cloud SKU and region-specific rates programmatically|
|AWS Price List API|[AWS Price List documentation](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-changes.html?utm_source=chatgpt.com)|Retrieve AWS service prices|
|Google Cloud Billing Catalog|[Cloud Billing Catalog API](https://docs.cloud.google.com/billing/v1/how-tos/catalog-api?utm_source=chatgpt.com)|Retrieve Google Cloud SKUs, regions and public rates|


















## 7. How your pricing engine should calculate costs

You'll need two fundamentally different calculations.

### External API
![[Pasted image 20261027052054.png]]

- \(N\): Number of monthly model requests.

- \(T_{\text{in}}\): Average billable input tokens per request.

- \(T_{\text{out}}\): Average billable output tokens per request.

- \(P_{\text{in}},P_{\text{out}}\): Prices per million tokens.

- \(C_{\text{extra}}\): Applicable tool calls, caching adjustments, support charges and other costs.


For production-grade estimates, extend the formula for cached versus uncached tokens, multiple model calls per ticket, retries, long-context tiers and batch discounts.

### Self-hosted model

![[Pasted image 20261027052345.png]]

Here \(G\) represents GPUs allocated, \(H\) is billable hours per GPU, and \(P_{\text{GPU}}\) is the hourly GPU or GPU-instance rate. Other costs include infrastructure and operations not already included in the quoted instance price.

Crucially, GPU count must be determined from measured model throughput, concurrency requirements, latency targets and availability requirements, not just monthly ticket volume.

For example, an enterprise receiving 100,000 tickets concentrated into business hours may need a different number of GPU replicas than one with the same ticket volume distributed uniformly across the month.

## 8. Minimum pricing database I would build

Your tool should store the following for each model-and-hosting configuration.

|   |   |   |
|---|---|---|
|Field group|Data to save|Priority|
|Provider and model|Provider, model ID, version, deployment type|Required|
|Inference pricing|Input/output token rates; cached and batch rates|Required for APIs|
|Compute pricing|GPU/VM hourly price, GPU type/count, reserved price|Required for hosting|
|Location|Region, processing location, data-storage location|Required|
|Capacity|Measured requests/sec, tokens/sec, peak concurrency|Required|
|Performance|Measured latency, task accuracy, language-level quality|Required|
|Billing terms|Minimum uptime, billing increments, commitment term|Required|
|Infrastructure|Storage, networking, load balancing, observability|Production estimate|
|Commercial terms|Currency, GST/taxes, discounts, support costs|Production estimate|
|Provenance|Official URL, retrieval date, price effective date, assumptions|Required|

For India-specific deployment decisions, maintain a separate verified regional capability and data-governance record. An India-hosted server does not, by itself, establish legal compliance, and a vendor's advertised price is not evidence that the selected model or GPU is available in the requested region.

## 9. Recommended scope for your first pricing comparison

To keep the project feasible while covering genuinely different deployment options:

|Deployment category|Suggested providers|
|---|---|
|Direct managed LLM APIs|OpenAI, Anthropic, Google Gemini|
|Open-weight model APIs|Together AI, Fireworks AI, Mistral|
|Large-cloud managed deployment|AWS Bedrock, Azure Foundry, Google Cloud|
|Self-hosted GPU cloud|AWS EC2 or Google Cloud|
|India-focused GPU infrastructure|E2E Networks, Yotta Shakti Cloud|
|Dedicated managed endpoint|Hugging Face Inference Endpoints|

You don't need to benchmark all these providers. A strong initial experiment would compare roughly 4–6 models across 3 deployment approaches, using equivalent workload assumptions and documented performance measurements.

The central research question is not simply which API has the lowest token rate. It is:

At what workload volume, concurrency, quality requirement and hosting restriction does one model–deployment configuration become preferable to another?

That is where your project's decision engine becomes useful.