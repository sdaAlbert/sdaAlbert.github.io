---
title: "Coordinating Data Movement in LLM Inference: A Research Map"
date: 2026-10-05
permalink: /posts/llm-inference-data-movement/en/
lang: en
translations:
  zh: /posts/llm-inference-data-movement/
  en: /posts/llm-inference-data-movement/en/
author_profile: false
read_time: true
excerpt: "A research map of weights, KV caches, and activations across GPU memory, host memory, storage, and networks, with concrete mechanisms from SGLang, Megatron Core, and TensorRT-LLM."
tags:
  - AI Infrastructure
  - LLM Inference
---

# Coordinating Data Movement in LLM Inference: A Research Map

When a GPU runs a large language model, where does the data needed for computation come from, and where does it move? Poor placement or timing makes requests wait for data. Moving too much at once can also consume bandwidth or GPU resources needed by computation.

## 1. What data does an inference request read and write?

Inside model execution, LLM inference mainly involves three kinds of data: model weights, the KV cache, and activations. They differ in purpose, location, and when they need to move. [Inference I/O survey, 2026](https://link.springer.com/article/10.1007/s10462-026-11651-1)

Weights are the parameters learned by the model. The KV cache stores the keys and values produced for previous tokens during attention, avoiding repeated computation during generation. Activations are intermediate results produced by model layers. A token is a basic unit of text processed by the model; logits are the scores assigned to candidate tokens.

Inputs and outputs also cross the serving boundary. The serving layer usually sends input token IDs to the execution device. Generated tokens or logits return to the serving layer or go to a sampling component, depending on where sampling happens. The main discussion focuses on text models, with image, audio, and video inputs covered briefly at the end.

| **Data** | **During input processing** | **During token-by-token generation** | **Storage and cross-device movement** | **Lifetime and access pattern** |
| --- | --- | --- | --- | --- |
| Weights | Read by each layer | Read again at every generation step | Loaded from storage into GPU memory at startup; when memory is insufficient, kept in CPU memory or on SSD and loaded by layer or block | Relatively fixed and repeatedly read by later computation |
| KV cache | Created and written for input tokens | Historical keys and values are read; new entries are appended | Offloaded to CPU memory, SSD, or remote storage and restored when needed; transferred to the generation stage when input processing and generation are deployed separately | Grows with requests and context; the corresponding prefix can also be recomputed |
| Activations | Produced by layers and passed to subsequent computation | Produced by layers and passed to subsequent computation | Mainly move between GPU memory and on-chip storage on one GPU; transferred between devices in tensor, pipeline, or expert parallelism | Usually short-lived; tiling and fusion affect how often they are written to and read from GPU memory |
| Inputs and outputs | Token IDs or multimodal tensors enter the model | Logits or sampled tokens return to the serving layer | Usually pass between CPU and GPU; multimodal inputs can be large | Data exchanged between serving and model execution |

## 2. Which paths does the data take?

Common paths can be organized by the hardware boundaries they cross. HBM is the high-bandwidth memory commonly used as GPU memory. Caches, shared memory, and registers are smaller on-chip stores that computation can access locally. Movement inside a GPU involves reads and writes across these memory levels; the other paths mainly involve device or storage transfers.

| Path | Common interconnect or memory levels | Inference example |
| --- | --- | --- |
| Inside a GPU | HBM, caches, shared memory, registers | Operators read weights and KV; activations pass between operators |
| CPU to GPU | Usually PCIe; platforms such as Grace Hopper use NVLink-C2C | Weights or KV move from CPU memory into a GPU |
| GPUs within one machine | NVLink and NVSwitch, or PCIe | Layer results are combined, activations handed off, or KV transferred |
| GPUs across machines | Network interface cards (NICs), switches, and InfiniBand or RoCE networks | KV, activations, or expert-routing traffic crosses nodes |
| Storage to GPU | NVMe through host memory and PCIe; GPUDirect Storage where supported | Weights or offloaded KV are read from SSD into a GPU |

InfiniBand is a high-speed network commonly used in data centers. RoCE carries RDMA over Ethernet. RDMA, or remote direct memory access, lets a NIC directly read or write remote memory. On supported hardware and topologies, GPUDirect RDMA lets the NIC perform direct memory transfers into GPU memory, reducing staging through CPU memory. GPUDirect Storage (GDS) provides a similar direct path from storage to a GPU. NVSwitch connects NVLink GPUs, and some rack-scale systems extend NVLink across machines. [NVIDIA NVLink and NVSwitch](https://docs.nvidia.com/hgx-platforms/fabric-manager-user-guide/index.html) · [NVLink-C2C](https://docs.nvidia.com/dccpu/grace-perf-tuning-guide/) · [GPUDirect RDMA](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/gpu-operator-rdma.html) · [GPUDirect Storage](https://docs.nvidia.com/gpudirect-storage/)

## 3. Movement paths and research directions for the three data types

The paths in Section 2 serve different purposes for different data. Following each data type shows where movement problems arise.

### Weights: loaded from storage, then read by each layer

At startup, weights typically move from SSD through host memory and PCIe into GPU HBM. Platforms supporting GPUDirect Storage can change the staging path. During inference, operators consume weights through GPU caches, shared memory, or registers. If GPU memory cannot hold the model, some weights may stay in CPU memory or on SSD and be loaded by layer or block.

```text
Request arrives → execution queue → prepare current layer
                                      │
                                      ├─ Resident weights:
                                      │  GPU HBM → cache / shared memory → compute
                                      │
                                      └─ Weights to load:
                                         SSD → host memory → PCIe → GPU HBM
                                                may load early       │
                                                                    │ weights must be ready
                                                                    ▼
                                                        current layer → next layer

With limited GPU memory, load weights by layer or block from CPU memory or SSD.
The next layer's weights can move while the current layer computes.
```

FlexGen demonstrates joint placement and scheduling across GPU, CPU, and SSD. Such designs primarily address capacity and throughput; low-latency online serving needs a separate evaluation. [FlexGen](https://arxiv.org/abs/2303.06865)

### KV cache: grows, is reused, and migrates with requests

Prefill processes the input and creates KV. Decode generates tokens one at a time, reading historical KV and appending new state at every step. KV is usually created in GPU HBM. When offloaded to CPU memory, SSD, or a remote tier, it returns through the PCIe, storage, or network paths described in Section 2. With separate prefill and decode deployments, KV also moves from the prefill GPU or host to the generation node.

```text
Request arrives → prefix match → wait for execution
                       │
                       ├─ GPU-memory hit:
                       │  GPU HBM → GPU memory hierarchy → attention
                       │
                       ├─ External hit:
                       │  SSD / remote → host memory → PCIe / network → GPU HBM
                       │                    may prefetch                    │
                       │                                                   │ KV must be ready
                       │                                                   ▼
                       └─ Miss: recompute prefix → create KV → decode

New KV may be offloaded in the background:
GPU HBM → PCIe / network → CPU memory, SSD, or remote cache

Separate deployments also transfer KV between stages:
prefill GPU / host → NVLink or NIC / network → decode GPU / host
```

Tiered offloading and HiCache illustrate different designs for cache hits, restoration, and partial reuse. A cache hit may involve GPU memory, host memory, or a network path, with very different end-to-end costs. [vLLM tiered offloading design](https://vllm.ai/blog/2026-09-10-tiered-kv-offloading) · [Mooncake × HiCache design](https://kvcache-ai.github.io/Mooncake/design/hicache-design.html)

### Activations: move inside a GPU and sometimes across GPUs

On a single GPU, operators produce activations and pass them to subsequent operators through HBM, caches, and on-chip storage. Tiling and fusion change how often intermediate data is written to HBM. Across GPUs, tensor parallelism may exchange activation shards within a layer; pipeline parallelism passes activations to the next GPU at stage boundaries. These paths may use NVLink, NVSwitch, or PCIe.

```text
Request arrives → input enters GPU → execute current layer
                                         │
                                         ├─ Single GPU:
                                         │  compute ⇄ on-chip storage ⇄ HBM
                                         │                              │
                                         │                              ▼
                                         │                        next operator
                                         │
                                         ├─ Tensor parallelism:
                                         │  GPU 0 ⇄ NVLink / NVSwitch / PCIe ⇄ GPU 1
                                         │          activation shards / layer results
                                         │
                                         └─ Pipeline parallelism:
                                            previous-stage GPU → interconnect / network
                                                               → next-stage GPU
                                                                 activations must arrive
```

FlashAttention demonstrates how to reduce HBM reads and writes for intermediate attention data. TensorRT-LLM documentation describes the communication-bandwidth and load-balancing trade-offs of tensor and pipeline parallelism. [FlashAttention](https://arxiv.org/abs/2205.14135) · [TensorRT-LLM parallel strategies](https://nvidia.github.io/TensorRT-LLM/1.2.0rc6.post2/features/parallel-strategy.html)

Input tokens, multimodal tensors, sampling results, and output tokens also cross the serving–device boundary. Their lifetimes differ from those of weights, KV, and activations inside the model, but multimodal input and distributed sampling can still introduce substantial transfer and synchronization costs.

### How does workload change movement pressure?

Knowing the paths is only a start; their access frequency also matters. Prefill processes multiple input tokens at once, allowing linear layers to reuse loaded weights for more computation. Small-batch decode processes fewer tokens per step, so weight reads often become more prominent relative to computation. Batching requests increases opportunities for weight reuse, while also increasing the KV that must be stored and read.

Context length changes another source of pressure. For attention implementations that read the full history, longer context means more KV to access per generation step. Weight reads therefore deserve attention at small batch sizes and short contexts, while KV capacity and access costs may become more important as context grows. Model architecture, cache hits, and parallelism all affect this balance; one bottleneck cannot be assigned to every workload.

Arithmetic intensity measures how much computation is performed per byte accessed. At low intensity, memory supply may limit performance first; at higher intensity, compute capacity may matter more. This is an initial approximation. Small workloads, insufficient parallelism, or launch overhead can leave both compute and bandwidth underused, so measurements are still necessary. [NVIDIA GPU performance guide](https://docs.nvidia.com/deeplearning/performance/dl-performance-gpu-background/index.html)

A research map therefore needs to identify data, paths, and workload together. The same KV may pose a capacity problem when GPU memory is scarce, an HBM-access problem during long-context decode, or a network-transfer problem in separate deployments. Establish the phase, batch size, and context length before choosing a path to optimize.

## 4. A research map for inference data movement

The data and paths above lead to six groups of research directions. Their connection is: **placement determines the path; layout and representation affect traffic volume; timing determines waits; shared resources determine the cost of concurrency; multi-GPU execution adds communication dependencies; request performance ultimately determines the benefit.**

### 4.1 Placement and lifetime: where should data stay?

- **Tiered placement and path selection:** Keeping weights or KV in CPU memory, on SSD, or remotely expands capacity and frees GPU memory, but adds reading and restoration costs when the data is needed again. The research direction is to choose placement using capacity pressure and reuse frequency, while evaluating staging and transfer costs along the full path.
- **Retention and reclamation:** Frequently reused prefixes are worth keeping close to computation; rarely reused data can be offloaded or released. Retention changes how many later transfers are needed. Reclamation must also wait for relevant computation and transfers to finish, connecting capacity management to execution synchronization.
- **Restore or recompute:** Even a cache hit can involve queueing and transfer, and under congestion may be slower than processing the prefix again. Comparing the actual costs under different context lengths and loads connects cache policy with compute scheduling.

Public examples: [FlexGen](https://arxiv.org/abs/2303.06865), [tiered KV caching](https://vllm.ai/blog/2026-09-10-tiered-kv-offloading).

### 4.2 Layout and traffic volume: how should data be organized, and which accesses can be avoided?

Once placement is chosen, organization and access patterns still affect capacity and traffic.

- **Paging and sharing:** Allocating KV in blocks reduces wasted reservations, while sharing valid prefixes avoids duplicate storage. Both free space for more requests and change how operators access data. Paging itself does not mean the data has been offloaded to CPU memory or SSD.
- **Transfer organization:** Combining small blocks reduces submission overhead, but waiting to combine them can delay the first usable data. SGLang HiCache uses a layer-first layout on the GPU and a page-first layout for host and storage I/O, illustrating the different needs of computation and transfer. Layout conversion, transfer granularity, and handoff timing should be evaluated together. [HiCache](https://www.lmsys.org/blog/2025-09-10-sglang-hicache/)
- **Reads and writes inside a GPU:** Even with all data in GPU memory, operators still access weights, KV, and intermediate results. Tiling and fusion can reduce HBM round trips while requiring careful control of on-chip resources. TensorRT-LLM's attention backend can also fuse output quantization into attention computation, illustrating how separate processing steps and intermediate data can be reduced. [TensorRT-LLM attention implementation](https://nvidia.github.io/TensorRT-LLM/features/attention.html)
- **Compression, quantization, and sparsification:** Compact representations or using less data in computation can reduce traffic, but may add encoding, decoding, or format-conversion costs, or affect output quality. Benefits must be assessed across processing, movement, and computation, rather than from bytes saved alone.

Public examples: [PagedAttention](https://arxiv.org/abs/2309.06180), [FlashAttention](https://arxiv.org/abs/2205.14135), [vLLM KV transfer implementation](https://vllm.ai/blog/2026-01-08-kv-offloading-connector).

### 4.3 Timing: when will the data be ready?

Even with identical placement and traffic volume, submission timing and handoff granularity change how long computation waits.

- **Prefetching:** Starting movement before data is used can take advantage of queueing time or other computation. Starting too early occupies buffers, and wrong predictions create unused transfers. Prefetch lead time, data selection, and capacity limits therefore need to be coordinated.
- **Chunked handoff:** Where dependencies allow, the current layer's data can arrive first, followed by a pipeline of current-layer computation and later transfers. Small chunks become usable earlier; larger chunks amortize submission costs. Transfer granularity is therefore tied to when computation can start.
- **Compute granularity and data preparation:** TensorRT-LLM's chunked prefill splits long inputs into smaller compute chunks, giving ongoing generation requests opportunities to execute and changing per-iteration activation-buffer requirements. It partitions computation; research should connect compute chunk size with data preparation and buffer use, keeping the distinction between chunked computation and chunked transfer clear. [Chunked prefill](https://developer.nvidia.com/blog/streamlining-ai-inference-performance-and-deployment-with-nvidia-tensorrt-llm-chunked-prefill/)
- **Compute overlap:** Asynchronous submission lets the submitting thread continue, but actual overlap depends on data dependencies, execution order, and device capabilities. The research direction is to identify independent computation that can run alongside transfers and place synchronization so that less waiting remains exposed.
- **Small data and state synchronization:** Megatron Core's dynamic inference context batches scheduling metadata for transfer to the GPU and, during asynchronous scheduling, prepares the next input directly from GPU-resident sampled tokens. Although the data is small, frequent transfers and waits can enter the critical path. Reducing round trips and scheduling buffer reuse must preserve consistent CPU and GPU state. [Megatron Core inference context](https://docs.nvidia.com/megatron-core/developer-guide/latest/apidocs/core/core.inference.contexts.dynamic_context.html)
- **Contention and interference:** Concurrent transfers and computation can compete for resources such as HBM bandwidth, and transfer implementations use different resources. Transfer concurrency and prefetch depth must balance hidden waits against added interference. More overlap does not necessarily mean faster execution.

Mechanism reference: [CUDA guide to overlapping transfers and computation](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/index.html#asynchronous-and-overlapping-transfers-with-computation).

### 4.4 Shared resources: which transfer goes first?

The previous group concerns the handoff between a transfer and computation. Concurrent requests also require coordination among tasks sharing queues, links, and buffers.

- **Priority:** Foreground restoration directly affects the current request; background backup, prefetching, and migration usually have different urgency. Ordering reduces critical waits, but must take effect before large amounts of work enter lower-level queues, while preventing background starvation.
- **Limits on outstanding work:** Capping submitted but unfinished transfers controls congestion and buffer occupancy. Since task sizes vary, a count limit alone may be insufficient. Task, byte, and buffer limits jointly balance concurrent throughput against queueing delay.
- **Admission and backpressure:** Admission control decides whether new work is accepted; backpressure lets downstream congestion slow upstream submissions. These complement priority: ordering decides who goes first, while admission and backpressure control whether work keeps accumulating.

Design reference: [Mooncake local transfer admission queue RFC](https://github.com/kvcache-ai/Mooncake/issues/2132). This is a design proposal, not a validated performance result.

### 4.5 Multi-GPU coordination: which compute boundary requires communication?

Distributing computation creates dependencies between devices. Different parallel strategies place waits at different boundaries.

- **Tensor parallelism:** A layer is split across GPUs, with partial results exchanged or combined before subsequent computation can proceed. Research concerns communication organization, synchronization frequency, overlap with independent work, and the effect of slower participants on the whole layer.
- **Pipeline parallelism:** Layers are divided into stages that hand off activations. Both slow transfers and uneven stage computation can leave downstream GPUs waiting. Handoff granularity must be coordinated with stage load and interleaved request execution.
- **Prefill/decode disaggregation:** Transferring KV between stages allows input processing and generation resources to be configured separately, but adds a state-handoff cost. Research must coordinate both stages' processing capacity with KV transfer speed, so scaling one side does not simply move the bottleneck to the link or receiver.
- **MoE expert parallelism:** A router assigns tokens to expert subnetworks, with activations dispatched and returned across GPUs. SGLang's two-batch overlap interleaves microbatch computation with expert communication, while expert load balancing changes expert distribution. These connect communication timing with device load; research must also check whether contention or local congestion offsets the overlap benefit. [SGLang expert parallelism](https://www.lmsys.org/blog/2025-05-05-large-scale-ep/)

These directions depend on GPU connectivity and shared links, and reuse the chunking, overlap, and traffic-control mechanisms above. Public references: [parallel strategies](https://nvidia.github.io/TensorRT-LLM/1.2.0rc6.post2/features/parallel-strategy.html), [disaggregated serving](https://docs.nvidia.com/dynamo/dev/kubernetes/disaggregated-serving/overview), [expert parallelism](https://nvidia.github.io/TensorRT-LLM/advanced/expert-parallelism.html).

### 4.6 Evaluation: did the request actually get faster?

Optimizations can move costs elsewhere. Their benefits must be checked against complete request performance.

- **Attribute the cost:** Separate queueing, waiting for data, transfer, synchronization, and slower computation to identify what changed. GPU-internal optimizations also need HBM-traffic and operator-duration measurements; copy speed or overlap percentage alone cannot explain the benefit.
- **Observe serving metrics:** Time to first token (TTFT) measures the wait for the initial output; inter-token latency reflects generation cadence; tail latency and throughput describe overall serving behavior. A local optimization can improve one metric while harming another, requiring a choice based on serving goals.
- **Establish the scope:** Phase, batch size, concurrency, context length, hit location, and background traffic all change the bottleneck. Research should explain where an optimization helps and when compute, capacity, or another link limits its benefit.

Section 5 describes measurement more concretely.

These projects demonstrate existing mechanisms and their trade-offs. A concrete research problem still requires a stable, measured shortcoming under the target workload; an existing feature alone is not an unsolved problem.

### Further directions

- **Multimodal input:** Images, audio, and video are preprocessed before entering the model. Preprocessing placement, chunked input transfer, and pipelined execution connect to the placement, handoff, and scheduling directions above, while large inputs also pressure buffers and queues.
- **Weight and adapter updates:** A LoRA adapter is a set of additional parameters that adjusts model behavior. Loading new parameters must preserve the version used by each request. Keeping old and new parameters together can simplify switching but increases temporary storage, so update timing and old-parameter reclamation must be coordinated.

## 5. From system behavior to a testable problem

This map organizes common research directions through data types, hardware paths, and coordination mechanisms. A concrete analysis also needs workload conditions: where data originates, how it is organized, which path it follows, which computation must wait for it, and how important that wait is at the current phase and batch size.

Start with an observable data path, locate it on the map, and compare the existing mechanisms through controlled measurements.

Fix the model, hardware, runtime version, and a reproducible request sequence. Then design separate comparisons that vary batch size, request concurrency, input and historical context lengths, the fraction of tokens actually covered by cache hits, or background traffic.

Choose measurements for the path. For explicit transfers, record queueing delay, bytes transferred, staging-buffer use, and when dependent computation starts. For GPU-internal accesses, record HBM traffic, operator duration, and resource utilization. For inter-GPU communication, also examine differences between participants and synchronization waits. Finally, compare TTFT, inter-token latency, tail latency, and throughput, repeating runs to confirm that the behavior is stable.

A direction becomes a concrete research problem when a target workload exposes a stable, explainable performance limitation that existing mechanisms have not resolved.

## References

- [I/O for LLM Inference: a survey of storage and memory bottlenecks, 2026](https://link.springer.com/article/10.1007/s10462-026-11651-1).
- [FlexGen: tiered inference across GPU, CPU, and SSD](https://arxiv.org/abs/2303.06865); [FlashAttention](https://arxiv.org/abs/2205.14135).
- [NVIDIA GPU performance guide](https://docs.nvidia.com/deeplearning/performance/dl-performance-gpu-background/index.html): arithmetic intensity, bandwidth, and latency limits; [PagedAttention](https://arxiv.org/abs/2309.06180): KV paging and sharing.
- [NVIDIA Dynamo disaggregated serving](https://docs.nvidia.com/dynamo/dev/kubernetes/disaggregated-serving/overview); [vLLM KV transfer implementation analysis](https://vllm-project.github.io/2026/01/08/kv-offloading-connector.html).
- [TensorRT-LLM parallel strategies](https://nvidia.github.io/TensorRT-LLM/1.2.0rc6.post2/features/parallel-strategy.html): tensor- and pipeline-parallel data exchange.
- [TensorRT-LLM expert parallelism](https://nvidia.github.io/TensorRT-LLM/advanced/expert-parallelism.html): expert distribution and communication.
- [SGLang HiCache](https://www.lmsys.org/blog/2025-09-10-sglang-hicache/); [SGLang large-scale expert parallelism](https://www.lmsys.org/blog/2025-05-05-large-scale-ep/): cross-tier layouts, communication overlap, and expert load.
- [Megatron Core dynamic inference context](https://docs.nvidia.com/megatron-core/developer-guide/latest/apidocs/core/core.inference.contexts.dynamic_context.html): scheduling-metadata transfers and sampled-token paths.
- [TensorRT-LLM attention implementation](https://nvidia.github.io/TensorRT-LLM/features/attention.html); [chunked prefill](https://developer.nvidia.com/blog/streamlining-ai-inference-performance-and-deployment-with-nvidia-tensorrt-llm-chunked-prefill/): operator fusion and compute granularity.
- [Mooncake local transfer queue RFC #2132](https://github.com/kvcache-ai/Mooncake/issues/2132); [Mooncake × HiCache design](https://kvcache-ai.github.io/Mooncake/design/hicache-design.html).
- [CUDA guide to asynchronous transfers and compute overlap](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/index.html#asynchronous-and-overlapping-transfers-with-computation).
- [NVIDIA NVLink and NVSwitch](https://docs.nvidia.com/hgx-platforms/fabric-manager-user-guide/index.html); [GPUDirect RDMA](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/gpu-operator-rdma.html); [GPUDirect Storage](https://docs.nvidia.com/gpudirect-storage/).
- [NVLink-C2C](https://docs.nvidia.com/dccpu/grace-perf-tuning-guide/).
