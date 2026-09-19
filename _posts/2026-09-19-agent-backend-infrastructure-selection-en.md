---
title: "How Should We Choose Infrastructure for an Agent Backend? From Data Flows to Engineering Boundaries"
date: 2026-09-19
permalink: /posts/agent-backend-infrastructure-selection/en/
lang: en
translations:
  zh: /posts/agent-backend-infrastructure-selection/
  en: /posts/agent-backend-infrastructure-selection/en/
author_profile: false
read_time: true
excerpt: "Starting from six data flows, this article explains how an Agent backend grows from a relational database into queues, event streams, workflows, and sandboxes."
tags:
  - LLM Agents
  - Agent Backend
  - System Design
---

My previous article discussed why Agents need durable state, how to deal with tool calls whose outcomes are unclear, and why recovery cannot trust Context alone.

This article moves one step further into backend design: once an Agent task enters the system, what different data flows does it create? What throughput, latency, transaction, and retention requirements do those flows have? Only after answering those questions do RDS, Redis, Kafka, and workflow systems have a clear place.

That also means this article will not prescribe a “standard Agent stack.” Public designs from mature products show that they tend to fix the interfaces between sessions, execution environments, events, and permissions first. The underlying storage can then be replaced.

## 1. A task entering the backend becomes six different flows

From the moment a user submits a task, the backend is doing more than dropping one message onto a Worker.

```text
User request
  ↓
Create Run ───────────────── state flow
  ↓
Create pending steps ──────── scheduling flow
  ↓
Assign Worker and environment  resource flow
  ↓
Model and tool results ────── event flow
  ↓
Save files and artifacts ──── artifact flow
  ↓
Serve UI, audit, and evals ── projection and observability flow
```

The state flow answers: “What is the task’s current status?” For example, running, waiting for approval, or completed.

The scheduling flow answers: “Who should perform the next step?” It handles queuing, rate limiting, claiming, and retries.

The resource flow answers: “Where should the work run?” It manages the creation and cleanup of Workers, containers, browsers, and sandboxes. A Worker is the background process that performs the task. A sandbox is a temporary execution environment isolated from the main system.

The event flow answers: “What just happened?” Examples include a tool call completing, an approval arriving, or a Run changing state.

The artifact flow stores the large files produced by execution: code patches, web snapshots, audio and video, and generated files.

The projection and observability flow shows the process to people. Users see progress there. Engineers inspect logs, metrics, and traces there. A trace is the record left as one request travels through several services.

At small scale, these six flows can share a small number of components. As the system grows, the rest of this article follows one path:

- Section 3 handles the state flow: keep the task’s ledger clear.
- Section 4 separates the scheduling flow: stop many Workers from competing for the database.
- Section 5 expands the event and projection flows: let multiple downstream systems see the same events.
- Section 6 handles the resource flow: release Workers during long waits and manage sandboxes.
- Artifact and observability flows run through all four stages. Move large files out of the primary database, and move growing diagnostic data into dedicated systems.

Every technology choice should therefore answer one question: which flow is this component serving? If the answer is unclear, the component may not be needed yet.

## 2. Two public systems that separate these flows

Let us look at only two examples. ByteDance’s public project is useful for seeing where different kinds of data go. Tencent’s public design is useful for seeing how communication and execution are separated.

### ByteDance: separate structured data, analytics, and asynchronous work

Coze Loop does not put every kind of data into one database.

- MySQL stores users, permissions, and evaluation tasks. It is a relational database, suited to structured data that needs transactions.
- ClickHouse stores large volumes of traces and evaluation details. It behaves more like an analytics warehouse: good at scanning large datasets, but not intended to handle every business transaction.[Coze Loop Architecture](https://github.com/coze-dev/coze-loop/blob/main/ARCHITECTURE.md)

Redis is used for caches and short-lived data. It is fast, but it should not automatically become the only archive of business facts. MinIO is object storage for files. RocketMQ is a message queue for telling background services to do work asynchronously.

Mapped back to the six flows: MySQL carries the state flow, RocketMQ carries the scheduling flow, ClickHouse carries observability analysis, and MinIO carries the artifact flow. Redis accelerates some short-lived access paths.

This does not mean a small team should deploy all five components on day one. The useful lesson is the order of separation: start with a relational database; move files to object storage when they grow; add an analytics system when reports slow down the primary database; add a queue when background work needs to scale independently.

### Tencent: keep communication alive, start expensive execution per task

Tencent Cloud’s public Agent Runtime focuses on a different problem: user connections need to stay online, while code or browser environments are needed only while a task is executing. If both are tied to the same instance, an expensive execution environment has to stay alive just to keep the connection open.

Its design gives communication to a persistent gateway and uses a message queue to wake a sandbox. A sandbox can be created, paused, and resumed per task.[Tencent Cloud Agent Runtime](https://developer.cloud.tencent.com/article/2686331) Tencent’s open-source CubeSandbox goes further by using lightweight virtual machines to isolate untrusted code and snapshots to reduce restart time.[CubeSandbox Architecture](https://github.com/TencentCloud/CubeSandbox/blob/master/docs/architecture/overview.md)

Here, the message queue serves the scheduling flow and the sandbox service serves the resource flow. Redis records coordination details, such as which sandbox is currently in use. It is not the Agent’s business database.

Together, the two examples show the main idea: ByteDance separates storage by data purpose, while Tencent separates execution by resource lifetime. Neither starts with a shopping list of technologies. Both first identify a flow that has developed its own pressure.

## 3. Case one: the task volume is modest, so keep the ledger clear

This stage addresses the state flow first. The goal is simple: even if a Worker is gone, the system can still answer where the task is.

Start with a rough estimate.

Suppose the system runs 100,000 Runs per day. Each Run changes state ten times on average. That is one million writes per day, or about 12 writes per second on average. Even if the peak is ten times the average, it is still about 120 writes per second.

This is an estimate, not a performance promise for any database. The point is to calculate the order of magnitude before discussing architecture. A common system-design estimate is straightforward: divide daily requests by 86,400 to get average requests per second, then estimate peak traffic, data size, and retention separately.[System Design Space estimation guide](https://system-design.space/en/chapter/back-of-envelope-estimation/)

At this stage, PostgreSQL or MySQL is often enough. Both are relational databases: data is stored in tables, and transactions can ensure that several changes either succeed together or fail together. Think of one as a ledger. It records the current Run state, approvals, and budget usage.

RDS also appears frequently in architecture diagrams. It is usually not a different kind of database. It is a cloud service that manages PostgreSQL, MySQL, or another database for you. The platform takes on part of the work for backups, failover, and upgrades.

When the task volume is modest, Workers can claim pending work directly from the database. When creating a Run, write a “waiting to be dispatched” record in the same transaction. This record is commonly called an Outbox. It is like a shipping slip inside the ledger, preventing the situation where the ledger says the task exists but no delivery request was created.[AWS Transactional Outbox](https://docs.aws.amazon.com/en_en/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html)

When should this design change? Look at symptoms, not slogans:

- Workers keep querying the database just to compete for work.
- Claiming locks begin to slow down product queries.
- Retries, priorities, and delayed execution make the SQL increasingly complex.
- Adding Workers no longer increases throughput.

If these symptoms have not appeared, do not add another component yet.

### The early stage still needs two supporting flows

Large files should go to object storage. Think of object storage as a cloud warehouse built for files; the database keeps only the file address.

Web snapshots, audio and video clips, code patches, model inputs, and tool outputs can be much larger than a state record. They can also have different lifetimes and access permissions. Store them in object storage, and keep only references, hashes, versions, and permissions in the Run. During recovery, retrieving the same input avoids database bloat and proves which version of the material informed the model’s decision.

Logs and traces should go to an observability system. SSE, WebSockets, and polling show a projection of the Run; they should not be the source of truth. If a connection breaks, the frontend should be able to reconstruct progress from durable state.

Logs should not be inspected only by container. One execution should at least connect `run_id`, `step_id`, `tool_call_id`, `effect_id`, `provider_request_id`, and `trace_id`. Otherwise the system may know that a service reported an error without knowing where this user’s task actually stopped.

The decision for this stage: when the state flow has no obvious pressure, keep the relational database. Get the state model, indexes, and transaction boundaries right before introducing more storage.

## 4. Case two: Workers multiply, so you need a “ticket machine”

This stage separates the scheduling flow from the state flow. The database keeps the ledger; a queue starts handing out work.

Polling is convenient at small scale. Polling means that a Worker periodically asks the database, “Do you have work for me?” With many Workers, it is like a crowd repeatedly asking the same question at a service desk. Suppose 100 Workers query once per second. Even with no work, the database handles 100 queries per second. At 1,000 Workers, that becomes 1,000 empty questions per second.

This is when a message queue can help. It is like a ticket machine: call a Worker when a task arrives instead of making Workers circle the database. The queue can also record whether a task was claimed, how long it has been unfinished, and whether it should be delivered again.

Which option fits depends on the existing environment:

- Redis is useful for low-latency coordination and short-lived leases, heartbeats, and rate-limit counters. Redis Streams is its feature for storing message sequences. It can distribute messages to a group of Workers and track messages that have been claimed but not completed. If the system already uses Redis and does not yet need a separate messaging platform, it is often convenient. It can be a coordination layer without becoming the only source of truth for Runs.[Redis Streams](https://redis.io/docs/latest/develop/use-cases/streaming/)
- SQS is an AWS-managed message queue. The team does not maintain its servers, and the cloud provider handles much of its availability and scaling. The trade-off is deeper dependence on the cloud platform.
- RabbitMQ is a dedicated messaging service. It fits systems that need many routing rules, priorities, or traditional delivery patterns, but the team must also learn and operate it.

Whichever option you choose, keep the boundary stable: the database stores task state, while the queue only wakes Workers. Keep queue messages small: task identifiers and a little routing information. To prevent two Workers from writing at the same time, a Run can also carry an `owner`, `lease_until`, `version`, or fencing token.

Delivery can still be duplicated. A Worker must be able to recognize, “I have already completed this step.” That is more reliable than assuming a message will arrive exactly once.

The decision for this stage: add a queue when the scheduling flow shows heavy empty polling, claiming contention, or backlog. The queue dispatches work; the database keeps the ledger.

## 5. Case three: one event needs to reach many downstream systems

This stage expands the event and projection flows. The same fact may need to reach notifications, billing, audit, evaluation, and the frontend.

A normal task queue is like a taxi: one task usually goes to one Worker. An event stream is like a newspaper: the same issue can go to many subscribers, and a new subscriber can read old issues that were kept.

Let us estimate again. Suppose the system produces 100 events per second, each 1 KB. The raw data is about 8.6 GB per day. With five downstream consumers, the system performs about 43.2 million consumer deliveries per day. Retained for 30 days, the raw events occupy about 259 GB, before replicas and indexes.

When `ToolCommitted` no longer only advances the Agent, but also enters audit, evaluation, notifications, billing, and analytics, a normal task queue becomes awkward. Downstream systems may need to consume at their own pace or recompute a metric from three days ago.

Kafka is a distributed event log designed for this situation. Different consumer groups can keep independent positions, which makes it useful for multiple subscribers, replay, and data pipelines.

With one execution cluster and one result processor, a normal queue is usually enough. Kafka becomes useful when:

- Several downstream systems each need their own copy of the events.
- A new service must replay historical data after it comes online.
- Events need to be retained for days or months.
- A single machine or queue no longer provides enough throughput.

[Kafka’s design](https://kafka.apache.org/design/) puts the same kind of event into a Topic. Think of a Topic as a newspaper column. Each kind of downstream system forms its own Consumer Group, or group of readers. The notification system’s position does not affect the audit system’s position. As data grows, a Topic can be split into partitions for parallel processing.

Kafka does not answer “Is this Run complete now?” That answer still belongs in the business database, or behind a query view built from events. Kafka stores what happened. The database stores the current result.

So do not begin by asking, “Should we use Kafka?” Ask instead: how many kinds of readers need this event, and do they need to look back in history?

The decision for this stage: with one consumer, a normal queue is usually enough. Consider Kafka when independent consumers, long retention, or historical replay become real requirements.

## 6. Case four: long-running tasks cannot keep a Worker on duty

This stage mainly handles the resource flow, while also affecting state and scheduling. Once a task leaves its current Worker, the system must still remember what it is waiting for.

Some tasks are not frequent but wait for a long time. They may wait for human approval, tomorrow’s timer, an external response, or several child tasks to finish.

Suppose 10,000 tasks must wait for 24 hours. Keeping 10,000 Workers asleep is like asking 10,000 couriers to stand outside a door waiting for a signature. Compute resources are occupied, and a process restart may make the system forget what each Worker was waiting for.

A better pattern is “archive, then set an alarm”:

1. Persist the current step and the waiting condition.
2. Release the Worker.
3. When approval, a callback, or a timer arrives, claim the next step.

For a small amount of waiting, a database state machine and a periodic scan are enough. If tasks regularly wait for hours, start several branches, wait for them to join, or need explicit failure handling, a dedicated workflow system becomes worthwhile.

A workflow system is not a “faster queue.” It is more like a process coordinator. It remembers which step the task reached, what it is waiting for, and which step should continue when a signal arrives.

A sandbox is a separate concern. It is an isolated workspace for running code, browsing the web, or operating a desktop. Create it when needed, pause it, snapshot it, or reclaim it when it is idle. Keep durable state in a database, Git, or object storage rather than only on the temporary workspace’s local disk.

The workflow layer is an archive and an alarm clock. The sandbox is a temporary workshop. Neither primarily solves “how do we deliver messages faster?” They solve a different problem: after the task leaves the current process, can the system still continue it?

The decision for this stage: if the resource flow only needs short-lived execution, Workers and containers are enough. When tasks wait across hours, or environments need isolation, pausing, and cleanup, add a workflow layer and a Sandbox Controller.

## 7. Questions to answer before building

An Agent backend does not need to begin as a diagram full of middleware. Return to the six flows and use this decision order:

```text
Draw the six flows
→ find the one under real pressure
→ add infrastructure only for that pressure
```

Put the same path into one small example. Start with a system processing 10,000 Runs per day:

```text
Relational database records state
→ Outbox records pending work
→ Worker claims and executes it
→ Files go to object storage
→ Logs and traces go to observability
```

When more Workers make database polling expensive, hand the job of waking Workers to Redis Streams or a managed queue. The database still holds the real Run state.

When evaluation, audit, and billing all need to read the same events independently, and historical replay matters, write those events to Kafka. Kafka stores what happened; the database still stores the current Run result.

When tasks wait for human approval, an external callback, or an overnight timer, add a workflow layer. When tasks must run code or browse the web, add a Sandbox Controller for the temporary environment.

Every step corresponds to one of the data flows above, and every step should be triggered by real pressure.

Reliable Agent infrastructure does not mean using the most complex product at every layer. It means every kind of data has a clear owner, every component has an explainable reason to exist, and the system still knows who owns the next step when a Worker, connection, or sandbox disappears.

---

## References

1. [Coze Loop Architecture](https://github.com/coze-dev/coze-loop/blob/main/ARCHITECTURE.md)
2. [Tencent Cloud Agent Runtime: Decoupling Communication and Execution](https://developer.cloud.tencent.com/article/2686331)
3. [CubeSandbox Architecture](https://github.com/TencentCloud/CubeSandbox/blob/master/docs/architecture/overview.md)
4. [AWS: Transactional Outbox Pattern](https://docs.aws.amazon.com/en_en/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html)
5. [Redis Streams](https://redis.io/docs/latest/develop/use-cases/streaming/)
6. [Apache Kafka Design](https://kafka.apache.org/design/)
7. [System Design Space: Back-of-the-envelope Estimation](https://system-design.space/en/chapter/back-of-envelope-estimation/)

## Scope notes

- The enterprise examples use public engineering posts, official documentation, and open-source implementations. Open-source code does not reveal every part of a company’s private production architecture.
- The request, write, and storage numbers in this article illustrate estimation methods. They are not universal performance limits for any component.
- Specific components still need to be validated against throughput, backlog, end-to-end latency, retention period, and the team’s operational capacity.
