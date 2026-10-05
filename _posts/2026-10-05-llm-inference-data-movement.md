---
title: "大模型推理中的数据搬运协调：研究切口"
date: 2026-10-05
permalink: /posts/llm-inference-data-movement/
lang: zh-CN
translations:
  zh: /posts/llm-inference-data-movement/
  en: /posts/llm-inference-data-movement/en/
author_profile: false
read_time: true
excerpt: "从权重、KV 与激活的数据路径，梳理放置、布局、时机、共享资源和多 GPU 协同，并结合 SGLang、Megatron Core 与 TensorRT-LLM 建立推理数据搬运研究地图。"
tags:
  - AI Infrastructure
  - LLM Inference
---

# 大模型推理中的数据搬运协调：研究切口

GPU 运行大模型时，计算要用的数据来自哪里搬到哪里？这是个值得研究的问题。搬运的位置和时间安排不合适，请求就会等数据；同时搬得太多，也可能占用计算所需的带宽或 GPU 资源。

## 1. 推理请求会读写哪些数据？

从模型执行内部的数据搬运看，大模型推理主要涉及三类数据：模型权重、KV Cache 和激活值。它们的用途、存放位置和搬运时机各不相同。[推理 I/O 综述，2026](https://link.springer.com/article/10.1007/s10462-026-11651-1)

权重是模型学习得到的参数；KV Cache 保存历史 token 在注意力计算中产生的键和值，避免生成时反复计算；激活值是模型各层产生的中间结果。token 是模型处理文本的基本单位，logits 是模型为候选 token 给出的分数。

服务边界还有输入与输出：输入 token ID 通常由服务层送入执行端；生成 token 或 logits 要返回服务层或交给采样组件，具体路径取决于采样放在哪里。本文正文聚焦文本模型，末尾简述图像、音频和视频输入带来的扩展问题。

| **数据**   | **处理输入时**                  | **逐 token 生成时**           | **存储与跨设备搬运**                                         | **生命周期与访问特点**                                       |
| ---------- | ------------------------------- | ----------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| 权重       | 各层读取                        | 每个生成步再次读取            | 启动时从存储加载到 GPU 显存；显存不足时可分层放在 CPU／SSD，按层或按块调入 GPU | 相对固定，后续计算会反复读取                                 |
| KV Cache   | 为输入 token 建立并写入         | 读取历史 K、V，追加当前 K、V  | 容量不足时换出到 CPU、SSD 或远端并在需要时恢复；输入处理与生成分离部署时传给生成阶段 | 随请求和上下文增长；也可选择重新计算对应前缀                 |
| 激活值     | 各层产生并传给后续计算          | 各层产生并传给后续计算        | 单卡时主要在 GPU 显存与片上存储之间流动；张量、流水线或专家并行时在设备间传递 | 由当前计算产生，通常短暂使用；分块和融合会影响写回、读回显存的次数 |
| 输入／输出 | 输入 token 或多模态张量送入模型 | logits／采样 token 返回服务层 | 通常在 CPU 与 GPU 之间传递；多模态输入可能较大               | 属于服务与模型执行之间的数据交换                             |

## 2. 数据经过哪些路径？

可以按数据跨越的硬件边界来看常见路径。HBM 是 GPU 常用的高带宽显存；缓存、共享内存和寄存器位于芯片内部，容量更小，供计算就近访问。GPU 内部路径会涉及这些存储层之间的读写，表中其他路径则主要涉及跨设备或存储传输。

| 路径 | 常见互联 | 推理中的例子 |
| --- | --- | --- |
| GPU 内部 | HBM、缓存、共享内存、寄存器 | 权重和 KV 被算子读取，激活在算子间传递 |
| CPU 与 GPU | 通常是 PCIe；Grace Hopper 等平台使用 NVLink-C2C | CPU 中的权重或 KV 搬入 GPU |
| 同机 GPU 之间 | NVLink 与 NVSwitch，也可能是 PCIe | 层内结果汇总、激活交接或 KV 传递 |
| 跨机器 GPU 之间 | 网卡（NIC）、交换设备与 InfiniBand 或 RoCE 网络 | 跨节点的 KV、激活或专家路由通信 |
| 存储与 GPU | NVMe 到主机再经 PCIe；支持时可用 GPUDirect Storage | SSD 中的权重或卸载 KV 读入 GPU |

InfiniBand 是数据中心常见的高速网络；RoCE 是在以太网上承载 RDMA 的方式。RDMA（远程直接内存访问）让网卡直接读写远端内存；GPUDirect RDMA 在受支持的硬件和拓扑上让 NIC 直接 DMA 到 GPU 内存，减少 CPU 内存中转。GPUDirect Storage（GDS）为存储设备到 GPU 提供类似的直接 DMA 路径。NVSwitch 用于连接 NVLink GPU；少数机架级系统还把 NVLink 扩展到多台机器。[NVIDIA NVLink／NVSwitch](https://docs.nvidia.com/hgx-platforms/fabric-manager-user-guide/index.html) [NVLink-C2C](https://docs.nvidia.com/dccpu/grace-perf-tuning-guide/) [GPUDirect RDMA](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/gpu-operator-rdma.html) [GPUDirect Storage](https://docs.nvidia.com/gpudirect-storage/)



## 3. 三类数据的搬运路径与问题切口

第二节列出的互联路径，在不同数据上承担不同任务。下面分别沿着这三类数据的路径看它们会遇到什么搬运问题。

### 权重：从存储加载，再进入每层计算

模型启动时，权重通常从 SSD 经主机内存和 PCIe 进入 GPU HBM；支持 GPUDirect Storage 的平台可以改变存储到 GPU 的中转方式。推理时，权重从 HBM 进入 GPU 的缓存、共享内存或寄存器供算子使用。若显存容不下模型，权重还可能留在 CPU 或 SSD，按层或按块调入。

```text
请求到达 → 进入执行队列 → 准备计算当前层
                              │
                              ├─ 权重已驻留：GPU HBM → 缓存／共享内存 → 计算单元
                              │
                              └─ 权重待加载：SSD → 主机内存 → PCIe → GPU HBM
                                                可提前加载       │
                                                               │ 当前层权重必须就绪
                                                               ▼
                                                        当前层计算 → 下一层

显存不足时，权重可按层／按块从 CPU 或 SSD 调入；当前层计算期间可搬下一层权重。
```

FlexGen 展示了 GPU、CPU、SSD 联合放置与调度的设计；这类方案首先解决容量和吞吐问题，在线低延迟还要单独评估。[FlexGen](https://arxiv.org/abs/2303.06865)

### KV Cache：随请求增长、复用和迁移

Prefill 是处理输入并建立 KV 的阶段；decode 是逐 token 生成的阶段，每一步读取历史 KV 并追加新状态。KV 通常在 GPU HBM 中建立。若缓存换出到 CPU、SSD 或远端，恢复就会沿第二节所列的 PCIe、存储或网络路径返回计算设备。prefill 与 decode 分离部署时，KV 还要从前一阶段所在的 GPU 或主机传到生成节点。

```text
请求到达 → 前缀匹配 → 等待执行机会
                   │
                   ├─ 显存命中：GPU HBM → GPU 内部层级 → 注意力计算
                   │
                   ├─ 外部命中：SSD／远端 → 主机内存 → PCIe／网络 → GPU HBM
                   │                         可提前读取             │
                   │                                                │ 对应 KV 必须就绪
                   │                                                ▼
                   └─ 未命中：重新计算前缀 → 建立 KV → decode

生成的新 KV 可后台换出：GPU HBM → PCIe／网络 → CPU、SSD 或远端缓存
分离部署时还需传递：prefill GPU／主机 → NVLink 或 NIC／网络 → decode GPU／主机
```

分层卸载和 HiCache 展示了缓存命中、恢复和部分复用的不同设计；相同的“缓存命中”可能经过显存、主机内存或网络，端到端成本并不相同。[vLLM 分层卸载设计](https://vllm.ai/blog/2026-09-10-tiered-kv-offloading) [Mooncake × HiCache 设计](https://kvcache-ai.github.io/Mooncake/design/hicache-design.html)

### 激活：在 GPU 内部流动，也可能跨卡传递

单卡执行时，激活由算子产生，通常经 GPU HBM、缓存和片上存储传给后续算子。算子分块与融合会改变中间数据写回 HBM 的次数。多卡执行时，张量并行可能在层内交换激活分片；流水线并行则在阶段边界把激活传给下一张 GPU，路径可能经过 NVLink／NVSwitch 或 PCIe。

```text
请求到达 → 输入送入 GPU → 执行当前层
                             │
                             ├─ 单卡：计算单元 ⇄ 片上存储 ⇄ HBM
                             │                         │
                             │                         │ 激活供下一算子使用
                             │                         ▼
                             │                    后续算子计算
                             │
                             ├─ 张量并行：GPU 0 ⇄ NVLink／NVSwitch／PCIe ⇄ GPU 1
                             │                         激活分片／层内结果
                             │
                             └─ 流水线并行：前一阶段 GPU → GPU 互联／网络 → 后一阶段 GPU
                                                            激活必须到达
```

FlashAttention 展示了减少注意力中间数据 HBM 读写的方向；TensorRT-LLM 文档概括了张量并行与流水线并行在通信带宽和负载均衡上的取舍。[FlashAttention](https://arxiv.org/abs/2205.14135) [TensorRT-LLM 并行策略](https://nvidia.github.io/TensorRT-LLM/1.2.0rc6.post2/features/parallel-strategy.html)

输入 token、多模态张量、采样结果和输出 token 也会经过服务端与执行设备之间的边界。这些数据通常不与权重、KV、激活占据同样的模型内部生命周期，但多模态输入和分布式采样仍可能带来显著传输与同步成本。

### 负载怎样改变搬运压力？

知道数据经过哪里，还要知道这些路径被使用得多频繁。prefill 一次处理多个输入 token，线性层可以让读取的权重服务更多计算。小批量 decode 每步处理的 token 较少，权重读取相对于计算的成本往往更突出。将多个请求组成批次，可以增加权重的复用机会，同时也会增加需要保存和读取的 KV。

上下文长度改变了另一部分压力。对读取完整历史 KV 的注意力实现，历史越长，每个生成步需要访问的 KV 就越多。因此，小批量、短上下文时值得关注权重读取；上下文变长后，KV 容量和访问成本也可能成为重点。模型结构、缓存命中和并行方式都会影响这种变化，不能给所有负载固定一个瓶颈。

计算强度描述每访问一个字节的数据，完成多少计算。计算强度较低时，内存供数速度可能先限制性能；较高时，计算能力可能更重要。这是初步判断：任务过小、并行度不足或启动开销较大时，GPU 也可能未充分利用算力和带宽，需要结合实际测量确认。[NVIDIA GPU 性能指南](https://docs.nvidia.com/deeplearning/performance/dl-performance-gpu-background/index.html)

于是，研究地图需要同时标出数据、路径和负载。同一段 KV 在显存不足时是容量问题，在长上下文 decode 中可能是 HBM 访问问题，在分离部署中又可能是网络传输问题。先确认运行阶段、批大小和上下文长度，再判断哪条路径值得优化。

## 4. 推理数据搬运研究地图

沿着前面的数据与路径，可以把研究切口归为六类。它们的联系是：**放置决定经过哪里，布局与表示影响搬运量，时机决定等待，共享资源决定并发代价，多 GPU 协同增加通信依赖，最后用请求性能检验收益。**

### 4.1 放置与生命周期：数据留在哪里？

- **分层放置与路径选择：**把权重或 KV 放到 CPU、SSD 或远端，可以扩展容量、释放显存，但再次使用时要付出读取和恢复成本。切口在于结合容量压力与复用频率选择位置，并评估整条路径的中转和传输成本。
- **保留与回收：**经常复用的前缀更值得靠近计算保留，很少再用的数据则可以换出或释放。保留策略会改变后续搬运次数；回收又必须等待相关计算和传输结束，因此容量管理与执行同步相连。
- **恢复或重算：**缓存命中仍可能要经历排队和传输，拥塞时未必比重新处理前缀更快。研究可以比较两条路径的实际成本，随上下文长度和当前负载选择，从而把缓存策略与计算调度联系起来。

公开案例：[FlexGen](https://arxiv.org/abs/2303.06865)、[分层 KV 缓存](https://vllm.ai/blog/2026-09-10-tiered-kv-offloading)。

### 4.2 布局与搬运量：数据怎样组织，哪些读写可以省掉？

位置确定后，同一份数据的组织和访问方式仍会影响容量与流量。

- **分页与共享：**KV 按块分配可以减少预留空间的浪费，共享有效前缀可以减少重复保存。它们为更多请求腾出空间，也改变算子访问数据的方式；分页管理本身不意味着数据已经卸载到 CPU 或 SSD。
- **传输组织：**合并小块可以减少提交开销，但等待合并也可能推迟首批数据到达。SGLang HiCache 在 GPU 侧按层组织 KV，在主机与存储侧采用便于按页 I/O 的布局，展示了计算与传输对布局的不同需求。切口是把布局转换、传输粒度和交接时机一起评估。[HiCache](https://www.lmsys.org/blog/2025-09-10-sglang-hicache/)
- **GPU 内部读写：**即使数据都在显存，算子仍要访问权重、KV 和中间结果。分块与融合可以减少 HBM 往返，但也要控制片上资源占用。TensorRT-LLM 的注意力后端还可将输出量化融合进注意力计算，展示了减少独立处理步骤和中间数据的方向。[TensorRT-LLM 注意力实现](https://nvidia.github.io/TensorRT-LLM/features/attention.html)
- **压缩、量化与稀疏化：**更紧凑的表示或减少参与计算的数据，可以降低流量，但可能增加编码、解码和格式转换成本，或影响输出质量。收益要沿着处理、搬运和计算的完整路径判断，不能只看减少了多少字节。

公开案例：[PagedAttention](https://arxiv.org/abs/2309.06180)、[FlashAttention](https://arxiv.org/abs/2205.14135)、[vLLM KV 搬运实现](https://vllm.ai/blog/2026-01-08-kv-offloading-connector)。

### 4.3 搬运时机：数据何时到位？

即使位置和搬运量相同，发起时间与交接粒度不同，也会改变计算等待。

- **预取：**在数据被使用之前启动搬运，可以利用排队或其他计算期间的时间。提前太多会占用缓冲，预测错误还会产生无用搬运，因此研究要协调预取提前量、数据选择和容量限制。
- **分块交接：**若计算依赖允许，可以先搬当前层所需的数据，再让当前层计算与后续搬运流水执行。小块更早可用，大块更容易摊薄提交开销，这把传输粒度与计算启动时机联系起来。
- **计算粒度与搬运衔接：**TensorRT-LLM 的 chunked prefill 将长输入分块处理，给正在生成的请求留出执行机会，并改变每轮激活缓冲需求。它划分的是计算工作，研究时应进一步连接计算块大小、数据准备和缓冲占用，避免把分块计算与分块传输混为一谈。[Chunked prefill](https://developer.nvidia.com/blog/streamlining-ai-inference-performance-and-deployment-with-nvidia-tensorrt-llm-chunked-prefill/)
- **计算重叠：**异步提交允许提交线程继续工作，实际重叠还要满足数据依赖、执行顺序和设备能力。切口是找出可与传输并行的独立计算，并控制同步位置，减少未被隐藏的等待。
- **小数据与状态同步：**Megatron Core 的动态推理上下文把调度元数据合并传到 GPU，并在异步调度中直接用 GPU 上的采样 token 准备下一步输入。数据虽小，频繁传输和等待仍可能进入关键路径；切口是减少往返、安排缓冲复用，同时保证 CPU 与 GPU 状态一致。[Megatron Core 推理上下文](https://docs.nvidia.com/megatron-core/developer-guide/latest/apidocs/core/core.inference.contexts.dynamic_context.html)
- **竞争干扰：**传输与计算同时运行时，可能争用 HBM 带宽等资源；不同搬运实现占用的资源也不同。因此，传输并发和预取深度需要同时考虑隐藏的等待与新增干扰，重叠更多未必更快。

机制参考：[CUDA 拷贝与计算重叠指南](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/index.html#asynchronous-and-overlapping-transfers-with-computation)。

### 4.4 共享资源：多个搬运任务谁先走？

上一类关注一次搬运与计算的衔接；多个请求同时执行后，还需要协调共用队列、链路和缓冲的任务。

- **优先级：**前台恢复直接影响当前请求，后台备份、预取和迁移的紧迫程度通常不同。排序可以减少关键请求的等待，但要在任务大量进入底层队列前生效，并避免后台工作长期得不到执行。
- **在途上限：**限制已经发出但尚未完成的任务，可以控制拥塞与缓冲占用。任务大小不同，只限制数量未必足够；任务数、字节数和缓冲上限要共同平衡并发吞吐与排队延迟。
- **接纳与背压：**接纳控制决定是否接受新工作，背压让下游的拥塞促使上游放慢提交。它们与优先级互补：排序解决先做谁，接纳和背压控制工作是否继续堆积。

设计参考：[Mooncake 本地传输队列 RFC](https://github.com/kvcache-ai/Mooncake/issues/2132)。这是设计提案，不能当作已验证的性能结果。

### 4.5 多 GPU 协同：哪个计算边界需要通信？

计算分到多个设备后，数据交接还会形成设备之间的依赖，不同并行方式对应不同等待位置。

- **张量并行：**同一层分给多张 GPU，局部结果需要交换或汇总，后续计算才能继续。切口在于通信组织、同步频率及其与独立计算的重叠，同时关注较慢参与者对整层执行的影响。
- **流水线并行：**不同层分成阶段，阶段之间交接激活。传输慢和阶段计算不均衡都可能让后续 GPU 等待，因此交接粒度需要与阶段负载、请求交错执行一起安排。
- **prefill／decode 分离：**阶段之间传递 KV，使输入处理与生成可以分别配置资源，但也增加了状态交接成本。研究要协调两侧处理能力与 KV 传输速度，避免一侧扩容后把瓶颈移到链路或接收端。
- **MoE 专家并行：**路由器把 token 分给不同专家子网络，跨卡分发与回收激活。SGLang 的两批次重叠把微批次计算与专家通信交错安排，专家负载均衡则调整专家分布。两者连接了通信时机与设备负载，研究还需检查重叠收益是否被资源竞争或局部拥堵抵消。[SGLang 专家并行](https://www.lmsys.org/blog/2025-05-05-large-scale-ep/)

这些切口都需要结合 GPU 连接方式和共享链路分析，并复用前面的分块、重叠与流量控制机制。公开参考：[并行策略](https://nvidia.github.io/TensorRT-LLM/1.2.0rc6.post2/features/parallel-strategy.html)、[分离式推理](https://docs.nvidia.com/dynamo/dev/kubernetes/disaggregated-serving/overview)、[专家并行](https://nvidia.github.io/TensorRT-LLM/advanced/expert-parallelism.html)。

### 4.6 收益评估：请求是否真的更快？

各类优化可能把成本从一处移到另一处，需要用完整请求的表现检验收益。

- **定位成本：**区分排队、等数据、实际传输、同步和计算变慢，才能判断优化改变了哪一段。GPU 内部优化还要观察 HBM 读写量与算子耗时，避免只凭拷贝速度或重叠比例解释收益。
- **观察服务指标：**首 token 延迟（TTFT）衡量首次输出的等待，后续 token 间隔反映生成节奏，尾延迟与吞吐反映服务整体表现。局部优化可能改善一个指标却损害另一个，需要按服务目标取舍。
- **验证适用范围：**运行阶段、批大小、并发、上下文长度、命中位置和后台流量都会改变瓶颈。研究应说明优化在哪些负载下有效，以及收益何时被计算、容量或其他链路限制。

具体测量方法见第五节。

这些项目展示的是已有机制及其取舍。形成具体研究问题，还需要在目标负载下测出稳定的不足，不能仅把已有功能重新列为待解决问题。

### 延伸切口

- **多模态输入：**图像、音频和视频先经过预处理，再送入模型。预处理位置、分块搬入和流水执行分别连接前面的放置、交接与调度问题，还要控制大输入对缓冲和队列的影响。
- **权重与适配器更新：**LoRA 适配器是一组调整模型行为的附加参数。装载新参数要与请求使用的版本保持一致；同时保留新旧参数可以方便切换，却增加暂存空间，因此更新时机与旧参数回收要共同安排。

## 5. 从系统现状走向可检验的问题

这张地图从数据类型、硬件路径和协调机制三个维度组织常见研究切口。具体分析时，还要加上负载条件：数据从哪里来、怎样组织、经过什么路径，哪一步计算必须等它，以及这种等待在当前阶段和批大小下有多重要。

切入研究时可以先选一条可观测的数据路径，确定它属于哪个切口，再对现有机制做对照测量。

先固定模型、硬件、运行时版本和可重复的请求序列，再分别设计对照，改变批大小、请求并发、输入与历史上下文长度、实际命中 token 比例或后台搬运量。
根据路径选择测量项。显式传输关注队列等待、传输字节数、中转区占用和依赖计算的启动时间；GPU 内部访问关注 HBM 读写、算子耗时和资源利用；跨卡通信还要关注各参与者的耗时差异与同步等待。最后统一比较 TTFT、输出间隔、尾延迟和吞吐，并重复运行确认现象稳定。

只有当某种负载下出现稳定、可解释且现有机制未解决的性能问题，才值得把它收束为具体研究问题。



## 参考资料

- [I/O for LLM Inference：存储与内存瓶颈综述，2026](https://link.springer.com/article/10.1007/s10462-026-11651-1)。
- [FlexGen：GPU、CPU 与 SSD 分层推理](https://arxiv.org/abs/2303.06865)；[FlashAttention](https://arxiv.org/abs/2205.14135)。
- [NVIDIA GPU 性能指南](https://docs.nvidia.com/deeplearning/performance/dl-performance-gpu-background/index.html)：计算强度、带宽与延迟限制；[PagedAttention](https://arxiv.org/abs/2309.06180)：KV 分页管理与共享。
- [NVIDIA Dynamo 分离式推理](https://docs.nvidia.com/dynamo/dev/kubernetes/disaggregated-serving/overview)；[vLLM KV 搬运实现分析](https://vllm-project.github.io/2026/01/08/kv-offloading-connector.html)。
- [TensorRT-LLM 并行策略](https://nvidia.github.io/TensorRT-LLM/1.2.0rc6.post2/features/parallel-strategy.html)：张量并行与流水线并行的数据交换路径。
- [TensorRT-LLM 专家并行说明](https://nvidia.github.io/TensorRT-LLM/advanced/expert-parallelism.html)：MoE 专家分布与通信。
- [SGLang HiCache](https://www.lmsys.org/blog/2025-09-10-sglang-hicache/)；[SGLang 大规模专家并行](https://www.lmsys.org/blog/2025-05-05-large-scale-ep/)：跨层布局、通信重叠与专家负载。
- [Megatron Core 动态推理上下文](https://docs.nvidia.com/megatron-core/developer-guide/latest/apidocs/core/core.inference.contexts.dynamic_context.html)：调度元数据传输与采样 token 路径。
- [TensorRT-LLM 注意力实现](https://nvidia.github.io/TensorRT-LLM/features/attention.html)；[Chunked prefill](https://developer.nvidia.com/blog/streamlining-ai-inference-performance-and-deployment-with-nvidia-tensorrt-llm-chunked-prefill/)：算子融合与计算粒度。
- [Mooncake 本地传输队列 RFC #2132](https://github.com/kvcache-ai/Mooncake/issues/2132)；[Mooncake × HiCache 设计](https://kvcache-ai.github.io/Mooncake/design/hicache-design.html)。
- [CUDA 异步拷贝与计算重叠指南](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/index.html#asynchronous-and-overlapping-transfers-with-computation)。
- [NVIDIA NVLink／NVSwitch](https://docs.nvidia.com/hgx-platforms/fabric-manager-user-guide/index.html)；[GPUDirect RDMA](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/gpu-operator-rdma.html)；[GPUDirect Storage](https://docs.nvidia.com/gpudirect-storage/)。
- [NVLink-C2C](https://docs.nvidia.com/dccpu/grace-perf-tuning-guide/)。
