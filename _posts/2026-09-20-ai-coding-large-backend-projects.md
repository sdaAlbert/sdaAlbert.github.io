---
title: "AI Coding 人机协作研究：新的编程能力"
date: 2026-09-20
permalink: /posts/ai-coding-large-backend-projects/
lang: zh-CN
translations:
  zh: /posts/ai-coding-large-backend-projects/
  en: /posts/ai-coding-large-backend-projects/en/
author_profile: false
read_time: true
excerpt: "从最小开发闭环、真实后端案例和个人工作节奏出发，讨论如何用 Coding Agent 加速大型项目，同时控制测试、审查、迁移和并行开发风险。"
tags:
  - AI Coding
  - Coding Agents
  - Backend Engineering
---

## 1. 代码生成越快开发反而越慢

AI Coding 的宣传常把“生成代码更快”说成“开发更快”。两者不是一回事。

METR 对 16 名有经验的开源维护者做了 246 个真实任务的随机实验。受试者原本预计 AI 能让任务快 24%，实际却慢了 19%。这个结果不能代表今天所有模型，但它提醒我们：熟悉代码库、需要高质量评审的任务，可能被上下文查找和返工拖慢。[METR 原始研究](https://metr.org/Early_2025_AI_Experienced_OS_Devs_Study-paper.pdf)

社区长期使用者反复提到计划文档、测试先行和人工最终检查。Simon Willison 将 coding agent 概括为“人提出任务，代理循环执行和测试，人再用领域知识纠正”。[观察](https://feeds.simonwillison.net/2025/Jun/18/coding-agents/)

往小里说，我觉得应该关注怎样把一个需求变成可验证、可审查、可合并的变更。

往大里说，我觉得对整个开发的掌控更是重要。考虑到之后的工作岗位边界的消失会演变成驾驭一堆ai的项目制，让我觉得不断学习怎么跟ai协作是每天都应该做的事情，于是我写了这篇blog。



## 2. AI coding的一个最小闭环

大规模代码没有任何一个人或上下文窗口能完整装下。代理遇到范围过大的任务，通常会继续读文件，直到忘记前面的约束，解决办法是先把每次修改需要理解的范围变小。


一个实用做法是模块化单体：系统一起部署，内部切成几个有边界的模块。比如一个带用户、订单、支付和通知的后端项目，可以这样组织：

```text
my-service/
├── CLAUDE.md                 # 全仓库规则，保持简短
├── docs/ARCHITECTURE.md      # 模块、依赖方向、数据位置
├── docs/decisions/           # 重要决策和被否决的方案
├── scripts/verify.sh         # 一分钟内的快速检查
├── scripts/verify-full.sh    # 全量测试和集成检查
├── src/
│   ├── shared/               # 共享类型、错误和工具，不放业务逻辑
│   ├── users/                # 用户和收货信息
│   │   ├── CLAUDE.md
│   │   ├── api.py            # 对外接口，其他模块只能从这里引用
│   │   └── tests/
│   ├── orders/               # 订单和订单状态
│   │   ├── CLAUDE.md
│   │   ├── api.py
│   │   └── tests/
│   ├── payments/             # 支付回调和幂等处理
│   │   ├── CLAUDE.md
│   │   ├── api.py
│   │   └── tests/
│   ├── jobs/                 # 重试和异步任务
│   └── notifications/        # 支付和订单通知
└── tests/protected/          # 跨模块不变量测试
```

依赖检查工具负责拦截跨模块访问内部实现。快速检查控制在一分钟内，全量测试单独运行。

再手写一个模范模块，让新模块照着它的接口、错误处理和测试方式做。一份真实代码比十页规范管用，因为 Agent 会复制它见过的代码形状。

拿一个真实的跨模块功能举例：接入支付成功回调。它会碰到 `payments`、`orders`、`jobs` 和 `notifications`，还需要新增一张支付事件表。

第一步是我自己写一页需求，不让 Agent 代写。写的时候才会发现，重复回调、乱序回调和通知失败之后怎么办，原本都没有想清楚。最后的 SPEC 大概是这样：

```text
# SPEC：支付成功回调

目标：合法回调把订单从 pending 改成 paid，并发送一次通知。

规则：
- 当签名合法且订单未支付时，系统应记录事件、更新订单、创建通知任务。
- 当签名不合法时，系统应返回 401，订单和库存保持不变。
- 当同一事件重复到达时，系统应返回成功，但不能重复扣库存、发货或通知。
- 当通知失败时，系统应重试通知，不能重新处理支付。

不做：暂不处理退款回调，不改已有支付方式。

影响范围：payments、orders、jobs、notifications；新增 payment_events 表，迁移必须可回滚。

完成标准：受保护测试和全量检查通过；在 staging 手动发送正常、重复、乱序回调。
```

第二步从仓库根目录启动会话，让 Agent 先读 `ARCHITECTURE.md` 和四个模块的 `api.py`，再把计划写进文件。我只检查四件事：有没有改范围外的模块，迁移能不能回滚，有没有新增依赖，有没有绕过公共接口。计划写进文件还有一个好处：长会话压缩后，聊天可能丢，计划仍在。

第三步先写不变量测试，再写实现。这个功能的不变量是：同一个支付事件无论到达多少次，订单最多完成一次状态迁移，通知最多创建一条。可以让 Agent 起草属性测试，随机生成重复、乱序和网络重试；但不变量由人决定，测试放进 `tests/protected/`，Agent 能读，不能为了让实现通过而修改。

第四步分段实现。顺序是共享事件类型、订单状态迁移、签名校验和事件去重、通知重试，最后才是数据库迁移。每段开一个新会话，单模块任务从模块目录启动，跨模块任务从仓库根目录启动。快速检查通过后立刻看 diff、提交，下一段出问题时可以直接回到上一个稳定点。

上下文也要设预算。跨模块调研交给子 Agent，它只返回结论和文件位置；主会话不要把搜索过程、失败尝试和上百个文件一起背着走。同一个问题纠正两次仍不对，就结束会话，把已经确认的事实写进新提示重新开始。

第五步换一个全新上下文审查整个 diff，对照 SPEC 只报正确性、安全性和范围外改动，不讨论格式。然后我自己读回调入口、订单状态迁移、事件唯一约束和通知发送点。全量检查通过后，在 staging 手动发送正常、重复和乱序回调；这个 Agent 没见过的场景，就是最后一道隐藏测试。

第六步把错误沉淀成机制。Agent 绕过模块接口，就加依赖检查；吞掉异常，就让 lint 拦；重复创建通知，就增加数据库唯一约束和集成测试。下一次再遇到同类任务，工具会先替人发现问题。[Thomas Wiegold：How My Agentic Coding Workflow Changed in a Year](https://thomas-wiegold.com/blog/agentic-coding-workflow-shorter-prompts/)、[TDD 工作流讨论](https://www.reddit.com/r/ClaudeCode/comments/1qd64xx/tdd_workflows_with_claude_code_whats_actually/)



## 3. 工作场景时该怎么控制：浅显举例

个人玩具项目可以把 AI 用得更激进。Peter Steinberger 的做法是先把核心能力做成 CLI，自己运行、感受结果，再扩展界面；他同时维护一个主项目和几个卫星项目，把可以等待的任务交给代理。这里可以让代理连续做较大的重构，但每次仍保留可运行版本和提交记录。个人项目的反馈来自作者本人，所以需求可以边用边改；限流、错误处理、环境变量、备份和 HTTPS 仍要主动检查。[Peter 的实践](https://steipete.me/posts/2025/shipping-at-inference-speed)

Robert Nicuta 的做法更适合小型长期项目：每次会话先交代项目、当前状态、本次任务、约束和成功标准，再开始改代码；他坚持接口和测试先于实现。Nemanja Jeremenkovic 也把 Claude Code 当作主要开发环境，但保留传统 IDE 做视觉调试和数据库检查，并明确承认这种方式更适合技术方向已经清楚、问题边界明确的人。两人的共同点不是“全程自动化”，而是让每次会话从一个可审查的上下文开始。[Robert Nicuta 的工作流](https://robertnicuta.com/en/blog/how-i-code-with-claude-code)、[Nemanja Jeremenkovic 的工作流](https://www.jeremenkovic.com/writing/claude-code-as-ide-2026-workflow)



开源 PR 的约束来自维护者。贡献者应该先读近期 PR、贡献指南、代码所有者和测试方式，再围绕一个 Issue 复现问题。代理可以帮助定位调用链、起草测试和改一处实现，但 PR 应保持小而单一；提交前要逐行读测试，确认没有为了让测试通过而改变公共行为。`noslop-oss` 要求检查 AI 生成的测试和 PR 模板；Alibaba 的贡献规范要求披露 AI 使用，提交者必须自己理解代码并回答 review，不能把代理生成的解释直接转发给维护者。[noslop-oss](https://github.com/omkar-foss/noslop-oss)、[Alibaba 规范](https://github.com/alibaba/open-code-review/blob/main/CONTRIBUTING.md)



公司生产代码还要增加责任链，尤其项目不能因为人员变动而失控。以一个大型后端模块为例，主代理只在自己的 worktree 中改动；调研子代理只返回结论，不直接写主分支；审查子代理拿到独立上下文和 SPEC；CI 负责快速检查、全量测试、契约测试和安全扫描；发布前由代码所有者确认迁移、凭证、监控和回滚。

Boris Cherny 分享过团队把 `CLAUDE.md` 放进仓库，持续把错误经验补回规则，并用 hooks、子代理和验证流程减少重复问题；PostHog 的 AI 政策则明确反对把未理解的 AI 输出直接变成 issue 或 PR。[Boris 的团队实践](https://www.reddit.com/r/AI_Agents/comments/1q3xw15/bcherny_creator_of_claude_code_shares_how_i_use/)、[PostHog AI policy](https://github.com/PostHog/posthog/blob/master/AI_POLICY.md)

而Moon Pixels 的实践有一个很有用的反思：早期把所有流程都塞进 `AGENTS.md`，后来改成“规则文件保持短，重复行为放进 skills，阶段和批准点单独控制”。这也说明社区方案可以借鉴结构，不能整套照搬。[Moon Pixels：The agentic coding workflow](https://moonpixels.co.uk/blog/the-agentic-coding-workflow-i-use-in-opencode/)



而当生产过程中项目越来越大，重构和大规模迁移都要单独降级处理。SWE Refactor Bench 在 520 次整仓迁移中，只有 28 次通过“迁移确实发生、行为测试通过、独立 Agent 能发现隐藏变化”这三道检查。这时候要注意：先把机械替换交给确定性变换工具，Agent 负责写和审变换脚本；先在少量文件上试跑，再扩大范围。需要判断的部分逐个处理，每个放进独立 worktree。

迁移前还要留下旧实现的对照结果。把关键输入输出记录成黄金样本，迁移后用同样输入比较新旧结果；系统保持可运行，一个模块一个模块替换，不能全部改完再看能否启动。Anthropic 用 GCC 作为已知正确的编译器来切分失败，让不同 Agent 处理不同文件；这比让十几个 Agent 同时修同一个整体问题更有效。[SWE Refactor Bench](https://arxiv.org/abs/2608.23564)、[Anthropic：Building a C compiler with a team of parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler)

多 Agent 并行也只在任务真正独立时划算。一个任务一个 worktree，协调者由人担任：人划边界、定合并顺序，保证两个 Agent 不改同一个文件。大型仓库可以只检出任务需要的目录，依赖目录共享；任务拆不开时，并行只会制造冲突和重复修复。

人不可能读完大仓库，也不需要读完。需要完整掌握的是架构地图、模块公共接口、迁移、安全路径和新增依赖，其余内容抽样检查。定期让 Agent 解释模块当前实现，再和架构文档对照，发现漂移就更新代码约束或测试；被否决的方案也要留下记录，避免几个月后被 Agent 重新提出来。



三种场景都不能省略四件事：范围清楚，改动可回退，验证可复现，提交者能解释结果。项目越接近真实用户，权限、审计和审批越不能交给默认配置。

## 4. 个人一天不同时间怎么分配给 AI Coding 提高效率

一天里最适合交给 AI 的任务，取决于两个变量：你当时还有多少注意力，以及任务多久能得到可靠反馈。把人的清醒时间留给判断，把等待时间交给可验证的循环。

早上或刚开始一个新任务时，人应该先掌握方向。阅读需求、确认数据边界、决定是否改接口、判断迁移能不能回滚，这些工作可以让最强模型参与调查和提出方案，但决策必须由人做。陌生仓库、跨模块改动、权限和并发问题，也适合让强模型先读代码、列出风险，再写设计文档。Peter Steinberger 记录过，Codex 经常先读 10–15 分钟才开始修改，Opus 则更快进入编辑；前者单次运行可能更慢，却可能少掉一轮“修复这个修复”。模型的等待时间只有在你能同时做别的事时才有价值。[Peter Steinberger：Shipping at Inference-Speed](https://steipete.me/posts/2025/shipping-at-inference-speed)

设计通过后，把工作切成一条条能运行的竖切链路，交给一个主代理执行：改数据模型、接口、测试和必要的文档，完成后跑验证。中档模型适合这段工作，前提是任务边界、验收命令和禁止事项已经写清楚。简单重命名、格式化、补重复测试、生成文档，可以交给更快的模型。失败两次还说不清原因，或者代理开始改动无关文件，就停止当前循环，回到强模型重新分析，不要继续追加提示词把上下文越堆越乱。

Boris Cherny 的公开工作流里，同时运行多个会话，但并不是把同一个功能拆给五个代理互相覆盖。他把会话分到独立任务，先计划，再执行；提交、格式化和验证被封装成命令或 hooks，并给代理提供测试、浏览器或模拟器这样的反馈工具。他反复强调，代理必须有办法验证自己的结果。对个人项目，我会把五个会话视为上限参考，而不是默认配置：一个主任务、一个调研任务、一个审查任务已经足够覆盖大多数功能。[Boris Cherny 的公开经验](https://www.reddit.com/r/AI_Agents/comments/1q3xw15/bcherny_creator_of_claude_code_shares_how_i_use/)

Mitchell Hashimoto 的节奏和 Boris 不同。他先用 Agent 重做自己熟悉的工作，摸清哪些任务可以放心委托；下班前让 Agent 做调研、Issue 分类和低风险准备，第二天获得一个 warm start；每次 Agent 犯错，就补 `AGENTS.md` 或写一个能自动发现错误的工具。他的目标是“始终有一个 Agent 在运行”，但实际有效时间只有普通工作日的 10%–20%，而且他目前更偏好一个后台 Agent，而不是同时维护一群 Agent。[Mitchell Hashimoto：My AI Adoption Journey](https://mitchellh.com/writing/my-ai-adoption-journey)

因此，并行代理适合互不依赖的任务：一个补测试，一个查文档，一个处理独立模块。涉及同一组文件、同一个数据库迁移或同一条业务规则时，优先串行。Addy Osmani 对“循环工程”的总结也要求代理拥有明确的停止条件和约束；代理数量增加后，人的审查负担会一起增加。[Practical Loop Engineering](https://addyosmani.com/blog/practical-loop-engineering/)

午间、会议间隙或等待 CI 时，可以把机器变成后台施工队：让代理运行测试、整理日志、更新文档、准备一个独立分支的重构草案。任务要带上范围、完成条件、验证命令和停止条件，不能只写“继续优化”。晚上也可以让代理长时间运行，但只允许访问隔离工作区，不允许直接部署、删库或修改生产配置。第二天先看 `git diff`、测试日志和失败原因，再决定是否合并。

这里可以采用 Mitchell 的“下班前启动、第二天接手”模式，但只安排高把握、低后果的任务：Issue 分类、调用链调研、补充测试、生成迁移草案。不要把模糊需求和生产权限留给夜间 Agent。后台任务的价值是减少第二天的冷启动，不是制造更多未审查的代码。

手机适合做控制面，不适合做主要工作台。通过远程机器、SSH、tmux 或类似工具，可以在手机上启动任务、查看状态、补充短说明、批准低风险步骤；阅读大段差异、审查权限逻辑、确认数据库迁移和生产发布，仍然要回到大屏幕。移动端实践普遍把手机定位为监控、委派和决策入口，而不是笔记本的替代品；在小屏幕和注意力分散时批准高后果操作，风险尤其高。[Tactic Remote：From Desk to Couch](https://tacticremote.com/blog/2026-02-28-from-desk-to-couch-mobile-developer-workflow/)、[Axios：Codex comes to your phone](https://www.axios.com/2026/05/14/openai-brings-codex-to-your-phone)

最后用交付记录校准分配，而不是凭感觉比较模型速度：

```text
总交付时间 = 研究 + 生成 + 等待 + 审查 + 返工 + CI/PR 往返
```

强模型的收益通常来自更少的错误计划和返工；快模型的收益来自把机械工作塞进等待窗口。Addy 建议用一个主代理配合少量审查代理，也提醒多代理会带来额外的认知负担。Simon Willison 的判断更直接：代理能否发挥作用，取决于使用者是否理解任务、会检查结果并纠正错误。[Simon Willison：Coding agents require skilled operators](https://feeds.simonwillison.net/2025/Jun/18/coding-agents/)

## 5. 建立自己的 Agent 工具箱

实践最后可以收敛到个人，一套围绕 Agent 的工具箱：短规则和架构地图、可重复的 skills、验证脚本和 hooks、只读的外部工具、隔离的 worktree、独立审查的 subagent，以及可以在等待时运行的后台任务。模型只是其中负责推理的一环。

这套工具箱应该从真实错误中长出来。代理连续跑错测试，就补一个快速检查脚本；总是越过模块边界，就加依赖 lint；每次都要重新解释发布流程，就写成 skill；需要查 GitHub Issue、staging 日志或浏览器状态，才接入对应 MCP。重复三次的人工提醒，通常已经说明它应该变成工具或规则。

Skills 适合封装“输入—步骤—验证—输出”的流程，例如排查故障、生成迁移草案、审查 PR。Hooks 和脚本适合确定性动作，例如格式化、阻止危险路径、提交前跑测试。MCP 只连接 Agent 当前确实需要的外部事实，并默认只读；工具越多，上下文和权限面越大。Subagent 适合调研、对照和审查，不适合和主代理抢同一批文件；并行时用 worktree 隔离。

本质上说，OpenAI 的 Codex harness 和 Anthropic 的 Skills 实践都在做同一件事：让代码、测试、日志、指标和操作边界对 Agent 可见、可执行、可验证。个人不需要复制大公司的整套系统，先把最常见的一次返工变成一个工具，再观察它是否真的减少了下一次返工。[OpenAI：Harness engineering](https://openai.com/index/harness-engineering/)、[Anthropic：Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)

工具箱的验收标准也很简单：新会话能否少解释一遍，Agent 能否更早发现错误，审查者能否更快定位风险，任务能否在隔离环境中安全停止。达不到这些结果的配置，就删掉，不要为了“看起来像专业工作流”继续堆东西。

## 结论

AI Coding 的效率来自任务设计，而不只是模型能力。先把需求变成任务包，再让代理研究、实现、验证和审查；把最强模型留给高风险判断，把快模型用于机械工作；用真实 PR 的总耗时和返工记录验证收益。

最终可合并的 PR，才是产出单位。代码行数、提示词长度和代理调用次数，都不能代替这个指标。

## 调研材料

- [METR：Experienced Open-Source Developer Productivity Study](https://metr.org/Early_2025_AI_Experienced_OS_Devs_Study-paper.pdf)
- [Simon Willison：Coding agents require skilled operators](https://feeds.simonwillison.net/2025/Jun/18/coding-agents/)
- [Reddit：Codex personal project workflow](https://www.reddit.com/r/codex/comments/1tf4s07/my_best_workflow_so_far_for_building_projects/)
- [Reddit：TDD workflows with Claude Code](https://www.reddit.com/r/ClaudeCode/comments/1qd64xx/tdd_workflows_with_claude_code_whats_actually/)
- [GitHub：codex-in-claude](https://github.com/briandconnelly/codex-in-claude)
- [GitHub：awesome-agent-conventions](https://github.com/ItamarZand88/awesome-agent-conventions)
- [GitHub：agent-skills](https://github.com/addyosmani/agent-skills)
- [PromptForge：AGENTS.md best practices](https://github.com/mbagalman/PromptForge/blob/main/guides/agents-md-best-practices-2026.md)
- [Thomas Wiegold：How My Agentic Coding Workflow Changed in a Year](https://thomas-wiegold.com/blog/agentic-coding-workflow-shorter-prompts/)
- [Peter Steinberger：Shipping at Inference-Speed](https://steipete.me/posts/2025/shipping-at-inference-speed)
- [Robert Nicuta：How I code with Claude Code](https://robertnicuta.com/en/blog/how-i-code-with-claude-code)
- [Nemanja Jeremenkovic：Claude Code as IDE](https://www.jeremenkovic.com/writing/claude-code-as-ide-2026-workflow)
- [Mitchell Hashimoto：My AI Adoption Journey](https://mitchellh.com/writing/my-ai-adoption-journey)
- [Moon Pixels：The agentic coding workflow](https://moonpixels.co.uk/blog/the-agentic-coding-workflow-i-use-in-opencode/)
- [Moon Pixels：How my workflow changed in three months](https://moonpixels.co.uk/blog/how-my-agentic-coding-workflow-changed-in-three-months/)
- [SWE Refactor Bench：Whole-Repository Stack Migration](https://arxiv.org/abs/2608.23564)
- [Anthropic：Building a C compiler with a team of parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler)
- [Boris Cherny workflow notes](https://github.com/diulama/claude-code-tips/blob/main/guides/boris-cherny-workflow.md)
- [Reddit：Boris Cherny shares his Claude Code workflow](https://www.reddit.com/r/AI_Agents/comments/1q3xw15/bcherny_creator_of_claude_code_shares_how_i_use/)
- [Addy Osmani：Practical Loop Engineering](https://addyosmani.com/blog/practical-loop-engineering/)
- [Addy Osmani：Agent Skills](https://addyosmani.com/blog/agent-skills/)
- [Addy Osmani：Agentic Code Review](https://addyosmani.com/blog/agentic-code-review/)
- [Anthropic：Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [Anthropic：Writing effective tools for AI agents](https://www.anthropic.com/engineering/writing-tools-for-agents)
- [Anthropic：Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- [OpenAI：Harness engineering](https://openai.com/index/harness-engineering/)
- [OpenAI：Unlocking the Codex harness](https://openai.com/index/unlocking-the-codex-harness/)
- [Model routing for coding agents](https://admix.software/blog/cut-ai-coding-agent-costs-model-routing)
- [Tactic Remote：From Desk to Couch](https://tacticremote.com/blog/2026-02-28-from-desk-to-couch-mobile-developer-workflow/)
- [Axios：Codex comes to your phone](https://www.axios.com/2026/05/14/openai-brings-codex-to-your-phone)
- [GitHub：noslop-oss contribution checklist](https://github.com/omkar-foss/noslop-oss)
- [Alibaba：open-code-review contribution policy](https://github.com/alibaba/open-code-review/blob/main/CONTRIBUTING.md)
- [PostHog：AI policy](https://github.com/PostHog/posthog/blob/master/AI_POLICY.md)
