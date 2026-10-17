---
title: "Generative AI Infrastructure for Game Content: Video Generation and Real-Time Characters"
date: 2026-10-17
permalink: /posts/game-content-generation-ai-infra/en/
lang: en
translations:
  zh: /posts/game-content-generation-ai-infra/
  en: /posts/game-content-generation-ai-infra/en/
author_profile: false
read_time: true
excerpt: "A comparison of Tencent Hunyuan, ByteDance Seed, and Anuttacon on systems work for video-model training, offline inference, and real-time character generation."
tags:
  - AI Infrastructure
  - Video Generation
---

Generative AI for game content now extends beyond 3D assets. Concept art and image editing, video and animation, speech and sound effects, and real-time character performance are all entering creative workflows. Each creates a different infrastructure workload. Long videos and high-resolution training stress sequence length, memory, and multi-GPU communication. Offline batch generation prioritizes throughput and cost per asset. Real-time character generation must keep producing continuously while responding quickly to new input.

Public materials from Tencent Hunyuan, ByteDance Seed, and Anuttacon describe infrastructure work for video-generation systems. The sections below compare the problems that arise in training clusters, offline inference, and online streaming generation.

## Tencent Hunyuan: optimizing the training cluster, memory, and recovery

HunyuanVideo is a 13-billion-parameter video-generation model. After a video is compressed into a long sequence of spatiotemporal features, training cost comes not only from model parameters but also from attention computation, activation storage, and communication across GPUs. The report says the team ran the model on the AngelPTM training framework, used Tencent's Xingmai network for communication across servers, and scheduled GPUs through the Angel platform. [HunyuanVideo technical report](https://arxiv.org/html/2412.03603)

During training, tensor parallelism splits model computation across GPUs, while sequence and context parallelism divide long video features into segments. Ring Attention passes the information required for attention across GPUs. The team also uses FusedAttention, recomputation, and activation offloading: the first speeds up attention, while the latter two trade extra computation or host memory for GPU memory. Automatic recovery detects failures and replaces nodes; the report gives a training stability rate of 99.5%. This work makes communication, memory, and recovery time concrete constraints in large-model training.

On the inference side, text-guidance distillation combines a guidance process that originally required separate conditional and unconditional computations, reporting about 1.9× speedup. Spatiotemporal tiling lets a single GPU encode or decode higher-resolution and longer videos. One reduces model computation; the other controls VAE memory use. They optimize different stages of the video-generation pipeline.

## ByteDance Seed: extending inference optimization to decoding and system execution

ByteDance's official Seedance 1.0 report says that generating a five-second 1080p video takes 41.4 seconds on an NVIDIA L20. The team divides acceleration into model algorithms and the underlying inference system. Multi-stage distillation reduces denoising work, while a narrower VAE decoder reduces the time to decode latent features into pixels. The system layer adds operator fusion, mixed-precision quantization and sparsity, adaptive hybrid parallelism, asynchronous offloading, and distributed VAE execution. The report claims about 10× overall inference acceleration, with the VAE decoder design alone contributing roughly 2× end-to-end speedup. [Seedance 1.0 technical report](https://seed.bytedance.com/en/blog/tech-report-of-seedance-1-0-is-now-publicly-available)

This case shows that the DiT backbone is only one part of video inference time. High-resolution output still needs VAE decoding, and execution may also be constrained by memory capacity, operator-launch overhead, and multi-GPU communication. The system has to measure model computation, decoding, and cross-device scheduling along the same performance path.

## Anuttacon: generating character video continuously in real time

LPM 1.0 targets video characters for conversation: a character speaks, listens, and responds continuously to a user's voice and text prompts. The team first trains a 17-billion-parameter diffusion model, then distills it into a causal streaming generator designed for low-latency continuous output and long-term identity consistency. Anuttacon was founded by Cai Haoyu; this research concerns conversational video characters, while miHoYo's work discussed in the companion 3D article concerns asset generation. [LPM 1.0 paper](https://arxiv.org/abs/2604.07823), [project page](https://large-performance-model.github.io/), [team background](https://www.ithome.com/0/937/955.htm)

The training optimizations start with uneven data shapes: clips of different durations and resolutions create different amounts of work on each GPU. The team precomputes VAE, audio, and text embeddings, then buckets examples by token length so GPUs in one step process similar workloads. It uses FSDP for model parallelism, hybrid sharding across multiple machines, and Ulysses-style context parallelism for sequences longer than 50K tokens.

Online inference connects the generator, refiner, and VAE decoder into a pipeline, so different video chunks can run in different stages at the same time. The paper reports about 0.35 seconds per chunk on one GPU after operator fusion, torch.compile, and efficient attention, targeting continuous output at 24 fps. The system also limits how far the generation queue can run ahead of playback, preventing excessive waiting from accumulating when a user interrupts. Optimization therefore extends from single-request speed to responsiveness and scheduling across long sessions.

## What these systems reveal about infrastructure

Video-generation infrastructure brings together three connected problems. Training must balance long sequences across GPUs while managing communication, memory, and failure recovery. Offline inference must reduce denoising and decoding costs. Online systems must divide generation into video chunks that can be scheduled continuously, balancing quality, response time, and queue length.

Leading work often advances algorithms and system execution together. Distillation cuts the number of computation steps; quantization and sparsity reduce compute demand; asynchronous offloading and parallel strategies manage memory and communication; pipelines and queues shape the interactive experience. Evaluations should track video quality, per-chunk latency, time to first frame, sustained frame rate, peak memory, and concurrency cost to determine whether a local speedup improves the actual creative or interactive workflow.
