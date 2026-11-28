# Performance data gaps and assumptions

## Artificial Analysis

The downloaded public figures and their observation date are recorded in
[artificial_analysis.yaml](../pome/registry/artificial_analysis.yaml). These are named hosted
API results for Gemma 4 26B A4B, Gemma 4 31B, Qwen3.8 27B, Llama 3.1 8B, and Muse Glimmer.
The source reports time to the first **answer** token, including reasoning when enabled.
Its endpoint error rate pools hosted requests, including rate limits and timeouts. It does
not measure the app's retry policy. [Artificial Analysis methodology](https://artificialanalysis.ai/methodology/performance-benchmarking)

The performance model adds the provider's observed first-answer time to a decode
calculation for the selected GPU. Decode seconds are the remaining 199 tokens multiplied by
weight size in GB, divided by GPU bandwidth in GB/s and the existing 70% utilization
assumption. Serial throughput is the number of independent GPU replicas divided by that
request time, assuming one active request per GPU. BF16 uses two bytes per weight. Gemma 4
12B W4A16 uses a packed 4-bit weight size before quantization metadata and runtime overhead.
The model omits GPU batching, scheduling, network changes and latency percentiles. It is a
mixed-source sizing scenario. Its first-answer input comes from a different deployment,
and can include reasoning overhead. Quantization and hardware details are recorded with
the provider rows where published.

Gemma 4 12B and Sarvam 30B had no usable first-answer observation in the reviewed public
provider tables. Their hardware plans use the existing 0.2-second start-delay assumption.
E2E A100 uses the conservative PCIe bandwidth specification. For AWS Mumbai, the model
applies AWS's published P5 family per-GPU bandwidth to its single-H100 p5.4xlarge SKU.
[AWS P5 family specifications](https://aws.amazon.com/ko/blogs/tech/2024-aws-reinvent-ec2-instance-recap/) [Gemma 4 12B providers](https://artificialanalysis.ai/models/gemma-4-12b/providers) ·
[Sarvam 30B](https://artificialanalysis.ai/models/sarvam-30b) ·
[AWS instance specifications](https://docs.aws.amazon.com/ec2/latest/instancetypes/ac.html)

The app shows modeled values under **Deployment variants** and the inputs and sources under
**Evidence**. The p95 latency, sustainable peak throughput, and post-retry error gates
still use matching deployment evidence. Artificial Analysis's local Qwen3.8 test uses
4-bit weights, speculative decoding and single-agent workloads. It is a useful hardware
reference and differs from this app's BF16 vLLM workload. [AA-AgentPerf-Local configurations](https://artificialanalysis.ai/hardware-inference-stack/laptops-workstations/configs)


Owned and rented candidates that use the same checkpoint and precision share benchmark
references. If you enter a custom GPU, supply memory bandwidth from its specifications to
enable the sizing calculation. With bandwidth blank, the app can still screen VRAM fit
and compute costs from the supplied quote. Node and GPU counts change the number of
replicas in the plan. The model keeps one replica per GPU and the short-context assumption.
