---
title: "游戏公司的 AI Infra 在做什么：从 3D 生成研究看系统问题"
date: 2026-10-17
permalink: /posts/game-3d-generation-ai-infra/
lang: zh-CN
translations:
  zh: /posts/game-3d-generation-ai-infra/
  en: /posts/game-3d-generation-ai-infra/en/
author_profile: false
read_time: true
excerpt: "从 Roblox、腾讯混元、Meshy、网易、米哈游、字节和 Meta 的公开工作，梳理游戏资产生成中的 GPU 执行、稀疏几何、模型载入与端到端优化。"
tags:
  - AI Infrastructure
  - 3D Generation
---

游戏公司使用 AI 的场景大致分三类：内容生产，用模型生成概念图、3D 资产、动画和语音；游戏内交互，让 NPC 理解玩家输入并实时回应；研发与运营工具，用于代码辅助、自动化测试、客服和内容审核。

这些应用都需要 AI Infra 支撑，但负载不同。内容生产常要训练大模型或批量生成资产，重点是 GPU 吞吐、显存利用和单次生成成本；游戏内交互要求低延迟、稳定输出和并发承载；研发与运营工具则要应对请求波动并保持服务可用。Infra 工作覆盖模型训练执行、GPU 资源调度、模型载入和在线推理服务。

本文从 3D 生成切入内容生产这条线。3D 生成除了模型计算，还要把模型输出解码成网格，再做拓扑整理、材质处理和游戏导入；这条链路能具体展示 AI Infra 如何面对 GPU 执行、显存、加载和后处理的工程问题。

## 从一句描述到游戏里的 3D 资产

用户输入文字或图片后，生成模型先在内部表示中构造物体，再把表示解码成三维表面。表面通常由顶点、边和面组成，合起来叫网格。拓扑描述这些元素如何连接，决定模型能否拆件、编辑和变形。产品还可能要补材质、纹理、部件、骨骼与碰撞信息，最后检查模型能否导入游戏并符合项目规范。

本文把 3D AI 聚焦在从文字或图像生成游戏资产，讨论几何生成、纹理与部件处理，以及这些步骤的训练和推理执行。下文选取公开披露的代表性游戏公司工作，以及直接影响生成效率的前沿研究。

```text
文字或图片 → 三维内部表示 → 形状与网格 → 材质和部件
           → 拓扑整理、骨骼或碰撞 → 游戏导入与验收
```

体素把空间切成立方格，三个方向的分辨率翻倍会让格子数增至八倍。稀疏表示跳过空白位置，但 GPU 仍要查坐标和访存；自回归模型逐个预测形状单元，长序列会拉长等待。直接输出网格省去中间转换，同时要预测顶点连接关系。

## Roblox：为 3D 自回归模型定制 GPU 执行

Roblox Cube 面向 Roblox 创作者，让他们从描述生成可放进虚拟场景的 3D 资产。它用两条序列协同工作：一条保存输入条件，另一条逐步生成形状单元。部分注意力层只看已生成的形状，另一些还要读取条件序列，因此每层面对的张量长度不同。执行框架需要按层支持不同的注意力访问方式和张量形状。

2026 年发布的 CubePart 把输入扩展到已有网格和部件说明，按语义拆出一组可组合的部件网格，目标是让结果可直接用于动画、物理和行为脚本。它说明游戏里的 3D 生成正在从单件外形走向有部件结构的资产；这类输出也会增加模型之后的检查、拼装和导入工作。[Roblox Cube 官方仓库](https://github.com/Roblox/cube)

官方工程文章先用 CUDA Graphs 处理 CPU 启动开销。它把一段固定尺寸的 GPU 运算录下来，后续整段重放，省掉 CPU 每一步重复发起小运算的时间。图捕获要求输入形状固定，Roblox 将常见尺寸标准化，并为不同尺寸准备执行图。第二步加入 KV cache（注意力键值缓存），保留已生成部分的注意力结果，供后续步骤复用。两项改动分别减少 CPU 启动和重复计算。

Roblox 官方工程说明测量的是单张 H100 上的单次推理执行：每个生成步骤从 60.5 毫秒降至 20.5 毫秒，再降至 7.8 毫秒；模型阶段从 31 秒降至 4 秒，连同网格后处理约 7 秒。[工程说明](https://about.roblox.com/newsroom/2025/06/accelerating-ai-inference-roblox-3d-creation)、[技术报告](https://arxiv.org/abs/2503.15475)、[官方仓库](https://github.com/Roblox/cube)。学习时可以复现一个生成请求，再用性能分析工具比较 CUDA Graphs 和 KV cache 前后的 CPU 运算启动耗时、GPU 空等时间、每步延迟与整段生成耗时。

## 腾讯混元：先找到 3D 推理时间花在哪里

FlashVDM 要把模型内部的三维特征还原成没有贴图的物体表面。它的流程包含反复修正形状的扩散采样，以及检查空间位置是否属于物体表面的体积解码。论文先对基线做时间拆分，发现解码约占 75.8%，采样约占 23.9%。如果只优化采样，即使采样时间降到零，按这个基线估算，整体上限也只有约 1.32 倍。因此，几何解码是首要优化对象。

团队因此先改体积解码：逐层细化物体表面附近的位置，减少要检查的三维坐标；再根据空间邻近关系筛选相关特征，避免每个坐标都读取完整特征集合；最后训练较轻的解码器，降低每次查询的计算量。论文消融中的解码时间从 22.33 秒，经层级查询降到 2.322 秒，再经轻量解码器和特征筛选降到 0.731 秒与 0.491 秒。这些改动针对的是几何解码计算本身，属于模型推理路径与计算方法的协同优化。

采样端再用渐进式蒸馏把扩散步骤从 50 步压到 5 步。蒸馏是用较大的教师模型训练小模型，让它用更少步骤近似原有结果；直接把原模型的采样步数改成 5 步会降低生成质量。在 RTX 4090 上，模型生成阶段的计时不含贴图、重拓扑、绑定和游戏适配；论文测得无纹理形状生成时间从 25.2 秒降到 0.79 秒，交并比略有下降。[ICCV 2025 论文](https://openaccess.thecvf.com/content/ICCV2025/html/Lai_Unleashing_Vecset_Diffusion_Model_for_Fast_Shape_Generation_ICCV_2025_paper.html)、[官方代码](https://github.com/Tencent-Hunyuan/FlashVDM)。对 Infra 工作的启发是给每个阶段打时间标记：分别记录模型载入、采样、几何解码和网格导出，再按总耗时找下一处值得优化的环节。

LATTICE 同属腾讯混元，它逐步扩展三维特征序列，把训练规模从 1024 增至 6144。论文报告 20 亿参数模型使用 64 张 GPU 训练 24 小时，但没有披露 GPU 型号和完整成本口径。复现实验可从单卡扩到 2、4、8 卡，记录样本吞吐、利用率、通信等待和检查点耗时，观察扩卡收益何时下降。[CVPR 2026 论文](https://openaccess.thecvf.com/content/CVPR2026/html/Lai_LATTICE_Democratize_High-Fidelity_3D_Generation_at_Scale_CVPR_2026_paper.html)、[作者项目页](https://lattice3d.github.io/)

混元还发布了 Hunyuan3D Studio，把部件生成、多边形网格生成和语义 UV 等模块接成面向游戏资产的流程，目标输出包括优化后的几何和 PBR 材质。这类生产链路让 Infra 的测量对象从单个形状模型延伸到网格优化、UV 和贴图等连续阶段，端到端任务时间才对应资产交付速度。[Hunyuan3D Studio 技术报告](https://arxiv.org/abs/2509.12815)

## Meshy：直接生成网格、整理几何数据和加快模型载入

Meshy T2 把文字或图像直接变成可编辑网格。它并行预测顶点及其连接关系，用流匹配从初始噪声逐渐生成形状，省去先生成体素或隐式形状再转网格的步骤。

T2 还提供了一项 GPU 数据布局的实现案例，公开论文描述了方法，没有单独计时。点编码器按空间位置整理顶点，再把同一区域的数据连续存放，让 GPU 聚合邻近顶点时少做零散读写。Infra 可以复现这项设计，并分别测量数据整理、邻近聚合和端到端生成的耗时。

T2 的公开速度数据来自不同测试口径：预印本在 115 个资产上报告图像到网格中位数 6 秒，测试资产通常约 4,000 个面，未说明推理 GPU 型号；产品博客另报工程版约 1 秒计算、约 2 秒端到端。比较时要统一输入规模、硬件和计时范围，并分开记录模型计算与端到端时间。[T2 预印本](https://arxiv.org/html/2607.28675v3)、[产品工程说明](https://www.meshy.ai/blog/meshy-t2-native-3d-mesh-generation)

Faithful Contouring 处理模型与几何工具之间的数据转换。传统做法先把网格修成封闭表面，再为三维空间计算离表面的距离，最后从距离数据中提取网格。该工作直接把网格编码成稀疏体素锚点和表面特征，省去上述中间表示。在单张 H100 的几何转换测试中，512 分辨率使用 43 MB、耗时 0.33 秒；2048 分辨率使用 711 MB、耗时 4.14 秒，编码和解码开销随分辨率上升。[CVPR 2026 论文](https://openaccess.thecvf.com/content/CVPR2026/html/Luo_Faithful_Contouring_Near-Lossless_3D_Voxel_Representation_Free_from_Iso-surface_CVPR_2026_paper.html)、[作者代码](https://github.com/Luo-Yihao/FaithC)。Infra 可以借这个例子练习分辨率扫描：画出时间与显存随输入规模变化的曲线，判断几何预处理在哪个规模开始成为瓶颈。

Overmind 解决模型切换时的重复载入。美术流水线可能调用多个低频模型，显存放不下所有权重时，服务就要在需要时从磁盘重新读取、恢复张量，再把数据传到 GPU。Overmind 把准备好的张量放进多个进程共享的主机内存，复用缓存可以跳过重复读取和张量重建。这里的零拷贝指多个 CPU 进程共享已有内存；GPU 推理仍需把数据传到 GPU。

在 Linux、i9-11900K 与 RTX 4090 的 ControlNet 测试中，基线载入为 6.16 秒，首次填充缓存要 24.20 秒，之后命中为 1.12 秒，约快 5.5 倍；暖载入仍需 0.87 秒传到 GPU，重建 pipeline 约 0.20 秒。复现这组基准时，可改变模型大小和复用次数，找出缓存准备成本开始回本的条件。[Meshy 工程文章](https://www.meshy.ai/blog/fast-ml-model-loading-overmind)、[开源代码与基准](https://github.com/meshy-dev/overmind)

## 网易伏羲：让生成结果直接成为游戏角色参数

网易伏羲的 EasyCraft 把玩家照片映射到《逆水寒手游》和《永劫无间手游》已有的捏脸参数。它冻结预训练图像编码器，为每款游戏训练小型转换器，并用游戏渲染生成训练图像。1000 张多风格照片在 RTX 4090 上平均推理 0.026 秒，F2P 基线为 1.140 秒，F2P v2 为 0.007 秒。对 Infra 来说，这类轻量预测的难点更多落在服务集成：接入编辑器、校验参数并处理超时和失败。[CVPR 2025 论文](https://openaccess.thecvf.com/content/CVPR2025/papers/Wang_EasyCraft_A_Robust_and_Efficient_Framework_for_Automatic_Avatar_Crafting_CVPR_2025_paper.pdf)

## Tripo 与 VAST：高分辨率形状为何需要稀疏计算

SparseFlex（ICCV 2025）用表面附近的稀疏体素保留高分辨率几何，并在分辨率逐级提高时剪掉不含表面的区域。普通体素网格会给整个立方空间分配位置，物体外的大量空白也占用内存；稀疏表示省去这些空白位置的存储与计算，同时需要维护活跃体素的坐标和邻居索引。

SparseFlex 的公开材料聚焦几何表示与网格重建。官方代码展示稀疏体素编码与网格重建，其中 1024³ 网格重建配置需要约 12GB 显存。[项目页](https://xianglonghe.github.io/TripoSF/)、[官方仓库](https://github.com/VAST-AI-Research/TripoSF) 。Infra 的研究切口是把索引、邻居查询、特征计算分开计时，再按稀疏度和分辨率画出端到端曲线，找出稀疏表示开始兑现收益的区间。

## 米哈游：从单图生成到自动场景合成

米哈游前图形 AI 负责人 Cheng Lin 参与的 Wonder3D 获 CVPR 2024 Highlight。给定一张物体图像，模型生成彼此一致的多视角法线图和颜色图，再融合为带纹理的网格；项目页报告单件生成约需 2 至 3 分钟。这条链路分为扩散生成和网格提取两段，可分别测量耗时、显存，再观察图像分辨率和视角数对端到端时延的影响。[Wonder3D 论文与代码](https://github.com/xxlong0/Wonder3D)、[CVPR 论文](https://openaccess.thecvf.com/content/CVPR2024/html/Long_Wonder3D_Single_Image_to_3D_using_Cross-Domain_Diffusion_CVPR_2024_paper.html)、[Cheng Lin 的经历与论文列表](https://clinplayer.github.io/)。

曾任米哈游 Lumi 团队图形算法研究员的杜仲烁（Zhongshuo Du）在个人项目页披露了概念图到场景合成的工程流程：识别图中物件并估计深度、对齐坐标、检索 3D 资产，再用 Blender 脚本自动摆放；缺少合适资产时调用 3D 生成模型。另一个项目会分块处理 CLAY 生成的粗网格并修整拓扑，得到适合后续制作的网格。[杜仲烁的项目说明](https://dosuremaker.github.io/)

这类流程把负载从单个模型扩展成多个阶段：视觉模型、资产检索、网格处理和场景装配交替运行。Infra 可以测每阶段的 GPU 与 CPU 时间、显存峰值和中间文件大小，再决定模型常驻、任务并行与失败重试怎样安排。

## 字节 Seed：把生成延伸到可仿真的 3D 资产

Seed3D 2.0 来自字节 Seed 团队，技术报告展示了几何、材质、部件和关节的联合生成，并通过稀疏查询、分层裁剪和网格简化减少计算。可据此做多阶段基准，分别测各类输出的耗时与显存，判断输出组合怎样影响单卡并发。[Seed3D 2.0 技术报告](https://arxiv.org/html/2605.13862v1)

## Meta Reality Labs：把生成和资产后处理一起加速

AssetGen 从单张参考图生成带纹理的网格，并把面数控制在适合实时渲染的范围。其 H100 结果约 30 秒完成高质量资产，快速版约 14 秒。速度来自一整条协同优化的链路：几何简化、清理、UV 展开和法线烘焙放在 GPU 上执行；模型做蒸馏、算子和精度优化；CPU、GPU 与 I/O 阶段再以流水方式重叠。团队报告固定样本的 MeshGen 路径经多项优化从 103.15 秒降至 12.25 秒。Infra 优化沿着关键路径统筹生成网络与后处理，让各阶段尽量并行运行。[AssetGen 技术报告](https://arxiv.org/abs/2605.26137)

## 3D 生成 Infra 的前沿研究切口

近期工作给出三类 Infra 研究切口：减少重复计算、提升稀疏数据执行效率，以及根据资产规模安排资源。它们从模型内部开始，最终都要用端到端服务指标验证。

**第一条线是少做重复计算。** CVPR 2025 的 Hash3D 研究文本到 3D 的逐视角优化：同一物体在相近相机角度、相邻去噪时间步下，会重复计算相似的图像特征；它用空间哈希缓存并复用这些特征，论文报告不同方法约 1.5 至 4 倍加速。复现时同时记录缓存命中率、显存占用、失效检查时间和端到端耗时，据此计算扣除缓存管理开销后的净节省。[Hash3D，CVPR 2025](https://openaccess.thecvf.com/content/CVPR2025/html/Yang_Hash3D_Training-free_Acceleration_for_3D_Generation_CVPR_2025_paper.html)

CVPR 2026 的 Fast3Dcache 将缓存进一步适配到稀疏体素生成：根据去噪过程中逐渐稳定的体素位置动态分配缓存额度，再按特征变化速度挑选可复用部分。在 TRELLIS 和 DSO、单张 RTX 4090 的测试中，论文报告最高 27.12% 推理加速和 54.83% FLOPs 减少，同时报告 Chamfer Distance 增加 2.48%、F-Score 下降 1.95%。它针对的是几何一致性容易受缓存误差影响的问题，说明 3D 生成需要按表示结构设计缓存策略。[Fast3Dcache，CVPR 2026](https://openaccess.thecvf.com/content/CVPR2026/html/Yang_Fast3Dcache_Training-free_3D_Geometry_Synthesis_Acceleration_CVPR_2026_paper.html)

FlashVDM 前文展示了如何先拆出采样与几何解码的耗时，再把优化投向真正占时的阶段；相关机制见[腾讯混元一节](#腾讯混元先找到-3d-推理时间花在哪里)。

**另一条线是缩短网格生成的串行步骤。** 自回归网格模型要按顺序逐个预测顶点和面，后一个 token 依赖前面的结果，网格越大，等待越长。CVPR 2026 的 MeshFlow 把网格压进更紧凑的连续表示，再并行生成顶点和边；论文称采样速度达到当时最快自回归方法的 26 倍。FlashMesh 保留逐步生成框架，但先并行猜测多个后续 token，再校正几何关系并由主模型验证，报告最高 2 倍加速。两者分别减少了必须串行处理的内容和每轮串行步数，展示模型结构与执行策略如何共同决定生成速度。[MeshFlow，CVPR 2026](https://openaccess.thecvf.com/content/CVPR2026/html/Li_MeshFlow_Efficient_Artistic_Mesh_Generation_via_MeshVAE_and_Flow-based_Diffusion_CVPR_2026_paper.html)、[FlashMesh，CVPR 2026](https://openaccess.thecvf.com/content/CVPR2026/html/Shen_FlashMesh_Faster_and_Better_Autoregressive_Mesh_Synthesis_via_Structured_Speculation_CVPR_2026_paper.html)

同届的 MeshMosaic 把艺术网格生成扩展到十万面以上：它先切成局部网格块，分别生成后再按共享边界拼接。这种分块路径为 Infra 留下了新的执行问题：局部块能否并行生成，边界一致性检查和最后拼接需要多少时间，网格规模增长时显存如何变化。[MeshMosaic，CVPR 2026](https://openaccess.thecvf.com/content/CVPR2026/html/Xu_MeshMosaic_Scaling_Artist_Mesh_Generation_via_Local-to-Global_Assembly_CVPR_2026_paper.html)

**第二条线是稀疏数据的 GPU 执行。** SparseFlex 与 TRELLIS.2 都依赖稀疏三维数据；TRELLIS.2 用 O-Voxel 表示几何与材质，并配套 FlexGEMM 稀疏卷积后端。后端避免把稀疏数据展开成大型中间矩阵，在 A100 部分 FP16、TF32 算子基准上报告约两倍加速。后续可测不同稀疏度下的坐标索引、邻居查询、算子和端到端耗时，判断局部加速何时转化为整体收益。[TRELLIS.2，CVPR 2026](https://openaccess.thecvf.com/content/CVPR2026/html/Xiang_Native_and_Compact_Structured_Latents_for_3D_Generation_CVPR_2026_paper.html)、[FlexGEMM 项目说明](https://jeffreyxiang.github.io/en/blogs/flexgemm)

**第三条线是按工作量调度。** TRELLIS 支持网格、3D 高斯等不同输出，SAR3D 在 A6000 上报告单样本生成约 0.82 秒。输入规模、目标精度和输出类型都会改变显存与计算量；可据此比较不同请求分桶方式对吞吐、95 分位延迟和显存峰值的影响。[TRELLIS，CVPR 2025](https://openaccess.thecvf.com/content/CVPR2025/html/Xiang_Structured_3D_Latents_for_Scalable_and_Versatile_3D_Generation_CVPR_2025_paper.html)、[SAR3D，CVPR 2025](https://openaccess.thecvf.com/content/CVPR2025/html/Chen_SAR3D_Autoregressive_3D_Object_Generation_and_Understanding_via_Multi-scale_3D_CVPR_2025_paper.html)

## 总结：前沿从单步加速走向整条生成链路

这些工作指向几类不同瓶颈：扩散模型反复计算相近特征，可用缓存；稀疏体素让规则 GPU 算子难以吃满，可改数据结构和内核；自回归网格生成受顺序依赖限制，可压短表示、并行预测或分块；完整资产还要经过几何和材质处理，服务端则需把这些阶段纳入同一条任务链。Infra 研究要测清各阶段的时间、显存和资源利用，再判断优化能否改善端到端生成与并发成本。

因此，3D 生成 Infra 的研究应从负载和瓶颈剖析出发，决定该优化采样、几何解码、稀疏访问、模型载入还是资产后处理。值得推进的方向，是让请求规模和输出类型参与执行策略选择，并把质量、分阶段耗时、端到端时延、显存峰值和并发成本放进同一套评测。这样才能判断局部加速是否改善了真正的生成体验。
