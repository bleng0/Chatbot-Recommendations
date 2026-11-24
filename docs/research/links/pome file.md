# Customer-Service LLM Evaluation Resource Map and Deterministic Model–Hosting Decision Framework

## Executive summary

Your project is technically stronger when framed as **an enterprise decision engine over model × hosting configurations**, rather than as another LLM benchmark or leaderboard.

The current proposal already has the right foundations: task-specific evaluation, measured token use and latency, explicit deployment requirements, deterministic cost scenarios, and a refusal to equate benchmark accuracy with business outcomes. However, it currently centers on banking intent classification, treats multilingual evaluation as optional, and defers self-hosting. The research landscape now supports a substantially richer version of the project without requiring you to invent most of the evaluation data yourself.

The most important finding from this review is that **there is no single benchmark that represents “customer service.”** Public resources are fragmented across intent classification, out-of-scope detection, knowledge retrieval, policy following, tool use, summarization, multilingual NLU, and voice. A credible recommender therefore needs a **benchmark portfolio indexed by task, domain, language and deployment mode**, not one universal score. BANKING77, for example, contains 13,083 English banking queries over 77 fine-grained intents, while MASSIVE covers more than one million multilingual utterances over 60 intents and 55 slot types; neither tests whether an agent can actually resolve a customer's problem.

A particularly important development for your project is the **τ-bench family**. The original τ-bench evaluates multi-turn customer-service agents that must converse with users, obey policies and operate backend tools; τ²-bench added a telecom troubleshooting environment in which both customer and agent affect the shared environment; τ-Knowledge added banking support over roughly 700 interlinked knowledge documents; and the October 2026 τ-bench 2.0 release added customer-service evaluations in **English, Spanish, Portuguese, Hindi, Chinese and Korean across retail, airline and telecom**, with 50 frozen tasks per domain/language in its text benchmark. The current official repository describes six-language text and voice packs, including Hindi, and is MIT-licensed at repository level.

That makes your proposed system unusually well-timed. You can now combine:

|Requirement|Best evidence sources|
|---|---|
|Banking intent understanding|BANKING77|
|Unknown/OOD query handling|CLINC150 + synthetic hard-OOS tests|
|Multilingual intent/NLU|MASSIVE|
|Hindi end-to-end customer service|τ-bench 2.0 / τ-i18n|
|Indian-language QA|IndicQA + IndicGenBench|
|Indian-language NLG/summarization|IndicNLG Suite + IndicGenBench|
|Retail policy-following/customer support|ABCD + τ-Retail|
|Telecom troubleshooting|τ²/τ-bench Telecom|
|FAQ / grounded knowledge|τ-Knowledge, Amazon Product Q&A, MedQuAD|
|Customer-service summarization|TweetSumm|
|Realistic dialogue|ABCD + MultiDoGO|
|Robustness|CLINC OOS, TextFlint, τ-Trait, code-mixing tests|
|Serving performance|MLPerf Endpoints + NVIDIA GenAI-Perf methodology|

The best domain strategy is therefore:

**Banking as the anchor domain**, because it gives you fine-grained intent classification, knowledge-heavy support and stringent deployment/governance considerations.

**Retail/e-commerce as the first additional domain**, because it has unusually strong public customer-service data: ABCD, Amazon Product Q&A and τ-Retail. ABCD alone provides more than 10,000 human-to-human support conversations over 55 customer intents and explicit company policies/actions.

**Telecom/technical support as the second additional domain**, because it stresses an entirely different interaction pattern: the agent often cannot perform the fix itself and must guide a customer through actions. τ²-bench was explicitly created around this dual-control problem.

**Healthcare/patient information as an extended third domain**, because it introduces high-consequence QA and escalation requirements. MedQuAD contains 47,457 question-answer pairs derived from 12 NIH sites under CC BY 4.0. Public healthcare datasets, however, are considerably stronger for medical information QA than for operational “customer service,” so I would treat healthcare as a stretch validation domain rather than your MVP.

The core architecture I recommend is:

Show code

The critical design principle is: **never rank “models” in isolation. Rank configurations** such as `Model A + Provider API + India region`, `Model B + managed inference`, and `Model C + self-hosted H100/vLLM`. The same model can have radically different cost, latency, data handling and operational implications depending on deployment.

## Domain strategy and benchmark taxonomy

Customer service should be represented as a collection of tasks rather than a single benchmark dimension. This matters because a model that excels at 77-way intent classification might perform poorly when required to retrieve a policy, follow a multi-step process, maintain a conversation, summarize a case, or operate in Hindi.

I recommend the following evaluation ontology.

|Evaluation family|Question it answers|Recommended metrics|Priority|
|---|---|---|---|
|Intent classification|“What does the customer want?”|Accuracy, macro-F1, per-intent F1|Core|
|OOS / abstention|“Should the system handle this?”|AUROC, AUPRC, FPR@95TPR, reject accuracy|Core|
|FAQ / grounded QA|“Can it answer using approved knowledge?”|Answer correctness, retrieval recall, faithfulness, citation correctness|Core|
|Response generation|“Can it respond appropriately?”|Task success, policy adherence, groundedness, escalation correctness|Core|
|Tool-using support|“Can it actually resolve the case?”|State-based task success, pass^k, tool correctness|Core for agentic use|
|Summarization|“Can it create an accurate ticket summary?”|Factuality/entity preservation + ROUGE/BERTScore + human/LLM judge|Core if summarization supported|
|Multilingual|“Does quality hold in required languages?”|Same task metrics separately by language|Core for India|
|Code-mixing|“Can it handle realistic bilingual usage?”|Task degradation vs monolingual baseline|Core for India|
|Robustness|“Does it survive typos, ambiguity and behavioral changes?”|Relative degradation and failure rate|Core|
|Serving|“Can deployment meet the workload?”|p95/p99 latency, TTFT, ITL, RPS, token throughput|Core|
|Cost|“Can it meet requirements economically?”|Cost/ticket, monthly cost, utilization, break-even volume|Core|

This taxonomy is consistent with the broader lesson from evaluation literature that model quality is multidimensional rather than adequately described by a single leaderboard number. HELM was explicitly developed around standardized evaluation across scenarios and multiple metrics, while recent agent benchmarks evaluate task completion separately from conversational reliability and serving work evaluates throughput separately from user-perceived latency.

**Recommended domains**

|Domain|Recommendation|Why it belongs in the project|Principal resources|
|---|---|---|---|
|**Banking / fintech**|Anchor domain|Fine-grained intents, knowledge-heavy policy support, sensitive customer data, strong public benchmarks|BANKING77, τ-Knowledge, NLU++, MASSIVE/Indic resources|
|**Retail / e-commerce**|First expansion|Excellent public customer-service coverage from intent through end-to-end actions and product QA|ABCD, τ-Retail, Amazon Product Q&A, HINT3|
|**Telecom / technical support**|Second expansion|Tests troubleshooting, user guidance, multi-step resolution and dual-control interaction|τ²/τ-bench Telecom, MultiDoGO software/media|
|**Healthcare / patient information**|Extended/high-risk domain|Tests grounded QA, safety, handoff and high-consequence factuality|MedQuAD, LiveQA-Med family, MedHELM-type evaluation|

Retail is especially attractive because ABCD was designed around realistic support procedures rather than generic dialogue: agents must balance customer requests against company policies and execute appropriate actions. Telecom provides a different form of complexity; τ²-bench models scenarios where the user must perform actions that the agent can only explain or coordinate. Those two domains therefore add methodological diversity rather than merely supplying more examples.

Healthcare is valuable as an extended validation domain, but its publicly available data is skewed toward **consumer medical information** rather than billing, appointments, insurance administration or contact-center operations. MedQuAD is substantial and high-quality for QA, with 47,457 pairs from NIH sites and 37 question types, but it does not by itself simulate a healthcare contact center. That distinction should appear explicitly in your thesis/report.

## Dataset and benchmark catalog

The following catalog prioritizes datasets that directly help build or evaluate your decision engine. It is intentionally broader than your current banking-only proposal, but it avoids filling the project with generic NLP benchmarks that do not materially inform customer-service deployment.

**Core customer-service and domain datasets**

| Dataset / benchmark                                            | Task(s)                                                                                      | Domain                                                             | Languages                                                                                               | Size                                                                                         | License / access                                                                                              | Download / benchmark links                                                                                                                                                                                                                                                                                                                                                          | Quality and use notes                                                                                                                                                                                                                                        |
| -------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **BANKING77**                                                  | Intent classification                                                                        | Banking                                                            | English                                                                                                 | 13,083 queries; 10,003 train, 3,080 test; 77 intents                                         | CC BY 4.0                                                                                                     | [Hugging Face](https://huggingface.co/datasets/PolyAI/banking77) · [Official source repo](https://github.com/PolyAI-LDN/task-specific-datasets/tree/master/banking_data) · [Paper](https://arxiv.org/abs/2003.04807) · [Papers With Code](https://paperswithcode.com/dataset/banking77)                                                                                             | Best core banking-intent benchmark. Fine-grained, but English-only and closed-set; does **not** evaluate answer generation or customer resolution.                                                                                                           |
| **CLINC150 / OOS**                                             | Intent classification, OOS detection                                                         | Multi-domain assistant                                             | English                                                                                                 | 22,500 in-scope examples plus 1,200 OOS in full split; 150 intents                           | Verify redistribution terms in official repository before packaging                                           | [Official repo](https://github.com/clinc/oos-eval) · [Papers With Code](https://paperswithcode.com/dataset/clinc150)                                                                                                                                                                                                                                                                | Essential complementary benchmark because it explicitly tests unsupported requests rather than forcing every request into a known intent. Official full data has 100/20/30 train/dev/test examples per intent and a 1,000-example OOS test set.              |
| **MASSIVE**                                                    | Intent classification, slot filling                                                          | 18 assistant domains                                               | 52 locales in v1.1; includes Hindi, Kannada, Malayalam, Tamil and Telugu among others                   | >1M utterances; 60 intents; 55 slot types                                                    | CC BY 4.0                                                                                                     | [Amazon Science](https://www.amazon.science/code-and-datasets/massive) · [Hugging Face](https://huggingface.co/datasets/AmazonScience/massive) · [Paper](https://www.amazon.science/publications/massive-a-1m-example-multilingual-natural-language-understanding-dataset-with-51-typologically-diverse-languages) · [Papers With Code](https://paperswithcode.com/dataset/massive) | Excellent language-control benchmark. It is localized from a general voice-assistant corpus, so do **not** report it as multilingual banking evidence.                                                                                                       |
| **ABCD**                                                       | Intent, next-action prediction, value filling, response selection, policy-following dialogue | Retail/e-commerce support                                          | English                                                                                                 | >10K human-human dialogues; 55 customer intents; 30 actions                                  | Official repository includes license; verify data terms when packaging                                        | [Official repo](https://github.com/asappresearch/abcd) · [ACL paper](https://aclanthology.org/2021.naacl-main.239/)                                                                                                                                                                                                                                                                 | One of the best datasets for your product because it models explicit company procedures and multi-step customer-service workflows rather than isolated queries.                                                                                              |
| **τ-bench / τ²-bench / τ-bench 2.0**                           | Multi-turn response, policy following, tools, task completion, reliability                   | Retail, airline, telecom; banking knowledge; intake                | v2 text/voice: English, Spanish, Portuguese, Hindi, Chinese, Korean for retail/airline/telecom          | v2 text benchmark: 6 languages × 3 domains × 50 frozen tasks = 900 runs at one trial         | Repository MIT license                                                                                        | [Official repo](https://github.com/sierra-research/tau2-bench) · [Leaderboard](https://taubench.com/) · [τ² paper](https://arxiv.org/abs/2506.07982)                                                                                                                                                                                                                                | **Highest-value end-to-end benchmark in this review.** Tests actual support completion rather than lexical similarity. v2.0 was released October 19, 2026; its scores are explicitly not comparable with 1.x because tasks/judges/prompts changed.           |
| **τ-Knowledge / τ-Banking**                                    | RAG, knowledge retrieval, policy reasoning, tools                                            | Banking/fintech support                                            | English in original banking-knowledge benchmark; current repo also supports broader voice configuration | Roughly 700 interconnected knowledge documents                                               | Included in τ-bench ecosystem                                                                                 | [Paper](https://arxiv.org/abs/2603.04370) · [Repo](https://github.com/sierra-research/tau2-bench)                                                                                                                                                                                                                                                                                   | Extremely relevant replacement for “bank FAQ benchmark” because it combines retrieval with actions and policy compliance. Frontier systems in the original study struggled substantially, showing that this is materially harder than intent classification. |
| **MultiDoGO**                                                  | Dialogue intent, slot labeling, dialogue modeling                                            | Airline, fast food, finance, insurance, media, software            | English                                                                                                 | >81K dialogues; >54K annotated                                                               | CDLA Permissive 1.0                                                                                           | [AWS repo](https://github.com/awslabs/multi-domain-goal-oriented-dialogues-dataset) · [ACL paper](https://aclanthology.org/D19-1460/) · [HF mirror](https://huggingface.co/datasets/jpcorb20/multidogo)                                                                                                                                                                             | Useful cross-domain dialogue resource and a reasonable proxy for software-support interactions. Wizard-of-Oz collection pairs a customer with a trained agent.                                                                                               |
| **TweetSumm**                                                  | Extractive and abstractive ticket/dialogue summarization                                     | Cross-company customer support                                     | English                                                                                                 | 1,100 dialogs; 3 extractive + 3 abstractive human summaries/dialog, close to 6,500 summaries | CDLA-Sharing-1.0 for released dataset; underlying tweets require reconstruction/source-term care              | [Official repo](https://github.com/guyfe/Tweetsumm) · [ACL paper](https://aclanthology.org/2021.findings-emnlp.24/)                                                                                                                                                                                                                                                                 | Best directly customer-service-specific summarization benchmark found. Underlying dialogs derive from Twitter support data, so redistribution and reconstruction deserve extra care.                                                                         |
| **Twitter Conversations / Conversational Document Prediction** | Retrieval / knowledge-document recommendation from dialogue                                  | Customer support across 25 organizations                           | English                                                                                                 | 10,000 train, 525 dev, 500 test conversations                                                | Apache 2.0 repo; tweet-content reconstruction governed by platform/source terms                               | [Official IBM repo](https://github.com/IBM/twitter-customer-care-document-prediction) · [Papers With Code](https://paperswithcode.com/dataset/twitter-conversations-dataset)                                                                                                                                                                                                        | Valuable FAQ/RAG precursor: predict the support document that should resolve a conversation. Public release uses tweet IDs to comply with Twitter redistribution rules.                                                                                      |
| **Amazon Product Q&A**                                         | Product FAQ/QA                                                                               | E-commerce                                                         | Primarily English                                                                                       | 1.48M questions; 4,019,744 answers; 191,185 products                                         | Source usage terms should be checked; no clear general-purpose license surfaced in the official page reviewed | [UCSD source](https://jmcauley.ucsd.edu/data/amazon/qa/)                                                                                                                                                                                                                                                                                                                            | Excellent scale for retail FAQ/product support, but it represents community/product QA rather than controlled enterprise support answers.                                                                                                                    |
| **HINT3**                                                      | Intent detection “in the wild”                                                               | Mattress retail, fitness-supplement retail, online gaming          | English                                                                                                 | Three domain datasets; size varies                                                           | License not clearly specified in PWC index—verify source repo                                                 | [Papers With Code](https://paperswithcode.com/dataset/hint3)                                                                                                                                                                                                                                                                                                                        | Useful extended retail-intent stress test because it contains narrow real-world-style domains rather than a generic assistant taxonomy.                                                                                                                      |
| **NLU++**                                                      | Multi-label intents, slots, compositional NLU                                                | Banking and hotels                                                 | English                                                                                                 | Domain-specific expert-annotated dataset                                                     | License needs verification                                                                                    | [Papers With Code](https://paperswithcode.com/dataset/nlu)                                                                                                                                                                                                                                                                                                                          | Strong extended benchmark because real queries may contain multiple intents; complements BANKING77's single-label setup. PWC describes expert annotation and generic/domain-specific intent modules.                                                         |
| **MedQuAD**                                                    | Medical FAQ/QA, retrieval                                                                    | Healthcare / patient information                                   | English                                                                                                 | 47,457 QA pairs from 12 NIH websites; 37 question types                                      | CC BY 4.0; some MedlinePlus answer subsets removed for copyright reasons                                      | [Official repo](https://github.com/abachaa/MedQuAD)                                                                                                                                                                                                                                                                                                                                 | High-quality healthcare information benchmark with explicit source provenance. It is not a complete patient-service benchmark and should be paired with safety/handoff evaluation.                                                                           |
| **Taskmaster-1/2**                                             | Goal-oriented dialogue / response generation                                                 | Restaurants, hotels, flights, transport, food, entertainment, etc. | English                                                                                                 | TM-1: 13,215 dialogs; TM-2: 17,289 dialogs                                                   | CC BY 4.0                                                                                                     | [Google Research repo](https://github.com/google-research-datasets/Taskmaster)                                                                                                                                                                                                                                                                                                      | Useful backup if you later add travel/hospitality; less directly aligned to enterprise support than ABCD or τ-bench.                                                                                                                                         |

A key cataloging policy follows from these resources: **dataset size should never become a proxy for relevance**. Amazon Product Q&A has millions of examples, but a 50-task τ-bench domain can be substantially more valuable for evaluating whether an agent follows policy and modifies a backend correctly. τ-bench uses verifiable environment state rather than merely comparing output text to a reference.

Similarly, published leaderboard results should be treated as discovery evidence rather than as inputs to your final decision engine. Exact model versions, prompts, tool interfaces and benchmark versions matter; τ-bench 2.0 itself warns that its English v2 results are not input-identical to v1.0.1 and therefore are not directly comparable. Your engine should preferentially consume **your own standardized reruns**.

## India-specific, multilingual and robustness resources

India-focused evaluation should be a separate evidence layer rather than a checkbox saying “supports Hindi.” At least four different questions matter:

1. Can the model understand a required language?
2. Can it perform the target customer-service task in that language?
3. Can it handle code-mixing, transliteration and noisy user text?
4. Does the chosen deployment configuration satisfy the enterprise's actual data-governance and outsourcing requirements?

Those questions require different resources.

**India and Indic-language catalog**

| Resource                            | Evaluation use                                                                            | Languages / coverage                                                                         | Scale                                                                                  | License                                                                            | Links                                                                                                            | Recommended role                                                                                                                                                                                                                                                                                |
| ----------------------------------- | ----------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **τ-bench 2.0 / τ-i18n**            | End-to-end multilingual customer-service task completion, tool use and conversation       | English, Spanish, Portuguese, **Hindi**, Chinese, Korean across retail/airline/telecom       | 50 frozen tasks/domain/language in text-v1; same task structure across language packs  | MIT repository                                                                     | [Repo](https://github.com/sierra-research/tau2-bench) · [τ-Multilingual paper](https://arxiv.org/abs/2609.35820) | **Best available Hindi customer-service benchmark in this survey** because the same functional tasks are evaluated across languages rather than measuring generic language competence. The multilingual work used native-speaker review and separates task, interaction and generation quality. |
| **MASSIVE**                         | Multilingual intent + slots                                                               | 52 languages/locales, including hi-IN, kn-IN, ml-IN, ta-IN, te-IN                            | >1M                                                                                    | CC BY 4.0                                                                          | [HF](https://huggingface.co/datasets/AmazonScience/massive)                                                      | Use for standardized per-language NLU comparisons; do not call it domain-specific customer-service evidence.                                                                                                                                                                                    |
| **IndicQA**                         | Closed-domain QA                                                                          | Assamese, Bengali, Hindi, Kannada, Marathi, Malayalam, Punjabi, Odia, Tamil, Telugu          | Small evaluation sets by language                                                      | CC BY 4.0                                                                          | [Hugging Face](https://huggingface.co/datasets/ai4bharat/IndicQA)                                                | Strong Indic QA capability gate; combine with domain benchmark rather than using it as banking evidence.                                                                                                                                                                                        |
| **IndicGenBench**                   | Cross-lingual summarization, translation, QA                                              | Up to 29 Indic languages / 13 scripts depending on component                                 | CrossSum-IN test 14.5K; XQuAD-IN test 14.2K; XorQA-IN test 15.1K; Flores-IN test 29.3K | Varies by component; verify each dataset card                                      | [Official Google repo](https://github.com/google-research-datasets/indic-gen-bench)                              | One of the most useful broad Indic generation suites. Use CrossSum-IN for summarization and XQuAD/XorQA components for QA capability.                                                                                                                                                           |
| **IndicNLG Suite**                  | Summarization, paraphrase, question generation, headline generation, biography generation | 11 Indic languages                                                                           | ~8.5M examples total                                                                   | Sentence summarization/headline/paraphrase: CC BY-NC 4.0; WikiBio/QG: CC BY-SA 4.0 | [AI4Bharat](https://indicnlp.ai4bharat.org/indicnlg-suite/)                                                      | Useful for extended Indian-language generation evaluation. Non-commercial licenses on some components matter for enterprise redistribution/use decisions.                                                                                                                                       |
| **MILU**                            | India-specific language and cultural/general knowledge                                    | Bengali, Gujarati, Hindi, Kannada, Malayalam, Marathi, Odia, Punjabi, Tamil, Telugu, English | 79,617 benchmark questions plus validation data                                        | Verify current dataset license before redistribution                               | [GitHub](https://github.com/AI4Bharat/MILU) · [HF](https://huggingface.co/datasets/ai4bharat/MILU)               | Not customer-service-specific, but useful as an **India capability diagnostic**, especially when a model claims broad Indic support.                                                                                                                                                            |
| **IndicVoices / IndicVoices-R**     | Voice/ASR/TTS extension                                                                   | 22 scheduled Indian languages                                                                | IndicVoices-R alone: ~1,700 h, >10,000 speakers                                        | Current AI4Bharat card reports CC BY 4.0; access may be gated                      | [IndiaAI listing](https://aikosh.indiaai.gov.in/home/datasets/details/indicvoices_r.html)                        | Only necessary when the product expands from chat/email into contact-center voice.                                                                                                                                                                                                              |
| **IndicNLG / AI4Bharat glossaries** | Vocabulary/domain stress-set construction                                                 | Multiple Indic languages; domain resources include finance, healthcare etc.                  | Varies                                                                                 | Resource-specific                                                                  | AI4Bharat ecosystem                                                                                              | Useful for creating deterministic domain-term perturbation tests; not a standalone customer-service benchmark.                                                                                                                                                                                  |

One particularly valuable recent result is that τ-Multilingual does **not** simply translate benchmark sentences and call that multilingual evaluation. It localizes customer personas and related language-specific content, and its reported experiments separated task completion, interaction quality and generation quality. The September/October 2026 work covers Hindi and provides a much closer model of multilingual customer service than a translated QA leaderboard alone.

MASSIVE is still valuable because its scale and parallel structure make cross-language comparison easy. Amazon reports more than one million utterances across 52 languages in the current dataset release, while the ACL publication describes the original 51-language corpus created through professional localization of SLURP. For your report, pin the exact dataset release so the “51 versus 52 languages” distinction does not create reproducibility problems.

**Robustness and synthetic testing**

|Test|Resource / construction|Why it matters|
|---|---|---|
|**Natural OOS**|CLINC150 OOS test set|Measures whether the model knows that an unsupported request is unsupported rather than hallucinating an intent.|
|**Hard OOS**|DETER / synthetic hard-negative OOS literature|Ordinary OOD examples can be too easy; hard negatives near supported intent boundaries expose overconfident classifiers.|
|**Typos/noise**|[TextFlint](https://github.com/textflint/textflint) transformations plus your own fixed perturbation templates|TextFlint supports broad NLP robustness transformations; use deterministic seeds and retain original labels.|
|**Hindi-English code-mixing**|COMI-LINGUA plus custom label-preserving Hinglish transforms|COMI-LINGUA contributes over 125K Hindi-English code-mixed instances across several language tasks; although not a customer-service intent set, it provides realistic code-mixing patterns.|
|**Romanized Hindi**|Construct from Hindi benchmark items using a fixed transliteration pipeline plus native review|Crucial for Indian chat channels because script choice and transliteration can differ from formal Hindi; score separately rather than mixing with Devanagari.|
|**Behavioral robustness**|[τ-Trait](https://github.com/collinear-ai/tau-trait)|Extends customer-service agent evaluation with traits such as impatience/incoherence and reports significant performance degradation across models; released over airline, retail, telecom and telehealth domains.|
|**Repeated-task reliability**|τ-bench `pass^k`|A model can have reasonable average task success but fail to repeat the same success reliably; pass^k explicitly evaluates consistent success across repeated trials.|

For the PME project, I would build a **small deterministic robustness layer yourself** rather than attempting another large benchmark. Starting from 500–1,000 held-out customer requests, create fixed variants for character deletion, word duplication, punctuation removal, colloquial phrasing, Romanized Hindi, Hindi-English mixing, ambiguous requests and unsupported requests. Store the transformation and seed with every example. This lets the recommender answer something much more useful than “Hindi supported”: it can report, for example, `Hindi clean = pass`, `Hinglish = pass`, `Romanized Hindi = fail`.

India-specific compliance should likewise not be encoded as `provider_country == India`. India's Digital Personal Data Protection Rules 2025 were published by MeitY on November 14, 2025, and the DPDP Act remains part of the governing framework. For regulated financial entities, the RBI's Outsourcing of IT Services Directions address risk management, confidentiality and integrity of customer data, access control, cloud controls, monitoring, subcontractors, logs, cross-border outsourcing and exit strategy—not merely server location. CERT-In also maintains cybersecurity directions under Section 70B.

Therefore your product should say:

> **“Configuration satisfies the buyer-specified controls for which current evidence has been recorded.”**

It should **not** say:

> “AWS India / Azure India / self-hosted = RBI compliant.”

That distinction makes the product much more credible.

A compliance evidence record could contain:

|Field|Example|
|---|---|
|Requirement|Customer content must remain in approved region|
|Applicability|Banking workload / buyer policy|
|Candidate configuration|Model X / provider Y / region Z|
|Evidence type|Provider documentation / contract term / enterprise attestation|
|Source URL|Provider's official data-handling page|
|Retrieved|2026-10-26|
|Result|Pass / fail / unknown|
|Expiry/review|2027-01-26|
|Notes|Retention feature requires enterprise setting|
|Human review|Security/legal sign-off pending|

`unknown` must be a first-class state. A missing provider document should not silently become either pass or fail.

## Literature, evaluation methods and existing decision tools

The academic literature gives you most of the pieces of the product, but they generally exist separately.

**Relevant literature**

|Work|Contribution relevant to your project|How you should use it|
|---|---|---|
|**Casanueva et al., BANKING77**|Fine-grained intent detection in banking; 77 classes|Core closed-set banking NLU benchmark.|
|**Larson et al., CLINC/OOS**|Explicit out-of-scope intent evaluation|Add abstention/OOS as a first-class capability rather than requiring a forced prediction.|
|**FitzGerald et al., MASSIVE**|Large parallel multilingual NLU corpus|Per-language intent/slot capability measurements.|
|**Chen et al., ABCD**|Explicit policy/action-driven customer-support dialogs|Use for retail support response/action evaluation, not just intent detection.|
|**Feigenblat et al., TweetSumm**|Customer-care dialogue summarization with human extractive and abstractive summaries|Establishes a customer-service-specific summarization evaluation set.|
|**Yao et al., τ-bench**|Tool-agent-user interaction, verifiable task completion and pass^k reliability|Strong basis for testing whether a support agent actually completes work consistently.|
|**Barres et al., τ²-bench**|Dual-control telecom troubleshooting|Tests customer guidance where the user must perform actions themselves.|
|**Shi et al., τ-Knowledge**|Agentic retrieval plus tools in banking support|Directly relevant to FAQ/RAG banking claims.|
|**Ray et al., τ-Voice / τ-Multilingual**|Full-duplex customer service; multilingual extension including Hindi|Future voice track and immediate Hindi end-to-end evaluation.|
|**RAGAS**|Separates RAG faithfulness, answer relevance and context/retrieval quality|Use as secondary automated QA/RAG diagnostics, not as sole ground truth.|
|**G-Eval**|LLM-based multidimensional scoring for summarization/dialogue; demonstrated better human correlation but also judge bias|Useful for generation/summarization scoring only after calibration against human judgments.|
|**FrugalGPT**|Prior work on cost/quality optimization across LLM services|Important evidence that “cost-aware LLM selection” itself is not novel; your contribution must be the deployment/domain/governance integration.|
|**MLPerf Endpoints / GenAI-Perf**|Standardized serving-performance concepts|Adopt their serving metrics rather than inventing arbitrary “speed scores.”|

For generated answers, do not rely on ROUGE or lexical overlap alone. G-Eval's authors explicitly note that conventional metrics such as BLEU/ROUGE correlate imperfectly with human judgments on open-ended generation and also show that LLM judges themselves can exhibit bias toward LLM-generated text. A defensible protocol therefore combines deterministic/reference metrics where possible, structured automated judges, and a relatively small human calibration sample.

For RAG, separate the pipeline. A model might retrieve the wrong document but faithfully summarize it, or retrieve the correct document and hallucinate an unsupported answer. RAGAS formalizes related dimensions such as context relevance, faithfulness and answer relevance. For your engine, I would additionally record deterministic retrieval measures such as `Recall@k` and exact citation/document match whenever a gold source is known.

**Existing tools and where your project differs**

| Tool / platform                                | What it already does                                                                                                                    | What it does not establish for your problem                                                                                                                                                                                                                                                |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Stanford HELM**                              | Standardized scenarios and multi-dimensional model evaluation; useful benchmark harness/reference                                       | It is fundamentally an evaluation framework, not an enterprise model×hosting optimizer with buyer-specific India governance gates. The HELM project entered maintenance mode in 2026, which also argues for consuming its methodology rather than depending on it as your product backend. |
| **Microsoft Foundry model benchmarks/catalog** | Model comparisons across quality/safety and, for supported models, cost/throughput and deployment information                           | Useful competitor/reference UX, but provider ecosystem and available benchmark coverage constrain the comparison; Microsoft itself notes benchmark availability varies across models.                                                                                                      |
| **Google Vertex AI / AWS Bedrock evaluation**  | Provider-integrated model evaluation and comparison workflows                                                                           | Useful evaluation infrastructure, but naturally centered on each cloud's model/deployment ecosystem rather than neutral cross-provider/self-hosted selection.                                                                                                                              |
| **Artificial Analysis**                        | Public model intelligence, price, speed and latency comparisons                                                                         | Excellent discovery data, but not domain-specific customer-service validation or buyer-specific compliance analysis.                                                                                                                                                                       |
| **MLPerf Endpoints**                           | Measures endpoint throughput vs per-user performance across concurrency levels                                                          | Provides the serving methodology, not a business recommendation engine. Current endpoint reporting includes system tokens/s, per-user interactivity, p90 TTFT and concurrency.                                                                                                             |
| **NVIDIA GenAI-Perf**                          | Measures TTFT, inter-token latency, request latency, sequence length, output tokens/s and request throughput; can collect GPU telemetry | Ideal measurement harness for self-hosted serving, but does not decide whether the resulting deployment is best for a specific enterprise workload.                                                                                                                                        |

This is important for your novelty statement.

I would **not** claim:

> “We are the first system to help enterprises choose an LLM.”

Model catalogs, leaderboards, evaluation platforms and cost-aware methods already exist.

A much more defensible contribution is:

> **A deterministic, evidence-backed decision framework that converts enterprise customer-service requirements into a ranked set of model × hosting configurations by jointly applying domain/task quality measurements, multilingual evidence, workload-dependent serving economics, and documented India-specific deployment/governance constraints.**

The integration is the research contribution.

Based on the tools and literature surveyed here, the distinctive combination is:

[ \text{domain quality} + \text{language quality} + \text{robustness} + \text{serving capacity} + \text{API/self-host economics} + \text{deployment controls} \rightarrow \text{deterministic recommendation} ]

I would describe this as **integration and decision-framework novelty**, not a novel optimization algorithm. The surveyed tools cover substantial subsets of the problem, so a formal literature review would still be required before making a publication-level “first” claim.

There is also a genuine research gap in public data. We have strong banking intent data, strong retail support data, strong generic multilingual data, and increasingly good end-to-end agent benchmarks, but there is still relatively little **native Indian-language, domain-specific enterprise customer-service data**. MASSIVE is multilingual but generic; BANKING77 is banking-specific but English-only; IndicQA/IndicGenBench are multilingual but not customer-service-specific. τ-bench 2.0's Hindi retail/telecom track substantially improves the situation but still does not provide Hindi banking intent/support coverage. That gap alone gives your project a strong motivation for a small, carefully constructed Hindi/Hinglish robustness set.

## Experimental protocol and deterministic recommendation data

The most important methodological distinction is this:

> **The recommendation engine can be deterministic even though LLM behavior and serving performance are stochastic.**

You make the engine deterministic by feeding it **frozen, versioned aggregate measurements** and applying fixed rules. Running the same enterprise profile against the same evidence snapshot must return the same answer.

### Evaluation protocol

**Candidate definition.** Treat every deployable combination as a separate candidate:

[ c = (\text{model},\text{model version},\text{host}, \text{region},\text{serving engine}, \text{quantization/configuration}) ]

Examples:

`Llama-X / self-hosted / AWS ap-south-1 / 4×H100 / vLLM / FP8`

and

`Llama-X / managed provider Y / Mumbai endpoint`

are different candidates even if the underlying weights are identical.

**Benchmark freezing.** Pin dataset versions, hashes where feasible, benchmark code, prompt templates, model endpoint identifiers and evaluation dates. Public datasets such as BANKING77 are old enough that benchmark contamination cannot be excluded; your original proposal already correctly notes this limitation.

**Prompt development.** Use development data only for prompt selection and label descriptions. Do not repeatedly inspect the official test set while optimizing prompts. For classification, request a constrained schema or exact label and count malformed outputs as failures unless you are explicitly measuring format recovery.

**Classification measurements.** Record accuracy, macro-F1, per-class precision/recall/F1, invalid-output rate and a confusion matrix. For OOS tasks additionally measure AUROC/AUPRC and an operational metric such as FPR at a fixed true-positive rate.

**QA/RAG measurements.** Record exact match/token F1 where references support them; document retrieval `Recall@k`, `MRR` or source-document hit rate; answer correctness; faithfulness to retrieved material; unsupported-claim rate; and citation/source accuracy. RAGAS-like automated metrics can help diagnose the pipeline, but should be calibrated against human judgments on a subset.

**Response-generation measurements.** Prefer task success and policy adherence over stylistic similarity. ABCD and τ-bench are particularly useful because they give you structured actions and/or environment outcomes. Record unnecessary tool calls, prohibited actions, escalation correctness, hallucinated policies and unresolved tasks separately.

**Summarization measurements.** Record entity/number preservation, unsupported-fact rate, omission of critical issue/resolution information, ROUGE/BERTScore as secondary reference metrics, and multidimensional human or calibrated LLM-judge scores for consistency, relevance and coherence. G-Eval is useful here, but its demonstrated evaluator biases are exactly why it should not be the sole metric.

**Multilingual measurements.** Never collapse all Indian-language scores into one number before retaining the individual scores. Evaluate:

[ Q_{\text{Hindi}}, Q_{\text{Tamil}}, Q_{\text{Telugu}}, \ldots ]

and let the enterprise specify requirements such as:

[ Q_{\text{Hindi}}\geq0.90 \quad\land\quad Q_{\text{Tamil}}\geq0.85 ]

This avoids a strong Hindi result hiding a poor Tamil result.

**Reliability.** For inherently stochastic end-to-end agents, run multiple trials. τ-bench's pass^k metric is directly relevant because it evaluates the probability of succeeding consistently across repeated attempts. Store the aggregate score and uncertainty in the registry; the recommender itself still behaves deterministically.

### Serving and workload measurements

For API and self-hosted configurations, the minimal performance record should include:

|Measurement|Why needed|
|---|---|
|Input tokens/request distribution|API billing + prefill workload|
|Output tokens/request distribution|Billing + generation workload|
|Requests/ticket|Converts support volume into inference volume|
|Peak requests/sec|Capacity planning|
|Mean/p50/p95/p99 end-to-end latency|SLA evaluation|
|TTFT|Perceived responsiveness|
|Inter-token latency / tokens/sec/user|Streaming quality|
|Total output tokens/sec|Server capacity|
|Requests/sec|Capacity|
|Error/timeout rate|Reliability|
|Retry rate|Cost + latency|
|Cache hit ratio|Cost/capacity where applicable|
|Concurrent requests|Interpreting all latency/throughput measurements|
|GPU utilization|Self-host efficiency|
|GPU memory|Feasible batch/context configuration|
|Power/energy where relevant|On-prem or sustainability/TCO extension|

MLPerf Endpoints explicitly models serving as a **frontier across concurrency**, with system throughput, per-user throughput/interactivity, TTFT and load rather than a single “latency number.” NVIDIA's GenAI-Perf similarly reports TTFT, inter-token latency, request latency, sequence lengths, output-token throughput and request throughput, with GPU telemetry available in supported deployments. These are excellent methodological templates for your self-host track.

You should therefore benchmark each self-hosted candidate under a concurrency sweep rather than only sending sequential requests:

[ 1,;2,;4,;8,;16,;32,;64,\ldots ]

until either throughput stops improving materially or the SLA is violated.

### Cost model

For an API candidate:

# [ C_{\text{request}}

\frac{ T_{in}P_{in} + T_{out}P_{out} + T_{cached}P_{cached} }{10^6} + C_{\text{other billed usage}} ]

and:

# [ C_{\text{month}}

N_{\text{tickets}} \times R_{\text{calls/ticket}} \times C_{\text{request}} + C_{\text{retries}} + C_{\text{fixed}} ]

where all pricing records have an effective date and currency.

For self-hosting, first estimate required replicas from **measured sustainable capacity**, not theoretical GPU FLOPS:

[ R = \left\lceil \frac{\text{PeakRPS}} {\text{Measured sustainable RPS per replica}\times U_{\text{target}}} \right\rceil ]

where (U_{\text{target}}<1) provides capacity headroom.

Then:

# [ C_{\text{self}}

R \times H_{\text{month}}\times P_{\text{instance/hour}} + C_{\text{storage}} + C_{\text{network}} + C_{\text{load balancing}} + C_{\text{observability}} + C_{\text{operations}} ]

For owned hardware, substitute amortized hardware cost, electricity, facilities, maintenance and staffing.

This creates one of the most useful outputs of the project: the **API ↔ self-host break-even curve**. The cheapest option at 50,000 tickets/month may differ from the cheapest at 20 million tickets/month because API cost is largely usage-linked while reserved self-hosted capacity introduces fixed/stepwise infrastructure costs.

### Deterministic decision rule

Do not begin with an opaque weighted score such as:

[ 0.4Q+0.3C+0.2L+0.1Compliance ]

because arbitrary weights create hard-to-defend recommendations.

Use **constraint filtering followed by lexicographic optimization**.

For enterprise request (x), candidate (c) is feasible only when:

[ \begin{aligned} &Q(c,t,d,l) \ge Q_{\min}(t,d,l)\ &Latency_{p95}(c,w) \le L_{\max}\ &Capacity(c,w)\ge Capacity_{\min}\ &Cost(c,w)\le Budget \quad\text{if budget is a hard limit}\ &LanguageSupport(c,l)=true\ &DeploymentControls(c,x)=pass\ &License(c,x)=allowed \end{aligned} ]

Then:

[ c^* = \arg\min_{c\in F(x)} C_{\text{monthly}}(c,x) ]

with fixed tie breakers:

[ \text{cost} \rightarrow \text{quality margin} \rightarrow \text{latency} \rightarrow \text{operational complexity} ]

The user could alternatively select a formally defined objective such as **highest measured quality within budget**, but the objective must be explicit.

If:

[ F(x)=\varnothing ]

the product must return:

> **No evaluated configuration satisfies all mandatory requirements.**

That outcome is one of the features that will distinguish a serious decision-support system from a recommendation website.

### Required evidence registry

The engine needs roughly five linked data tables.

| Registry                  | Critical fields                                                                                                                                              |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Model**                 | model ID, exact version, provider/developer, weight availability, architecture/size where known, context limits, model license, supported inference features |
| **Hosting**               | host/provider, region, API vs managed vs self-host, accelerator, serving engine, quantization, redundancy, availability model                                |
| **Evaluation**            | model configuration, dataset/version, task, domain, language, prompt/version, date, score, CI, evaluator, run count                                          |
| **Performance**           | hardware/endpoint, input/output length distribution, concurrency, TTFT, ITL, p95/p99 latency, RPS, token/s, failures                                         |
| **Commercial/governance** | price/date, billing unit, data region, retention configuration, training-on-data policy, log controls, contract evidence, applicable buyer requirements      |

Every recommendation should preserve provenance:

> “Model A + host B was selected because it passed Hindi intent ≥ 90%, retail task-success ≥ 80%, p95 latency ≤ 3 s and buyer control set RBI-CS-01…05, and had the lowest modeled monthly cost at the submitted workload. Evidence snapshot: 2026-12-15.”

That explanation is itself a major product feature.

## Prioritized implementation and validation roadmap

I would divide the evidence portfolio into three tiers rather than attempting to integrate every available dataset on day one.

**Priority portfolio**

|Tier|Resource|Why it belongs there|
|---|---|---|
|**MVP**|BANKING77|Clean banking anchor; easy deterministic scoring|
|**MVP**|CLINC150|Adds abstention/OOS, which a deployable support system needs|
|**MVP**|τ-bench 2.0 Retail + Telecom, English + Hindi|End-to-end customer service, two additional domains, multilingual, policy/tool use|
|**MVP**|MASSIVE: English, Hindi + 2–4 selected regional Indian languages|Controlled multilingual NLU comparison|
|**MVP**|ABCD|Deep retail workflow/policy evaluation|
|**MVP**|TweetSumm|Customer-service summarization|
|**MVP / extended depending on task scope**|τ-Knowledge Banking|Grounded banking QA/RAG and policy use|
|**Extended**|IndicQA + IndicGenBench|Broader Indic QA/summarization capability|
|**Extended**|Amazon Product Q&A|Large retail FAQ evaluation/training source|
|**Extended**|MultiDoGO|Cross-domain conversational NLU|
|**Extended**|NLU++|Multi-intent compositional banking/hotel NLU|
|**Extended**|HINT3|Additional in-the-wild retail intent evidence|
|**Extended**|MedQuAD|Healthcare QA stress domain|
|**Robustness**|TextFlint + deterministic perturbation suite|Typos/noise|
|**Robustness**|Hinglish/code-mixed subset|Indian conversational realism|
|**Robustness**|τ-Trait|User-behavior robustness|
|**Future**|τ-Voice + IndicVoices|Contact-center voice deployment|

The resulting validation matrix would be much stronger than a traditional “benchmark every model on five datasets” approach:

||Banking|Retail|Telecom|Healthcare|
|---|---|---|---|---|
|Intent|BANKING77|ABCD / HINT3|τ task setup|custom/optional|
|OOS|CLINC overlay|CLINC overlay|CLINC overlay|safety/handoff set|
|FAQ/RAG|τ-Knowledge|Amazon QA / support docs|knowledge extension|MedQuAD|
|Resolution/tool use|τ-Knowledge|τ-Retail / ABCD|τ-Telecom|future|
|Summarization|TweetSumm transfer test|TweetSumm|TweetSumm|MeQSum/extended|
|Hindi|custom + MASSIVE capability|τ-i18n|τ-i18n|IndicQA capability|
|Regional Indian languages|MASSIVE/Indic suite|MASSIVE/Indic suite|MASSIVE/Indic suite|IndicQA|
|Robustness|OOS + typo + Hinglish|same|same|safety-oriented stress set|

The empty cells are useful findings rather than project failures. They reveal exactly where public benchmark evidence is insufficient, which is why the engine must represent **evidence coverage** rather than pretending every model has been equally validated for every domain.

A model could therefore have a profile such as:

|Capability|Evidence|
|---|---|
|Banking intent / English|Strong|
|Banking QA / English|Strong|
|Retail resolution / English|Strong|
|Telecom resolution / English|Strong|
|Retail / Hindi|Strong|
|Telecom / Hindi|Strong|
|Banking / Hindi|**Insufficient**|
|Banking / Tamil|**Insufficient**|

The recommender should distinguish **failed** from **not evaluated**. This is crucial.

**Data-collection and validation timeline**

01 Nov08 Nov15 Nov22 Nov29 Nov06 Dec13 Dec20 Dec27 Dec03 Jan10 JanDataset, license and version inventoryModel and hosting schemaGovernance evidence schemaClassification and OOS harnessQA / RAG / summarization harnessTau agent benchmark integrationBanking English baselineAPI endpoint load testsRetail and telecomSelf-host configuration experimentsHindi and regional-language evaluationRobustness / OOS / code-mixingCost and break-even modelHuman audit and judge calibrationRecommendation stability testsFinal evidence freeze and reportRegistryEvaluation harnessBenchmark runsHostingValidationEvidence collection and validation roadmap

Show code

The first milestone should not be a dashboard. It should be a versioned evidence table in which you can query something like:

text

Copy

```text
model = M
host = H
domain = retail
task = resolution
language = hi
benchmark = tau2-text-v1
quality = ...
p95_latency = ...
sustainable_rps = ...
cost_profile = ...
governance_evidence = ...
evaluated_at = ...
```

Once that table is correct, the dashboard is comparatively straightforward.

The final PME demonstration should use three or four enterprise scenarios that force different answers. For example:

|Scenario|Likely decision tension|
|---|---|
|Small English-only e-commerce company|Cheap managed API may dominate|
|High-volume multilingual retail platform|Throughput/self-host economics become important|
|Indian regulated bank with sensitive support workflow|Governance gates eliminate otherwise attractive options|
|Telecom provider with Hindi-heavy troubleshooting|Hindi task completion and dual-control performance matter more than generic leaderboard scores|

A good project outcome is **not** that one model wins every scenario. The stronger result is that your deterministic framework shows _why the winning configuration changes when workload, language, quality threshold, deployment constraints or traffic volume changes_.

The deepest research opportunity is therefore no longer “Which LLM is cheapest for BANKING77?” It is:

> **Can a reproducible evidence model translate a real enterprise workload into a defensible model-and-hosting decision, while distinguishing measured capability, untested capability, cost, serving capacity and India-specific deployment constraints?**

That is a substantial PME project. It has a product problem, a backend data architecture, an evaluation platform, systems benchmarking, deterministic decision logic, India-specific relevance, multilingual research value, and a demonstrable final artifact. Most importantly, the available 2026 benchmark ecosystem—particularly τ-Knowledge, τ²-bench and the newly released Hindi-capable τ-bench 2.0—means you can now validate much more of that vision with public, reproducible resources than was possible under the original banking-intent-only proposal.