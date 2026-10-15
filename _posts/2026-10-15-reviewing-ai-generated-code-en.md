---
title: "Reviewing Agent-Written Code: How to Grow as You Use AI"
date: 2026-10-15
permalink: /posts/reviewing-ai-generated-code/en/
lang: en
translations:
  zh: /posts/reviewing-ai-generated-code/
  en: /posts/reviewing-ai-generated-code/en/
author_profile: false
read_time: true
excerpt: "A practical guide for junior engineers reviewing agent-written code: keep humans involved in the decisions that matter, examine risk and evidence, and turn each review into a way to build engineering judgment."
tags:
  - AI
  - Software Engineering
  - Code Review
---

This article is for interns and junior engineers who are just starting to build projects with coding agents. A request may arrive in Slack, Feishu, or an issue. You ask Codex to explore the project, change files, run tests, and prepare a Git commit. The code appears quickly. The hard part is deciding whether it is right.

A single change can touch hundreds of lines across several directories. Reading every line takes time, and it may still not reveal that the work started from a misunderstanding. The code can look tidy and the tests can pass while the feature misses what the user asked for.

That is why review starts when you receive the request, not at the end of implementation. You need to learn to understand the goal, make sense of the approach, and then decide whether the code delivers both. Reading the diff matters, but it is only one part of the work.

## Human involvement is more than a final approval

“Human in the loop” can sound like “AI writes the code; a person approves it.” People need to make decisions at several points: turn a vague request into behavior that can be tested, check that the approach fits the system’s constraints, and use evidence to decide whether the change is ready to merge. An agent can write code, look things up, and run commands. The team remains responsible for product trade-offs, release risk, and future maintenance.

This is where people and agents bring different strengths to review. A 2026 preprint analyzed more than 278,000 review conversations across 300 GitHub projects. Agent comments focused mostly on defects and code improvements. Human reviewers also asked about design intent, checked tests, and shared project knowledge. In the study, 16.6% of agent suggestions and 56.5% of human suggestions made it into the final code. Those figures are not a comparison of accuracy, but they are a reason not to turn agent findings directly into a to-do list. In a sample of unadopted agent suggestions, researchers classified 28.7% as incorrect and another 24% as identifying an issue but proposing a different fix from the one the author chose. The data comes from mature open-source projects and observes existing reviews, so it does not prove that people are always more accurate. It does point to a useful division of work: agents can broaden the search, while people interpret context, clarify intent, and make trade-offs. [Study: Human-AI Synergy in Agentic Code Review](https://arxiv.org/abs/2603.15911)

Human involvement does not mean rewriting the agent’s work or rereading every line mechanically. Put human judgment where it matters: check the goal and design first, then decide which risks need closer verification. An agent can map call sites or suggest boundary inputs. Ask what code or test supports its claim, then verify that evidence yourself. A confident explanation without evidence is not understanding.

## Senior engineers review the direction before the implementation

Google’s public reviewer guide calls design the most important part of a review. Does the feature belong in this system? Will the pieces work together? Is it good for the people who use the code? Those users include product users and the engineers who will call and maintain the code later. An experienced reviewer first clarifies what the change must deliver, then asks whether the implementation makes sense. [Google: What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)

Suppose the request says only “retry after failure.” Which errors are retryable? How many attempts are allowed? Could retrying charge a customer or send a message twice? Inspecting an agent’s retry loop line by line cannot settle those questions. Clarify the acceptance conditions and invariants first. For a broad change, ask the agent to outline its approach, touched modules, and assumptions before it edits files. Then split the work into smaller pieces, each tied to behavior you can verify.

Once the direction is clear, follow the change into the system. Could it break an interface or make old data unreadable? Could a failure leave state stuck? Could concurrent requests repeat an operation? Can monitoring detect the problem, and can the change be rolled back? Google’s guide asks reviewers to understand every line they have been assigned and to consider the surrounding file and system context. Risk-based review helps you decide where to look most closely; it is not permission to approve code you do not understand. Ask the author to explain or split code that is hard to follow. Bring in an experienced maintainer for areas such as privacy, security, concurrency, and migrations.

AI can produce code quickly, which can send larger batches into review. DORA’s 2025 model estimated that a 25% increase in AI adoption was associated with a 1.5% decrease in delivery throughput and a 7.2% decrease in delivery stability. The report points to larger change batches as one possible mechanism: they take longer to review and can make systems less stable. This is an organization-level association, not proof that AI directly caused the declines. For an individual engineer, the practical lesson is to control the size of each change. When one commit answers one clear question, reviewers can reason about its direction, impact, and rollback. [DORA: State of AI-assisted Software Development 2025](https://dora.dev/ai/gen-ai-report/report/)

## Good reviews explain the reason and teach judgment

Experienced engineers do not treat every suggestion as a required command. Google’s standard is to approve a change once it clearly improves the overall health of the codebase; a reviewer should not hold it up in pursuit of perfection. Explain the impact and evidence behind important concerns. Mark style preferences as non-blocking. Reviewers are responsible for code health, and they should also let authors keep making progress. [Google: The Standard of Code Review](https://google.github.io/eng-practices/review/reviewer/standard.html)

Explaining why a change matters teaches more than offering a replacement. A 2025 ACM study analyzed 793 code-review comments and found that 42% contained a suggestion without an explanation. The researchers identified several ways reviewers explain feedback, including citing a rule, pointing to a similar example, and describing future impact. For example, instead of writing only “use a transaction,” explain: “If the write succeeds but sending the event fails, the two systems will disagree. We need a transaction here or a way to compensate for the failure.” Once the author understands the reason, they can recognize the same problem next time. [Study: Explaining Explanations](https://doi.org/10.1145/3708518)

Review does not require one person to know everything. A good reviewer says which parts they checked and where they are unsure, and brings in the right maintainer for privacy, security, performance, or concurrency questions. Junior engineers can do the same: own the requirement check, trace the call path, and inspect the tests; ask someone familiar with the domain to fill in business constraints you cannot explain.

## How can you turn each review into practice?

Before reading the code, write down the behavior the request should change, the modules involved, and the failure you are most worried about. Then follow a critical path from input to result and ask whether the tests would fail if the implementation were wrong. Google also reminds reviewers to inspect the tests themselves: do the assertions mean anything, and could incorrect code still pass? Walk through a real user path for a UI change. For concurrent code, reason about state and timing.

Then ask an agent for a second perspective. The `mattpocock-skills:code-review` skill you installed checks separately whether a change matches the request and follows repository standards. Give it a clear comparison point and the issue or specification. Form your own view first, then compare it with the skill’s findings. Its output is not a verdict: verify each finding against the source, tests, and project conventions, especially when the skill may not know a past design decision.

A 2026 randomized study from Anthropic also offers a reason to leave room for your own thinking. Fifty-two participants, mostly junior engineers, learned a Python asynchronous library. On an immediate comprehension quiz, the AI-assisted group averaged 50%, while the group that coded by hand averaged 67%; the difference in task-completion time was not statistically significant. The study measured only immediate understanding, and its assistant was different from a coding agent used in real work, so it cannot show that AI will make engineers lose skills on the job. The researchers also found that participants who showed stronger mastery asked conceptual follow-up questions, requested explanations, and used AI to check their understanding while writing code themselves. Using AI to learn and handing the task to AI are different ways of working. [Anthropic: How AI Assistance Impacts the Formation of Coding Skills](https://www.anthropic.com/research/AI-assistance-coding-skills)

After each review, write down one project constraint you learned or one failure path you missed. For a real bug, `mattpocock-skills:diagnosing-bugs` can help you reproduce it and narrow down the cause; then use `mattpocock-skills:tdd` to capture the failure in a regression test. If you cannot see why modules are divided as they are, `mattpocock-skills:codebase-design` can help you examine their interfaces and responsibilities. Skills give you a structure for practice. Your judgment still has to come from understanding the project and its evidence.

## How much of the project should you understand?

Junior engineers do not need to read the whole repository first. For the change in front of you, be able to explain the user-visible behavior, the modules and interfaces involved, how important data moves, which invariants must hold, and where the relevant tests and rollback live. Ask the module maintainer to review a high-risk area or one beyond your experience. Knowing a project is not memorizing every file. It is knowing who and what a change can affect, where the evidence is, and what context you still need.

If you form your own view before review and can explain it afterward with code and tests, AI is amplifying your ability. If all that remains is more code and a “tests passed” note, while no one understands what changed or why it works, AI slop is starting to accumulate.

## Conclusion

Reviewing agent-written code starts with the goal and design, then checks implementation and evidence in proportion to risk. People add value by understanding project context, clarifying intent, owning impact decisions, and passing their reasons on to the next maintainer. Each review should leave you understanding the system a little better. That is how you get stronger as you use AI.
