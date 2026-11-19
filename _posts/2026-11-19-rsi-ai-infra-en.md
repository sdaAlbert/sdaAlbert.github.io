---
title: "Recursive Self-Improvement in AI Infrastructure Is Moving Beyond Kernel Optimization"
date: 2026-11-19
permalink: /posts/rsi-ai-infra/en/
lang: en
translations:
  zh: /posts/rsi-ai-infra/
  en: /posts/rsi-ai-infra/en/
author_profile: false
read_time: true
excerpt: "Recent AI infrastructure research is expanding from algorithm and kernel search to inference and training systems, while beginning to carry experimental experience across runs."
tags:
  - AI Infrastructure
  - AI Research
---

Recursive self-improvement (RSI) is often used to describe AI helping develop more capable AI. In engineering, it helps to start with an ordinary experiment. A system proposes a change, runs it against a fixed task, evaluates the result, and decides which changes move on to the next round. The next round starts from a tested version and its records, then proposes, runs, and filters another set of changes.

To understand an RSI system, look at what each round changes, how it is evaluated, what gets retained, and how retained results shape the next round. If the next round inherits only a faster kernel or a better training configuration, the system is accumulating infrastructure improvements. If experiment records change how candidates are generated, how the search is ordered, or when it stops, the process that produces improvements is changing too. Recent public work in AI infrastructure has expanded from algorithm and kernel search to inference and training systems, and is beginning to reuse experience across rounds and improve search strategies. These projects occupy different points along that progression, and together they show a field gradually broadening its focus.

## Starting with a kernel

A GPU kernel is a specific operation in a model’s computation, such as matrix multiplication or normalization. Its inputs and outputs can be described precisely, and its execution time can be measured on a given device. That makes kernels a natural starting point for automated search.

Google DeepMind’s AlphaEvolve uses language models to propose algorithm candidates and automated evaluators to check them. It found a more efficient heuristic for scheduling Google data centers and improved a matrix multiplication kernel used in Gemini training. The kernel ran 23% faster on the relevant workload, reducing Gemini’s overall training time by about 1%. Those two figures show the distance between speeding up one operation and speeding up an entire training run. [Google DeepMind](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/)

Meta’s KernelEvolve brings this kind of search to production across several hardware platforms. The system generates implementations for a target operator, checks correctness and performance, then uses measurements to guide further search. Meta reports a throughput improvement of more than 60% in one ads-model inference case, and says KernelEvolve is used to optimize code serving large-scale online inference traffic. [Meta KernelEvolve](https://engineering.fb.com/2026/04/02/developer-tools/kernelevolve-how-metas-ranking-engineer-agent-optimizes-ai-infrastructure/)

Systems like these leave behind faster kernels and evaluation results. Even if the search program, model, and rules stay the same, a better kernel can serve as the starting point for later optimization. The infrastructure artifact improves, while people and the existing procedure still provide the experimental method.

Whether a kernel speedup translates into a practical gain depends on how much time that operation accounts for in a larger workload and how it interacts with other operations. Model inference and training combine many compute and resource-scheduling stages, so the overall gain from a local change often needs to be measured again in the complete system. Recent work is therefore evaluating optimization within inference engines and training workflows.

## From kernels to an inference engine

SEIS starts with a small SGLang inference engine and lets an agent modify kernels, fuse operators, and change runtime logic across multiple sessions. Code and experiment reports carry over between sessions, and parallel search chains can share discoveries. On an H100 running a single-request Qwen3-0.6B workload, the paper reports 3.27 times the throughput of the initial mini-sglang implementation. This result comes from a specific model, device, and single-request setting. It shows how much of the inference implementation can be changed over successive rounds. [SEIS paper](https://arxiv.org/abs/2610.04646) · [Project page](https://nehzux.github.io/SEIS/)

An inference implementation brings kernels, memory, and request scheduling together. Reducing an operator launch may lower latency, while changing batching can affect concurrent throughput. SEIS repeatedly tests these changes on the same inference workload, so its result measures a complete implementation. It should not be compared directly with a single-kernel speedup.

Training infrastructure adds more moving parts. A distributed training run depends on code, launch configuration, communication patterns, memory limits, and data workloads. Changing one setting can trigger an out-of-memory error or a compiler conflict, while cluster interference can make measurements fluctuate. InfraRSI searches over both training-code patches and launch parameters, and retains out-of-memory runs to help identify infeasible combinations.

Across four dense-model and mixture-of-experts (MoE) workloads, InfraRSI reports a geometric-mean speedup of 1.83× and an increase in model FLOPs utilization (MFU) from 17.4% to 30.0%. It also records experience transferred across GPU types. In one Qwen3.5-9B run on eight H100s, using filtered experience from other GPU types increased the final speedup from 1.70× with a cold start to 1.82×. These results touch on another aspect of RSI: the system produces optimized training configurations and tries to bring past experimental results into the next search round. [InfraRSI paper](https://arxiv.org/html/2611.11558v1)

InfraRSI also rechecked 1,212 historical runs offline and found that 400 did not meet its verification criteria. Reasons included incomplete runs, workload mismatches, numerical deviations, and conditions that could not be verified. For systems like this, failed runs also become part of the experience record. They can help the next round identify resource constraints or metrics that still need confirmation. Reading the speedup numbers alongside the verification method helps clarify where the results apply.

## The search process becomes part of what is improved

AlphaEvolve, KernelEvolve, SEIS, and InfraRSI show the loop improving algorithms, kernels, inference implementations, and training configurations. Another group of projects turns its attention to the loop itself, asking whether an agent can improve how it proposes candidates and selects results.

For GPU kernel search, Alibaba’s Atrex-Bench samples production inference traces. It covers 30 operators and 440 input shapes, weighted by each operator’s share of observed GPU time. This lets automated search evaluate workloads that occur in production. The accompanying Atrex Kernel Agent uses measurements to guide its next rewrite and interleaves tests of a candidate with the current implementation. [Atrex paper](https://arxiv.org/abs/2607.14541) · [Atrex Kernel Agent](https://github.com/alibaba/atrex-kernel-agent/releases/tag/v0.4.0)

To see whether the experimental method itself has improved, compare the search process before and after the change. Keep the base model, task type, and experiment budget fixed, then ask whether the updated method finds verifiable improvements faster on new tasks. Sakana AI’s Darwin Gödel Machine retains multiple agent versions, allowing search to continue from historical versions. In its SWE-bench experiment, the system that could continue from the archive reached 50%, compared with 39.7% for a greedy method that extended only the current top-scoring version. Different branches can preserve different capabilities, leaving room to combine and explore them later. [DGM paper](https://arxiv.org/html/2505.22954v3#S4)

RRSI, from Google Cloud AI Research and collaborators, constrains how much an agent can change its own harness. A harness includes the prompts, tools, control flow, and context management around a model. RRSI records the hypothesis behind a change, its code diff, score, and cost, then uses held-out tasks to check whether gains transfer. Two independent searches improved all six held-out splits over the initial version. The result suggests that search quality can account for more than the highest score. Performance on unseen tasks and the system’s operating cost also matter. [RRSI paper](https://arxiv.org/html/2609.24972v3#S4)

Weco’s AIDE² pushes the recursion another step outward. An outer agent modifies the code of an inner research agent, which performs AI research-engineering tasks under a fixed budget. In one eight-day run, the system proposed 99 changes and accepted seven, raising its selection score from 0.703 to 0.778. The final version also transferred to four held-out benchmarks. The researchers tested whether the improved agent could take over as the outer proposer. The small comparison so far is inconclusive on whether the improver itself became more effective. The cycle for improving task execution can be tested experimentally. Evidence that the improver can improve the improvement process is still accumulating. [AIDE² paper](https://arxiv.org/html/2609.26457)

## RSI is shifting the research bottleneck

As models generate candidates and automated systems run experiments, the human contribution gradually shifts. Whether an evaluator measures the intended outcome, whether failures are interpretable, and whether results reproduce across tasks all affect how far a search can go. AI increases the number of attempts, while making it more valuable for researchers to judge evidence and choose directions.

Anthropic’s internal measurements published in 2026 show that Claude leads most of the work in 26% of the evaluated model-research tasks, with human supervision. The measurement found no work completed fully autonomously. METR’s independent assessment of Anthropic’s internal progress estimated that the growth rate of internal model-capability metrics since October 2025 was about 1.9 times the earlier rate, with a 95% confidence interval of 1.5 to 2.8. METR judged that AI automation likely contributed to much of the recent acceleration, while noting substantial uncertainty in attribution. Task-automation share and model-capability growth describe different parts of the research process. [Anthropic](https://www.anthropic.com/institute/measuring-pace-of-ai-development) · [METR](https://metr.org/blog/2026-11-05-anthropic-ai-rd-acceleration-assessment/)

These developments bring RSI down from the distant question of whether a model can build a more capable model to several engineering changes that can be observed separately. Can automated evaluation lead to continued algorithmic gains? Can infrastructure systems accumulate useful experience across rounds? Do search methods transfer to new tasks? Can a research agent take over the design of the next research agent? Each question calls for different evidence. Existing projects cover some parts, while a complete recursive chain has yet to appear in a public experiment.

The changes in AI infrastructure are especially worth following. Search is moving from individual operators toward full inference and training systems. The record of each improvement is expanding from a code patch to include experimental conditions, failure causes, and experience across hardware types. Infrastructure is both what gets improved and the environment that carries experiments, verification, and memory. Future progress may depend on whether these systems can turn more experiments into knowledge that is reproducible and transferable.

This article draws on public posts, papers, and code repositories from Anthropic, Meta, Google, Alibaba, and others. The performance numbers come from different hardware, workloads, and evaluation methods. They describe their respective experiments and should not be read as a direct ranking. The account of RSI in AI infrastructure is an interpretation of these public examples.
