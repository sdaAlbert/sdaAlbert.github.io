---
title: "当 Agent 不能只向前：从代码恢复到实时业务的 Runtime 设计"
date: 2026-09-18
modified: 2026-09-18
permalink: /posts/checkpointing-and-recoverable-execution/
lang: zh-CN
translations:
  zh: /posts/checkpointing-and-recoverable-execution/
  en: /posts/checkpointing-and-recoverable-execution/en/
author_profile: false
read_time: true
excerpt: "Agent 的恢复策略并不由框架决定，而由事实来源、状态边界与结果剩余的时间价值共同决定。"
tags:
  - AI Infrastructure
  - LLM Agents
  - Agent Runtime
  - Reliability
---

## 1. 从一个最简单的 Agent Loop 开始

我最初对 Agent Runtime 的理解很直接：模型请求失败就重试，用户不想继续就取消，任务太长就保存 Checkpoint。一个最小的 ReAct Loop 也确实很简单：

```text
用户任务
→ 模型决定下一步
→ Runtime 调用工具
→ 工具改变外部状态
→ 结果进入模型上下文
→ 模型继续执行
```

但只要工具会修改外部世界，这个 Loop 就隐含了几个危险假设：模型和工具总能明确返回成功或失败；超时代表操作没有成功；同一个操作执行两次不会产生额外影响；内存中的消息就是完整任务状态；进程、上下文和工具环境会一起存活。

最典型的反例是：Agent 调用工具创建工单，工单已经写入数据库，但响应返回前网络断开。Runtime 只看到了超时，却不知道外部世界已经改变。直接重试可能创建两条工单；读取一份旧 Checkpoint，也无法回答第一次调用究竟有没有成功。

一次失败之后，Agent 的记忆、执行环境与已经发生的业务事实，是否仍然一致？

这篇文章想进一步提出一个更具体的判断：**恢复策略不是由 Agent 框架决定的，而是由事实来源、状态边界和剩余时间共同决定的。** 可以先把它写成一个不严格但有用的式子：

```text
Recovery Decision
= Truth Anchor（什么能证明真实发生过）
+ Recovery Boundary（什么仍在 Runtime 控制内）
+ Time Value（结果现在是否还有价值）
```

后文梳理不同系统，并不是为了列出更多恢复名词，而是要验证这三个问题怎样改变最终决策。

## 2. 恢复之前，先问哪些状态仍然可信

Agent 每走一步，至少有三类状态同时变化。

第一类是 **Context**，也就是模型看到的消息、计划、观察和中间结论。错误一旦进入 Context，后续推理即使形式正确，也可能建立在错误前提上。

第二类是 **受控环境**，例如代码工作区、Sandbox、浏览器页签或临时文件。Runtime 往往能快照、重建或替换这些状态，但它们不会因为 Context 回退就自动回退。

第三类是 **外部副作用**，例如已经发出的消息、数据库写入、处罚决定、订单、礼物、退款和线上配置变更。这些事实通常已经离开 Agent 的控制边界，不能靠“删除几条对话”来撤销。

这三类状态可能在失败后发生分叉：模型认为动作失败了，数据库里却已经成功；工作区回到了旧版本，模型仍记得新版本中的测试结果；Agent 恢复了任务，却把几秒前已经过期的数据再次发布。

TikTok Privacy Innovation Lab 在 [When Tools Become Prompts](https://developers.tiktok.com/blog/when-tools-become-prompts) 中观察到一个相邻的问题：单个 MCP 工具调用都可能符合权限规则，但信息、意图与隐含授权会在多轮 Context 中逐渐累积，最终产生单步检查无法发现的风险。这说明 Context 不只是聊天记录，它也携带了会影响后续动作的“解释”和“权限假设”；恢复时若不处理错误后缀，这些假设仍会继续传播。

因此，恢复并不等于“加载最近的 Checkpoint”。Runtime 至少要判断：错误污染到了哪里，外部动作是否发生，历史状态是否还能满足业务约束，以及结果现在是否仍有价值。近两年的研究和工程实践，正是在逐步补齐这些问题。

## 3. 现有 Agent 系统是怎样一步步处理失败的

### 3.1 最早也最便宜的办法：在当前状态上继续修

许多 Agent 的第一反应并不是回退，而是重新规划。[Magentic-One](https://arxiv.org/abs/2411.04468) 的 Orchestrator 会维护任务账本，持续记录已经完成的工作、仍待解决的问题和当前进展；当执行停滞时，它根据当前状态形成新计划，再调度不同 Agent 继续工作。

这种方式很实用，因为很多失败只是“这条路走不通”：搜索词不好、工具选错、代码测试没通过。只要当前环境仍可信，保留已有成果并换一条路，通常比从头开始便宜。

但重新规划有一个前提：当前状态没有被早期错误污染。若 Agent 已经依据错误信息修改了十个文件，或者一次状态不明的退款已经发出，新计划仍会继承这些问题。换计划解决的是“接下来怎么走”，不是“脚下这块地是否还可靠”。

### 3.2 让任务跨进程活下来：持久化执行与重放

[LangGraph](https://docs.langchain.com/oss/javascript/langgraph/thinking-in-langgraph) 把长任务拆成有状态的节点，并在节点边界保存执行状态。进程中断后，系统可以从已经持久化的位置继续，而不必把所有工作重做一遍。它同时提醒了一个关键事实：恢复时某个节点可能再次运行，所以节点中的外部写操作仍需幂等。

[Temporal 的 AI 工作流模式](https://go.temporal.io/platform-hub/ai-engineering/ai-patterns) 更明确地区分了两件事：Workflow 的控制状态可以从历史中重建，真正访问数据库或第三方服务的 Activity 却可能以 at-least-once 方式再次执行。换句话说，Durable Execution 能保证“编排不会因 Worker 消失而遗忘”，却不自动保证“业务动作只发生一次”。为写操作设置稳定的幂等键，并在状态不明时查询真实结果，仍然是业务侧责任。

这类系统解决的是 **resume**：计算进程可以消失，任务仍可接着跑。它们并不天然解决另一种情况——任务没有中断，却在错误方向上运行了很久。

### 3.3 Claude Code 的做法：把跨会话恢复变成可接力的工程过程

Anthropic 在 [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) 中讨论了 Claude Code 长时间开发时的一个现实问题：仅靠 Context compaction，下一次会话仍可能不知道前一会话真正完成了什么。Agent 可能一次改动太多，在半成品处耗尽上下文；新会话也可能看到部分结果后误以为任务已经完成。

它给出的办法非常朴素：让 Agent 小步工作，用功能清单描述剩余任务，用进度文件说明当前状态，用 Git 历史保存可验证的增量，并在每次会话结束前留下可以运行、可以测试、便于下一位 Agent 接手的工作区。这里的恢复不是一次神奇的 rollback，而是把“交接”设计成 Harness 的正常职责。

在 [Managed Agents](https://www.anthropic.com/engineering/managed-agents) 中，这种思路又被抽象为三个可替换部分：`session` 保存追加式事件历史，`harness` 负责调用模型和路由工具，`sandbox` 提供实际执行环境。Sandbox 坏了可以重新供应，Harness 挂了可以从 Session 唤醒，任务历史不再依赖某个 Worker 或容器的寿命。

这说明长任务恢复首先是一个 Runtime 结构问题：重要状态必须落到进程之外，而且新执行者拿到的不应只是聊天记录，还应包括可验证的环境和明确的下一步。

### 3.4 AgentRewind：Context 与工作区必须一起回退

如果错误已经污染了当前状态，仅仅 resume 就不够了。[AgentRewind](https://arxiv.org/pdf/2608.14380) 的核心做法，是将 Agent Context 与受控工作区绑定到同一个历史 Checkpoint。系统发现执行失败后，不只恢复文件，也删除与错误后缀对应的上下文；同时保留一份失败经验，告诉 Agent 哪条路径已经被证明不可行，然后从较早状态重新执行。

这比“Git reset 后继续聊天”更严谨。假设文件已经回到第 20 步，而模型仍记得第 35 步才出现的测试结果，两边仍然不一致。联合回退要求模型所知与环境所处的位置重新对齐。

不过，AgentRewind 能直接恢复的是受控边界内的状态。代码、临时进程和 Sandbox 可以回退，已经发出的邮件、第三方订单或直播间里展示过的内容并不会随工作区一起消失。这条边界非常重要：Rewind 是代码 Agent 的强能力，却不是所有企业 Agent 的通用答案。

### 3.5 DART：能回退，不代表应该回退到那里

[DART](https://arxiv.org/abs/2605.23311) 进一步提出“语义可恢复性”。假设步骤 A 生成数据，步骤 B 消费它并向外部系统提交结果。此时只把 A 回退，而保留 B 的结果，虽然机械上加载成功，语义上却产生了一个没有合法上游来源的事实。

因此，选择恢复点之前要检查依赖关系和 effect 约束：哪些结果依赖待撤销的状态，哪些副作用已经对外提交，哪些下游步骤必须一同失效。如果最近的 Checkpoint 不满足这些约束，系统就应扩大恢复范围；如果没有合法恢复点，就不应继续自动执行。

这将恢复问题从“找到最近快照”变成了“找到仍然成立的历史”。恢复点首先要合法，其次才考虑少重算多少。

### 3.6 DeltaBox：当语义明确后，还要让回退足够便宜

频繁保存整个环境会带来很高成本。[DeltaBox](https://arxiv.org/abs/2605.22781) 关注的是另一个层面：增量记录文件和进程状态，让 Checkpoint 与 rollback 足够轻量，因而可以更密集地布置恢复点。

可以把以上工作看成一条逐步加深的脉络：Magentic-One 在当前状态上修计划；LangGraph 和 Temporal 让控制流程可恢复；Claude Code 用持久化产物完成跨会话接力；AgentRewind 联合恢复 Context 与环境；DART 判断哪个历史状态还能成立；DeltaBox 则尝试降低保存和回退环境的代价。

它们不是互斥方案，而是分处不同层次。一个成熟 Runtime 往往同时需要前向修复、持久化执行、受控环境回退，以及对外部副作用的核对或补偿。

## 4. 放进真实业务后，恢复方式为什么会完全不同

决定恢复方式的并不是模型名称，而是三个业务属性：结果晚到以后还有没有价值，Runtime 能控制多少环境，以及一次动作会不会影响用户、资金或线上系统。

### 4.1 代码 Agent：最适合联合回退

代码 Agent 的主要环境是 Git 工作区与 Sandbox，大部分状态可以版本化，结果也能通过编译和测试重新验证。它可以把 Session 事件、工具调用和 Git commit 绑定到同一个 CheckpointID；Worker 崩溃时从事件日志恢复 Harness，从 commit 恢复工作区；方向错误时同时删除错误 Context 后缀和文件改动，再带着失败摘要重走。

但“文件恢复了”仍不等于“工程上下文恢复了”。TikTok 工程团队公开的 [Rush MCP Server](https://developers.tiktok.com/blog/rush-mcp-server) 利用构建系统向 Agent 提供大型 monorepo 的项目关系，避免模型靠扫描全仓库猜依赖。对企业代码 Agent 来说，构建图、测试结果、任务清单和清晰的 handoff，都是可恢复状态的一部分。

### 4.2 LIVE 互动 Agent：时间不能回退，只能继续最新现场

TikTok 展示过在 LIVE Studio 边缘侧运行的互动 Agent，用来响应主播或观众的语音指令；同类能力还可能包括字幕、翻译、内容理解与互动助手。[InfiniEdge 的公开案例](https://developers.tiktok.com/blog/2025-infiniedge-ai-1-1-release) 强调低延迟和 edge-to-cloud 协作，这使它与代码 Agent 有根本区别：三秒前的回答即使最终算对，也可能已经没有价值。

可以把一次失败具体展开。假设观众送出礼物后，系统希望由 Agent 生成一句感谢并触发直播间特效：

```text
T0  礼物服务完成扣款，账本写入 EffectID=gift-731
T1  礼物事件以 offset=8421 进入直播事件流，回复 deadline 为 2 秒
T2  Agent 生成感谢语，并调用发布服务
T3  发布服务已经接收请求，但确认响应在返回前丢失
T4  推理 Worker 重启，本地 Checkpoint 只记录到“准备发布”
```

此时不能简单执行“从 T2 重试”。Context 只知道响应丢失，不是事实来源；礼物是否成立应查询交易账本，内容是否展示应查询发布记录。即使发布记录仍然无法确认，2 秒 deadline 也可能已经过去，再生成一次感谢语只会造成迟到或重复互动。更合理的处理是用稳定 EffectID 核对并抑制重复发布，然后从最新 offset 继续，而不是回退礼物或重放整段直播。

这个例子同时暴露了三个维度：账本和发布记录是 **Truth Anchor**，Agent Worker 只是可替换的 **Recovery Boundary**，而 deadline 决定了旧结果的 **Time Value**。同样是一次超时，在代码 Agent 中可能值得回退重算，在 LIVE 中却可能应该直接丢弃。

这类系统可以沿直播链路拆成几层。

实时数据面接收音视频、评论、礼物和指令，为每个事件设置 offset 与 deadline；

Agent 推理面理解输入、生成候选结果，允许超时、取消、模型替换和云边降级；

确定性发布面负责去重、权限和真正展示；

恢复控制面记录 Session、结果状态与发布记录。

这样的分层与 Managed Agents 的 `session / harness / sandbox` 解耦相似。

失败后，系统通常不回放所有遗漏的互动，而是从最新 offset 继续；迟到结果直接丢弃；边缘模型不可用时降级到云端、规则或静态提示；已经展示的错误字幕通过新的 correction event 更正，不能假装观众从未看到。恢复目标不是复原完整轨迹，而是在 deadline 内保持最新状态，并避免同一内容重复发布。

[BytePlus MediaLive 的 RTM 文档](https://docs.byteplus.com/en/docs/byteplus-media-live/docs-introduction-to-real-time-media) 和播放器能力中提到弱网优化、动态追帧以及必要时跳过旧帧。它讨论的不是 Agent 恢复，但背后的实时系统原则相同：当“完整处理历史”和“追上当前现场”冲突时，系统有时必须牺牲旧进度来保住实时性。

### 4.3 客服与流程 Agent：对话可以恢复，业务动作必须核对

客服 Agent 会跨多轮读取订单、更新工单、发券甚至退款。对话中断后可以从持久化 Session 继续，但工具超时后不能仅凭消息历史判断业务动作是否成功。

实践中，读取操作可以安全重放；工单更新等写操作应携带稳定 IdempotencyKey；退款状态不明时先按业务键查询，再决定复用结果、重试还是补偿；金额较高或无法确认时转人工。Temporal 式的 Durable Workflow 可以保存控制流程，而数据库和第三方服务中的真实状态才是动作是否完成的依据。

### 4.4 支付、礼物与交易 Agent：账本比 Context 更可信

资金场景不能通过覆盖旧快照来“恢复”，因为后续可能已经发生结算、提现或风控处理。可靠实现会使用不可变账本与全局唯一业务键，每条命令先检查是否已处理；状态不明时执行 reconciliation；需要撤销时追加退款或冲正记录，而不是删除原交易。

Agent 可以解释用户意图并提出候选动作，但金额校验、账户状态、权限和最终提交应由确定性服务完成。这里最能体现 DART 的问题：一段上游历史一旦被下游结算消费，就不能因为 Agent 改变了想法而随意重写。

### 4.5 SRE 与运营 Agent：先限制执行边界，再谈自动恢复

能够修改线上配置、扩缩容或处理故障的 Agent，环境部分可控，后果却很大。它需要将 Plan 与 Execute 分开：执行前记录当前状态、变更 diff、风险与 rollback plan；高风险动作经过审批；每次执行绑定 change ID；配置类变更用版本回滚，数据迁移、删除和外部通知则使用补偿或人工 Runbook。

一旦 Context 丢失或真实状态无法确认，正确动作往往不是“自主恢复后继续”，而是停止执行并重新读取系统事实。对 SRE Agent，恢复能力必须服从变更控制。

## 5. 收束成一套 Runtime 判断方法

把这些场景放在一起，Runtime 在失败后可以按一个固定顺序判断。这个顺序不是先找 Checkpoint，而是先找事实。

第一步，找到 Truth Anchor：代码看 Git 与测试，交易看账本，发布看回执，审核看 decision log，而不是相信模型对自己行为的描述。第二步，确定 Recovery Boundary：Context、Sandbox 和未提交的候选结果可以恢复，已经送达用户或被下游消费的事实通常只能核对、纠正或补偿。第三步，检查 Time Value：结果是否已经超过 deadline，迟到后是仍有价值、需要更正，还是应该直接丢弃。

完成这三步后，再判断失败发生在哪一层：只是模型计算失败，还是 Harness、Sandbox、Context 或业务动作失败？如果副作用尚未越过受控边界，可以 resume 或联合 rewind，并重新验证结果；如果副作用已经提交，就应先 reconcile，再决定复用、幂等重试或补偿；如果结果已经超过 deadline，则丢弃旧结果并继续最新事件；如果状态无法确认且风险不可接受，就必须停止自动推进。

最后还要做一次 DART 式检查：选中的恢复点会不会让已有下游结果失去合法来源？只有通过这一关，才比较哪个恢复点成本更低。

为了支持这套判断，企业 Runtime 不必一开始就实现庞大的“万能恢复框架”，但应保留几个稳定抽象：追加式 Session 记录发生过什么；用 RunID、StepID、ToolCallID 和 EffectID 关联同一次尝试；明确标注只读、幂等写、可补偿写与不可逆动作；声明哪些状态能快照、哪些只能查询；把 deadline 和 policy gate 放在执行路径上；最终以真实环境 outcome 验证成功，而不是相信 Agent 自己说“已经完成”。

## 结语：恢复的核心是时间与事实

对代码 Agent，Git、Sandbox 和测试让 Rewind 成为强有力的工具；对 LIVE 互动 Agent，过期结果没有价值，关键是 deadline、offset、去重和降级；对审核 Agent，决定必须可追踪、可覆盖、可申诉；对支付和礼物 Agent，账本比 Context 更可信；对 SRE Agent，可靠性来自严格的变更边界。

因此，一个企业级 Agent Runtime 不应承诺“任何失败都能恢复”。它真正需要回答的是：哪些状态可以恢复，哪些动作只能补偿，哪些结果过期后应该丢弃，以及哪些不确定性必须交给人。

可靠的 Agent 不是永远向前的 Agent，而是知道什么时候可以继续、什么时候必须回到可信历史，以及什么时候应该停下来。

---

## 主要参考资料

1. [AgentRewind: Recoverable Execution for Long-Horizon LLM Agents](https://arxiv.org/pdf/2608.14380)
2. [DART: Semantic Recoverability for Structured Tool Agents](https://arxiv.org/abs/2605.23311)
3. [DeltaBox: Efficient State Checkpointing for Computer-Use Agents](https://arxiv.org/abs/2605.22781)
4. [Magentic-One: A Generalist Multi-Agent System for Solving Complex Tasks](https://arxiv.org/abs/2411.04468)
5. [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
6. [Scaling Managed Agents: Decoupling the brain from the hands](https://www.anthropic.com/engineering/managed-agents)
7. [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
8. [LangGraph: Thinking in LangGraph](https://docs.langchain.com/oss/javascript/langgraph/thinking-in-langgraph)
9. [Temporal AI Engineering Patterns](https://go.temporal.io/platform-hub/ai-engineering/ai-patterns)
10. [TikTok InfiniEdge AI 1.1 and TikTok LIVE](https://developers.tiktok.com/blog/2025-infiniedge-ai-1-1-release)
11. [Rush MCP Server: Helping AI Understand Your Monorepo](https://developers.tiktok.com/blog/rush-mcp-server)
12. [BytePlus MediaLive product architecture](https://docs.byteplus.com/en/docs/byteplus-media-live/docs-product-overview)
13. [When Tools Become Prompts: Why Multi-Turn MCP Systems Break Traditional Security Assumptions](https://developers.tiktok.com/blog/when-tools-become-prompts)
14. [BytePlus MediaLive: Introduction to Real Time Media](https://docs.byteplus.com/en/docs/byteplus-media-live/docs-introduction-to-real-time-media)

## 写作说明

- 本文以公开论文和官方工程文章为依据，不代表 TikTok、Anthropic 或其他公司未公开的内部实现。
- 2026 年相关论文属于较新的 arXiv 预印本，其结论仍应结合后续同行评审与具体实验设置理解。
