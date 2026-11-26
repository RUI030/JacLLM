# Parameters and Setup

> **In plain words.** Almost every setting here is a trade-off against **GPU memory**. A 27B model does not normally fit on one 48 GB card for training. We make it fit by:
>
> - storing the model in 4-bit (QLoRA),
> - training only small add-ons (LoRA),
> - feeding one example at a time (batch 1),
> - adding up 10 examples' worth of updates before changing the model (gradient accumulation).
>
> This file explains each knob with a worked example. Unfamiliar terms are in the [glossary](glossary.md).

The two recipes to know (values come from the recipe files, which are the record of what was actually trained):

| | `1023-v135` (Ornith-1.5-9B, main line) | `1123-qwen27b-r32` (Qwen3.8-27B, latest) |
|---|---|---|
| GPU | RTX 5080 16 GB | RTX PRO 5000 48 GB (shared server, 32 GB host RAM) |
| Quantization | 4-bit (QLoRA) | 4-bit (QLoRA) |
| LoRA | CPT r64 α32, SFT r64 α16, rsLoRA | r32 α23, rsLoRA, both stages |
| Target modules | q, k, v, o, gate, up, down | q, k, v, o, gate, up, down |
| max_seq_length | CPT 4096, SFT 16384 | 16384, both stages |
| Batch / grad_acc | 1 / 10 | 1 / 10 |
| LR | CPT 5e-5, SFT 2e-4 | CPT 5e-5 (warmup 5), SFT 2e-4 (warmup 10) |
| Optimizer | adamw_8bit, linear schedule | adamw_8bit, linear schedule, weight decay 1e-3 |
| Epochs | 1 | 1 |
| Grad checkpointing | `unsloth` (offload to host RAM) | `true` (on-GPU) |
| Packing | on | on |
| Mixing | `sequential` (curriculum) | `sequential` (curriculum) |

Sources: `script/train/recipe/1023-v135/{cpt,sft}.yaml`, `script/train/recipe/1123-qwen27b-r32/{cpt,sft}.yaml`, schema in `script/train/recipe/README.md`. The code defaults in `default_config()` are fallbacks only and differ from these (for example, CPT defaults to 3 epochs and r128). Always read the recipe.

---

## 1. Context window (`max_seq_length`)

### What it is

`max_seq_length` is how many tokens fit in one training example. Memory grows with length. On the 27B, every extra 1k tokens costs about 1 GB of VRAM. So on a fixed GPU, this is the hardest limit.

**Measured ceilings** (batch 1, 4-bit, on-GPU gradient checkpointing):

| Model, GPU | Longest trainable example | Source |
|---|---|---|
| Ornith-9B, RTX 5080 16 GB | 16k fits (13.1 GB peak) | `1022-trajectory-sft/sft.yaml` header |
| Ornith-9B, RTX PRO 5000 48 GB | 65,536 runs (42.75 GB); 81,920 runs out of memory | [report/weekly/1026.md](../../report/weekly/1026.md) |
| Qwen3.8-27B, RTX PRO 5000 48 GB | about 22.5k–25k (depends on Unsloth version and LoRA rank) | measured with `script/eval/probe/seq_mem.py` (results not checked in) |

The 27B run therefore uses 16,384, which leaves headroom.

### Why it is a big problem: trajectory fine-tuning

To teach agent behaviour, we train on **trajectories**: whole agent sessions. They are long, typically 100k–200k tokens:

- In the JacHammer production sessions, the largest request per session had a median of 125,531 tokens and a maximum of 474,763.
- Only 7 of 84 sessions fit in 64k ([report/weekly/1026.md](../../report/weekly/1026.md)).

We do not have a context window anywhere near that size, so the data must be cut.

**Scenario.** One trajectory is 150k tokens, of an agent building a todo app. Our window is 16k.

```
turn:   1  2  3 ... 20 (creates models.jac)  21 ... 60 (edits models.jac)  ... 120
tokens: |-------------------------------------- 150k -------------------------------|
window: |-- 16k --|
```

- **Truncate** (keep the end, drop the start). The sample for turn 60 no longer contains turn 20, where `models.jac` was created. The model is trained to edit a file it never saw.
- **Chunk** (cut into 10 independent 15k pieces). Same problem at every cut. Chunk 4 references paths and imports from chunk 2. This trains the model to **hallucinate file paths and dependencies**. In the production data we observed path errors in 10 of 102 tool calls after context compaction (same report).
- **Sliding window** (`--window` in `script/dataset/sft/tool_use.py`). Overlapping windows, each starting with the original user prompt and keeping the recent turns the current one depends on. This effectively reduces the problem. But because the windows overlap, the same tokens are processed several times, so **training is slow**.

We also **mask unsupported replies**: a reply that refers to a path or `old_string` not visible in its sample gets weight 0 (rule G, 210 hits, [report/weekly/1026.md](../../report/weekly/1026.md)). Whether this reduces hallucination has not been measured.

**The longer-term fix** is to make trajectories short in the first place. We are building a lean harness (Jach) and a shorter-trajectory dataset; this is in progress. See [bottleneck_and_current_solution.md](bottleneck_and_current_solution.md).

---

## 2. LoRA, and why we use it

### What it is

LoRA freezes all the original weights and trains a small add-on next to each layer. For a weight matrix W, LoRA learns two thin matrices B and A whose product B·A is the change. Only A and B are trained (Hu et al., ICLR 2022).

**Worked example: one 5,120 × 5,120 layer.**

| | Trainable numbers |
|---|---|
| Full fine-tuning (change W directly) | 5,120 × 5,120 = 26.2M |
| LoRA r32 (A is 32 × 5,120, B is 5,120 × 32) | 2 × 5,120 × 32 = 0.33M |

So LoRA trains about 1/80 of the numbers in that layer. For the whole 27B model:

- **Trainable size.** r16 is 80M trainable, r32 159M, r64 319M (`seq_mem.py` probe). That is under 1.2% of 27B.
- **Full fine-tuning would need about 432 GB.** AdamW needs about 16 bytes per trained parameter (weight + gradient + 2 optimizer states), so 27B × 16 bytes ≈ 432 GB.
- **LoRA r32 needs about 2.5 GB.** 159M × 16 bytes ≈ 2.5 GB.

### Why we use it

- **Memory.** Full fine-tuning simply does not fit on our GPUs. LoRA does.
- **Small, stackable files.** Each run produces an adapter of tens to hundreds of MB in `output/adapter/<run>/adapter/`. The SFT stage continues the CPT adapter, and adapters can be compared or swapped without copying the whole model.
- **Less forgetting.** On code and math, LoRA learns less than full fine-tuning but keeps more of the base model's other abilities (Biderman et al., TMLR 2024). That is the trade we want: learn Jac without forgetting Python and general reasoning.

### Our settings

- **Targets.** We put LoRA on all attention and feed-forward parts (q, k, v, o, gate, up, down).
- **Rank.**
  - The 9B uses **r64**.
  - The 27B uses **r32**. On the 48 GB card a bigger rank costs context length, about ±3k tokens per rank step (r16 → r32 → r64). The 27B also has more capacity to begin with.
- **rsLoRA.** We use rsLoRA, which scales the add-on by α/√r so that changing the rank does not change its strength. For the 27B, α = 23 was chosen so that 23/√32 ≈ 4, matching the v135 CPT setting of 32/√64 = 4 (comment in `1123-qwen27b-r32/sft.yaml`). rsLoRA has no peer-reviewed reference; treat it as a common practice.

---

## 3. QLoRA, and why we use it

### What it is

QLoRA stores the frozen base model in **4-bit** (the NF4 format) instead of 16-bit, and trains a normal 16-bit LoRA on top. With LoRA on all linear layers, quality matches 16-bit fine-tuning (Dettmers et al., NeurIPS 2023).

**Worked example: model weights alone.**

| Model | 16-bit (bf16) | 4-bit |
|---|---:|---:|
| Ornith-9B | about 18 GB | about 5 GB |
| Qwen3.8-27B | about 54 GB | about 14 GB (17.6 GB measured once loaded) |

In 16-bit, the 27B does not even fit on a 48 GB card before training starts. In 4-bit it leaves about 30 GB for LoRA, activations and the training example. Likewise, 4-bit is what makes the 9B trainable on a 16 GB RTX 5080. Every recipe sets `load_in_4bit: true`.

### Pitfalls

- **Merging the adapter into a 4-bit base loses accuracy.** The 27B checkpoint scored **24.0%** pass@1 merged into 4-bit vs **39.0%** kept separate, on the same 972 problems (`script/eval/Nitin-test/out/`). Evaluate with the adapter attached, or merge into a 16-bit base.
- **MoE adapters with LoRA on the experts** cannot be merged into the 4-bit base at all: the result silently behaves like the untrained base model (see `utils/model.py`).

---

## 4. Batch size and gradient accumulation

### Batch size is 1

One 16k-token example already fills the GPU, so every recipe uses `batch_size: 1`.

### The problem with batch 1

A single example gives a noisy direction:

- Example 1 is a JS → Jac translation, and says "move the weights this way".
- Example 2 is an OSP walker, and says "move them that way".
- If the model updated after each one, it would zig-zag and spin in place instead of making progress.

Some noise is fine: small batches tend to find solutions that generalize better (Keskar et al., ICLR 2017). But the noise grows as the batch shrinks (Smith & Le, ICLR 2018), and batch 1 is the extreme.

### Gradient accumulation (`grad_acc`)

With `grad_acc: 10`, the model processes 10 examples one at a time and **adds up their gradients**. Only then does it make **one** update, in the averaged direction.

```
example 1 → gradient g1 ┐
example 2 → gradient g2 │
   ...                  ├─ average → ONE update to the weights
example 10 → gradient g10┘
```

- **Memory.** It costs the same memory as batch 1, because only one example is in memory at a time.
- **Stability.** The update behaves like batch 10.
- **Time.** One update takes 10 forward and backward passes. On the 27B at 16k, that is about 190 s per update.

### Packing

`packing: true` glues short examples into one 16k sequence. A 300-token completion example would otherwise waste 15.7k tokens of padding.

- **27B CPT:** 23,880 records were packed into 820 sequences, which is 82 updates at grad_acc 10 (`logs/cpt.log`).
- **Speed:** on the PRO 6000, packing cut one SFT run from about 6.5 h to about 80 min ([docs/CLOUD_GPU.md](../CLOUD_GPU.md), doc only).
- **Caveat:** Unsloth ignores packing for Ornith, because of its hybrid linear attention ([report/v1.3/v13_report.md](../../report/v1.3/v13_report.md)).

---

## 5. Epochs

**We train 1 epoch per stage.** Every CPT and SFT recipe since `0909` uses `epochs: 1`; the one exception is `1015-toolfim-v13A` with 2.

- **Common practice.** 1–2 epochs for CPT and 1–3 for SFT.
- **Our early runs.** We tried 3 epochs very early on, and the model overfit (team-reported, not in repo; the runs predate the recipe system).
- **The 2-epoch tool-FIM run** ([report/v1.3Tool/tool-fim-spike.md](../../report/v1.3Tool/tool-fim-spike.md)). Training loss halved right at the epoch boundary: 0.154 at epoch 0.97 → 0.078 at 1.04 → 0.055 at 1.97. A sudden drop exactly when the model starts seeing the same rows again means it is recognizing them, not learning something new. Held-out loss was not measured, so this is a warning sign, not proof.
- **The literature.** Repeating data gives diminishing returns and then degrades LLMs (Xue et al., NeurIPS 2023). Up to about 4 epochs, repeated data is nearly as good as new data, and after that its value decays toward zero (Muennighoff et al., NeurIPS 2023).
- **Not yet done:** there is no controlled 1-epoch vs N-epoch SFT comparison.

**GRPO is the exception.** RL has few tasks, and its "data" is the model's own fresh attempts, so repeating tasks is normal. In the GRPO spike, 50 steps was about 7 epochs over 14 tasks ([report/v1.3RL/v13rl_report.md](../../report/v1.3RL/v13rl_report.md)). The team's observation is that the best validation accuracy came at about 3–4 epochs (team-reported; the report records only the final checkpoint, and checkpoint-25, about 3.5 epochs, is kept for comparison).

---

## 6. Curriculum: dataset order, easy → hard

### Why order matters with batch 1

With a random mix, consecutive updates come from completely different tasks. That makes the zig-zag from section 4 worse. So we order the data **from basic to advanced**, and abilities are added one at a time, like a school syllabus: you learn to write a function before you build a full app. Easy-to-hard ordering is known to speed up learning and help generalization (Bengio et al., ICML 2009).

### The order we use

In both `1023-v135` and `1123-qwen27b-r32` (`mixing: sequential`, commented "Ordered basic -> advanced"):

```
CPT:  Jac docs → small functions (composer-fn) → JS→Jac → ODM models (farm)
      → human JacHacks code → OSP programs → whole app repos

SFT:  complete a function → translate JS → translate ODM models → write OSP
      → lift Python to OSP → fix compiler errors → fix tests → implement an app from a scaffold
```

Together with grad_acc 10, each update averages 10 examples from the **same stage**, so it points in a consistent direction instead of spinning in place.

### Caveats

- **A sampler bug made early runs random.** Before commit `31da523`, the trainer's random sampler silently reshuffled "sequential" mixes, so those runs were effectively random ([docs/DEBUG.md](../DEBUG.md), doc only).
- **Sequential vs random has not been A/B tested.**
- **Possible downside: early stages are never revisited.** In v1.3, code-completion loss stayed flat and completion scores regressed ([report/v1.3/v13_report.md](../../report/v1.3/v13_report.md)).

---

## 7. Gradient checkpointing and host RAM

Training normally keeps every intermediate result from the forward pass for use in the backward pass. **Gradient checkpointing** keeps only some of them and recomputes the rest when needed. It trades extra compute for less memory (Griewank & Walther, ACM TOMS 2000).

- **`grad_checkpt: unsloth`** also moves the kept results to host RAM ("offload"). This suits the RTX 5080 PC, which has only 16 GB VRAM but plenty of RAM.
- **`grad_checkpt: true`** keeps everything on the GPU. It is required on the 48 GB server, where the 32 GB of host RAM is shared with other people. Offload there bought no extra context, and risked crashing the machine.

## References

- Hu, E. et al. "LoRA: Low-Rank Adaptation of Large Language Models." ICLR 2022. https://openreview.net/forum?id=nZeVKeeFYf9
- Dettmers, T. et al. "QLoRA: Efficient Finetuning of Quantized LLMs." NeurIPS 2023. https://proceedings.neurips.cc/paper_files/paper/2023/hash/1feb87871436031bdc0f2beaa62a049b-Abstract-Conference.html
- Biderman, D. et al. "LoRA Learns Less and Forgets Less." TMLR 2024. https://openreview.net/forum?id=aloEru2qCG
- Keskar, N. S. et al. "On Large-Batch Training for Deep Learning: Generalization Gap and Sharp Minima." ICLR 2017. https://openreview.net/forum?id=H1oyRlYgg
- Smith, S. L. & Le, Q. V. "A Bayesian Perspective on Generalization and Stochastic Gradient Descent." ICLR 2018. https://iclr.cc/virtual/2018/poster/289
- Xue, F. et al. "To Repeat or Not To Repeat: Insights from Scaling LLM under Token-Crisis." NeurIPS 2023. https://papers.neurips.cc/paper_files/paper/2023/hash/b9e472cd579c83e2f6aa3459f46aac28-Abstract-Conference.html
- Muennighoff, N. et al. "Scaling Data-Constrained Language Models." NeurIPS 2023. https://proceedings.neurips.cc/paper_files/paper/2023/hash/9d89448b63ce1e2e8dc7af72c984c196-Abstract.html
- Bengio, Y. et al. "Curriculum Learning." ICML 2009. https://doi.org/10.1145/1553374.1553380
- Griewank, A. & Walther, A. "Algorithm 799: Revolve." ACM TOMS 26(1), 2000. https://doi.org/10.1145/347837.347846
