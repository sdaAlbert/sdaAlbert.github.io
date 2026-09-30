---
title: "A Voodoo Doll's Guide to Landing an AI Infra Job"
date: 2026-09-30
permalink: /posts/ai-infra-job-guide/en/
lang: en
translations:
  zh: /posts/ai-infra-job-guide/
  en: /posts/ai-infra-job-guide/en/
author_profile: false
read_time: true
excerpt: "A newcomer’s map of AI Infra careers: cluster platforms, training and inference frameworks, and hardware–software co-design, with JD signals and portfolio scope."
tags:
  - Industry Observation
  - AI Infrastructure
---

This guide is for people entering AI infrastructure through campus recruiting or junior-level roles. Thanks to [Moon Uncle’s career-change talk](https://www.youtube.com/watch?v=aHAXzFT8IuQ), which inspired the three career tracks and the idea of reverse-engineering engineering experience from job-description keywords.

AI infrastructure turns models into systems that can be trained, deployed, and operated reliably. Its core concerns are compute efficiency, resource use, and recovery from failures. Cluster platforms place jobs and allocate compute; AI frameworks organize training or inference; hardware–software co-design improves execution at the lower layers. These are three ways to classify the work, and specific roles often cross two of them. Career discussions on Reddit make a similar point: look at the system layer a role owns instead of relying on the title “AI Infra.” [Reddit: moving into LLMOps or AI Infra](https://www.reddit.com/r/mlops/comments/1u0sgh9/job_switch_to_llmops_or_ai_infra/)

This roadmap has a time window. As of September 2026, public job descriptions include domestic accelerator onboarding, compute acceptance testing, RL training environments, and cache pools. Changes in models, hardware, and workloads reshape both team boundaries and skill requirements; hiring headcount also depends on budgets and recruiting cycles. One job description tells you what a team needs to solve now, not whether the field as a whole is expanding. Revisit target teams’ current openings and separate durable systems skills from the tools in fashion today. [Tencent heterogeneous-compute platform role](https://careers.tencent.com/jobdesc.html?postId=2099328404741603328) · [Baidu AI Infra RL campus role](https://talent.baidu.com/jobs/detail/GRADUATE/9c20ea8d-db12-4bea-8c69-292391ba31d4)

A job description can be treated as an open-book exam. Following Moon Uncle’s analysis of a Roblox job description, translate keywords into evidence of engineering experience:

- **Training and inference workflows:** Understand how a framework executes. Megatron points to distributed training, `torch.compile` to compilation, and continuous batching to request scheduling. Choose the main thread that matches the role.
- **Performance analysis:** Use Nsight Systems to locate system-level waits and Nsight Compute to analyze GPU kernels. Let measurements support the optimization hypothesis.
- **Model optimization, deployment, and open-source work:** Make a reusable change. A strong contribution should explain the problem, code, validation, and maintainer feedback; there is no fixed PR-count requirement.
- **Providing a backend for algorithm teams:** Integrate a model method into a framework. For example, add support in NeMo-Aligner for a particular RLHF model interface.
- **Scalability and collaboration:** Understand deployment, routing, monitoring, and interfaces. Projects such as the vLLM Production Stack show how an engine becomes part of a serving system.

Choose a track before building a résumé, then decide which module to understand and change. Check your learning at three levels: reproduce a result and document the environment, configuration, baseline, and outcome; trace a real code path and make a bounded change; validate and maintain that change by checking correctness, performance, failure cases, and regressions, and by stating where it applies. A system map helps locate components, while concrete problems determine the learning order. This distinction is also useful in [A Gan’s AI Infra learning map](https://arganzheng.life/ai-infra-learning-roadmap.html).

## Track 1: AI Cluster Platform Engineer (Backend-Oriented)

A cluster platform lets model teams submit jobs, obtain resources, inspect status, and recover from failures. Typical deliverables include job platforms, scheduling and quotas, container management, monitoring, and fault handling. Backend and cloud-platform engineers often have transferable experience.

AI jobs have distinct constraints. Synchronous training often needs a group of processes to obtain GPUs together. Gang scheduling tries to make the group runnable together so that some processes do not hold resources while waiting indefinitely for the rest. Quota admission, node placement, and readiness of every worker still need separate checks. GPU, NIC, and network topology affect communication speed. Shared clusters also need quotas, priorities, and isolation. A GPU may be idle while a job remains pending because resources are fragmented or its constraints cannot be met. [Kubernetes scheduling](https://kubernetes.io/docs/concepts/scheduling-eviction/kube-scheduler/) · [Kueue all-or-nothing scheduling](https://kueue.sigs.k8s.io/docs/concepts/all_or_nothing/)

Industrial teams consider scheduling and reliability together. Meta’s cluster article discusses topology-aware placement and GPU fault detection. Krea describes sharing a GPU pool between training and production inference, including borrowing and returning capacity and moving inference workloads. Newcomers should first understand the relationship between resources, jobs, and failures; scale-specific details can come later. [Meta GenAI Infrastructure](https://engineering.fb.com/2024/03/12/data-center-engineering/building-metas-genai-infrastructure/) · [Krea 2 technical report](https://www.krea.ai/blog/krea-2-technical-report)

Another entry point is **compute onboarding and acceptance testing**. When a new accelerator is introduced, the platform must identify its capabilities, make it schedulable, run benchmarks, and bring faults and performance variation into monitoring. A Baidu IaaS internship description calls out GPU and RDMA admission, capability discovery, benchmarking, device plugins, networking, storage, capacity, and cost management. Backend engineers can start with this concrete path. High-performance networking and storage also form specialized roles focused on communication latency, model and checkpoint mounts, and data loading. [Baidu IaaS internship JD](https://talent.baidu.com/jobs/detail/INTERN/520472fa-81c9-462f-b603-b1e7ec4763e7) · [Tencent high-performance networking role](https://careers.tencent.com/jobdesc.html?postId=2067452809405706240) · [Tencent AI Infra platform JD](https://careers.tencent.com/jobdesc.html?postId=2099328404741603328)

Another kind of platform serves research experiments. OpenAI’s research analytics role describes ingesting, storing, and querying metrics, samples, trajectories, and evaluation results from pretraining, post-training, and RL. Researchers use them to compare experiments and investigate anomalies. This work is closer to data systems and observability platforms: a newcomer could start by joining metrics to samples from a training run, handling duplicate writes, and building queries or visualizations. That opening is for experienced engineers; it illustrates the work, not a campus hiring bar. [OpenAI Research Analytics role](https://openai.com/careers/software-engineer-infrastructure-analytics-platform-san-francisco/)

### Translating Platform JDs into Project Evidence

A campus recruiting sample for ByteDance’s Volcano Engine Ark scheduler mentions Kubernetes, containers, heterogeneous resources, multi-tenancy, networking, and training/inference workloads. [Reposted JD](https://www.jdwatch.work/jobs/jyxxg89e1) The keywords below map to evidence a candidate could demonstrate. Combine a few related items into one project.

- **Kubernetes and distributed systems:** Implement a training-job controller that creates workers, updates status, stops jobs, and releases resources. Repeated submissions and controller restarts should not create duplicate jobs or leak resources.
- **Docker / Containerd and runtime environments:** Package a training or inference program in a container, including image dependencies, model files, mounts, and startup checks. When the GPU is unavailable or permissions or versions are wrong, locate the failing layer.
- **Scheduling, quotas, priorities, and multi-tenancy:** Use Kueue or a similar project to let two user groups share GPUs. Observe how large jobs, small jobs, and high-priority jobs compete; record why a job waits, how much quota it holds, and when resources are returned.
- **Distributed training and gang scheduling:** Integrate a multi-process training job and observe cases where quota is admitted but nodes cannot fit the workers, a worker never becomes ready, or one exits. Show how the job waits, times out, or requeues, and how failures reach the other processes.
- **Heterogeneous compute, GPUs / CPUs, and device management:** Let a job select a node by device type and count, and report when no suitable node exists. Start with a complete request, allocation, and release path for one device type.
- **Compute admission, benchmarking, and observability:** For one new device configuration, record discovery, startup, and benchmark results. Distinguish environment failures from performance regressions, and connect the results to job logs or monitoring so schedulers and capacity planners can use them.
- **Cloud storage, VPC / RDMA, and multi-cluster systems:** Add data mounts and checkpoint uploads to the job platform, recording load time and failure causes. Then distinguish service networking from the needs of training communication. Building an RDMA network or cross-region scheduler is beyond an entry-level project.
- **Training and online inference reliability:** Connect a model artifact from training to an inference service, then simulate a process failure. Record the different states of a batch job and a long-running service, and clarify which state the platform recovers versus what the framework must save.

**A minimum portfolio project for applying:** a job path that can be submitted, scheduled, run, diagnosed, and cleaned up, with one module—such as a controller, queue, or resource manager—owned in depth and failure/recovery evidence recorded. Extend into heterogeneous devices, RDMA, or multiple clusters when target JDs call for them.

### How Deep to Learn

Moon Uncle suggests spending **about 80% of platform preparation on scheduling, containers, fault tolerance, and Kubernetes, and about 20% on the AI development workflow**. Treat this as a way to prioritize, not a universal ratio. The platform role’s depth comes from systems you build and maintain; model knowledge helps you reason about the workloads those systems serve.

#### The 80%: Learn Enough Systems Engineering to Design a Platform

Linux, networking, and distributed systems are the foundation. Connect process, memory, file, and network behavior to a running job. Connect container images, isolation, resource limits, and mounts to runtime delivery. In Kubernetes, understand how declarative state, controllers, the scheduler, and node-level container startup work together. GPU jobs also involve device plugins, drivers, and model loading. Backend and operations engineers can enter through these adjacent components and then add model-runtime knowledge. [Networking engineer’s transition discussion](https://www.reddit.com/r/kubernetes/comments/1tejfyz/interview_prep_for_ai_infra_role/)

Scheduling centers on queues, quotas, fairness, priorities, gang admission, and placement. Test your understanding with concrete questions: Why is a job pending when the cluster has free GPUs? If a high-priority job preempts another, how does the displaced job recover? Which processes must be ready for multi-node training? Does higher utilization also make jobs finish sooner? You understand scheduling when you can explain its rules in terms of actual workloads.

Learn fault tolerance through job state. What state remains after a process exits, a node disconnects, a controller restarts, or a submission is repeated? Who retries, cleans up, and releases resources? Which operations must be idempotent? Distinguish restarting a process from resuming training from a checkpoint: the latter depends on saved model, optimizer, and other training state. Know where the platform’s responsibility ends and the framework’s begins.

**Understanding how a training/inference platform is built** means being able to map the path from submission onward: API and permissions, job state, queues and scheduling, runtime, data and model artifacts, logs and metrics, and recovery. Place training checkpoint/restart and inference rollout, autoscaling, and rollback on this map. In an open-source project, go deep on one path—such as a controller, scheduling policy, or resource manager—instead of building an entire platform.

#### The 20%: Run an AI Pipeline to Understand Its Workloads

An AI pipeline spans data preparation, training or fine-tuning, evaluation, model saving, deployment, and serving. Run a manageable model through this workflow to see what each stage needs and produces. Data processing consumes CPU, memory, and storage; training depends on GPUs and communication; deployment involves model loading and startup time; serving needs APIs, monitoring, and version management.

Having run the pipeline helps you ask useful system-design questions: Does training need checkpoint recovery? How large is the model artifact, and where does it load from? How long until the service is ready? Can preprocessing starve the GPUs? These constraints turn “build a platform for model teams” into specific system requirements.

Learn the basics of Transformers well enough to draw the structure and follow tensor shapes: tokens enter embeddings, attention and feed-forward layers process tensors, backpropagation updates parameters during training, and inference uses prior context to generate output. For a platform role, you do not need to write an attention kernel immediately, but you should understand why batch size, sequence length, and model size change memory use and execution time.

#### Connect the Pieces Through Industry Engineering Blogs

When reading Meta or Krea engineering articles, extract the problem, constraints, and decision: Why did the workload need that scheduler? How was a failure detected? Where did the platform and framework divide responsibility? Under what pressure did the design become more complex? Map those answers onto a platform component you know. This builds system-design depth instead of a list of component names.

Keep the scope to one job type and one platform module. Place pending jobs, startup failures, and recovery on the boundary between scheduler, runtime, and framework; when operating conditions change, predict which component is affected. Model fundamentals clarify workload constraints. Expand into cross-cluster strategies when real problems call for them.

## Track 2: AI Framework Engineer (Algorithms and Systems)

Framework engineers connect models to execution systems. Training roles focus on parameter updates, cross-GPU synchronization, and recovery. Inference roles focus on batching requests, using memory, and returning results. Both share foundations in PyTorch, Transformers, and GPUs, but choosing one main track makes it easier to build depth.

### Training Frameworks: Memory, Parallelism, and Communication

Training memory includes weights, gradients, optimizer states, and activations. With data parallelism (DDP), each GPU keeps a model replica, processes different data, and synchronizes gradients. DeepSpeed ZeRO partitions training state in stages. PyTorch FSDP reduces memory pressure through sharding and on-demand parameter gathering. Each approach trades memory use against communication. [DeepSpeed ZeRO](https://www.deepspeed.ai/tutorials/zero/) · [PyTorch FSDP design](https://pytorch.org/blog/introducing-pytorch-fully-sharded-data-parallel-api/)

Tensor parallelism splits a layer’s computation across GPUs; pipeline parallelism places different layers on different devices. Long context and mixture-of-experts models introduce other forms of parallelism. Start with data, tensor, and pipeline parallelism, and understand how collectives such as All-Reduce support computation. Megatron shows how these strategies combine; PyTorch Distributed and TorchTitan provide a native PyTorch path. Hugging Face’s Ultra-Scale Playbook is a useful map. [Megatron parallelism guide](https://docs.nvidia.com/megatron-core/developer-guide/latest/user-guide/parallelism-guide.html) · [Ultra-Scale Playbook](https://huggingface.co/spaces/nanotron/ultrascale-playbook)

Training efficiency also depends on data loading, mixed precision, activation recomputation, and checkpoints. Recomputation trades extra compute for memory; checkpoints save the state needed to resume training; `torch.compile` captures and compiles computation graphs. These solve different problems and should be understood in the context of the training path. PyTorch’s checkpointing and FSDP2 articles, along with the MegaScale production paper, connect the concepts to practice. [Distributed Checkpointing](https://pytorch.org/blog/performant-distributed-checkpointing/) · [FSDP2 and Float8 training](https://pytorch.org/blog/training-using-float8-fsdp2/) · [MegaScale](https://www.usenix.org/system/files/nsdi24-jiang-ziheng.pdf)

RL post-training also coordinates sample generation, reward computation, parameter updates, and weight synchronization. First understand the inputs, outputs, and resource needs of these stages; then study more complex orchestration. Netflix and slime provide public engineering references. [Netflix post-training platform](https://medium.com/netflix-techblog/scaling-llm-post-training-at-netflix-0046f8790194) · [slime design blog](https://www.lmsys.org/blog/2025-07-09-slime/)

Recent RL Infra roles list coordination among training, inference, environments, and rewards as a distinct responsibility. The environment produces interactive tasks and feedback, the inference engine generates trajectories, and the trainer updates the model. A Baidu campus JD mentions asynchronous training, KV Cache reuse, and training/inference consistency. This work crosses training and inference, so it is a specialization to explore after building depth in one of them. Another less visible direction is **framework engineering productivity**: hardware compatibility, build and installation workflows, and continuous integration/evaluation (CI/CE) that prevent functional and performance regressions. [Baidu RL Infra campus JD](https://talent.baidu.com/jobs/detail/GRADUATE/9c20ea8d-db12-4bea-8c69-292391ba31d4) · [Baidu training Infra campus JD](https://talent.baidu.com/jobs/detail/GRADUATE/dc2ffe50-f9ff-4907-bf2b-d5e83cf7db5e)

#### Translating Training JDs into Project Evidence

A Tencent training-framework JD mentions Megatron, DeepSpeed, and FSDP, along with data loading, memory, communication, parallelism, and RL post-training. [Official JD](https://careers.tencent.com/jobdesc.html?postId=2072330929078190080) Its large-scale responsibilities are not an entry-level bar; a newcomer can build evidence in one of these modules at small scale.

- **PyTorch, models, and algorithm implementation:** Integrate a model or loss function into an existing training loop. Check tensor shapes, gradients, and training curves, and preserve evidence of interface integration and correctness.
- **Megatron / DeepSpeed / FSDP and distributed training:** Choose one implementation and trace how parameters, gradients, and optimizer state are distributed and when communication occurs. Compare DDP with one sharded approach on the same small model; record memory, step time, and configuration, and explain from the execution path what memory was saved and what communication was added.
- **Memory optimization, mixed precision, and recomputation:** Run controlled experiments that enable one technique at a time. Record peak memory, step time, and loss, and explain which setting made the model fit and which actually improved speed.
- **Data loading and end-to-end training performance:** Adjust the DataLoader, variable-length batching, or preprocessing path, and use a timeline to check GPU idle time. Under the same training conditions, show that the data supply improved and explain whether sample order or semantics changed.
- **Communication, parallel strategies, and NCCL:** Capture a multi-GPU task’s compute and communication timeline, locate synchronization waits, and try an existing overlap or bucketing configuration. Show the change in wait time; rewriting a communication library is not required.
- **Checkpoints, stability, and recovery:** Interrupt and resume a training run, then compare it with uninterrupted training. List which model, optimizer, random-number, and data-progress states were saved, and explain when resumption is only approximate.
- **PPO / GRPO, Verl / ROLL / AReal, and post-training integration:** Choose one method and framework; follow generation, reward, update, and weight synchronization. Add a reward function or model interface, then inspect output format, valid-token masks, and training inputs along the sample path. Finish a bounded integration before tackling complex algorithms or orchestration.
- **Framework compatibility, CI/CE, and performance regression:** Reproduce a hardware or environment compatibility problem in an existing training framework, or add a fixed-workload performance check. Record the failure condition, fix scope, and regression result.
- **Compilation and `torch.compile`:** This is another common framework-JD thread. Find a graph break in a model submodule or compare eager and compiled execution. Separate first-run compilation cost from steady-state time and check numerical results across multiple input shapes. [PyTorch compile tutorial](https://docs.pytorch.org/tutorials/intermediate/torch_compile_tutorial)

**A minimum portfolio project for applying:** run one distributed-training strategy, trace its key source path, and complete one diagnosis or change backed by comparative measurements of memory, time, and training results. Explore post-training, compilation, and additional parallel strategies when target JDs call for them.

#### How Deep to Learn

Most of the work should focus on model execution and framework implementation. Understand a training loop: the forward pass produces outputs and loss, backpropagation computes gradients, and the optimizer updates parameters. Explain what batch size, learning rate, gradient accumulation, and mixed precision change. To analyze distributed training, understand how gradients move through the computation graph and why intermediate activations consume memory.

Choose PyTorch Distributed/TorchTitan, DeepSpeed, or Megatron as a source-reading path. For DDP, understand the relationship between model replicas, data partitioning, and gradient synchronization. For FSDP/ZeRO, trace which state is sharded, when parameters are gathered, and what communication is added for memory savings. First be able to draw how tensor and pipeline parallelism distribute computation across GPUs and explain communication points and pipeline bubbles; then go deeper into implementation as the target role requires.

Put data, compute, and communication on one timeline when analyzing training performance. Estimate major memory costs. Explain why adding GPUs may not produce proportional speedup, and determine whether the bottleneck is data supply, compute, synchronization, or a straggling device. For checkpoints, know what state is saved and how training resumes. When using a framework, distinguish configuration, model, and environment failures.

Use the Ultra-Scale Playbook for an overview, and FSDP, checkpointing, and MegaScale articles to understand specific tradeoffs. For each optimization, ask what cost it removes, what cost it adds, and how to verify that training remains correct. Roles focused on post-training should add sample generation, reward computation, updates, and weight synchronization, first at the workflow and interface level.

An InfoQ practitioner interview notes that interrupted training, abnormal loss, and startup failures can originate in hardware, data, algorithms, frameworks, or the environment. Follow logs, metrics, and timelines to identify the failing layer before narrowing down the cause. Performance problems can also combine data starvation and communication waits. [AI Infra field interview](https://www.infoq.cn/article/edwy1v3xy14pgkefdv1u)

Limit the initial scope to one model and one parallelism implementation. Understand the tradeoffs in mixed precision and recomputation. Study FP8, complex multi-dimensional parallelism, and large-scale RL when a target role requires them. Those are extensions, not prerequisites for every training-framework candidate.

### Inference Frameworks: Requests, Caches, and Latency

Inference first processes the input context, called Prefill, then generates output one token at a time, called Decode. The KV Cache stores intermediate attention state from prior tokens to avoid recomputing it, while consuming more memory as sequence length and concurrency grow. The inference engine schedules requests under these constraints.

Continuous batching lets requests join and leave between generation steps. Chunked Prefill reduces interference from long inputs; paged KV management improves memory allocation; prefix caching reuses shared context. These affect time to first token, inter-token latency, and throughput. Anyscale explains why batching matters, vLLM connects the scheduler, KV manager, and GPU workers, and SGLang shows how caching and scheduling work together. [Continuous batching](https://www.anyscale.com/blog/continuous-batching-llm-inference) · [Inside vLLM](https://vllm.ai/blog/2025-09-05-anatomy-of-vllm) · [SGLang / RadixAttention](https://www.lmsys.org/blog/2024-01-17-sglang/)

Production serving also involves quantization, replicas, routing, monitoring, and autoscaling. The vLLM Production Stack is a deployment reference. An Anyscale/Google optimization shows that bottlenecks can also occur in routing and response forwarding. Evaluate an optimization alongside model quality, input/output lengths, concurrency, and hardware. [Production Stack](https://docs.vllm.ai/en/latest/deployment/integrations/production-stack/) · [Ray Serve LLM performance analysis](https://www.anyscale.com/blog/high-performance-distributed-inference-ray-serve-llm-vllm-google-kubernetes-gke)

**Cache transfer and disaggregated serving** are another set of real engineering problems. When Prefill and Decode run on separate instances, how does request state and KV Cache move? Can the cache pool be reused? Does network cost erase the benefit? A Baidu inference-base campus JD lists disaggregated deployment, cache pooling, and transfer optimization. This work sits between inference engines, distributed storage, and service networking; the foundation is still understanding a single-machine request and cache path. [Baidu inference-base campus JD](https://talent.baidu.com/jobs/detail/GRADUATE/7753cdb4-70b0-462b-a634-ee53818c7c9a)

**Multimodal generation serving** is also a specialized inference opportunity. A miHoYo campus posting mentions text-to-image, video generation, and Diffusion Transformers; Alibaba’s ROCK team recruits inference-system engineers for multimodal understanding and generation. Prefill/Decode and KV Cache remain useful systems foundations, but image and video generation also depend on sampling steps, resolution, batching, intermediate state, image quality, and memory. Choose one workload and compare latency, throughput, and memory at a fixed quality target. Do not apply text-model tokens-per-second metrics directly. [miHoYo inference campus JD repost](https://www.nowcoder.com/feed/main/detail/b1606910d57d4cceb8bb4edae73fcbca) · [Alibaba ROCK careers](https://alibaba.github.io/ROCK/zh-Hans/careers/)

#### Translating Inference JDs into Project Evidence

A miHoYo inference-optimization campus JD covers highly available serving, concurrency, low latency, autoscaling, KV Cache, paged attention, speculative decoding, and LLM/Diffusion deployment. [Reposted JD with official application link](https://www.nowcoder.com/feed/main/detail/b1606910d57d4cceb8bb4edae73fcbca) These keywords describe different layers and should lead to focused project evidence.

- **High concurrency, low latency, and bottleneck analysis:** Deploy a streaming model service and load-test it with a mix of short and long requests. Locate where latency grows—in queueing, compute, or response forwarding—and preserve workload conditions and tail latency.
- **Inference-engine optimization and continuous batching:** Trace the vLLM or SGLang scheduling path and compare batching or chunked-Prefill configurations. Record how long requests affect short ones and how throughput and latency change together.
- **KV Cache and PagedAttention:** Follow block allocation and reclamation when requests finish, are cancelled, or run out of cache. Add a boundary-case fix or metric, verify resources are returned, and relate cache use to concurrency limits.
- **Speculative decoding:** Use an existing framework implementation to compare performance with and without speculation. Record draft-model overhead and acceptance rate, and explain why some models or workloads do not benefit.
- **Model deployment, compression, and quantization:** Compare a model in its original precision with one quantized version. Evaluate task quality, memory, and speed, and report whether the target GPU actually benefits.
- **Kubernetes / Docker / Ray, autoscaling, and availability:** Deploy with the Production Stack or Ray Serve, then observe replica restarts and changing traffic. Record routing, scale-up delay, and how deployment handles requests that are still generating.
- **Prefill/Decode disaggregation, cache pooling, and transfer:** Trace KV Cache creation, transfer, and release across instances. Record compute and network time separately, and identify the workloads that benefit from disaggregation.
- **LLMs / Diffusion / long sequences:** Choose one workload and understand its execution interface and main compute path. Adapt a model or analyze long-context capacity, including input shape, cache, and numerical checks. Different models have different bottlenecks; you do not need text, image, and video projects just to cover the keywords.
- **Open-source work and tooling:** Turn a reproduced deployment issue, model-compatibility problem, or missing performance metric into a PR. Include a minimal reproduction, rationale, and regression check. PR count is superficial; explain the code and maintainer feedback.

**A minimum portfolio project for applying:** follow a real request path in vLLM or SGLang through scheduling, caching, and execution. Make one reproducible performance or correctness change and show its effect on service metrics. Explore speculative decoding, quantization, or multi-node serving when target JDs call for them.

#### How Deep to Learn

Connect model structure, engine implementation, and serving metrics. Understand a Transformer forward pass well enough to follow tensor changes, explain Prefill versus Decode, describe what the KV Cache stores, and estimate memory for model weights and request caches. Understand the goals of model compression and quantization, their accuracy effects, and hardware support before choosing a deployment method.

A teaching implementation such as nano-vLLM can establish the basic structure. Then choose a request entry point, scheduler, KV manager, or model-execution path in vLLM or SGLang. Follow how a request enters a queue, obtains cache, joins a batch, emits tokens, finishes, and releases resources. Mixed request lengths, cache exhaustion, and cancellation reveal whether you understand runtime state.

Study the relationship between latency and throughput. Time to first token captures the wait before the response begins; inter-token latency captures generation pace; throughput depends on workload and concurrency. Record the model, precision, hardware, input/output lengths, and arrival pattern in a load test. Hold conditions constant when comparing changes, and check whether cache hits, warmup, or failed requests distort results. Explaining why a result changed matters more than reporting a peak tokens-per-second number.

Work with deployment as well: how a model loads, how a service exposes its API and streams output, which metrics it records, and how failures are diagnosed. Production Stack and Ray Serve help explain routing and management around an engine; Anyscale’s performance article helps identify bottlenecks outside the GPU. Build experience around one concrete model adaptation, cache/scheduling change, or diagnosis, and connect the code to measurements.

Check software versions, configuration, and test data when comparing performance. An InfoQ SGLang practitioner account notes that these differences can make results on the same hardware hard to reproduce. Understand the boundary between a single-machine engine and its serving layer: the engine schedules and executes requests; the service also handles routing, rollout, and failures. Explore multi-node Prefill/Decode disaggregation, cache pools, and device adaptation afterward.

Evaluation and deployment can also lead into engine work. In a career-change account, Zhuqiu describes moving from evaluation and deployment toward SGLang source code: measure a problem, trace it through the request path, then contribute a fix. This connects service experience with framework understanding. [Career-change account, repost with link to the original Zhihu post](https://jishuzhan.net/article/2099048899215020034)

## Track 3: Hardware–Software Co-Design Engineer

Hardware–software co-design maps model computation onto GPU/NPU execution. Common areas include kernels, compilers, and device adaptation. Newcomers can choose kernels or compilers as a main thread; chip architecture design is a more specialized role.

**Domestic accelerator adaptation** appears in AI Infra hiring and crosses all three tracks. The platform layer integrates device plugins, topology, and cluster acceptance. The framework layer makes models, operator calls, and training/inference paths work on a new backend. The co-design layer builds kernels, compilers, and communication libraries and optimizes for device characteristics. A Tencent inference-platform JD names Ascend, Hygon, and Iluvatar accelerators for cloud-native adaptation; Baidu Kunlunxin roles cover framework customization, compute libraries, and communication libraries. A newcomer can choose one layer and demonstrate compatibility or performance validation: explain what the existing implementation could not handle and how the change was verified. [Tencent AI Infra platform JD](https://careers.tencent.com/jobdesc.html?postId=2099328404741603328) · [Baidu Kunlunxin framework JD](https://talent.baidu.com/jobs/detail/SOCIAL/f59ecdc6-28f7-4c0d-8712-2aa204d7d83f) · [Baidu Kunlunxin compute-library JD](https://talent.baidu.com/jobs/detail/SOCIAL/d16b195d-394e-44e1-9612-38d351f3ffa2)

Kernel roles need C++, CUDA/Triton, parallel computing, and GPU memory hierarchy. Connect thread assignment, data movement and reuse, tiling, and fusion to actual computation. Compiler roles study how model graphs are transformed, how data layouts are selected, and how device code is generated. [CUDA Programming Guide](https://docs.nvidia.com/cuda/cuda-programming-guide/) · [Triton programming guide](https://triton-lang.org/main/programming-guide/chapter-1/introduction.html)

Industrial optimizations target a specific model, input shape, and device. The FlashAttention-3 article shows how attention uses hardware properties to reduce waits. It is a useful co-design reference; newcomers do not need to reproduce every technique. Performance analysis must distinguish compute limits, bandwidth limits, and launch overhead, then check whether a kernel improvement matters for the full model. [FlashAttention-3 design](https://tridao.me/blog/2024/flash3/) · [Nsight Compute Guide](https://docs.nvidia.com/nsight-compute/ProfilingGuide/index.html)

### Translating Kernel and Compiler JDs into Project Evidence

A Tencent kernel role mentions CUDA / CUTLASS / Triton, SMs / warps / memory hierarchy / occupancy, profiling, overlapping communication with compute, and framework collaboration. [Official JD](https://careers.tencent.com/jobdesc.html?postId=2072509101644103680) A newcomer can start with one kernel or compiler module; the entire expert-role scope is not a prerequisite.

- **CUDA / Triton and kernel development:** Implement or modify one Softmax, normalization, or reduction kernel. Compare it with PyTorch across shapes and precisions, and preserve boundary-case inputs and error measurements. [Triton tutorials](https://triton-lang.org/main/getting-started/tutorials/)
- **CUTLASS, matrix multiplication, and Tensor Cores:** Modify tiling or configuration in an existing GEMM example and compare performance for target shapes. Record alignment, precision, and hardware constraints; there is no need to build a full matrix-multiplication library from scratch.
- **SMs / warps, memory hierarchy, and occupancy:** Adjust block size, tiling, or data reuse for one kernel and explain the profile. Record registers, shared memory, and execution time; higher occupancy alone does not prove a kernel is faster.
- **Nsight, profiling, throughput / latency / memory:** Use a system timeline to locate a real model hotspot, then inspect kernel memory and execution metrics. Report both kernel and end-to-end model time after optimization, and check whether other stages erase the gain.
- **Kernel fusion, memory traffic, and launch overhead:** Fuse two adjacent elementwise operations. Compare small and large inputs, validate broadcasting, precision, and boundaries, and show which memory accesses were removed and where gains disappear.
- **Communication kernels and compute/communication overlap:** If multi-GPU hardware is available, analyze overlap in a training timeline and modify one existing scheduling configuration. This is an advanced project; writing NCCL kernels is not an entry-level requirement.
- **Framework integration and model-team collaboration:** Integrate a kernel into a PyTorch model and validate the model output. A training kernel also needs a backward implementation; check `torch.compile` compatibility if compilation is involved. [PyTorch custom operators](https://docs.pytorch.org/tutorials/advanced/custom_ops_landing_page.html)
- **GPU / NPU backend adaptation:** Choose a model subgraph or kernel and identify an unsupported operation, precision, or layout in an existing backend. Implement one missing path and validate numerical results, performance, and supported device scope.
- **Compilers, graph optimization, code generation, and device support:** Choose one graph fusion, layout transformation, or backend adaptation. Show the graph and generated code before and after, then check semantics and performance. Demonstrate how one transformation reaches device execution; building a full compiler from scratch is unnecessary.

**A minimum portfolio project for applying:** one kernel or compiler change integrated into a real model, with numerical correctness and both module-level and end-to-end performance results. Explore communication kernels and multi-device backends when target JDs call for them.

### How Deep to Learn

Kernel work centers on C++, GPU execution and memory models, and CUDA/Triton. Explain how threads and warps divide work; how registers, shared memory, and global memory hold data; why tiling increases reuse; and why fusion reduces intermediate reads and writes. Tie each idea to a real operator. Model structure helps identify what the operator does and which input shapes are worth optimizing.

Performance analysis must account for both correctness and cost. Establish a reference implementation and an error tolerance, then inspect compute time, memory traffic, and resource use. Propose a bottleneck from the profile and test it with a measured change. Do not infer the cause from one metric alone; warmup, asynchronous execution, and input size affect timing. Nsight guides and the FlashAttention article help develop this approach.

For compiler work, choose one graph optimization or code-generation mechanism. Understand its input graph, which semantics must be preserved, how layout or fusion changes execution, and what code is produced. `torch.compile` and Triton materials connect framework behavior to kernels. Build depth in one optimization or adaptation module before expanding to a complete compiler pipeline.

Kernel roles require understanding how shape, precision, layout, and hardware determine optimization opportunities. Compiler roles require understanding semantic constraints and generated code. A suitable depth boundary is one module whose principles and conditions of use you can explain independently. Complex communication kernels, the latest instruction pipelines, and chip design can follow in later work.

## Conclusion

Choose a clear main thread: cluster platforms go deep on jobs and resources; training frameworks on compute and synchronization; inference frameworks on requests and caches; hardware–software co-design on kernels and devices. Domestic accelerator adaptation, RL Infra, research analytics platforms, and multimodal serving cross these tracks. First decide which system layer you can own, then see what new problem current JDs place there.

**My forecast:** upcoming roles are likely to value three kinds of transferable experience: running the same model or job correctly across hardware and environments, backed by compatibility and performance data; finding end-to-end bottlenecks across training, inference, caches, and networking while accounting for quality, latency, and resource cost; and making training experiments, serving systems, and recovery reproducible, observable, and verifiable. This is an inference about skill direction from public role descriptions, not a forecast of hiring headcount. Build changes in one bounded module and preserve baselines, failure cases, and regression evidence. Update the tools and target skills as target teams publish new JDs.
