---
title: "Working with AI Coding Agents: A New Core Development Skill"
date: 2026-09-20
permalink: /posts/ai-coding-large-backend-projects/en/
lang: en
translations:
  zh: /posts/ai-coding-large-backend-projects/
  en: /posts/ai-coding-large-backend-projects/en/
author_profile: false
read_time: true
excerpt: "A practical workflow for using coding agents on large backend projects while keeping tests, reviews, migrations, and parallel work under control."
tags:
  - AI Coding
  - Coding Agents
  - Backend Engineering
---

## 1. Faster code generation can make development slower

AI coding is often marketed as faster code generation, as if that automatically meant faster development. It does not.

METR ran a randomized study with 16 experienced open-source maintainers completing 246 real tasks. The participants expected AI to make them 24% faster. In the experiment, they were 19% slower. The result does not represent every current model, but it exposes a durable risk: in familiar codebases that demand careful review, searching for context and repairing plausible mistakes can outweigh faster generation. [METR study](https://metr.org/Early_2025_AI_Experienced_OS_Devs_Study-paper.pdf)

Long-term users repeatedly converge on written plans, test-first development, and final human verification. Simon Willison describes the productive pattern as a skilled person defining a clear task, an agent repeatedly editing and testing, and the person correcting the result with domain knowledge. [Simon Willison's observation](https://feeds.simonwillison.net/2025/Jun/18/coding-agents/)

At the feature level, the useful question is how to turn a request into a change that can be verified, reviewed, and merged.

At the project level, the important skill is retaining control as roles blur and one developer starts directing several agents. Learning how to collaborate with them is becoming part of everyday engineering work.

## 2. A minimal AI coding loop

No person or context window can hold an entire large codebase. When a task grows too broad, an agent often keeps reading until noise fills its context and earlier constraints disappear. The first move is to reduce the amount of the system that each change must understand.

A modular monolith is one practical structure: deploy one application, but divide it into modules with enforced boundaries. A backend with users, orders, payments, and notifications might look like this:

```text
my-service/
├── CLAUDE.md                 # Short repository-wide rules
├── docs/ARCHITECTURE.md      # Modules, dependency direction, data ownership
├── docs/decisions/           # Important decisions, including rejected options
├── scripts/verify.sh         # Fast checks that finish within a minute
├── scripts/verify-full.sh    # Full tests and integration checks
├── src/
│   ├── shared/               # Shared types, errors, and utilities; no business logic
│   ├── users/                # Users and shipping information
│   │   ├── CLAUDE.md
│   │   ├── api.py            # Other modules may import only this public interface
│   │   └── tests/
│   ├── orders/               # Orders and order state
│   │   ├── CLAUDE.md
│   │   ├── api.py
│   │   └── tests/
│   ├── payments/             # Payment callbacks and idempotency
│   │   ├── CLAUDE.md
│   │   ├── api.py
│   │   └── tests/
│   ├── jobs/                 # Retries and asynchronous jobs
│   └── notifications/        # Payment and order notifications
└── tests/protected/          # Cross-module invariant tests
```

Dependency checks should reject imports of another module's internals. Keep the fast check below a minute and run the full suite separately.

It also helps to hand-write one reference module. New modules can copy its interface shape, error handling, and test style. A concrete example is often more useful to an agent than ten pages of prose.

Consider a real cross-module feature: handling a successful payment callback. It touches `payments`, `orders`, `jobs`, and `notifications`, and it needs a new payment-event table.

The first step is to write a one-page requirement yourself. Do not delegate it to the agent. Writing it exposes unresolved decisions about duplicate callbacks, out-of-order delivery, and notification failures. The specification might look like this:

```text
# SPEC: Successful payment callback

Goal: A valid callback moves an order from pending to paid and sends one notification.

Rules:
- When the signature is valid and the order is unpaid, record the event, update the order,
  and create a notification job.
- When the signature is invalid, return 401 and leave the order and inventory unchanged.
- When the same event arrives again, return success without charging inventory,
  shipping, or notifying twice.
- When notification delivery fails, retry the notification without processing payment again.

Out of scope: Refund callbacks and changes to existing payment methods.

Impact: payments, orders, jobs, and notifications. Add payment_events;
the migration must be reversible.

Done: Protected tests and the full verification suite pass. Manually send normal,
duplicate, and out-of-order callbacks in staging.
```

Second, start the session at the repository root. Ask the agent to read `ARCHITECTURE.md` and the four modules' `api.py` files, then write its plan to a file. Review only four questions: Did it touch anything outside the approved scope? Is the migration reversible? Did it add a dependency? Did it bypass a public interface? Keeping the plan in a file also means it survives context compaction even when chat history does not.

Third, write invariant tests before the implementation. The central invariant is that a payment event may move the order state at most once and create at most one notification, no matter how many times it arrives. The agent may draft a property-based test with duplicates, reordering, and network retries, but a human defines and reviews the invariant. Put it under `tests/protected/`, where the implementation agent may read it but may not weaken it to make the code pass.

Fourth, implement in stages: shared event types, the order state transition, signature verification and event deduplication, notification retries, and finally the database migration. Use a fresh session for each stage. Start module-local work inside that module and cross-module work from the repository root. Once the fast check passes, inspect the diff and commit. If the next stage fails, the previous stable point is easy to restore.

Set a context budget as well. Give cross-module research to a subagent and ask it to return only conclusions and file locations. Do not make the main session carry every search, failed attempt, and hundreds of opened files. If the same problem is still unresolved after two corrections, end the session and restart with the facts you have already verified.

Fifth, review the whole diff in a fresh context. Ask only for correctness, security, and out-of-scope changes, not style. Then read the callback entry point, order transition, unique event constraint, and notification call yourself. After the full suite passes, manually send normal, duplicate, and out-of-order callbacks in staging. A scenario the implementation agent has never seen is the final hidden test.

Sixth, turn failures into mechanisms. If the agent bypasses a module interface, add a dependency check. If it swallows exceptions, add a lint rule. If it creates duplicate notifications, add a database uniqueness constraint and an integration test. The next similar task should encounter the guardrail before a reviewer has to repeat the lesson. [Thomas Wiegold: How My Agentic Coding Workflow Changed in a Year](https://thomas-wiegold.com/blog/agentic-coding-workflow-shorter-prompts/), [TDD workflow discussion](https://www.reddit.com/r/ClaudeCode/comments/1qd64xx/tdd_workflows_with_claude_code_whats_actually/)

## 3. How control changes across working contexts

You can use AI more aggressively on a personal experiment. Peter Steinberger starts with a CLI so he can run and feel the core behavior before expanding the interface. He keeps one main project and several satellite projects, delegating work that can run while he waits. Requirements can evolve through direct use, but rate limits, error handling, environment variables, backups, and HTTPS still need explicit attention. [Peter Steinberger's workflow](https://steipete.me/posts/2025/shipping-at-inference-speed)

Robert Nicuta's approach fits small projects that must live for a long time: each session starts with the project, current state, current task, constraints, and definition of success, and interfaces and tests come before implementation. Nemanja Jeremenkovic uses Claude Code as his primary development environment but keeps a traditional IDE for visual debugging and database inspection. He also states that this workflow best suits well-scoped problems with a clear technical direction. Both start each session from reviewable context rather than aiming for full autonomy. [Robert Nicuta's workflow](https://robertnicuta.com/en/blog/how-i-code-with-claude-code), [Nemanja Jeremenkovic's workflow](https://www.jeremenkovic.com/writing/claude-code-as-ide-2026-workflow)

An open-source pull request is constrained by the maintainers. Read recent pull requests, contribution rules, code ownership, and test commands before asking an agent to change anything. Let it trace calls, draft a test, and change one implementation, but keep the pull request small and singular. Read generated tests line by line and confirm that they do not redefine public behavior merely to pass. `noslop-oss` asks contributors to scrutinize AI-generated tests and follow its PR template. Alibaba requires disclosure of AI assistance and expects contributors to understand their code and answer review comments themselves. [noslop-oss](https://github.com/omkar-foss/noslop-oss), [Alibaba contribution policy](https://github.com/alibaba/open-code-review/blob/main/CONTRIBUTING.md)

Production work adds a chain of responsibility. The primary agent edits only its worktree. Research subagents return findings instead of writing to the main branch. A review subagent receives a clean context and the specification. CI runs fast checks, the full suite, contract tests, and security scans. Code owners approve migrations, credentials, monitoring, and rollback plans before release.

Boris Cherny has described a team keeping `CLAUDE.md` in the repository, adding lessons from recurring failures, and using hooks, subagents, and verification loops to prevent repetition. PostHog's AI policy similarly rejects turning AI output that the author does not understand into an issue or pull request. [Boris Cherny's workflow](https://www.reddit.com/r/AI_Agents/comments/1q3xw15/bcherny_creator_of_claude_code_shares_how_i_use/), [PostHog AI policy](https://github.com/PostHog/posthog/blob/master/AI_POLICY.md)

Moon Pixels offers a useful counterexample. The author initially put the entire workflow into `AGENTS.md`, then moved toward a short rules file, reusable skills, separate stages, and explicit approval gates. Community workflows are useful structures to adapt, not packages to copy without measuring their cost. [Moon Pixels: The agentic coding workflow](https://moonpixels.co.uk/blog/the-agentic-coding-workflow-i-use-in-opencode/)

As a production codebase grows, large refactors and migrations deserve stricter controls. In SWE Refactor Bench, only 28 of 520 whole-repository migration runs passed all three checks: the migration actually happened, behavioral tests passed, and an independent agent could not expose hidden behavior changes. Mechanical replacement should therefore be done with deterministic transforms that an agent can write and you can review. Test the transform on a few files before applying it broadly. Handle judgment-heavy cases one at a time, each in its own worktree.

Record the old implementation's outputs before the migration. These become golden results for comparing old and new behavior. Keep the system runnable and replace one module at a time. Anthropic's compiler project used GCC as a known-good oracle to localize failures so different agents could work on different files. That was more effective than having many agents collide on one system-wide failure. [SWE Refactor Bench](https://arxiv.org/abs/2608.23564), [Anthropic: Building a C compiler with a team of parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler)

Parallel agents pay off only when their tasks are genuinely independent. Give each task a worktree. A human defines boundaries, chooses merge order, and ensures that two agents do not edit the same files. Large repositories can use sparse checkouts and shared dependency directories. When a task cannot be separated, parallelism creates conflict and duplicated debugging.

You cannot read every line in a large repository, and you should not try. You should fully understand the architecture map, public module interfaces, migrations, security-sensitive paths, and new dependencies; sample the rest. Periodically ask an agent to explain how a module works today, compare that explanation with the architecture document, and turn drift into updated constraints or tests. Record rejected decisions too, or an agent will suggest them again months later.

Across all three contexts, four rules remain: scope must be clear, changes must be reversible, verification must be reproducible, and the submitter must be able to explain the result. As software moves closer to real users, permissions, auditability, and approval must become stricter.

## 4. How to allocate a day around AI coding

The best task to delegate depends on two variables: how much attention you have and how quickly the task can receive reliable feedback. Reserve your clearest hours for judgment. Put bounded, verifiable loops into waiting periods.

At the start of the day or a new task, keep control of direction. Read the requirement, confirm data boundaries, decide whether an interface must change, and determine whether a migration can be rolled back. A frontier model can investigate and critique the design, but the decision remains yours. Unfamiliar repositories, cross-module work, permissions, and concurrency are good places to spend the strongest model's reasoning budget. Peter Steinberger reports that Codex may spend 10–15 minutes reading before editing, while Opus starts faster. Codex can take longer per run yet save a later “fix the fix” cycle. Waiting is useful only when you can work on something else. [Peter Steinberger: Shipping at Inference-Speed](https://steipete.me/posts/2025/shipping-at-inference-speed)

After the design is approved, give one primary agent a runnable vertical slice: data model, interface, tests, and necessary documentation. A mid-tier model is often enough when scope, verification commands, and prohibitions are already clear. Use a faster model for renaming, formatting, repetitive tests, and documentation. If the agent fails twice without explaining the cause, or starts changing unrelated files, stop the loop and return to a stronger model for analysis instead of piling more instructions into a polluted context.

Boris Cherny runs several sessions at once, but not to make five agents overwrite the same feature. Sessions receive independent tasks; planning comes before execution; commits, formatting, and verification are encoded as commands or hooks; and agents get feedback from tests, browsers, or simulators. For an individual project, treat five sessions as an upper-bound example, not a default. One primary task, one research task, and one review task cover most features. [Boris Cherny's public workflow](https://www.reddit.com/r/AI_Agents/comments/1q3xw15/bcherny_creator_of_claude_code_shares_how_i_use/)

Mitchell Hashimoto uses a different cadence. He first had agents reproduce work he already knew how to do so he could learn what was safe to delegate. Late in the day, he sends agents research, issue triage, and low-risk preparation so that the next morning starts warm. Every recurring mistake becomes an `AGENTS.md` rule or a programmatic verification tool. His goal is to always have one useful agent running, but he estimates he currently achieves that for only 10–20% of a normal workday and prefers one background agent to a fleet. [Mitchell Hashimoto: My AI Adoption Journey](https://mitchellh.com/writing/my-ai-adoption-journey)

Parallel agents fit independent tasks: one adds tests, one researches documentation, and one handles a separate module. Work that shares files, a database migration, or one business rule should remain serial. Addy Osmani's loop-engineering guidance likewise requires explicit constraints and stopping conditions. More agents also create more review work. [Practical Loop Engineering](https://addyosmani.com/blog/practical-loop-engineering/)

During lunch, meetings, or CI waits, let agents run tests, summarize logs, update documentation, or prepare an isolated refactoring draft. Each task needs scope, a completion condition, verification commands, and a stop condition. Overnight work belongs in an isolated workspace without permission to deploy, delete data, or modify production configuration. The next morning, inspect the diff, logs, and failures before merging anything.

Mitchell's end-of-day pattern works best for high-confidence, low-consequence tasks: issue classification, call-chain research, additional tests, and migration drafts. Do not leave vague requirements or production permissions with an overnight agent. The goal is a faster start the next morning, not a larger pile of unreviewed code.

A phone works as a control surface, not a primary workstation. A remote machine, SSH, tmux, or a similar tool can start a task, show status, accept a short clarification, or approve a low-risk step. Large diffs, authorization logic, database migrations, and production releases still belong on a larger screen. Mobile workflows consistently frame the phone as a place to monitor, delegate, and decide, not as a laptop replacement. Approving consequential actions on a small screen while distracted is especially risky. [Tactic Remote: From Desk to Couch](https://tacticremote.com/blog/2026-02-28-from-desk-to-couch-mobile-developer-workflow/), [Axios: Codex comes to your phone](https://www.axios.com/2026/05/14/openai-brings-codex-to-your-phone)

Measure the whole delivery cycle instead of comparing generation speed by feel:

```text
Total delivery time = research + generation + waiting + review + rework + CI/PR round trips
```

The strongest model earns its cost by avoiding bad plans and rework. Faster models earn theirs by filling mechanical waiting periods. Addy recommends one primary agent with a small number of reviewers and warns that multi-agent work carries cognitive overhead. Simon Willison's version is even simpler: an agent is useful only when its operator understands the task, inspects the result, and corrects mistakes. [Simon Willison: Coding agents require skilled operators](https://feeds.simonwillison.net/2025/Jun/18/coding-agents/)

## 5. Build your own agent toolbox

In practice, the surrounding toolbox matters as much as the model: short rules and an architecture map, reusable skills, verification scripts and hooks, read-only external tools, isolated worktrees, review subagents, and background tasks that can run while you wait. The model is one reasoning component inside that system.

The toolbox should grow from real failures. If an agent repeatedly runs the wrong tests, add a fast verification script. If it crosses module boundaries, add dependency linting. If you repeatedly explain the release process, turn it into a skill. Connect an MCP server only when the agent actually needs a GitHub issue, staging logs, database reads, or browser state. A reminder repeated three times probably belongs in a tool or rule.

Skills are useful for workflows with inputs, steps, verification, and outputs: diagnosing an incident, drafting a migration, or reviewing a pull request. Hooks and scripts handle deterministic actions such as formatting, blocking dangerous paths, and running tests before a commit. MCP should expose only the external facts needed for the current job and should be read-only by default. More tools consume more context and widen the permission surface. Subagents are useful for research, comparison, and review; they should not race the primary agent over the same files. Use worktrees for parallel editing.

OpenAI's Codex harness and Anthropic's Skills work point in the same direction: make code, tests, logs, metrics, and operational boundaries visible, executable, and verifiable to the agent. An individual developer does not need to reproduce an enterprise platform. Turn the most common source of rework into one tool, then observe whether the next task produces less rework. [OpenAI: Harness engineering](https://openai.com/index/harness-engineering/), [Anthropic: Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)

The acceptance test for the toolbox is straightforward: does a new session require less explanation, does the agent discover errors earlier, can a reviewer locate risk faster, and can the task stop safely inside an isolated environment? Remove configuration that does not improve those outcomes.

## Conclusion

AI coding productivity comes from task design, not model capability alone. Turn requirements into bounded work packages, then let agents research, implement, verify, and review them. Reserve the strongest models for high-risk judgment, use faster models for mechanical work, and measure total pull-request time and rework rather than generated lines.

A mergeable pull request is the unit of output. Lines of code, prompt length, and agent-call counts are not substitutes for it.

## Research sources

- [METR: Experienced Open-Source Developer Productivity Study](https://metr.org/Early_2025_AI_Experienced_OS_Devs_Study-paper.pdf)
- [Simon Willison: Coding agents require skilled operators](https://feeds.simonwillison.net/2025/Jun/18/coding-agents/)
- [Reddit: Codex personal project workflow](https://www.reddit.com/r/codex/comments/1tf4s07/my_best_workflow_so_far_for_building_projects/)
- [Reddit: TDD workflows with Claude Code](https://www.reddit.com/r/ClaudeCode/comments/1qd64xx/tdd_workflows_with_claude_code_whats_actually/)
- [GitHub: codex-in-claude](https://github.com/briandconnelly/codex-in-claude)
- [GitHub: awesome-agent-conventions](https://github.com/ItamarZand88/awesome-agent-conventions)
- [GitHub: agent-skills](https://github.com/addyosmani/agent-skills)
- [PromptForge: AGENTS.md best practices](https://github.com/mbagalman/PromptForge/blob/main/guides/agents-md-best-practices-2026.md)
- [Thomas Wiegold: How My Agentic Coding Workflow Changed in a Year](https://thomas-wiegold.com/blog/agentic-coding-workflow-shorter-prompts/)
- [Peter Steinberger: Shipping at Inference-Speed](https://steipete.me/posts/2025/shipping-at-inference-speed)
- [Robert Nicuta: How I code with Claude Code](https://robertnicuta.com/en/blog/how-i-code-with-claude-code)
- [Nemanja Jeremenkovic: Claude Code as IDE](https://www.jeremenkovic.com/writing/claude-code-as-ide-2026-workflow)
- [Mitchell Hashimoto: My AI Adoption Journey](https://mitchellh.com/writing/my-ai-adoption-journey)
- [Moon Pixels: The agentic coding workflow](https://moonpixels.co.uk/blog/the-agentic-coding-workflow-i-use-in-opencode/)
- [Moon Pixels: How my workflow changed in three months](https://moonpixels.co.uk/blog/how-my-agentic-coding-workflow-changed-in-three-months/)
- [SWE Refactor Bench: Whole-Repository Stack Migration](https://arxiv.org/abs/2608.23564)
- [Anthropic: Building a C compiler with a team of parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler)
- [Boris Cherny workflow notes](https://github.com/diulama/claude-code-tips/blob/main/guides/boris-cherny-workflow.md)
- [Reddit: Boris Cherny shares his Claude Code workflow](https://www.reddit.com/r/AI_Agents/comments/1q3xw15/bcherny_creator_of_claude_code_shares_how_i_use/)
- [Addy Osmani: Practical Loop Engineering](https://addyosmani.com/blog/practical-loop-engineering/)
- [Addy Osmani: Agent Skills](https://addyosmani.com/blog/agent-skills/)
- [Addy Osmani: Agentic Code Review](https://addyosmani.com/blog/agentic-code-review/)
- [Anthropic: Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [Anthropic: Writing effective tools for AI agents](https://www.anthropic.com/engineering/writing-tools-for-agents)
- [Anthropic: Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- [OpenAI: Harness engineering](https://openai.com/index/harness-engineering/)
- [OpenAI: Unlocking the Codex harness](https://openai.com/index/unlocking-the-codex-harness/)
- [Model routing for coding agents](https://admix.software/blog/cut-ai-coding-agent-costs-model-routing)
- [Tactic Remote: From Desk to Couch](https://tacticremote.com/blog/2026-02-28-from-desk-to-couch-mobile-developer-workflow/)
- [Axios: Codex comes to your phone](https://www.axios.com/2026/05/14/openai-brings-codex-to-your-phone)
- [GitHub: noslop-oss contribution checklist](https://github.com/omkar-foss/noslop-oss)
- [Alibaba: open-code-review contribution policy](https://github.com/alibaba/open-code-review/blob/main/CONTRIBUTING.md)
- [PostHog: AI policy](https://github.com/PostHog/posthog/blob/master/AI_POLICY.md)
