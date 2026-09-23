---
title: "Why Are Agent Model Calls Slow? A First Look at AI Infrastructure Through One Request"
date: 2026-09-23
permalink: /posts/agent-inference-lifecycle/en/
lang: en
translations:
  zh: /posts/agent-inference-lifecycle/
  en: /posts/agent-inference-lifecycle/en/
author_profile: false
read_time: true
excerpt: "Follow one Agent model request to understand queuing, input processing, generation, and inference design across multiple GPUs."
tags:
  - LLM Agents
  - AI Infrastructure
---

# Why Are Agent Model Calls Slow? A First Look at AI Infrastructure Through One Request

After receiving a task, an Agent may first ask a model which tool to call, then ask the model what to do next after getting the tool result. A single task can involve several model requests. So when users say an Agent feels slow, time may be spent waiting in a queue, processing the model input, generating the answer, or executing tools. Following these sources of delay helps explain how inference infrastructure (AI Infra) schedules requests and uses compute and memory—and why open-source systems make different design choices.

## 1. First, find out where the time goes

A model request roughly follows these steps:

```text
Wait for compute → Process the input → Generate tokens one by one → Return the result
```

When a request arrives, the model service first schedules GPU compute for it. Once its turn comes, the model processes the full prompt and builds intermediate state needed for generation. This is called prefill. Then comes decode: the model generates the next token from what it has so far, appends it to the context, and generates another. A streaming interface sends generated content to the client as it becomes available.

Start by recording three timings. **Queue time** is the time from request arrival until computation begins. **Time to first token (TTFT)** is the time from sending the request until receiving its first token. **Time per output token (TPOT)** is the interval between neighboring tokens once the answer has started. TTFT includes queuing, prefill, and the cost of generating the first token. For an Agent, also record tool time and total task time to see how multiple rounds add up.

The rest of this article follows one thread: when the queue grows, look at how the service schedules concurrency; when the queue is short but TTFT is high, inspect input processing; when the first token arrives quickly but later tokens are slow, look at generation.

## 2. When the queue grows: how can one GPU serve more requests?

A server can have a GPU process several requests at once. This is called batching. Requests in the same batch have different lengths: some need only a few tokens, while others keep generating for a long time. If the service must wait for the whole batch to finish before scheduling another one, it cannot promptly give a completed request's compute slot to a new request in the queue.

Orca's key observation was that generating an answer requires running the model repeatedly, one token at a time. The scheduler therefore need not wait for an entire answer to finish before rearranging requests. Suppose a batch contains requests A and B. A finishes after step ten, while B needs another hundred steps. With a fixed batch for each complete request, the slot freed by A cannot promptly go to a new request C. Orca instead chooses the batch members again at every step: A can return immediately, and C can join. This dynamic movement in and out of a batch is a useful way to understand what later became known as continuous batching. [Orca paper](https://www.usenix.org/conference/osdi22/presentation/yu)

But once requests can enter and leave at any time, requests in the same batch may have contexts of different lengths. Their operations cannot all be packed into one regular-shaped tensor. Orca therefore introduced selective batching: combine the computations that can be batched, while handling attention computations that depend on each request's own context separately. Step-by-step scheduling answers “who goes next?” Selective batching answers “how can requests of different lengths be computed together?” Together they make dynamic batching practical, at the cost of tighter coordination between scheduling and execution.

Even a more flexible batch must have room for each request's intermediate state. Scheduling can decide who takes the next step, but it cannot solve a shortage of GPU memory. That is the next problem.

To evaluate this kind of optimization, watch queue time and TPOT together. A larger batch may increase the amount of work completed per unit of time, but each request may also wait longer for its next token. The goal is not to maximize concurrency by itself; it is to complete as many requests as possible within latency requirements.

## 3. Concurrency will not grow: what is occupying GPU memory?

Model weights take up some GPU memory, and every active request also needs to keep a KV cache. The cache stores intermediate state from prefill and generation. When generating a new token, the model can reuse this state instead of processing the entire preceding context again. The longer the context and the more requests running at once, the larger the cache tends to be. If memory runs out, the service cannot accept more requests even if the GPU still has compute capacity.

Orca made it easier for requests to move in and out of a batch. The next challenge is fitting those requests in memory. The [PagedAttention paper](https://arxiv.org/abs/2309.06180) points out that KV cache grows with input and output, while the service does not know in advance how long a request will generate. Reserving one large, contiguous region for the maximum possible length leaves unused space for short answers. Repeatedly allocating and releasing space for requests of different lengths can also cause fragmentation. As a result, memory management can limit the size of a runnable batch before compute capacity does.

vLLM's approach resembles virtual memory paging in an operating system: it splits the KV cache into fixed-size blocks, allocates the next block only as a request grows, and uses a mapping table to track where each logical block resides in GPU memory. A request's context is logically contiguous, but its physical blocks need not be adjacent; related sequences can also share existing blocks. This reduces waste from reserving memory in advance and makes fragmentation less of a constraint on batch size. Block management and non-contiguous reads have their own costs, and the final block may not be full, so the benefit still depends on request lengths and concurrency patterns.

This is why “the model fits on the GPU” is not enough to tell you how much a service can handle. Once the weights are loaded, memory must still be available for requests of different lengths and concurrency levels. In experiments, track concurrency, memory use, queue time, and TPOT together to find where capacity starts to degrade.

## 4. The queue is short, but the first token is still slow: can the input be read less often?

Several rounds in one Agent task may carry the same system instructions, tool definitions, and part of the conversation history, while only the latest question or tool result changes. If the model processes the repeated opening again every round, prefill repeats the same work. TTFT can remain high even when queue time is short.

Prefix caching reuses the KV cache already computed for a matching opening. For example, with vLLM's [automatic prefix caching](https://docs.vllm.ai/en/latest/features/automatic_prefix_caching.html), an incoming request looks for existing blocks that match its prefix. The matching portion does not need to go through prefill again; new content still has to be processed, and the answer still has to be generated token by token. So caching mainly improves TTFT for repeated, long inputs; it does not directly shorten decode for a long answer.

The [SGLang paper](https://arxiv.org/abs/2312.07104) shifts the perspective from a single request to a “program made up of multiple generations.” For example, an Agent might generate a plan and then explore two options from the same context. These calls have ordering, branches, and shared prefixes. SGLang's frontend provides operations for generation, prompt extension, branching, and merging, so that these relationships can be expressed in the program. Its runtime's RadixAttention keeps computed KV cache in a prefix tree. A later call matches its longest shared prefix and reuses the corresponding cache; branches in the tree can share their common portions, and the cache can be reclaimed according to a policy when space is tight. When prefixes really do repeat, this reduces prefill and may free memory for more requests.

The paper also addresses another source of waste in structured output. When generating content constrained by a format such as JSON, grammar may uniquely determine some consecutive tokens, making it unnecessary to run the model for each one. SGLang uses a compressed finite-state machine to identify such spans and generate multiple determined tokens at once where possible. For models available only through an API, the paper also proposes generating extra tokens in advance and trying to reuse them in a later call. In this light, SGLang's central idea is to use the structure of a multi-step program as a clue for execution optimizations; the prefix tree is only one mechanism. For the prefix caching discussed here, putting stable content first and changing content later makes a cache hit more likely, though the benefit still depends on how much content repeats and whether it remains cached.

## 5. The first token is fast, but later ones are slow: what competes during generation?

Some tokens in the structured output discussed above can be generated without predicting each one. For an ordinary open-ended answer, however, the model must have the previous token before it can predict the next. At every step it reads model weights and the request's existing KV cache. Compared with the amount of data read, the computation for one request at that step is often modest, so decode with a small batch is often limited by memory bandwidth. Combining requests into a batch lets one read of the weights serve more requests. But larger batches also require reading more KV cache at each step, which may take longer; TPOT may stop improving. Long answers also occupy batch slots and cache for longer, affecting the queue for later requests.

One approach is to make each step faster. With a long context and a small batch, attention during generation must read a large KV cache, yet the GPU may be underused because there are too few requests to parallelize. [Flash-Decoding](https://crfm.stanford.edu/2023/10/12/flashdecoding.html) splits the cache along the context into chunks, computes attention for those chunks in parallel, and then combines the results. It shortens the computation for one step; it does not reduce the number of sequential steps required to generate an answer. Its gains also vary when the context is short or attention is not the bottleneck. [FlashInfer](https://arxiv.org/abs/2501.01005) packages efficient attention computation for different KV layouts and request patterns into reusable operators used by serving systems such as vLLM and SGLang.

Another approach is to make the large model perform fewer sequential steps. [Speculative decoding](https://proceedings.mlr.press/v202/leviathan23a.html) first asks a cheaper draft model to guess several tokens, then has the target model verify those candidates in one pass. With the paper's acceptance and correction method, the output still follows the target model's original distribution. [EAGLE](https://arxiv.org/abs/2401.15077) further improves how candidates are generated. The gain depends on how many candidate tokens are accepted and how much time drafting and verification add. If guesses are often rejected or the overhead is too high, this may not be worthwhile.

So first compare TPOT across different concurrency levels, context lengths, and output lengths. If attention is slow per step with long contexts, consider operator-level optimizations. If sequential generation dominates, examine speculative decoding's acceptance rate and actual latency. If TPOT is stable but answers are simply too long, remove unnecessary output. Throughput and per-request latency still need to be considered together.

Streaming can display generated content earlier and improve the waiting experience. It does not make the model generate fewer tokens or automatically lower TPOT.

## 6. One machine has reached its limit: how should more GPUs be divided up?

First identify what has reached its limit. If the model itself does not fit on one GPU, its computation can be split across multiple cards. This is called model parallelism: tensor parallelism splits computation within a layer, while pipeline parallelism places different layers on different cards. Both require data to move between cards, so adding GPUs does not guarantee a faster individual request. If the model fits but request volume consistently exceeds one machine's capacity, run multiple model replicas and route different requests to different replicas. This also requires routing, scaling, and health checks. [vLLM parallelism guide](https://docs.vllm.ai/en/v0.18.0/serving/parallelism_scaling/)

Before adding GPUs, you can also try reducing the space each request occupies. [Quantization](https://docs.vllm.ai/en/stable/features/quantization/) stores model weights or KV cache at lower precision, which may free memory and reduce the amount of data read. Whether it actually speeds things up depends on the hardware, operator support, and changes in model quality. It addresses data representation and capacity; it does not replace the scheduling and cache reuse discussed above.

Multiple replicas also change the benefits of caching from Section 4. Each replica has its own KV cache. If an Agent's next request goes to a different machine, it may have to pay the prefill cost again even if the prefix was just processed on the original replica. Routing must therefore balance two goals: send a request to a less busy replica to reduce queuing, or to one that already has the same prefix to increase cache hits. [Ray Serve LLM's routing documentation](https://docs.ray.io/en/latest/serve/llm/architecture/routing-policies.html) describes concrete policies: by default, choose the less busy one of two candidate replicas; with prefix-aware routing, prefer cache reuse when load is similar, and fall back to balanced routing when load is uneven. The SGLang paper also discusses prefix-aware routing across replicas; Ray Serve LLM shows a configurable implementation at the service layer. Both illustrate that, with multiple replicas, cache hits are no longer determined only within each replica.

At larger scale, the two phases may also slow each other down. A long prefill can occupy compute and make other requests' decode wait for their next token. If decode is always prioritized, new requests may wait longer to see their first token. Without splitting machines yet, [chunked prefill](https://docs.vllm.ai/en/v0.21.0/configuration/optimization/) can divide a long input into smaller compute chunks and interleave them with decode. This can help control output intervals, but chunk size still requires a trade-off between TTFT and TPOT.

The two phases have different compute characteristics and latency goals, yet putting them on the same GPU pool forces them to share resource settings. The [DistServe paper](https://www.usenix.org/system/files/osdi24-zhong-yinmin.pdf) therefore places prefill and decode in separate GPU pools and configures them independently. It measures how many requests can meet both TTFT and TPOT requirements. Once separated, the KV cache produced by prefill must be transferred to decode, making network bandwidth and placement new constraints. This split is worthwhile only when measurements show substantial interference between the phases and the transfer cost is acceptable.

## 7. What do these works tell us when viewed together?

These works target different bottlenecks; they are not steps on a single upgrade path that every system must follow. When requests queue and batches turn over slowly, Orca changes the scheduling granularity. When memory limits batch size, PagedAttention changes KV cache allocation. When multi-step programs reuse prefixes, SGLang connects program structure with cache reuse. Generation can also be improved by shortening each computation step or having the large model verify multiple candidate tokens at once. With multiple replicas, routing must balance cache reuse and queuing. DistServe addresses interference between prefill and decode, and the difficulty of meeting both latency targets at once: it trades phase separation for more useful throughput within those targets, while incurring the cost of transferring KV cache.

Back to a single model request: queue time, TTFT, and TPOT each point to a different constraint. Repeated prefixes, varying input lengths, and multiple rounds in an Agent change how often those constraints appear. AI infrastructure keeps finding ways to work around them and make better use of hardware—and that is where the questions and opportunities for further study lie.

## References

- Yu et al., [Orca: A Distributed Serving System for Transformer-Based Generative Models](https://www.usenix.org/conference/osdi22/presentation/yu), OSDI 2022.
- Kwon et al., [Efficient Memory Management for Large Language Model Serving with PagedAttention](https://arxiv.org/abs/2309.06180), SOSP 2023.
- Zhong et al., [DistServe: Disaggregating Prefill and Decoding for Goodput-optimized LLM Serving](https://www.usenix.org/system/files/osdi24-zhong-yinmin.pdf), OSDI 2024.
- Zheng et al., [SGLang: Efficient Execution of Structured Language Model Programs](https://arxiv.org/abs/2312.07104).
- Leviathan et al., [Fast Inference from Transformers via Speculative Decoding](https://proceedings.mlr.press/v202/leviathan23a.html), ICML 2023.
- [Flash-Decoding](https://crfm.stanford.edu/2023/10/12/flashdecoding.html) · [FlashInfer](https://arxiv.org/abs/2501.01005) · [EAGLE](https://arxiv.org/abs/2401.15077).
- [vLLM automatic prefix caching](https://docs.vllm.ai/en/latest/features/automatic_prefix_caching/) · [Ray Serve LLM request routing](https://docs.ray.io/en/latest/serve/llm/architecture/routing-policies.html)
- [vLLM quantization](https://docs.vllm.ai/en/stable/features/quantization/) · [Chunked prefill](https://docs.vllm.ai/en/v0.21.0/configuration/optimization/) · [Multi-GPU parallelism](https://docs.vllm.ai/en/v0.18.0/serving/parallelism_scaling/)
