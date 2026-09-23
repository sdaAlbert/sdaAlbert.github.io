---
title: "Agent 调用模型时为什么会慢？从一次请求一瞥 AI Infra"
date: 2026-09-23
permalink: /posts/agent-inference-lifecycle/
lang: zh-CN
translations:
  zh: /posts/agent-inference-lifecycle/
  en: /posts/agent-inference-lifecycle/en/
author_profile: false
read_time: true
excerpt: "沿着一次 Agent 模型请求，理解排队、输入处理、生成与多 GPU 部署中的推理基础设施设计。"
tags:
  - LLM Agents
  - AI Infrastructure
---

# Agent 调用模型时为什么会慢？从一次请求一瞥 AI Infra

一个 Agent 接到任务后，可能先让模型决定调用什么工具，拿到工具结果后再问模型下一步。一项任务会产生多次模型请求，所以用户感到“Agent 很慢”时，时间可能花在请求排队、模型处理输入、生成回答，或工具执行上。沿着这些耗时环节往下看，就能理解推理基础设施（AI Infra）怎样安排请求、使用计算和显存，以及开源系统为什么采用不同的设计。

## 1. 先确定时间花在哪里

一次模型请求大致经过这些步骤：

```text
等待计算资源 → 处理输入 → 逐个生成 token → 返回结果
```

请求到达后，模型服务先安排 GPU 计算资源。轮到这个请求时，模型处理整段提示词，建立后续生成所需的中间状态，这叫 prefill（预填充）。随后进入 decode（解码）：模型根据已有内容生成下一个 token，再把它加入上下文，继续生成下一个。流式接口会把已生成的内容陆续发给客户端。

先记录三个时间：**排队时间**，从请求到达服务到开始计算；**首 token 延迟**（TTFT），从发出请求到收到第一个 token；**输出 token 间隔**（TPOT），开始回答后相邻 token 到达的时间。TTFT 包含排队、prefill 和生成首个 token 等开销。对 Agent，还要记录工具耗时与整项任务耗时，才能看到多轮请求如何累积。

后文将沿着一条线索展开：排队变长，先看服务怎样安排并发；排队不长但 TTFT 高，检查输入处理；首 token 来得快而后续慢，再看生成阶段。

## 2. 排队变长：怎样让一张 GPU 接住更多请求？

服务端可以让 GPU 一次处理多个请求，这叫 batching（批处理）。同一批里的请求长短不一：有些只需生成几个 token，有些会持续生成很久。如果必须等整批结束才能安排下一批，已完成请求腾出的计算位置就无法及时交给队列里的新请求。

Orca 的观察是：生成一个回答要反复执行模型，每一步只产生下一个 token，调度器没有必要等整个回答结束才重新安排请求。假设同批有 A、B 两个请求，A 在第十步结束，B 还要生成一百步。按整条请求固定批次，A 退出后留下的位置不能及时交给新请求 C；Orca 每执行一步便重新决定下一批成员，A 可以立刻返回，C 也能加入。后来常说的 continuous batching（连续批处理），可以先按这个动态进出批次的过程来理解。[Orca 论文](https://www.usenix.org/conference/osdi22/presentation/yu)

但允许请求随时进出后，同批请求的上下文长度各不相同，不能把所有操作都塞进同一个规则形状的张量。Orca 因此提出 selective batching（选择性批处理）：把适合合并的计算一起执行，依赖各自上下文的注意力计算则分别处理。逐步调度回答“下一步轮到谁”，选择性批处理回答“长短不同的请求如何一起算”。两者共同使动态批处理可行，代价是调度与执行要更紧密地协作。

批次即使安排得更灵活，也要先让每个请求的中间状态装得下。调度能决定谁进入下一步，却不能解决显存空间不足；这正是下一节的问题。

观察这类优化，要同时看排队时间和 TPOT。批次变大，单位时间完成的工作可能增加，每个请求生成下一个 token 却也可能要等更久。系统追求的是在延迟要求内完成的请求量，而非单独把并发数调到最大。

## 3. 并发加不上去：显存被什么占着？

模型权重先占用一部分 GPU 显存，每个运行中的请求还要保存 KV cache（键值缓存）。这是 prefill 和后续生成过程中留下的中间状态；生成新 token 时，模型可以使用这些状态，无需重新处理整个前文。上下文越长、同时运行的请求越多，缓存通常越大。显存不足时，即使 GPU 还有计算余力，也无法继续接纳请求。

Orca 让请求更灵活地进出批次，接下来就要让显存容得下这些请求。[PagedAttention 论文](https://arxiv.org/abs/2309.06180) 指出，KV cache 大小随着输入和输出增长，服务却不知道请求最后会生成多长。若按可能达到的最大长度预留一大块连续空间，短回答用不完的部分会闲置；若不断为不同长度的请求分配、释放空间，还会留下碎片。于是“可运行的批次”常常先被显存管理方式限制，而不是先被计算能力限制。

vLLM 的做法近似操作系统的分页：把 KV cache 切成固定大小的块，请求增长时才取得下一块，用映射表记录“逻辑上的第几块”实际放在显存哪里。一个请求的上下文在逻辑上连续，物理块却不必挨在一起；相关序列还可以共享已有的块。这样既减少了提前预留的浪费，也降低了碎片对批次大小的限制。块的管理和非连续读取本身有开销，最后一个块也可能没装满，所以收益仍取决于请求长度和并发分布。

这也解释了为什么仅凭“模型能装进 GPU”还不能判断服务容量。模型权重装下以后，还要留空间给不同长度、不同并发量的请求。实验里应同时记录并发数、显存占用、排队时间和 TPOT，找出容量开始恶化的位置。

## 4. 排队不长，首 token 仍来得慢：输入能少读一次吗？

一项 Agent 任务的多轮请求，可能都携带相同的系统指令、工具定义和部分历史消息，只有新问题或工具结果发生变化。如果模型每轮都重新处理这段相同的开头，prefill 就会重复做工；排队时间不长，TTFT 仍可能居高不下。

前缀缓存复用相同开头已计算出的 KV cache。以 vLLM 的[自动前缀缓存](https://docs.vllm.ai/en/latest/features/automatic_prefix_caching.html)为例，请求到来时查找已有的相同前缀块，命中部分无需重新 prefill；新加入的内容仍要计算，回答也仍需逐个 token 生成。缓存因而主要改善重复长输入的 TTFT，不能直接缩短长回答的 decode。

[SGLang 论文](https://arxiv.org/abs/2312.07104) 把视角从单次请求移到“由多次生成组成的程序”。例如 Agent 先生成计划，再沿同一段上下文探索两个方案：这些调用有先后、分支和共同前缀。SGLang 的前端提供生成、扩展提示词、分叉与合并等操作，让这种关系在程序里表达出来；运行时的 RadixAttention 则把已算过的 KV cache 留在前缀树中。下一次调用先匹配最长共同前缀，复用对应缓存；树上的分支可共享共同部分，空间紧张时再按缓存策略回收。它在前缀确实重复时减少 prefill，也可能腾出显存容纳更多请求。

论文还处理结构化输出的另一种浪费：生成 JSON 等受格式约束的内容时，有些连续 token 已被语法唯一确定，逐个运行模型没有必要。SGLang 用压缩的有限状态机识别这类片段，尽可能一次生成多个确定的 token。对只能通过 API 使用的模型，论文还提出提前多生成、在后续调用中尝试复用的办法。这样看，SGLang 的核心是让多轮程序的结构变成执行优化的线索；前缀树只是其中一项机制。对本文关注的前缀缓存，稳定内容放前面、变化内容放后面更容易命中，但收益仍要看重复程度和缓存是否还在。

## 5. 第一个 token 很快，后面却慢：生成阶段在争什么？

上一节的结构化输出有些 token 可以跳过逐个预测；普通开放式回答仍要在得到上一个 token 后，才能预测下一个。每一步都要读取模型权重，并读取该请求已有上下文的 KV cache；相对于读取的数据，单个请求这一步的计算量通常不大，因此小批次 decode 往往受显存带宽限制。把多个请求合成一批，可以让一次权重读取服务更多请求，但批次越大，需读取的 KV cache 也越多，每一步可能更久，TPOT 未必继续改善。长回答还会持续占用批次位置和缓存，影响后来请求的排队。

一种办法是让每一步更快。长上下文、小批次时，生成阶段的注意力计算要读很长的 KV cache，却可能因为可并行的请求太少而用不满 GPU。[Flash-Decoding](https://crfm.stanford.edu/2023/10/12/flashdecoding.html) 把缓存沿上下文切成多段，并行计算各段的注意力，再合并结果。它缩短的是单步计算，不会减少生成所需的顺序步骤；上下文不长或瓶颈不在注意力时，收益也会不同。[FlashInfer](https://arxiv.org/abs/2501.01005) 则把不同 KV 布局和请求形态下的高效注意力计算做成可复用算子，供 vLLM、SGLang 等服务系统使用。

另一种办法是让大模型少执行几次顺序步骤。[推测解码](https://proceedings.mlr.press/v202/leviathan23a.html) 先让较便宜的草稿模型猜出若干 token，再由目标模型一次验证这些候选；按论文的接受与修正方法，输出仍服从目标模型原有的分布。[EAGLE](https://arxiv.org/abs/2401.15077) 进一步改进候选的生成方式。这里的收益取决于候选被接受的长度，以及草稿和验证额外花了多少时间：猜不中或额外开销太高，反而可能不划算。

因此，先比较不同并发、上下文长度和输出长度下的 TPOT。长上下文下单步注意力慢，可以考虑算子优化；顺序生成次数占主导，再看推测解码的接受率和实际延迟。若 TPOT 稳定，只是答案太长，就减少无用输出。吞吐量与单请求延迟仍要一起衡量。

流式返回可以更早显示已生成的内容，适合改善等待体验；它不会让模型少生成 token，也不会自动降低 TPOT。

## 6. 单机已经到上限：增加 GPU 后怎样分工？

先判断上限来自哪里。模型本身放不进一张 GPU，可以把模型的计算拆到多张卡，这叫模型并行：张量并行拆分同一层的计算，流水线并行把不同层放在不同卡上。它们都要跨卡传数据，增加 GPU 不保证单个请求更快。模型能放下，但请求量持续超过单机容量，则可以运行多个模型副本，把不同请求分给不同副本；这又需要路由、扩缩容和健康检查。[vLLM 并行指南](https://docs.vllm.ai/en/v0.18.0/serving/parallelism_scaling/)

增加 GPU 前，还可以考虑减少每个请求占用的空间。[量化](https://docs.vllm.ai/en/stable/features/quantization/)用更低精度保存模型权重或 KV cache，可能腾出显存、减少读取的数据量；是否真的提速，要看硬件、算子支持和质量变化。它处理的是数据表示与容量，不代替前面讨论的调度和缓存复用。

多副本还会改变第四节的缓存收益。每个副本持有自己的 KV cache：Agent 下一轮请求若被送到另一台机器，即使前缀刚在原副本算过，也可能重新支付 prefill 成本。路由因此要权衡两件事：送到较空闲的副本，减少排队；送到已有相同前缀的副本，提高缓存命中。[Ray Serve LLM 的路由文档](https://docs.ray.io/en/latest/serve/llm/architecture/routing-policies.html) 给出具体策略：默认从两个候选副本中选较空闲的；前缀感知策略在负载接近时优先复用缓存，负载失衡时退回均衡分流。SGLang 论文也讨论了跨副本的前缀感知路由；Ray Serve LLM 展示的是可配置的服务层实现。它们都说明：扩成多个副本后，缓存命中不再只由副本内部决定。

扩大部署后，还可能发现两个阶段互相拖慢：一个长输入的 prefill 占用计算时，其他请求的 decode 要等下一个 token；若总优先保证 decode，新请求又要等更久才看到首个 token。先不拆机器，也可以用[分块 prefill](https://docs.vllm.ai/en/v0.21.0/configuration/optimization/)把长输入切成较小的计算段，与 decode 交错安排；这有助于控制输出间隔，但分块大小仍要在 TTFT 与 TPOT 之间权衡。

两阶段的计算特点和延迟目标不同，放在同一组 GPU 上也迫使它们共用资源配置。[DistServe 论文](https://www.usenix.org/system/files/osdi24-zhong-yinmin.pdf) 因此把 prefill 与 decode 放到不同 GPU 池，分别配置资源，并用“同时满足 TTFT、TPOT 要求的请求量”衡量效果。拆开后，前一阶段生成的 KV cache 必须传给后一阶段，网络带宽和部署位置便成为新约束。只有测出两阶段明显互相干扰、且传输成本可接受时，这种拆分才值得考虑。

## 7. 这些工作连起来，能说明什么？

这些工作针对不同瓶颈，并非一条必须依次升级的技术路线。请求排队、批次难以周转，Orca 从调度粒度入手；显存限制批次，PagedAttention 从 KV cache 分配入手；多轮程序反复使用相同前缀，SGLang 把调用结构与缓存复用联系起来；生成阶段还可缩短单步计算，或让大模型一次验证多个候选 token。扩成多副本时，路由又要权衡缓存与排队。DistServe 面对的是 prefill 和 decode 互相干扰、两项延迟目标难以同时满足的问题，用阶段拆分换取满足目标的有效吞吐，但也付出 KV cache 传输成本。

回到一次模型请求：排队、TTFT 和 TPOT 分别指向不同的约束。Agent 的重复前缀、输入长度波动和多轮调用，都会改变这些约束出现的概率，而ai infra则不断地想出克服他们的方法，榨干硬件能力，从而带给我们研究的价值和机会。

## 参考资料

- Yu et al., [Orca: A Distributed Serving System for Transformer-Based Generative Models](https://www.usenix.org/conference/osdi22/presentation/yu), OSDI 2022.
- Kwon et al., [Efficient Memory Management for Large Language Model Serving with PagedAttention](https://arxiv.org/abs/2309.06180), SOSP 2023.
- Zhong et al., [DistServe: Disaggregating Prefill and Decoding for Goodput-optimized LLM Serving](https://www.usenix.org/system/files/osdi24-zhong-yinmin.pdf), OSDI 2024.
- Zheng et al., [SGLang: Efficient Execution of Structured Language Model Programs](https://arxiv.org/abs/2312.07104).
- Leviathan et al., [Fast Inference from Transformers via Speculative Decoding](https://proceedings.mlr.press/v202/leviathan23a.html), ICML 2023.
- [Flash-Decoding](https://crfm.stanford.edu/2023/10/12/flashdecoding.html) · [FlashInfer](https://arxiv.org/abs/2501.01005) · [EAGLE](https://arxiv.org/abs/2401.15077).
- [vLLM 自动前缀缓存](https://docs.vllm.ai/en/latest/features/automatic_prefix_caching/) · [Ray Serve LLM 请求路由](https://docs.ray.io/en/latest/serve/llm/architecture/routing-policies.html)
- [vLLM 量化](https://docs.vllm.ai/en/stable/features/quantization/) · [分块 prefill](https://docs.vllm.ai/en/v0.21.0/configuration/optimization/) · [多 GPU 并行](https://docs.vllm.ai/en/v0.18.0/serving/parallelism_scaling/)
