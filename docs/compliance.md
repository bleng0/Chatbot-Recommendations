# Deployment compliance screening

POME screens 20 catalog configurations and any additional owned hosting plans against buyer-selected requirements before ranking eligible configurations. The standard profile keeps the seven new filters off. The documented replay still uses the standard profile. Screening results describe specific evidence and settings. Regulatory applicability and deployment approval remain with the buyer.

## Gate decisions

| Gate | Rule | Why |
| --- | --- | --- |
| G12 · Processing | All inference using prompts and responses must stay in India. | A billing address, nearby endpoint, or VM location alone cannot establish the complete inference route. |
| G13 · Retention | Require a documented upper bound in whole days on provider persistence of prompts and responses. Use **0** for no persistence after inference. | Routine deletion windows, abuse exceptions, caches, saved datasets, and backups can differ. |
| G14 · Licence | Use the existing commercial-use check. | Permission to use the model or API commercially is separate from data governance. |
| G15 · Storage | Persisted prompt and response content stays in India. Explicit evidence of no persistence also qualifies. | Processing and storage have separate geographic commitments. |
| G16 · Training | Require evidence that the provider excludes this workload's prompts and responses from model training. | Commercial and free tiers can have different data-use terms. |
| G17 · Prompt logs | Require evidence that provider logs exclude prompt and response content. | Removing content from logs can leave operational metadata, and a retention cap alone does not disable logging. |
| G18 · Contract | Require an applicable contract or DPA review recorded by the buyer. | A public template does not establish acceptance or coverage for a particular account. |
| G19 · Settings | Require a buyer review of the actual deployment settings. | Available settings and approved settings are different evidence. |

Enable each independently under **Compliance filters**. **Require India + zero provider retention** activates G12 and G13 at zero and preserves the other filters. **Reset compliance filters** turns off the compliance filters and restores the pending retention input to 30 days. **Gates** shows the observed facts and verdicts, and **Compliance gate information** describes the active requirements. **Evidence** shows source and scope, including conditional or missing claims. The Baselines tab reports unmet requirements alongside its comparison candidates.

A conflicting fact fails and absent, inapplicable, or conditional facts are unverified. Both exclude a configuration when the corresponding gate is on. The engine accepts deployment-specific public evidence and buyer-reviewed facts. Modeled evidence cannot qualify for these seven filters. A vendor's ordinary retention period is not used as a ceiling when broader retention may apply. No public record in this release establishes an operational retention ceiling covering its full deployment scope. Buyer confirmation can enable a qualifying retention result.

## Owned self-hosting

Owned configurations in the interactive app assume that the operator runs inference in India,
keeps prompt data out of external storage, disables content logging and training, and completes
internal contract and settings review. With no external inference provider, provider retention
is set to zero and provider storage is treated as absent. The Evidence tab identifies these
inputs as operator assumptions. The same assumptions appear in the laptop comparison for
compliance screening. Its lab-only deployment status still applies.

These assumptions affect the seven opt-in compliance checks. Commercial-use permission still
follows the checkpoint licence. Managed APIs and rented GPUs continue to use their provider
evidence. Score, budget and deployment readiness use the existing gates.

## Catalog decisions and outstanding evidence

[POME Compliance research brief](research/links/POME%20Compliance.md) supplies the initial source list. The runtime catalog records the scope, observed date and links. The review below is dated 2026-11-24. Exact configuration IDs distinguish the direct DeepSeek API from the same model family hosted in India and distinguish the global Vertex endpoint from regional offerings.

| Configuration IDs | Recorded decision and evidence still needed |
| --- | --- |
| `gem35fl-api-global` | Global endpoint. Billing eligibility and retention are unresolved for the listed workload. Verify the project tier, content logging and feature settings. [Gemini terms](https://ai.google.dev/gemini-api/terms) |
| `gem25f-api-global` | Global paid Gemini endpoint. Paid terms exclude training use, but prompts can be logged for abuse monitoring. Check project settings and retention across enabled features. [Gemini terms](https://ai.google.dev/gemini-api/terms) · [Gemini data retention](https://ai.google.dev/gemini-api/docs/zdr) |
| `gemma4-26b-api-global` | The catalog identifies unpaid Gemini quota. For the India buyer, the unpaid terms permit content use to improve models. Confirm billing and retention before production use. [Gemini terms](https://ai.google.dev/gemini-api/terms) |
| `gpt54nano-api-global`, `gpt54mini-api-global` | Global Standard API, with no training by default for ordinary API content. The routine abuse-log window has exceptions. Review project approval and enablement, exact model and endpoint, and enabled features before asserting ZDR. [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data) · [Regional eligibility](https://developers.openai.com/api/docs/guides/data-residency) |
| `haiku55-api-global`, `sonnet55-api-global` | Global Claude API. No training by default for commercial API content. The routine 30-day deletion policy has exceptions. Verify approved organization, model and request features for ZDR. [Anthropic training](https://privacy.claude.com/en/articles/7996868-is-my-data-used-for-model-training) · [Retention](https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data) · [ZDR](https://platform.claude.com/docs/en/manage-claude/api-and-data-retention) |
| `gem35f-vertex-global` | The Vertex global endpoint offers no India processing or storage boundary. No vendor training under ordinary Google Cloud service terms. Review applicable terms, logging exceptions and features. [Residency](https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/data-residency) · [Retention](https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/zero-data-retention) |
| `mistralsmall4-api-global` | The published dedicated EU and US options are different endpoints. Standard endpoint residency remains unknown. Verify tier, training settings, approved ZDR and supported stateless features. [Regional inference](https://docs.mistral.ai/inference/regional-inference) · [ZDR](https://docs.mistral.ai/admin/monitor-comply/zero-data-retention) · [Commercial terms](https://legal.mistral.ai/terms/commercial-terms-of-service/) |
| `sarvam105b-api-in`, `deepseekv41flash-sarvam-in` | Vendor documents India inference. Workspace retention defaults to indefinite until configured, and ZDR is available on request. Confirm the actual workspace, storage region, logging, training and retention. [Inference](https://www.sarvam.ai/token-factory) · [Retention](https://docs.sarvam.ai/api/platform/data-retention) · [Account settings](https://docs.sarvam.ai/api/platform/faq) |
| `deepseekflash-api-global` | The direct DeepSeek privacy policy describes processing and storage in China for covered personal data. The API terms exclude downstream end-user handling from that policy. Verify inference location, storage, retention, logging, and training for actual customer content. Commercial use now cites the developer terms applicable to applications and services. [Privacy policy](https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html) · [API terms](https://cdn.deepseek.com/policies/en-US/deepseek-open-platform-terms-of-service.html) |
| `gemma4-12b-ollama-local-q4` | The laptop quality replay does not establish a production operating location, logging policy or retention. Confirm operator routing, storage, telemetry and backups. [Ollama FAQ](https://docs.ollama.com/faq) |
| `gemma4-12b-vllm-in-bf16`, `gemma4-31b-vllm-in-bf16`, `gemma4-26b-vllm-in-bf16`, `qwen38-27b-vllm-in-bf16`, `llama31-8b-vllm-in-bf16`, `sarvam30b-vllm-in-bf16`, `museglimmer30b-vllm-in-bf16` | Evidence follows the selected GPU offering. Azure Central India and EC2 Mumbai identify the offered VM location. The E2E GPU options need instance-location confirmation. All require buyer validation of deployed inference routing, persistence, training, logs, and applicable agreements. [Azure regions](https://learn.microsoft.com/en-us/azure/reliability/regions-list) · [AWS regions](https://docs.aws.amazon.com/global-infrastructure/latest/regions/regions-zones.html) · [E2E GPU cloud](https://www.e2enetworks.com/gpu-cloud) |

Future candidates include Bedrock, Azure Foundry, and additional India GPU offerings such as Yotta. Introduce each as a distinct configuration after validating model availability, routing, tier, costs and scope. A different endpoint or model family cannot inherit an existing entry's evidence. [Bedrock cross-region routing](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html) · [Azure Foundry deployment types](https://learn.microsoft.com/azure/ai-foundry/foundry-models/concepts/deployment-types) · [Yotta Shakti Cloud](https://shakticloud.ai/pricing/)

## Operator workflow

Set `POME_COMPLIANCE_EVIDENCE_FILE` to the absolute path of a local JSON file. Store it outside the repository and image build context. Use non-sensitive review references and scope descriptions because POME displays them in Evidence. Keep contracts, credentials, account identifiers, and customer information in the buyer's own records system.

The top-level shape is `{"records": [...]}`. Use one record per configuration ID and GPU option. Copy the identity fields exactly from the registry, including the full `host`, `region`, `serving`, `version` and `quant` strings. For rented GPU options, also record the selected GPU option key from the sidebar implementation. Omit it for managed APIs and the local benchmark. Configurable owned plans remain unverified for these filters because buyer reviews are not bound to their hardware and operating settings. The following synthetic review illustrates the shape.

```json
{
  "records": [{
    "config_id": "sarvam105b-api-in",
    "model_id": "sarvam-105b",
    "version": "alias; no pinned version string on the pricing page",
    "host": "Sarvam API",
    "serving": "managed",
    "region": "India (Azure Central India; inference on Yotta and NxtGen GPUs)",
    "quant": "n/a (vendor-managed)",
    "reference": "SYNTHETIC-REVIEW-012",
    "scope": "Reviewed stateless text inference and the applicable workspace controls",
    "reviewed_on": "2026-11-24",
    "expires_on": "2027-02-24",
    "contract_verified": true,
    "configuration_verified": true,
    "facts": {
      "processing_region": "India",
      "storage_region": "No persistence",
      "retention_days": 0,
      "no_training": true,
      "no_prompt_logging": true
    }
  }]
}
```

Use only facts established for the actual endpoint and features. The accepted region labels are `India`, `China`, `United States`, `EU`, and `Global`. Storage also accepts `No persistence`. Omit unknown facts and any verification flag that lacks a review. The reviewer must explicitly confirm the configuration before adding deployment facts. Use the actual expiry when known, and revisit records when provider terms or deployment settings change. Reviews are evaluated against the current UTC date. A malformed file triggers an app warning and public-only evaluation. Expired, future-dated, or mismatched reviews do not contribute facts. A review cannot replace a known catalog processing boundary with a different one. Use a new catalog configuration for a different deployment.

For a Docker run, mount the file read-only and pass the container path. The image must be available locally and the mounted file readable by the container user.

```sh
docker run --rm -p 127.0.0.1:8501:8501 \
  --mount type=bind,src=/absolute/path/buyer-review.json,dst=/run/pome-review.json,readonly \
  -e POME_COMPLIANCE_EVIDENCE_FILE=/run/pome-review.json pome-app:local
```

## Regulatory review and implementation

India processing and no retention are buyer requirements in the preset. RBI payment-system storage guidance has a defined payments scope. RBI outsourcing review should separately examine the applicable contract, subcontractors, audit rights, safeguards and exit arrangements. Check which DPDP Act and Rules provisions apply and have commenced for the workload. CERT-In operational ICT log requirements concern a different data scope from provider prompt and response content. Record legal applicability and clearance separately from the gate verdicts. [RBI payment-data FAQ](https://www.rbi.org.in/CommonPerson/english/Scripts/FAQs.aspx?Id=2995) · [RBI outsourcing directions](https://rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=13088) · [DPDP Act](https://www.meity.gov.in/static/uploads/2024/02/Digital-Personal-Data-Protection-Act-2023.pdf) · [Commencement notification](https://www.meity.gov.in/static/uploads/2025/11/c56ceae6c383460ca69577428d36828b.pdf) · [CERT-In directions](https://www.cert-in.org.in/Directions70B.jsp)

The [catalog](../pome/registry/compliance.yaml) records public evidence. The [evidence loader](../pome/evidence/compliance.py) validates the buyer file and projects applicable facts into the snapshot. The [selection engine](../pome/selection/engine.py) evaluates active gates before ranking. The [Streamlit entrypoint](../pome/app/home.py) supplies the controls and evidence display. A change to applicable evidence or enabled requirements can change the decision hash. The app reads snapshots and local sources without making live provider calls.
