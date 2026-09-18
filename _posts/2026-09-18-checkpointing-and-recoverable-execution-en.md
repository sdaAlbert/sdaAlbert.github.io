---
title: "When Agents Cannot Just Move Forward: Runtime Recovery from Coding to Real-Time Systems"
date: 2026-09-18
permalink: /posts/checkpointing-and-recoverable-execution/en/
lang: en
translations:
  zh: /posts/checkpointing-and-recoverable-execution/
  en: /posts/checkpointing-and-recoverable-execution/en/
author_profile: false
read_time: true
excerpt: "An agent's recovery strategy is determined not by its framework, but by its sources of truth, recovery boundary, and the remaining time value of its result."
tags:
  - AI Infrastructure
  - LLM Agents
  - Agent Runtime
  - Reliability
---

## 1. Start with the simplest possible agent loop

My first mental model of an agent runtime was straightforward: retry failed model requests, cancel when the user wants to stop, and save a checkpoint when the task grows too long. A minimal ReAct loop really can be this simple:

```text
User task
→ Model chooses the next step
→ Runtime invokes a tool
→ Tool changes external state
→ Result enters the model context
→ Model continues
```

But as soon as a tool can modify the outside world, this loop quietly assumes several dangerous things: the model and tool always return an unambiguous success or failure; a timeout means the operation did not happen; executing the same operation twice has no additional effect; the in-memory transcript is the complete task state; and the process, context, and tool environment always live and die together.

Consider a common counterexample. An agent calls a tool to create a support ticket. The ticket is written to the database, but the network connection drops before the response reaches the runtime. The runtime sees only a timeout, even though the outside world has already changed. A blind retry may create a duplicate ticket, while loading an older checkpoint still cannot tell us whether the first call succeeded.

After a failure, are the agent's memory, its execution environment, and the business facts that have already occurred still consistent with one another?

This article argues for a more specific view: **recovery strategy is determined not by the agent framework, but by the source of truth, the boundary of controllable state, and the amount of time value left in the result.** A deliberately informal formula is useful here:

```text
Recovery Decision
= Truth Anchor       (what proves what actually happened)
+ Recovery Boundary  (what remains under runtime control)
+ Time Value         (whether the result is still useful now)
```

The systems discussed below are not merely a taxonomy of recovery terms. They help show how these three questions change the correct decision.

## 2. Before recovering, ask which state is still trustworthy

At least three kinds of state evolve whenever an agent takes a step.

The first is **context**: the messages, plans, observations, and intermediate conclusions visible to the model. Once an error enters the context, later reasoning can be internally coherent while still resting on a false premise.

The second is the **controlled environment**: a code workspace, sandbox, browser session, or temporary files that the runtime may be able to snapshot, rebuild, or replace. These states do not automatically roll back when the context does.

The third is **external effects**: messages already sent, database writes, moderation decisions, orders, gifts, refunds, or production configuration changes. These facts have usually crossed the runtime boundary. Deleting a few messages from the transcript cannot undo them.

After a failure, these three states can diverge. The model may believe an action failed even though the database committed it. The workspace may have returned to an older revision while the model still remembers a test result from a newer one. A recovered agent may republish data whose real-time value expired seconds ago.

TikTok Privacy Innovation Lab observed a related problem in [When Tools Become Prompts](https://developers.tiktok.com/blog/when-tools-become-prompts). Individual MCP tool calls may each comply with their own access rules, while information, intent, and implied authority accumulate across turns until they produce a risk that no single-step check can see. Context is therefore more than a chat transcript: it also carries interpretations and assumptions about authority that shape later actions. If recovery preserves a corrupted suffix, those assumptions continue to propagate.

Recovery is therefore not simply “load the latest checkpoint.” A runtime must determine how far the error spread, whether an external effect occurred, whether a historical state still satisfies business constraints, and whether the result still has value at the current time. Recent research and engineering work fill in different parts of this picture.

## 3. How existing agent systems progressively address failure

### 3.1 The cheapest option: repair forward from the current state

Many agents respond to failure by replanning rather than rewinding. The Orchestrator in [Magentic-One](https://arxiv.org/abs/2411.04468) maintains a task ledger that tracks progress, completed work, and unresolved items. When execution stalls, it forms a new plan from the current state and dispatches agents again.

This is useful because many failures mean only that a particular route did not work: the search query was poor, the wrong tool was selected, or a test failed. If the current environment is still trustworthy, preserving completed work and choosing another route is usually cheaper than starting over.

Replanning, however, assumes that the current state was not already contaminated by an earlier error. If an agent modified ten files based on incorrect information, or issued a refund whose outcome is unknown, a new plan inherits those problems. Replanning answers “where should we go next?” It does not answer “is the ground beneath us still sound?”

### 3.2 Let the task outlive the process: durable execution and replay

[LangGraph](https://docs.langchain.com/oss/javascript/langgraph/thinking-in-langgraph) structures long-running work as stateful nodes and persists state at node boundaries. After an interruption, execution can resume from persisted progress instead of repeating the entire task. It also exposes an important constraint: a node may execute again during recovery, so external writes performed inside a node must still be idempotent.

[Temporal's patterns for AI workflows](https://go.temporal.io/platform-hub/ai-engineering/ai-patterns) draw the boundary even more clearly. Workflow control state can be reconstructed from history, while Activities that access a database or an external service may execute with at-least-once semantics. Durable execution guarantees that orchestration does not forget when a worker disappears. It does not automatically guarantee that a business action happens only once. Stable idempotency keys and read-after-timeout reconciliation remain application responsibilities.

These systems solve **resume**: the compute process can disappear while the task continues. They do not automatically solve a different problem—a task that never crashed but spent a long time moving in the wrong direction.

### 3.3 Claude Code: make cross-session recovery an engineering handoff

Anthropic's [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) describes a practical failure in long Claude Code sessions: context compaction alone does not ensure that the next session understands what the previous one actually completed. An agent may attempt too much at once and exhaust its context halfway through an implementation. A later session may instead see partial progress and prematurely declare the task finished.

The proposed solution is strikingly ordinary: work in small increments; use a feature list to describe what remains; keep a progress file that explains the current state; preserve verifiable increments in Git history; and leave the workspace runnable, testable, and ready for the next agent at the end of each session. Recovery here is not a magical rollback. It is a clean handoff designed as a normal responsibility of the harness.

[Managed Agents](https://www.anthropic.com/engineering/managed-agents) abstracts this idea into three replaceable components: a `session` that stores an append-only event history, a `harness` that calls the model and routes tool requests, and a `sandbox` that provides the execution environment. A failed sandbox can be provisioned again. A failed harness can wake from the session. Task history no longer shares the lifetime of one worker or container.

Long-task recovery is therefore a runtime-structure problem before it is a prompting problem. Important state must live outside the process, and the next executor needs more than a transcript: it needs a verifiable environment and an explicit next step.

### 3.4 AgentRewind: context and workspace must move back together

Resume is insufficient once an error has contaminated the current state. [AgentRewind](https://arxiv.org/pdf/2608.14380) aligns the agent context and the controlled workspace under the same historical checkpoint. When execution fails, it restores files and removes the context suffix associated with the failed trajectory. It also preserves a memory of the failed attempt so the agent knows which route has already been disproven before generating a new suffix.

This is more rigorous than resetting Git while continuing the same conversation. If the files return to step 20 while the model still remembers a test result that appeared at step 35, the system remains inconsistent. Joint rewind realigns what the model knows with where the environment actually is.

AgentRewind can directly restore only state inside its controlled boundary. Code, temporary processes, and sandbox state may be rewound. An email already delivered, an order placed with a third party, or content already shown in a live room does not disappear with the workspace. That boundary is fundamental: rewind is powerful for coding agents, but it is not a universal answer for enterprise agents.

### 3.5 DART: a loadable checkpoint is not necessarily a valid checkpoint

[DART](https://arxiv.org/abs/2605.23311) goes further by introducing semantic recoverability. Suppose step A produces data and step B consumes it before committing a result to an external system. Rolling back A while keeping B may be mechanically possible, yet it leaves B without a valid upstream source.

A recovery point must therefore be checked against dependencies and effect constraints: which results depend on the state being removed, which effects have already been committed, and which downstream steps must be invalidated with them? If the most recent checkpoint violates these constraints, recovery must expand further back. If no valid point exists, automatic recovery should stop.

The problem changes from “find the nearest snapshot” to “find a history that is still true.” Validity comes first; minimizing recomputation comes second.

### 3.6 DeltaBox: once semantics are clear, make rewind affordable

Saving a complete environment frequently can be expensive. [DeltaBox](https://arxiv.org/abs/2605.22781) addresses a different layer of the problem by incrementally tracking filesystem and process state, reducing the cost of checkpoints and rollback so recovery points can be placed more densely.

Taken together, these systems form a progression. Magentic-One repairs the plan from the current state. LangGraph and Temporal make control flow durable. Claude Code uses durable artifacts for session-to-session handoff. AgentRewind restores context and environment together. DART asks which historical state remains semantically valid. DeltaBox reduces the systems cost of saving and restoring that state.

They are not mutually exclusive. A mature runtime may need forward repair, durable execution, controlled-environment rewind, and reconciliation or compensation for external effects at the same time.

## 4. Why recovery changes completely in real businesses

The correct recovery mechanism is determined less by the model than by three business properties: whether a late result retains value, how much of the environment the runtime controls, and whether an action affects users, money, or production systems.

### 4.1 Coding agents: the best fit for joint rewind

The main environment of a coding agent is a Git workspace and a sandbox. Most state can be versioned, and outcomes can be revalidated through builds and tests. Session events, tool calls, and Git commits can share one checkpoint ID. After a worker failure, the harness can be reconstructed from the event log and the workspace from a commit. When the approach itself is wrong, the system can remove both the failed context suffix and the corresponding file changes, preserve a failure summary, and try again.

But restoring files is not the same as restoring engineering context. TikTok's [Rush MCP Server](https://developers.tiktok.com/blog/rush-mcp-server) uses the build system to expose project relationships in a large monorepo, instead of asking an agent to scan the entire repository and guess its dependency graph. For an enterprise coding agent, build topology, test results, task lists, and a clean handoff are all part of recoverable state.

### 4.2 LIVE interaction agents: time cannot rewind, so follow the latest event

TikTok has demonstrated an interactive agent running at the edge in LIVE Studio to respond to voice commands from hosts or viewers. Related use cases could include captions, translation, content understanding, and interactive assistants. The public [InfiniEdge case study](https://developers.tiktok.com/blog/2025-infiniedge-ai-1-1-release) emphasizes low latency and edge-to-cloud coordination. This creates a fundamental difference from coding agents: an answer can be correct three seconds later and still be useless.

Consider one failure in detail. A viewer sends a gift, and the system wants an agent to generate a thank-you message and trigger an on-stream effect:

```text
T0  The gift service charges the account and records EffectID=gift-731
T1  The gift enters the live event stream at offset=8421 with a 2-second deadline
T2  The agent generates a thank-you message and calls the publishing service
T3  The publishing service accepts the request, but its acknowledgement is lost
T4  The inference worker restarts; its checkpoint only says "ready to publish"
```

The runtime cannot simply “retry from T2.” The context knows only that the acknowledgement was lost; it is not the source of truth. Whether the gift exists must come from the transaction ledger, and whether the message was displayed must come from the publishing record. Even if publication remains uncertain, the two-second deadline may already have passed. Generating another message may create a late or duplicate interaction. A safer response is to reconcile using the stable effect ID, suppress duplicate publication, and continue from the latest stream offset instead of rewinding the gift or replaying the live session.

This example exposes all three dimensions. The ledger and publishing record are the **Truth Anchors**. The agent worker is merely a replaceable **Recovery Boundary**. The deadline determines the old result's **Time Value**. The same timeout may justify recomputation in a coding agent and immediate discard in a LIVE agent.

Such a system can be separated into several planes.

The real-time data plane receives media, comments, gifts, and commands, assigning offsets and deadlines to events.

The agent inference plane interprets inputs and produces candidate results, while allowing timeouts, cancellation, model replacement, and edge-to-cloud degradation.

The deterministic publication plane owns deduplication, authorization, and actual delivery to the live room.

The recovery control plane records sessions, result state, and publication receipts.

This resembles the `session / harness / sandbox` separation in Managed Agents, with one additional protocol-level concern: whether the result can still arrive in time.

After a failure, the system generally should not replay every missed interaction. It should continue from the latest offset, discard late results, fall back from edge inference to cloud models or deterministic rules, and correct already-visible captions through a new correction event rather than pretending they were never shown. The recovery goal is not to reproduce the entire trajectory. It is to remain current within the deadline while preventing duplicate publication.

[BytePlus MediaLive's Real Time Media documentation](https://docs.byteplus.com/en/docs/byteplus-media-live/docs-introduction-to-real-time-media) describes weak-network optimization, dynamic frame chasing, and skipping old frames when necessary. It is not an agent-recovery design, but it reflects the same real-time systems principle: when complete historical processing conflicts with catching up to the present, preserving immediacy may require abandoning old progress.

### 4.3 Customer-support and workflow agents: recover the conversation, reconcile the action

A support agent may read orders, update tickets, issue coupons, and initiate refunds across many turns. The conversation can resume from a durable session after an interruption, but a tool timeout cannot be resolved from message history alone.

Reads may be replayed safely. Writes such as ticket updates should carry a stable idempotency key. When a refund has an unknown outcome, the runtime should query by business key before deciding whether to reuse the result, retry, or compensate. High-value or unresolvable cases should move to a human. A Temporal-style durable workflow can preserve control flow; the database or third-party system remains the authority on whether the action completed.

### 4.4 Payments, gifts, and trading agents: the ledger outranks the context

Financial state cannot be “recovered” by overwriting it with an old snapshot, because settlement, withdrawal, or risk controls may already depend on later records. A reliable implementation uses an immutable ledger and globally stable business identifiers, checks whether each command has already been processed, reconciles unknown outcomes, and adds a refund or reversal record instead of deleting the original transaction.

The agent may interpret intent and propose an action, but deterministic services must own amount validation, account state, permissions, and final commit. This is where DART's concern becomes concrete: once downstream settlement has consumed an upstream fact, the agent cannot rewrite it merely because it changed its mind.

### 4.5 SRE and operations agents: constrain execution before automating recovery

An agent that changes production configuration, scales infrastructure, or responds to an incident operates in a partly controllable environment with potentially severe consequences. It should separate planning from execution: capture current state, the proposed diff, risk, and a rollback plan before making a change; require approval for high-risk operations; bind every execution to a change ID; use version rollback for reversible configuration; and use compensation or a human runbook for migrations, deletion, and external notification.

When context is lost or the real system state cannot be established, the correct response is often not “recover autonomously and continue.” It is to stop and read the system of record again. For an SRE agent, recovery capability must remain subordinate to change control.

## 5. A unified decision process for the runtime

Across these scenarios, a runtime can evaluate failure in a consistent order. The first step is not to find a checkpoint. It is to find the truth.

First, identify the **Truth Anchor**: Git and tests for code, a ledger for transactions, receipts for publication, and a decision log for moderation—never the model's own description of what it did. Second, locate the **Recovery Boundary**: context, sandbox state, and uncommitted candidate outputs may be restorable, while facts already delivered to users or consumed downstream usually require reconciliation, correction, or compensation. Third, evaluate **Time Value**: has the deadline passed, and is a late result still useful, in need of correction, or better discarded?

Only then should the runtime ask which layer failed: model computation, harness, sandbox, context, or business action. If the effect has not crossed the controlled boundary, the runtime can resume or jointly rewind and then verify the outcome. If it has been committed, the runtime should reconcile before deciding to reuse, retry idempotently, or compensate. If the result has expired, it should be discarded in favor of the latest event. If the state cannot be established and the risk is unacceptable, automatic progress must stop.

A DART-style check comes last: would the selected recovery point leave an existing downstream result without a valid source? Only recovery points that pass this semantic test should be compared by cost.

An enterprise runtime does not need a universal recovery framework on day one, but it should preserve a few stable abstractions: an append-only session that records what happened; RunID, StepID, ToolCallID, and EffectID identities that connect attempts to one logical operation; explicit classification of reads, idempotent writes, compensatable writes, and irreversible actions; declared boundaries for what can be snapshotted and what can only be queried; deadlines and policy gates in the execution path; and outcome verification against the real environment rather than the agent's claim that it has finished.

## Conclusion: recovery is about truth and time

For coding agents, Git, sandboxes, and tests make rewind a powerful tool. For LIVE interaction agents, expired results have no value, so deadlines, offsets, deduplication, and degradation matter more. Moderation decisions must remain traceable, supersedable, and appealable. Payment and gifting agents must trust the ledger over their context. SRE agents derive reliability from strict change boundaries.

An enterprise agent runtime should therefore not promise that every failure is recoverable. It should explain which state can be restored, which actions can only be compensated, which results should be discarded after they expire, and which uncertainties must be handed to a person.

A reliable agent is not one that always moves forward. It is one that knows when it can continue, when it must return to a trustworthy history, and when it should stop.

---

## References

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

## Notes on scope

- This article is based on public papers and official engineering posts. It does not claim knowledge of undisclosed internal implementations at TikTok, Anthropic, or any other company.
- Several papers cited from 2026 are recent arXiv preprints. Their conclusions should be interpreted within their published experimental settings and revisited as peer review progresses.
