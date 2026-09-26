---
title: "龙虾退潮后：锐评营销先行的 Agent 创业"
date: 2026-09-26
permalink: /posts/agent-messaging-tollbooth/
lang: zh-CN
translations:
  zh: /posts/agent-messaging-tollbooth/
  en: /posts/agent-messaging-tollbooth/en/
author_profile: false
read_time: true
excerpt: "借 Photon 观察 Agent 创业：消息接入服务能否成为基础设施，开源产品如何收费，热闹的生态又是谁在买单？"
tags:
  - 行业观察
---

龙虾热的时候，人人都在讨论 Agent 走进聊天界面干活了。

安装教程、模型账单、Mac mini 和各种自动化案例一起涌出来，仿佛只要给 Agent 足够多的权限，它很快就会变成每个人的数字员工。

热度一起来，产品还在找稳定场景，叙事已经先一步抵达未来。

本期节目的嘉宾是 [Photon](https://photon.codes/)。不是因为我想刻意针对它，而是想借它做个样本，一窥整个 Shipping Fast 式的幽默应用创业。我曾经也是被这些创业公司的营销洗脑的一员，现在想写这篇文章，是希望它能提供一点冷静思考和批判思维的价值。

Photon，是一个“聊天转接台”——开发者把自己做的 Agent 接到 Photon，Photon 再帮它接上 iMessage 之类的聊天软件，让用户能像发消息一样给 Agent 派活、收回复。

不知道你有没有看过, [《Clawdbot 是一场马斯克发动的中登炒作》](https://m.aitntnews.com/newDetail.html?newId=22138) ，和[《OpenClaw 不如狗一条》](https://funeralai.cc/test/r10/doubao-seed-2-1-pro-260628/articles/067/)，简单概括一下就是文中觉得龙虾的创新堪比让人在健身房里用手机让 Agent 写代码，闹麻了。

当然我们这可是能让agent接入imessage的，那可不一样了。问题是：**有用的接线服务，怎么就是 Agent 时代的基础设施？**

## Agent 是刚需，不等于每个入口都是刚需

Photon 的愿景文把故事讲得很顺：Agent 现在困在开发者工具和新 App 里；普通人不应该再下载一个应用；妈妈可以直接在 iMessage 里跟 Agent 对话。[《Introducing Spectrum》](https://photon.codes/blog/introducing-spectrum)

它博客里给出的具体方向也不少：个人助理、礼宾服务、客服、编程搭档、日程助理；还有一个跑在小芯片上的 MimiClaw，可以提醒待办、回答问题、记住用户之前说过的事，再通过 iMessage 找到它。[Photon 对 Agent 场景的介绍](https://photon.codes/blog/photon-vs-sendblue-choosing-an-imessage-api-for-ai-agents) · [MimiClaw 案例](https://photon.codes/blog/how-mimiclaw-put-a-pocket-ai-assistant-on-imessage)

但 Photon 卖给开发者的核心理由，其实不是“iMessage 里有个 Agent 很酷”，而是：别自己养 Mac、折腾 Apple 账号和消息转发，接上 Spectrum 就能上线。这个价值听起来很像基建，拆开看却有个尴尬问题：

如果产品还没找到用户，Photon 帮你把它接进五个聊天软件，也只是让一个没人用的 Agent 多了五个入口；如果已经有用户，真正决定他们留下来的，还是 Agent 能不能把事办好，而不是后面接的是谁家的消息管道。

至于“iMessage 是大家每天都在用的地方”，应该是吧？

而这篇文章写作不久前，腾讯 QClaw 宣布在 2026 年 12 月停止运营，并引导用户迁移到 WorkBuddy。腾讯称这是业务发展调整和资源整合。[QClaw 停运报道](https://www.ithome.com/1/006/528.htm) · [财新报道](https://companies.caixin.com/2026-09-24/102488349.html)

腾讯仍然在做 Agent，只是选择把产品和资源并到另一个入口里。

如果 Agent 产品本身、用户入口和团队资源都可能被大厂重新整合，那么独立的中间层凭什么默认能长期卡在中间？今天你替客户少写一段代码，明天那段代码可能就被框架顺手加进去了。

那小公司能怎么办？先营销赚了快钱积累一批人再等收购啊！

## 营销优先：卖的是接入，讲的是文明转型

关于收费：开发者可以下载免费的 Spectrum 代码，自己准备设备、号码并维护这条通道；也可以付钱让 Photon 帮忙托管和处理线路。官网列出的 Pro 是每月 25 美元，Business 是每条专用 iMessage 线路每月 250 美元。[定价页](https://photon.codes/pricing)

Photon 收费并不荒唐。客户买托管、线路和维护时间，完全可以算一笔成本账。自己跑 Mac 也不是零成本，蓝泡泡桥接、权限配置和系统升级都有维护负担。Photon 自己的对比文章也把它的卖点说得很直白：本地试验用自建方案；要做生产服务，就买托管线路。[BlueBubbles 与 Photon 对比](https://photon.codes/blog/the-path-from-bluebubbles-to-production-imessage-agents-on-photon)

这条线路里有人替你维护一条复杂、脆弱、还受 Apple 平台变化影响的消息链路，而且这不只是把一台 Mac 放在机房里替你开着。Photon 的工程复盘写到，他们的共享线路要在大量号码和消息之间判断“这条消息该送给哪个 Agent”；旧方案遇到过静默断连、消息路由错误和高峰期延迟，后来他们把消息接收改成先写入持久化事件日志，再处理归属和分发。[共享线路重构复盘](https://photon.codes/blog/how-we-rebuilt-our-shared-imessage-routing-to-handle-10m-messages-a-day) 对一个真有用户、不能漏消息的产品来说，这类故障处理、持续在线和线路维护，确实可能比自己临时拼一个桥接方案值钱得多。

建了桥，卖出去收过路费天经地义。

但前面也说过了，过路费最难解释的地方是为什么必须从你这里过？

所以 Photon 的博客不断宣布把 iMessage 接到新的框架：Hermes、NanoClaw、Mastra、Vercel Chat SDK、Convex。接一个框架，写一篇“现在它也能发 iMessage 了”；再接下一个，再写一篇。

看起来生态越来越大，框架越来越多，也不必然是繁荣。比如这个[Agent 框架开发实践研究](https://arxiv.org/abs/2512.01939)分析 10 种 Agent 框架、整理近 1.2 万条开发者讨论的研究发现，开发者面对不断增长的框架选择时，常常难判断哪个适合自己的需求。

框架本来该替开发者省事，但这波 Agent 框架经常先把模型调用、工具、记忆和流程各包一层，再给这层起一套自己的概念和 API。于是开发者先要选“该押哪家”，接着学它的写法；研究里反复出现：框架一升级，工具接口、状态管理和部署配置又得重新对。

这就是这波“生态繁荣”里很幽默的一幕：每家公司都说自己在降低开发门槛，开发者桌上却多了十几套框架、几十种集成和一长串版本兼容问题。说白了“Agent”这个标签下面，试点、套壳、接入层和真正解决业务问题的产品，很容易挤在同一张生态海报上。

Gartner 在 2025 年就提醒，许多 Agent 项目还停留在受炒作驱动的早期试验，并预测到 2027 年底，超过 40% 的 Agent 项目可能因成本、商业价值不清或风险控制不足而被取消。[Gartner 的预测](https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027)

AI 让“能发布的东西”涨得比“有人愿意长期用的东西”更快了。[AI 辅助软件开发中的 slop 研究](https://arxiv.org/abs/2603.27249)于是，框架适配越列越长，Photon 每接一家，就越像一份“我们已经站在生态中心”的宣传单。

还有 Photon 称每天处理千万级 iMessage API 调用，并在博客中列出 Rho、Vercel、Hermes、Ditto、FlipText 等名字。

当然了，公开资料没有拆分这些名字是付费客户、合作伙伴、集成案例还是社区使用者，也没有给出客户留存、续费率或收入结构。[Photon 的基础设施文章](https://photon.codes/blog/how-photon-built-one-of-the-most-stable-and-enterprise-ready-imessage-apis)

但数字是越来越大的，叙事是必须升格的。

“替开发者维护一条复杂的消息通道”。

“让 Agent 进入普通人的生活！”

“我们是 Agent 时代的基础设施！”

还有一个容易被跳过的问题：用户把消息发给托管 Agent，消息就会经过服务商的基础设施。Photon 的隐私政策列出 TLS、静态加密和访问控制，但我查看时没有找到 Reddit 上员工所说“消息缓存约一周”或“员工无法访问”的具体说明。该员工后续解释，访问限制靠政策和物理隔离，而不是 Photon 在技术上完全没有解密能力。[Photon 隐私政策](https://app.photon.codes/privacy-policy) · [Reddit 讨论](https://www.reddit.com/r/hermesagent/comments/1uayr7v/cybersecurity_for_hermes_ios_ux_imessage_matrix/)

底下别人建议隐私页面加上这句员工发言，我查了一下，到这篇博客写作的现在为止还没加。

## 讨论一下开源 Agent 创业：代码放出来以后，究竟卖什么？

Photon 把 Spectrum SDK 按 MIT 开源，同时把托管线路和云服务作为收费产品。它不是孤例，而是近十年开发者工具创业的一种常见结构：先把代码开放出来降低尝试门槛，再把托管、协作、可观测性、治理或支持做成付费层。

先看 [Supabase 对“要不要开源公司”的讨论](https://supabase.com/blog/should-i-open-source-my-company)：开源能让开发者先试、自己部署、检查代码，也能让社区贡献适配和修复；它同时带来维护负担，而且成功后还要面对云厂商凭更强分发能力托管同类产品的风险。这个案例提醒创业者：开源能帮你把门打开，让人在社区里有方向迭代，但不能替你守住门里的生意。

再看 [n8n 的 Sustainable Use License 说明](https://blog.n8n.io/announcing-new-sustainable-use-license/)。n8n 明确选择 fair-code：源代码可以查看、修改和在一定范围内使用，但商业使用有边界。它的理由也很直白：如果云服务商拿走开源项目创造的价值，原团队可能没有足够收入持续维护，所以开源创业常常要在“尽量开放、扩大采用”和“限制别人免费复制商业化”之间做选择。

放到 Agent 应用创业上，问题就更实际了：开源让用户先把 Agent 下载下来，在自己的电脑上跑通；公司什么时候能让他掏钱？通常不是因为代码突然变贵，而是因为试用变成了日常工作——Agent 得整晚在线，团队要一起用，账号权限不能串，出错后得查清它读了什么、做了什么。谁把这些事长期做稳，谁才有机会从“项目”卖成“服务”。

可如果收费理由只是“一键部署”或“替你接几个模型和工具”，用户一旦证明需求，云平台和模型公司就有机会把它顺手打包；代码开源后，别的团队也能照着做。开源带来的星星和下载量，最多证明有人愿意试，不能证明有人会续费。真正要看的，是用户把业务放进去以后，迁走会不会丢掉可靠运行、团队流程或责任保障——没有这些，云托管就只是方便；有了这些，才开始像一门能长期收钱的生意。

回到 Photon，定位确实清楚，但也是在大公司的阴影下活着。iMessage 还有一层特殊限制：接入能力受 Apple 的封闭平台约束。Photon 可以比单个开发者更专业地维护线路，却不能决定 Apple 未来允许什么、封禁什么或改变什么。多平台接入能降低对单一渠道的依赖，但也会让客户问一个实际问题：我买的是一套长期通信基础设施，还是今天恰好省了接线时间的托管服务？

所以，开源不是天然的护城河，但它一定是天然的引流方式。

## 谁在承担 Agent 的泡沫？

Photon 现在卖的东西能省开发时间、解决线路维护的麻烦，收费本身没什么问题。类似的还有 [Sendblue](https://www.sendblue.com/)、[LoopMessage](https://loopmessage.com/) 和 [Claw Messenger](https://www.clawmessenger.com/)。它们不是完全相同的产品，也不能一概判成“割韭菜”；但商业结构相似：Agent 本体由别人做，聊天平台由苹果或其他平台掌握，中间的服务商负责把消息送进去、再把回复送出来，向开发者收一笔省事费。

而“让软件通过 API 收发消息”根本跟 Agent 没啥关系。Twilio 2008 年成立时，做的就是把复杂的电信网络变成开发者可以调用的云服务；它的可编程消息 API 让应用收发短信，早已支撑起客服通知、预约提醒和双向沟通等生意。[Twilio 公司历史](https://www.twilio.com/en-us/company) · [Twilio 可编程消息资料](https://investors.twilio.com/static-files/ab80b58f-a26d-473e-956c-4fccb39a14d0)

Photon 把 CPaaS 那套老生意搬过来，再专门解决 iMessage 这条没有通用公开 Bot API、需要绕过设备和线路维护的窄通道。这里当然有真实的工程差异，但加上 agent 之后是不是瞬间感觉老女人颇有姿色了呢？

而且对比其他项目，赚开发者的钱总比赚 C 端客户们的钱更稳定点不是吗？生意的好坏如果取决于站在链条的哪一层，那最底端吃不到油水、要被模型更新冲烂的 AI 应用，就应该卡在这里，教育开发者们别掉队，这种新玩法你应该付钱尝试！

到底是谁在做基础设施，谁又在替这场热潮交学费？这是个悲哀的循环。

至少踏上了这条路的，我希望他不是没验证商业模式的新的创业开发者；而是那些待在传统行业里赚到了钱、想释放 Agent 能力的人，突然看到 iMessage 能接入：多么不可思议！这样模型、云服务、数据和渠道一层层买单下来，也总算 Agent 为他创造出了价值。

---

*稿件说明：本文是作者基于公开资料所作的评论与商业模式分析，文中对 Photon 的评价属于观点，不构成对 Photon 或其员工存在违法、欺诈、故意误导等行为的事实指控。涉及产品功能、客户案例、调用量、可靠性及隐私政策的陈述，均以文中链接的公开来源为依据；厂商自行公布的数据已注明为厂商说法。相关信息可能随时间变化，如有更新应以来源页面及公司后续公开说明为准。*
