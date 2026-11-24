## 1. Direct LLM API providers


|Provider|Pricing and billing|Data policies, retention, logging and contract evidence|
|---|---|---|
|OpenAI API|[API price list](https://developers.openai.com/api/docs/pricing?utm_source=chatgpt.com)|[Data controls, retention, regional processing and logging](https://developers.openai.com/api/docs/guides/your-data?utm_source=chatgpt.com) · [Data Processing Addendum](https://openai.com/policies/data-processing-addendum/?utm_source=chatgpt.com)|
|Anthropic Claude API|[Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing?utm_source=chatgpt.com)|[API retention and ZDR](https://platform.claude.com/docs/en/build-with-claude/api-and-data-retention?utm_source=chatgpt.com) · [Training policy](https://privacy.claude.com/en/articles/7996868-is-my-data-used-for-model-training?utm_source=chatgpt.com) · [Standard retention](https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data?utm_source=chatgpt.com)|
|Google Gemini Developer API|[Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing?utm_source=chatgpt.com)|[Paid/free-tier data terms](https://ai.google.dev/gemini-api/terms?utm_source=chatgpt.com) · [Zero data retention](https://ai.google.dev/gemini-api/docs/zdr?utm_source=chatgpt.com) · [Logging and sharing controls](https://ai.google.dev/gemini-api/docs/logs-policy?utm_source=chatgpt.com)|

## 2. Major cloud platforms: pricing, regions and data controls


|Platform|Official links|What the sources establish|
|---|---|---|
|Amazon Bedrock|[Pricing](https://aws.amazon.com/bedrock/pricing/?utm_source=chatgpt.com) · [Model-specific regions](https://docs.aws.amazon.com/bedrock/latest/userguide/models-region-compatibility.html?utm_source=chatgpt.com) · [Inference routing](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html?utm_source=chatgpt.com)|Token/reserved pricing, model availability, in-region versus cross-region routing|
|Amazon Bedrock data policies|[Data protection](https://docs.aws.amazon.com/bedrock/latest/userguide/data-protection.html?utm_source=chatgpt.com) · [Retention modes](https://docs.aws.amazon.com/bedrock/latest/userguide/data-retention.html?utm_source=chatgpt.com) · [Logging controls](https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html?utm_source=chatgpt.com)|Prompt handling, model-specific retention policies, configurable account logging|
|Microsoft Foundry / Azure OpenAI|[Pricing](https://azure.microsoft.com/en-us/pricing/details/azure-openai/?utm_source=chatgpt.com) · [Deployment types and processing regions](https://learn.microsoft.com/azure/ai-foundry/foundry-models/concepts/deployment-types?utm_source=chatgpt.com)|Per-token, batch and provisioned capacity; global versus geographical processing|
|Azure data policies|[Data privacy and retention](https://learn.microsoft.com/en-us/azure/ai-foundry/responsible-ai/openai/data-privacy?utm_source=chatgpt.com) · [Abuse-monitoring controls](https://learn.microsoft.com/azure/foundry/openai/concepts/abuse-monitoring?utm_source=chatgpt.com)|Training restrictions, content filtering, regional processing, modified monitoring|
|Google Cloud generative AI|[Generative model pricing](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing?utm_source=chatgpt.com) · [Model endpoints and regions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/locations?utm_source=chatgpt.com)|Model-specific prices and endpoint locations|
|Google Cloud data policies|[Zero-data-retention guidance](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/vertex-ai-zero-data-retention?utm_source=chatgpt.com) · [Cloud DPA](https://cloud.google.com/terms/data-processing-addendum/?utm_source=chatgpt.com)|Training restrictions, abuse-monitoring exceptions, caching and contractual obligations|



## 3. Other LLM API and managed-inference providers

|Provider|Pricing|Data/privacy evidence|Regional or contractual evidence|
|---|---|---|---|
|Mistral AI|[API pricing](https://mistral.ai/pricing/api/?utm_source=chatgpt.com)|[ZDR](https://docs.mistral.ai/admin/monitor-comply/zero-data-retention?utm_source=chatgpt.com) · [Training opt-out](https://help.mistral.ai/en/articles/455207-can-i-opt-out-of-my-input-or-output-data-being-used-for-training?utm_source=chatgpt.com)|[Regional inference](https://docs.mistral.ai/inference/regional-inference?utm_source=chatgpt.com) · [DPA](https://legal.mistral.ai/terms/data-processing-addendum/?utm_source=chatgpt.com)|
|Cohere|[API and dedicated pricing](https://cohere.com/pricing?utm_source=chatgpt.com)|[Enterprise data commitments, retention and ZDR](https://cohere.com/enterprise-data-commitments?utm_source=chatgpt.com)|[SaaS, private cloud and on-premises deployment](https://docs.cohere.com/docs/deployment-options-overview?utm_source=chatgpt.com)|
|Together AI|[Serverless, dedicated and GPU prices](https://www.together.ai/pricing?utm_source=chatgpt.com)|[Data-handling and security commitments](https://www.together.ai/dedicated-model-inference?utm_source=chatgpt.com)|Deployment-region evidence should be requested for the selected endpoint|
|Fireworks AI|[Inference and training pricing](https://fireworks.ai/pricing?utm_source=chatgpt.com)|[Privacy policy](https://fireworks.ai/privacy-policy?utm_source=chatgpt.com) · [Trust Center](https://trust.fireworks.ai/?utm_source=chatgpt.com)|[Dedicated hosting, BYOC and regional controls](https://fireworks.ai/product/inference?utm_source=chatgpt.com)|
|Hugging Face Inference Endpoints|[Endpoint rates](https://huggingface.co/docs/inference-endpoints/pricing?utm_source=chatgpt.com)|[Security, logs, retention and DPA](https://huggingface.co/docs/inference-endpoints/security?utm_source=chatgpt.com)|[Available regions](https://huggingface.co/docs/inference-endpoints/faq?utm_source=chatgpt.com)|


## 4. Self-hosted and India-based GPU cloud evidence

| Provider                   | Price and region evidence                                                                                                                                                                               | Privacy, security and contract evidence                                                                                                                                                                         |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| AWS EC2                    | [EC2 pricing](https://aws.amazon.com/ec2/pricing/on-demand/?utm_source=chatgpt.com)                                                                                                                     | [Data privacy and region controls](https://aws.amazon.com/compliance/data-privacy-faq/?utm_source=chatgpt.com) · [Audit and agreements](https://aws.amazon.com/artifact/?utm_source=chatgpt.com)                |
| Google Cloud GPU           | [GPU rates](https://cloud.google.com/products/compute/gpus-pricing?utm_source=chatgpt.com) · [Region/GPU availability](https://docs.cloud.google.com/compute/docs/regions-zones?utm_source=chatgpt.com) | [Cloud DPA](https://cloud.google.com/terms/data-processing-addendum/?utm_source=chatgpt.com) · [Audit reports](https://cloud.google.com/security/compliance/compliance-reports-manager/?utm_source=chatgpt.com) |
| Azure GPU VMs              | [VM pricing](https://azure.microsoft.com/en-us/pricing/details/virtual-machines/linux/?utm_source=chatgpt.com)                                                                                          | [Microsoft Service Trust Portal](https://aka.ms/STP?utm_source=chatgpt.com)                                                                                                                                     |
| E2E Networks (India)       | [GPU prices, India data centers and security claims](https://www.e2enetworks.com/gpu-cloud?utm_source=chatgpt.com)                                                                                      | Confirm applicable service agreement, SLA, logging responsibilities and audit evidence with vendor                                                                                                              |
| Yotta Shakti Cloud (India) | [GPU VM, bare-metal and storage pricing](https://shakticloud.ai/pricing/?utm_source=chatgpt.com)                                                                                                        | Obtain applicable service agreement, deployment-location attestation, retention and backup configuration                                                                                                        |
| RunPod                     | [GPU, serverless and storage pricing](https://www.runpod.io/pricing?utm_source=chatgpt.com)                                                                                                             | Confirm physical region, tenancy, log retention and service terms for the selected deployment                                                                                                                   |
.

## 5. Where to find actual contract and audit evidence

| Provider        | Official contract/audit source                                                                                                                                                                                    | What to collect                                                             |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| OpenAI          | [DPA](https://openai.com/policies/data-processing-addendum/?utm_source=chatgpt.com) · [Security and compliance](https://openai.com/security-and-privacy/?utm_source=chatgpt.com)                                  | DPA, organization-specific retention approval, applicable service agreement |
| Anthropic       | [Retention arrangements](https://platform.claude.com/docs/en/build-with-claude/api-and-data-retention?utm_source=chatgpt.com) · [Trust Center](https://trust.anthropic.com/?utm_source=chatgpt.com)               | Commercial agreement, ZDR confirmation, applicable audit reports            |
| Google Cloud    | [Cloud DPA](https://cloud.google.com/terms/data-processing-addendum/?utm_source=chatgpt.com) · [Reports Manager](https://cloud.google.com/security/compliance/compliance-reports-manager/?utm_source=chatgpt.com) | Contract, SOC/ISO reports, data-location terms                              |
| Microsoft Azure | [Service Trust Portal](https://aka.ms/STP?utm_source=chatgpt.com)                                                                                                                                                 | Data protection terms, audit reports, account configuration                 |
| AWS             | [AWS Artifact](https://aws.amazon.com/artifact/?utm_source=chatgpt.com)                                                                                                                                           | SOC/ISO reports, accepted agreements, applicable service terms              |
| Mistral         | [DPA](https://legal.mistral.ai/terms/data-processing-addendum/?utm_source=chatgpt.com) · [Commercial terms](https://legal.mistral.ai/terms/commercial-terms-of-service/?utm_source=chatgpt.com)                   | Contractual training provisions, retention exceptions, regional commitments |
| Cohere          | [Enterprise commitments](https://cohere.com/enterprise-data-commitments?utm_source=chatgpt.com)                                                                                                                   | Enterprise agreement and requested DPA/ZDR confirmation                     |
| Fireworks       | [Trust Center](https://trust.fireworks.ai/?utm_source=chatgpt.com)                                                                                                                                                | SOC/ISO evidence, data-handling commitments and contract terms              |

## 6. India-specific buyer requirements: official sources

|Sector|Official source|What to evaluate|
|---|---|---|
|All sectors|[Digital Personal Data Protection Act, 2023](https://www.indiacode.nic.in/indiacode/handle/123456789/22037?view_type=browse&utm_source=chatgpt.com)|Personal-data processing obligations and restrictions, subject to commencement|
|All sectors|[DPDP Rules 2025 and enforcement timeline](https://www.meity.gov.in/documents/act-and-policies/digital-personal-data-protection-rules-2025-gDOxUjMtQWa?utm_source=chatgpt.com)|Applicable rules, phased effective dates, notices and safeguards|
|All applicable ICT organizations|[CERT-In cybersecurity directions and FAQs](https://www.cert-in.org.in/Directions70B.jsp?utm_source=chatgpt.com)|Incident reporting, ICT log retention and security responsibilities|
|Banking / financial services|[RBI payment-data storage directions](https://rbi.org.in/Scripts/NotificationUser.aspx?Id=11244&utm_source=chatgpt.com)|Domestic payment-system data storage restrictions|
|Banking / financial services|[RBI IT outsourcing directions](https://systemhealth.rbi.org.in/Scripts/BS_ViewMasDirections.aspx_id%3D12486.html?utm_source=chatgpt.com)|Vendor due diligence, audit rights, subcontractors, security and exit requirements|
|Banking / financial services|[RBI IT governance directions](https://systemhealth.rbi.org.in/Scripts/BS_ViewMasDirections.aspx_id%3D12562%283%29.html?utm_source=chatgpt.com)|Risk management, information security and operational resilience|
|Telecom|[DoT Telecom Cyber Security Rules](https://www.eservices.dot.gov.in/telecom-cyber-security?utm_source=chatgpt.com)|Security obligations applicable to telecom entities|
|Healthcare|[ABDM Health Data Management Policy](https://abdm.gov.in/publications/policies_regulations/health_data_management_policy?utm_source=chatgpt.com)|Relevant health-data consent, privacy and security obligations|





























## 7. How I recommend storing these sources in your project

One record should represent one specific model, provider, deployment method, region and billing tier, associated with its evidence.

Suggested evidence-record structure

```
{
  "provider": "example_provider",
  "model_id": "example_model",
  "deployment_type": "managed_api",
  "region": "region_id",

  "pricing": {
    "unit": "USD_per_million_tokens",
    "effective_date": null,
    "observed_at": "2026-10-27",
    "source_url": null
  },

  "data_governance": {
    "storage_region": "unknown",
    "processing_region": "unknown",
    "retention_days": null,
    "training_policy": "unknown",
    "prompt_logging": "unknown",
    "zero_retention_approved": false
  },

  "evidence": {
    "policy_urls": [],
    "contract_verified": false,
    "configuration_verified": false
  },

  "applicable_requirements": []
}
```

Schema illustration, not a record describing a real provider. `null` and `unknown` mean no verified value is available.

For price/date, save both the date the rate was observed and its stated effective date, where published. Also save the currency, billing unit, pricing tier, geographic surcharge, minimum commitment and the exact SKU. A webpage without an effective date is evidence of a displayed price at retrieval, not evidence of when that price originally took effect.

For contract evidence, save the document identifier, version, signing or acceptance status, contractual scope and expiry or renewal details. Public URLs are references; the accepted contract is the actual buyer-specific evidence.

For compliance rules, record applicability conditions, effective dates, required controls and supporting legal sources. Where applicability requires interpretation, have the engine mark it for legal or compliance review rather than treating the interpretation as a verified fact.

## 8. How these fields should influence recommendations

Consider an Indian banking customer-service system with a strict requirement for India-only inference processing and no provider-side prompt retention.

Your engine should first eliminate configurations that cannot satisfy those requirements, before comparing prices.

|Evidence state|Recommendation-engine behavior|
|---|---|
|Processing region verified as India and retention requirement verified|Eligible for further evaluation|
|Processing is global or can occur outside the permitted boundary|Exclude when India-only processing is mandatory|
|ZDR advertised but not approved for the account|Pending verification; not automatically eligible|
|Region available but no evidence of actual processing location|Unknown; request evidence|
|Valid contractual and technical evidence, but exceeds budget|Exclude on cost|
|All mandatory constraints satisfied|Rank by your chosen cost/performance objective|

This is the crucial feature to add to your PME: an evidence-backed eligibility layer before the deterministic cost/performance ranking.

The tool should not claim to certify compliance. It should identify documented configurations that satisfy explicitly defined buyer requirements, explain missing evidence, and flag unresolved legal or contractual questions.

For an achievable MVP, I would prioritize OpenAI, Anthropic, Gemini, AWS Bedrock, Azure Foundry, and two India-hosted GPU configurations from E2E or Yotta. That gives you direct APIs, managed cloud inference and self-hosting, with materially different privacy, pricing and regional controls.