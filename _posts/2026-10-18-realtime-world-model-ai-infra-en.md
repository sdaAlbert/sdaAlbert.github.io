---
title: "Infrastructure for Interactive Video Generation (World Models): Latency, Scene Memory, and Multi-User Serving"
date: 2026-10-18
permalink: /posts/realtime-world-model-ai-infra/en/
lang: en
translations:
  zh: /posts/realtime-world-model-ai-infra/
  en: /posts/realtime-world-model-ai-infra/en/
author_profile: false
read_time: true
excerpt: "Interactive video generation must maintain the world each player has experienced. This article examines how state placement shapes GPU execution, scene memory, streaming, and multi-user serving."
tags:
  - AI Infrastructure
  - Video Generation
---

Interactive video generation means continuously creating a scene in response to player input. The model receives an initial frame, key presses, camera movement, or similar controls, and predicts what the player will see next. A conventional game first updates character coordinates, object positions, and collisions, then lets a renderer draw the next frame. A generative system can modify images produced by a game, build a renderable 3D scene, or continue a scene directly from earlier frames. All three approaches produce video, but they preserve changes to the scene in different ways.

Models usually generate video in short chunks. They first compute over a compressed representation of the image, then decode it into pixels for playback. Some models repeat this computation several times to turn noise into a clear frame. AI infrastructure must keep input capture, GPU computation, video decoding, and playback on a shared timeline, while retaining the data needed by each ongoing session. Frames per second (FPS) measures output rate; interaction latency measures how long a player waits to see a response to an input. Even a fast model can feel sluggish if the player is watching a queue of old frames.

When a player presses forward, the view should change promptly. After walking around and returning, the street layout should still make sense, and a door they opened should remain open. Google’s Genie 3 public demo reaches 720p at 24 FPS and shows about one minute of visual memory; details of its inference implementation have not been made public. [Official Genie 3 overview](https://deepmind.google/blog/genie-3-a-new-frontier-for-world-models/) Whether a scene remains consistent on return depends on how the system stores its **state**: a game program can record positions and rules, a 3D scene can preserve renderable geometry, or a model can retrieve the scene from old frames or internal features. Who maintains that state determines what infrastructure must store and move, how much history each generation reads, and how GPU resources are assigned when many players are online. The work discussed here includes public implementation or measurement details, so the approaches can be compared through state placement and the video execution path.

## Reading guide

1. [The game program owns state: EdenLive handles the timing gap between input and video](#edenlive)
2. [An explicit 3D scene: MoVerse stores revisitable places in renderable geometry](#geometry)
3. [The model retrieves old frames: finding places within a fixed budget](#retrieval)
4. [The model compresses history: controlling memory without forgetting](#compressed)
5. [Streaming runtimes: getting video to respond on time](#runtime)
6. [Multi-user serving: WorldMove migrates sessions within playback deadlines](#migration)
7. [What these approaches mean for infrastructure](#synthesis)

## The game program owns state: EdenLive handles the timing gap between input and video {#edenlive}

### How game state reaches the generator

EdenLive takes simplified frames from a game, a first frame that sets the visual style, and a text prompt, then turns the simplified frames into more detailed video. The game program still calculates player position, collisions, and camera movement. The model therefore does not have to infer the game rules, but each generated frame must correspond to the right moment in the game. If the player has already turned while the screen is still showing the view from before the turn, a faster model alone will not make the interaction feel responsive. [EdenLive project and code](https://github.com/VAST-AI-Research/EdenLive)

### Reference-frame capture and playback cadence

EdenLive’s open game example exposes the full path. The browser advances the simulation 60 times per second and captures 16 reference frames per second by default. The model processes 12 frames at a time, or about 0.75 seconds of game time. While it generates the current video chunk, the system captures reference frames for the next one, then plays the generated frames over WebRTC, a real-time browser video protocol. The documentation estimates about two chunks of input-to-display delay when simulation, generation, and playback run at similar rates.

### The cost of capturing reference frames

The same run reports 27.87 FPS for model generation alone: 12 frames take about 430 milliseconds. Rendering the 12 reference frames in the browser and encoding them as JPEG takes another 100 to 123 milliseconds. The code captures these frames while the model is working, hiding as much of that cost as possible. It also uses the same render for the preview and model input, so they do not show different game states. If the container lacks NVIDIA graphics drivers, Chromium falls back to software rendering, and frame capture can become a new bottleneck instead of overlapping with model work. [Capture timing and GPU rendering notes](https://github.com/VAST-AI-Research/EdenLive/blob/main/realtime/integrations_v2/eden/apps/game2v/README.md)

### LightX2V: single-GPU inference acceleration

EdenLive also publishes a single-GPU inference acceleration setup. In the project documentation, LightX2V uses low-bit quantization to shrink model weights, fused GPU operators to reduce intermediate data movement, and optimizations to the key-value cache (KV cache) that stores historical features. `torch.compile` and CUDA Graphs reduce repeated execution overhead, while streaming LightTAE decoding passes generated frames to the player sooner. The documentation reports about 24.7 FPS inference throughput for the 5B model at 1280 × 704 on one RTX 5090, enough to supply frames for 24 FPS playback. [EdenLive LightX2V real-time inference setup](https://github.com/VAST-AI-Research/EdenLive#real-time-inference-with-lightx2v-on-rtx-5090)

### From model throughput to input response

EdenLive shows two layers of infrastructure work: the model must produce playable frames in time, and the serving path must align game input, reference frames, generated output, and playback. Model throughput measures the first; the time from a key press to its displayed response and playback stalls measure the second. Browser rendering, frame capture, and playback buffering all belong in the end-to-end path.

## An explicit 3D scene: MoVerse stores revisitable places in renderable geometry {#geometry}

MoVerse studies another kind of navigable scene. Starting from one photograph, it first fills in a panorama, then builds a 3D Gaussian scene that can be rendered from different viewpoints. When the player moves the camera, the system renders a rough view from the scene and a video model adds detail. A Gaussian scene is a collection of spatial points with attributes such as position and color; here it serves as long-term scene memory. The video model only needs to keep short-term context, rather than relying on an ever-growing history of frames to remember the whole scene. The paper reports an exploration rate of 8 FPS on a single RTX 4090. [MoVerse paper](https://arxiv.org/abs/2606.13376)

This design moves the infrastructure question to the boundary between two stages. Teams need to measure how long scene construction takes, how much GPU memory the scene occupies, and whether geometry rendering can produce the model’s next input in time. The reported 8 FPS describes sustained generation in the paper’s setup; input-to-display latency also depends on geometry rendering, video-chunk generation, and playback buffering. If objects in the scene must change over time, the system also needs a way to update the 3D scene and invalidate outdated renders. These runtime questions follow from the paper’s architecture. [MoVerse method and inference setup](https://arxiv.org/html/2606.13376v2)

## The model retrieves old frames: finding places within a fixed budget {#retrieval}

Another approach lets a model generate the next video chunk directly from player actions and existing frames. This is called chunk-wise autoregressive generation: each new chunk depends on the chunks generated before it. The model needs recent frames to keep motion continuous, and it needs older frames when the player returns to a place they have already visited. Feeding every past frame back into the model would make computation and memory grow throughout the session.

### Tencent WorldPlay: retrieve a relevant view from history

Tencent Hunyuan’s WorldPlay is a real-time video model controlled by camera movement, and it extends a scene by 16 frames at a time. For the next chunk, it selects the three most recent chunks to maintain motion continuity, then retrieves an older frame related to the current camera view. The retrieval uses field-of-view overlap and camera distance. After selecting an old frame, the system also adjusts its position in the model’s input timeline so that a large real-time gap does not cause the model to ignore it. The runtime must retain old frames and camera positions, then filter, encode, and combine the selected history before each generation. [Official code](https://github.com/Tencent-Hunyuan/HY-WorldPlay)

Video diffusion models repeatedly compute from noise to produce a clear frame. WorldPlay uses distillation to reduce generation to four denoising steps, then distributes video-chunk computation across eight H800 GPUs. Its image decoder also runs in parallel, decoding and transmitting frames in batches. The paper reports 720p output at 24 FPS for this setup. The generation backbone, decoding, and transfer together form the real-time path, so each stage must fit within the input-to-display timeline. [WorldPlay inference method](https://arxiv.org/html/2512.14614v1)

### Matrix-Game 3.5: retrieve patches by spatial location

Matrix-Game 3.5 also lets users explore generated worlds along camera trajectories, with a focus on scene changes when turning or returning to an old location. Matrix-Game 3.0 searched for old frames by camera position; version 3.5 divides memory into smaller spatial patches and retrieves only the regions visible from the new viewpoint. It also stores static scenery separately from moving characters. At runtime, memory therefore consists of retrievable patches and a spatial index. The system must decide which patches to load and when to encode them into the model, all within the deadline for the next chunk. The paper reports up to 20 FPS for single-GPU 720p generation. Its one-minute evaluation lists a peak memory use of 77 GB on one GPU, showing the capacity cost of retrievable memory. [Matrix-Game 3.5 preprint](https://arxiv.org/abs/2608.29910)

### ReWorld: keep old-place features in CPU memory

ReWorld also lets players explore generated scenes through camera movement, but fixes the amount of history available to each computation at 12 video chunks: the five most recent chunks maintain motion continuity, six are retrieved from older places based on the current position, and one serves as an initial anchor. It keeps features for up to 30 old places in CPU memory and transfers only the selected chunks to the GPU. During training, it also randomly drops some old chunks so that the model can work with this discontinuous history at inference time. [ReWorld paper and cache design](https://arxiv.org/html/2608.23565v1)

### Alaya-EVOKE: bounded geometric reads and writes for long-term memory

Alaya-EVOKE generates video in 1.5-second chunks. Each chunk reads about 3.2 seconds of recent video, the current camera path, and the instruction; older parts of the scene are kept separately as geometric memory. The paper reports stronger image quality, scene consistency, and physical plausibility than the few-step models it compares on WBench navigation tests. [Alaya-EVOKE paper](https://arxiv.org/abs/2608.13546)

To add a scene to memory, the system estimates depth from the new video and reconstructs spatial geometry. When the player returns, it selects up to eight relevant views based on camera position and renders them into reference images for the current view. In its long-duration test, memory is capped at 90 seconds and stores one frame out of every three. This window sets both how much history can be read and how far back the system can remember.

To reduce generation time, the team first trains a teacher that can handle long sequences, then distills it into a student that needs only three denoising steps per chunk. The teacher groups long videos into chunks, samples a few distant frames, and uses linear attention to compress their cues, so training compute and memory grow linearly with video length. The student is trained over 30-second generation sequences to learn long-term consistency and mid-session instruction changes. The paper times denoising and geometric memory separately: on one H200 at 384 × 640, denoising a 1.5-second chunk takes 2.11 seconds, while the geometry-memory path adds 1.84 seconds per chunk. For infrastructure, the split matters: fewer denoising steps reduce generation compute, while reading and rendering old scenes create another GPU path that needs its own optimization. [Paper experiments and ablations](https://arxiv.org/html/2608.13546v2)

### How retrieval scope becomes a runtime budget

These approaches retrieve history at different levels: full frames, spatial patches, a fixed number of feature chunks, or geometric memory. ReWorld moves part of its long-term memory from GPU memory to CPU memory, so selected features must be moved back in time for each revisit. Evaluation should include revisit consistency, retrieval and transfer time, memory per session, and input-to-display latency.
## The model compresses history: controlling memory without forgetting {#compressed}

### SANA-WM: compress long history into a fixed-size state

SANA-WM generates minute-long videos from an initial frame and a predefined camera path. Its public tests focus on the cost of generating long sequences. Standard attention stores historical features in a key-value cache (KV cache) for later frames to query; the cache grows as the video gets longer. SANA-WM uses linear attention to fold much of the history into a fixed-size state while keeping some standard attention. This lets it handle a one-minute 720p sequence on a single GPU. Its distilled, low-precision version reports 34 seconds for the **denoising stage** of a 60-second video on an RTX 5090. [SANA-WM preprint](https://arxiv.org/abs/2605.15178)

### HLA-WM: recover information about old places

HLA-WM complements this kind of fixed-size memory. If the camera leaves a room for a long time, a continually updated state may lose details about earlier doors and windows. HLA-WM does not retrain the original generator. Instead, it saves a compact summary of state changes after each video chunk. When the camera returns to an old location, it retrieves relevant summaries using camera geometry and reconstructs the state needed for that view. The method keeps recent information while recovering some distant history by location.

In HLA-WM’s 60-second context experiment, these history summaries use 2.15 GiB, about 12 times less than storing the full KV history. The authors measure up to a 1.6% throughput decrease while revisit-frame similarity improves. For deployment, each ongoing session still needs its summary saved and updated. [HLA-WM efficiency results](https://arxiv.org/abs/2610.05739)

### Ant LingBot-World 2.0: coordinate compute and memory during continuous generation

LingBot-World 2.0 continuously generates explorable video from an initial frame and player input, supporting movement, combat, and events triggered by text. The paper reports that the complete system outputs 720p at 60 FPS. This stream also goes through spatial enhancement and temporal frame interpolation, so the native frame rate of the generation backbone should be measured separately. Its one-hour continuous-generation test examines long-term visual stability. To assess scene memory, a test could also include leaving and returning to a location during continuous play. [LingBot-World 2.0 paper and deployment section](https://arxiv.org/html/2607.07534v1)

Its public infrastructure techniques address computation and memory together. Compilation and optimized attention operators reduce the generation backbone’s cost; multiple GPUs split the computation; and a separate image decoder overlaps its work with generation of the next chunk. The history cache is selected dynamically according to current actions, reducing how much old content each chunk reads. As a session gets longer, that selection affects both read cost and whether an old scene can be recovered when needed. The paper also uses a vision-language model to propose triggerable scene events. Event detection and video generation are two stages of computation, and both belong in any measurement of action response. [LingBot-World 2.0 deployment section](https://arxiv.org/html/2607.07534v1)

### PixVerse R2: adapt memory and chunk length to the interaction

PixVerse R2’s technical note focuses on memory and acceleration in a real-time generation model. It divides memory into three kinds: fixed anchors preserve characters, environments, and rules; recent history preserves motion and scene changes; compressed features preserve objects that may matter later. It also adjusts video-chunk length to the input: key presses use short chunks for faster feedback, while a complete text event can use a longer chunk to preserve motion and audio continuity. Memory length and chunk length therefore become runtime budgets. The authors report that more than 90% of historical attention connections can be skipped per chunk. Training with replayed generation errors reduced its long-sequence brightness-drift metric by 35.8% in an internal evaluation. These results point to two system questions: how to reduce the history read for each chunk, and whether the model can recover from an incorrect state without resetting. [PixVerse R2 technical note](https://pixverse.ai/en/blog/pixverse-r2-scaling-real-time-omni-world-models)

### World-T3: write scene memory into an updatable state

World-T3 studies whether visited scenes can be written directly into an updatable set of model parameters, which the model reads according to camera position. The paper says the state size and per-step computation do not continue to grow with exploration time. It reports 20.6 FPS at 1280 × 704 on a single B200. [World-T3 preprint](https://arxiv.org/abs/2610.17434) These frame-rate results come from continuous generation tests. In multi-user serving, teams would also need to measure how each player’s state is updated in order, where it is saved when a session pauses, and which version is restored when it resumes. Frame rate alone does not tell us the cost of managing that state.

## Streaming runtimes: getting video to respond on time {#runtime}

Even when the models described above generate video in chunks, the GPU and the screen operate at different speeds: the GPU produces chunks at its own pace, while the screen plays frames at a fixed rate.

### Alibaba HappyOyster: build a world before starting a live session

HappyOyster creates an explorable world from a prompt and a first frame, then delivers it as a real-time audio-video stream. Alibaba’s published details focus on the API lifecycle: the server builds a world in the background, the client checks progress, then joins through a real-time communications SDK and sends movement or text instructions. The server uses a long-lived key to manage the world; the client receives a short-lived credential to join. [HappyOyster API and SDK documentation](https://docs.bailian.console.aliyun.com/en/model-studio/happyoyster-overview), [Create World API](https://www.alibabacloud.com/help/en/model-studio/happyoyster-acting-create-world-api-reference)

The path has two stages: world construction before entry and continuous generation after entry. Measure time until the world can be joined, input-to-display latency, and GPU and connection use in each stage to identify where the wait occurs.

### Murea InWorld: connect world state, planning, and generation

Each InWorld turn plans an event, generates the corresponding audio and video, then updates character and object state from the final frame. Murea-Mind handles planning; Murea generates the media. Long instructions are split into segments. Streaming retains the latest video segment but keeps a longer audio history so dialogue can continue. Branching and multiplayer require separate session states and a way to combine player actions in one world.

Planning happens before generation, so it adds to first-response delay. The report combines event planning and prompt preparation in one call, returns what generation needs first, and prepares supplemental suggestions in parallel. Its infrastructure focus is reducing serial wait and managing video, audio, and world state for each session.

On eight H20 GPUs, the end-to-end baseline took 231.65 seconds per generation with 50 model steps. After optimization, it took 6.96 seconds, a 33.3× speedup. A single RTX PRO 6000 Blackwell generated 5.04 seconds of 720p video in 3.6 seconds. Fused operators were enabled throughout the reported stages.

The optimizations target different costs: few-step distillation reduces the model to four steps; SageAttention accelerates attention; Adaptive BlockCache reuses intermediate results between nearby denoising steps and caches reference-image encodings; super-resolution generates a smaller image before enlarging it. The report also uses Ulysses to distribute video and audio computation across GPUs. [Murea InWorld technical report](https://murea.ai/page/paper/InWorld-technical-report.pdf)

### NVIDIA FlashDreams: manage input, generation, and playback queues

NVIDIA’s FlashDreams is an open-source runtime that connects a generation model to an interactive interface; EdenLive’s real-time service also uses it. FlashDreams runs model generation and interface playback on separate threads, puts input events in a buffer with independent read positions, and sends generated results to a bounded playback queue.

A bounded queue forces the system to handle mismatched rates. If the model runs ahead, it can pause generation or drop old frames that can no longer be played in time. If the screen runs out of frames, it can repeat the most recent one or wait for a new frame. Interactive play usually values a prompt response to new input, while offline frame-by-frame comparisons need every frame preserved. When a player presses reset, the runtime assigns an identifier to the new generation and drops any unplayed frames from the previous one, preventing the old scene from flashing back. [Playback queue and reset design](https://github.com/NVIDIA/flashdreams/blob/main/ARCHITECTURE.md)

Multi-GPU models also need every GPU to stay synchronized on the same video chunk. FlashDreams receives browser input on the primary GPU and sends actions and reset events to the others before a chunk begins. Each GPU confirms the event before entering the same order of model computation and communication. If one GPU skips a step on its own, the others may wait indefinitely. Infrastructure work here includes event delivery, queue policy, cross-GPU coordination, and failure handling; it goes beyond speeding up a single model operator.

### Waypoint 1.5: separate control updates from displayed frame rate

Waypoint 1.5 offers another way to examine interaction speed. It uses keyboard and mouse input to control generated video and is designed to run on consumer GPUs. The paper reports compressed frames generated per second, final displayed frame rate, and control-input update rate separately. Its video representation compresses 60 original frames into 15 internal time steps, generates them one by one, and uses a lightweight decoder to restore the video. The paper also keeps the history cache unchanged during denoising and writes it only after the current frame is complete, preventing unfinished content from contaminating the next frame. [Waypoint 1.5 technical report](https://arxiv.org/html/2609.37107v2)

This suggests a concrete requirement for benchmarks: record when a key press enters the system, which internal time step receives it, when that step finishes, and when its frame appears on screen. The paper provides tables for internal frame throughput across several GPUs; using those numbers alone to compare player experience would miss input batching and playback queues. It also shows that lightweight decoding, fixed-shape compilation, and low-precision inference can reduce single-GPU cost, provided that image quality and response time are evaluated alongside them.

### DreamX-World: overlap decoding with the next generation

DreamX-World 1.0 starts from text or an image and lets the user guide generation through camera movement. Like the retrieval approaches above, it uses camera geometry to recover old views. It also distills a generation process that would otherwise require many rounds into a small number of steps. At deployment, generation, history-cache updates, and video decoding run as a pipeline: while one chunk is being decoded, the GPU begins computing the next. The paper also uses low-precision operators, reuses some denoising computation, trims the decoder network, and distributes long-sequence computation across GPUs. [DreamX-World method and inference section](https://arxiv.org/html/2606.16993v1)

In a generation setup using eight RTX 5090 GPUs, the paper reports up to 16 FPS. Multiple GPUs enable continuous output, while the GPU allocation per session, cross-GPU communication, and time to the first visible response become costs to measure in a serving deployment. [DreamX-World paper](https://arxiv.org/abs/2606.16993)

### Light Interaction: read only the history needed for the current action

Light Interaction introduces inference optimizations for models such as WorldPlay that retrieve old frames, without retraining the model. It uses the player’s trajectory to decide how much history to read and how much computation to perform: it skips irrelevant old frames while exploring a new place and reuses some denoising results when revisiting a familiar one. For historical features that still need to be read, it uses sparse attention operators.

On a single A100, generating a ten-second 480p video, Light Interaction reduces HY-WorldPlay’s generation-backbone latency from 228.60 to 88.24 seconds. The paper also fuses the preparation and retrieval of historical features into GPU operators, reducing the cost of sparse indexing itself. At runtime, the system therefore needs to decide both which old frames to read and how to organize and move them on the GPU. [Light Interaction preprint](https://arxiv.org/html/2605.31158v3)

### minWM: an end-to-end recipe for reproducing real-time autoregressive generation

minWM adapts an existing video model to continue generation in response to camera movement. It publishes code and checkpoints for the full process, from controllability training and autoregressive training to few-step distillation and streaming inference. Researchers can use it to reproduce a basic question: how should training change the model’s input, history dependence, and denoising steps so that the next video chunk can start sooner? [minWM paper and open-source project](https://arxiv.org/abs/2605.30263)

### StreamDiffusionV2: schedule multiple videos by frame deadlines

StreamDiffusionV2 targets real-time video-stream generation and studies how multiple video streams can share a GPU. Its use case differs from a revisitable game world. The paper keeps each processed video segment short, then adjusts the number of concurrent streams according to per-frame deadlines. Across multiple GPUs, it pipelines model layers and denoising stages and redistributes layers to prevent a GPU that also handles video decoding from slowing down the whole pipeline. [StreamDiffusionV2, MLSys 2026](https://arxiv.org/html/2511.07399v2)

This work suggests setting the scheduling goal in terms of whether each video stream produces frames on time, rather than total FPS alone. Combining more sessions can improve GPU utilization, but also increase the wait for each stream. Its frame-rate and first-frame measurements on four H100 GPUs belong to this video-stream task; they are not a direct measure of player input latency. The transferable ideas are deadline-aware batching, measuring time spent at each GPU stage, and including cross-GPU communication in the end-to-end budget.

### Shengshu Vidu S2: let inference stages share GPUs

Shengshu’s Vidu S2 targets real-time digital characters and video editing, an adjacent real-time vision workload. Its paper describes an inference setup in which video encoding, the generation backbone, refinement, and decoding take turns using the same GPUs, avoiding a separate GPU group sitting idle for each module. The system also selects attention algorithms by model layer and uses W8A8 low-precision matrix operations, operator fusion, and CUDA Graphs to reduce compute and launch overhead. Multi-GPU runs compress data exchanged between devices. The Avatar path reports about 25–42 FPS at 720p, while the editing path focuses on end-to-end latency from input video to output. [Vidu S2 paper](https://arxiv.org/abs/2609.11638)

This kind of time-sharing may also help world models: when scene encoding, generation, upscaling, and decoding belong to one request path, GPU planning can allocate shared resources according to each stage’s measured runtime rather than reserving a fixed GPU group for a stage that is temporarily idle.

## Multi-user serving: WorldMove migrates sessions within playback deadlines {#migration}

For a single player, the model state can stay on one group of GPUs. As more players join, the cluster must decide which GPU should host each session. A session’s history cache may grow to several gigabytes and changes after every video chunk. Loading the model weights onto a new GPU does not give it the world that this player has just experienced.

### WorldMove: migrate session caches at video-chunk boundaries

The systems preprint *Stateful Worlds, Stateless Elasticity* studies this migration problem on controlled GPU setups. At a video-chunk boundary, WorldMove organizes a session’s cache, copies it to a target GPU, and checks that the contents match before allowing the target to continue generation. Whether to migrate depends on the interaction deadline, cache size, network bandwidth, and how much the data changes during copying. The authors report about 18.8 milliseconds for same-node migration. In a four-node network experiment, a separately executed migration moved about 1.67 GB of state in 182 milliseconds, against a 400-millisecond interaction-chunk budget. [WorldMove preprint](https://arxiv.org/abs/2607.10389)

The preprint tests the serving loop and fast migration mechanism separately. Bitwise-identical continuation also requires the same GPU architecture and controlled software configuration. Its scheduling rule is concrete: the target GPU needs room for the session, copying and verification must finish before the next chunk is played, and several sessions must not saturate the same network link at once. When these conditions cannot be met, keeping a session on its current GPU or using a warm standby is more compatible with continuous playback than migrating without checking capacity.

### Memory design determines what must move

WorldMove’s experiments use a model cache as the migration object. Other memory designs change what needs to move. ReWorld keeps its old-location library in CPU memory, so a target machine needs access to that library and must prepare the selected features before the next generation. World-T3 continuously updates internal state, so migration needs to identify which video chunk has been committed. If several sessions share a MoVerse 3D scene, the scene itself could be managed separately from each player’s short-term context. These deployment questions follow from the structure of each state representation.

## What these approaches mean for infrastructure {#synthesis}

### Make state readiness part of the interaction deadline

All these approaches lead to the same engineering question: is the correct player state ready before the next video chunk begins? Keeping state in the game program, a 3D scene, a history library, or a model cache creates different synchronization, rendering, retrieval, or migration costs. Asynchronous world creation and time-sharing between inference stages also determine how GPU and connection resources are occupied. Compare designs by measuring time to enter a world, input-to-display latency, memory per session, and concurrent session capacity together.

### Extend evaluation from image quality to multi-turn memory

Recent evaluations separately measure visual quality, player response, and world state after multiple turns. WorldMark separates action response, consistency on revisiting a location, and image quality; WBench uses multi-turn cases for navigation, character actions, event changes, and camera movement. Infrastructure evaluations can reuse these action sequences while recording retrieval, denoising, decoding, input-to-display latency, and per-session resource use, so service cost and visual results can be compared on the same scenarios. [WorldMark paper](https://arxiv.org/html/2604.21686v2), [WBench paper](https://arxiv.org/abs/2605.25874)

### Read resource metrics alongside world state

Released in October, WorldMemBench separates retention of static content from memory of dynamic events, using 260 cases with repeated departures and revisits. It finds that remembering the appearance of people, objects, and environments does not guarantee remembering events triggered by the player; repeated revisits also reveal continued memory decay. Infrastructure researchers can use the same revisit tasks to track whether a door remains open, whether the scene stays spatially consistent, retrieval time, GPU memory, and concurrent sessions. The goal is to keep more player worlds running correctly within acceptable response times and resource budgets. [WorldMemBench paper](https://arxiv.org/abs/2610.19063)
