# Cloud GPU guide (RunPod)

Lessons from bringing up Qwen3-Coder-30B-A3B training and eval on a RunPod
RTX PRO 6000 Blackwell (96GB, driver 595 / CUDA 13.2, 200GB `/workspace`
network volume). Each item is symptom → cause → fix.


## Storage: what survives a restart

| Survives (`/workspace`, network volume) | Lost on pod reset (container disk, ~30GB) |
|---|---|
| repo, `output/`, HF cache (`HF_HOME=/workspace/.cache/huggingface`) | conda env in `/root/miniforge3/envs/` |
| `/workspace/bin/jac`, `/workspace/unsloth-studio` (incl. its llama.cpp) | `~/.local/bin`, `~/.bashrc` (PATH, `HF_TOKEN`) |
| | page cache (model shards in RAM) |

Restart checklist:

```bash
PATH=/root/miniforge3/bin:$PATH TORCH_BACKEND=cu130 bash setup_env.sh jacllm   # if env is gone (~5 min)
mkdir -p ~/.local/bin && ln -sf /workspace/bin/jac ~/.local/bin/jac               # jac on PATH
export HF_TOKEN=...                                                              # write-scoped, see below
```

Keep secrets out of files you might `cat` or share: `~/.bashrc` holds
`HF_TOKEN` in plain text.


## Environment setup

- **`mamba` not found.** RunPod's miniforge lives at `/root/miniforge3` but is
  not on PATH. `setup_env.sh` falls back to `$HOME/miniforge3/bin/mamba`.
- **Env path garbage / exit 127.** mamba 2.x prints `base environment : <path>`
  for `mamba info --base`; `setup_env.sh` strips the label.
- **CPU-only torch installed (`torch==2.11.0+cpu`, `torchvision==0.2.0`).**
  Unsloth caps `torch<2.12`. On CUDA 13.2 drivers `uv --torch-backend=auto`
  picks the cu132 index, which has no build under that cap, and uv silently
  falls back to a CPU wheel. Fix: `TORCH_BACKEND=cu130 bash setup_env.sh`.
  Check with `python -c "import torch; print(torch.__version__, torch.cuda.is_available())"`.
- **`jac` for eval.** The pinned toolchain (`jac 0.36.1`) is not on PyPI
  (`jaclang` tops out at 0.16.x). Install with
  `curl -fsSL https://raw.githubusercontent.com/jaseci-labs/jaseci/main/scripts/install.sh | bash -s -- --version 0.36.1`,
  then move the single binary to `/workspace/bin/jac` and symlink it. It
  unpacks a runtime into `~/.cache/jac/` on first run (~10s), re-done after a
  restart automatically.


## `jac mcp` (MCP server for AI-assisted Jac)

- **Every tool that runs code fails as root** (`run_jac`, `graph_visualize`,
  `execute_command` with `run`/`test`), even for `print("hello")`:
  `initdb: error: cannot be run as root`. `jac run` always starts the embedded
  PostgreSQL, which refuses root, and there is no switch to disable it (the docs
  say there is one persistence stack). The error comes back inside a normal
  tool result (`isError` unset), so clients show the call as successful. Static
  tools (`validate_jac`, `check_syntax`, `search_docs`, ...) are unaffected.
- **Fix:** run the server as a non-root user (the same `jacgrader` used for
  Nitin grading), e.g. for Claude Code:

  ```bash
  claude mcp add jac -- runuser -u jacgrader -- env HOME=/home/jacgrader \
      PATH=/workspace/bin:/usr/local/bin:/usr/bin:/bin /workspace/bin/jac mcp
  ```

  Other clients: the same `runuser ... jac mcp` as `command` + `args`.
- Graph state persists across `run_jac` calls (one embedded database per
  project). `jac db stop` as that user stops the server; deleting
  `~/.cache/jac/pg/main` clears the data. The user and its cache live on the
  container disk, so `useradd -m jacgrader` again after a pod reset.


## Hugging Face

- **Downloads crawl (~5MB/s).** Unauthenticated requests are throttled; set
  `HF_TOKEN` before the first download.
- **`403 ... rights to create a model under the namespace "jaseci"`.** A
  fine-grained token scoped only to your user can't create org repos even if
  your account can. Use a write token (or add the org to the fine-grained
  scopes). `HF_TOKEN` overrides the stored `$HF_HOME/token`; check what a
  token can do with `HfApi().whoami(token)["auth"]`.
- Push adapters with `hf upload <org>/<repo> <adapter_dir> . --private`
  (`adapter/` only; checkpoints are for resuming, not sharing).


## Loading 30B weights from the network volume

- **Loading takes 30+ min (~4s per shard).** Reads from `/workspace` are slow
  one file at a time. Prefetch in parallel into page cache first (57GB in
  ~95s):

  ```bash
  ls $HF_HOME/hub/models--unsloth--qwen3-coder-30b-a3b-instruct/snapshots/*/*.safetensors \
    | xargs -P 16 -I{} cat {} > /dev/null
  ```

  The host is shared, so the cache gets evicted between runs; prefetch again
  if a load is slow.
- **bf16 load of the 30B MoE** reached 59GB VRAM at 13% loaded. Use
  `load_in_4bit: true` (~17GB).
- **Host RAM during load** peaks at ~52GB (bf16 shards quantized on the fly);
  training itself uses ~3.5GB. Plan for this on unified-memory machines.


## Long runs

- Launch detached so a dropped session doesn't kill training:
  `setsid nohup bash -ic '<python ...>' > logs/<run>.log 2>&1 < /dev/null & disown`.
- **`pkill -f <pattern>` killed my own shell** (the pattern was in its command
  line). Stop jobs by PID: `ps -eo pid,args | grep "[p]ython script/train/train.py"`.
- `script/monitor.sh logs/usage.csv 30` logs GPU/VRAM/CPU/RAM. `free` inside
  the container reports the whole host; use the `train_rss_gb` column.


## Disk budget (r64 LoRA on Qwen3-Coder-30B-A3B)

| Item | Size |
|---|---|
| base model in HF cache | 57GB |
| adapter (`adapter_model.safetensors`, fp32) | 9.6GB |
| checkpoint (adapter + optimizer state) | 15GB |
| merged 16-bit model | 57GB |

Checkpoints every `save_steps` fill 200GB fast: set
`hyperparams.save_total_limit: 2`. Saving a checkpoint also spikes host RAM
by ~9.5GB (safetensors builds the file in memory).


## Memory: what training and export actually need

Training is QLoRA: `load_in_4bit: true` quantizes the original bf16 weights to
4-bit NF4 on the fly at load (~17GB), the 4-bit base stays frozen, and only the
16-bit LoRA adapter trains (saved as fp32). The 16-bit export merges the adapter
into the *original* bf16 shards from the HF cache, one shard at a time, not into
the 4-bit copy, so nothing is dequantized and requantized; GGUF quantization
happens once, afterwards. The adapter was trained against the 4-bit base, so the
merged bf16 model differs slightly from what training saw (standard QLoRA; the
merged model and its GGUF scored like the unmerged adapter here).

Measured on the RTX PRO 6000 (VRAM from `torch.cuda.max_memory_*` and 1s
`nvidia-smi` samples, RAM = process RSS; `script/plot_usage.py` for the curves):

| Stage | VRAM peak | Host RAM peak | Time |
|---|---|---|---|
| load 4-bit base + adapter | 35.6GB (bf16 and 4-bit copies overlap while quantizing) | 58.2GB | ~5 min |
| CPT / SFT training (r64, 4096 ctx, packed) | 44.1GB steady | 3.5GB, +~6GB per checkpoint save | — |
| `save_pretrained_merged(..., "merged_16bit")` | 25.2GB | under the load peak | ~2 min |
| llama-server Q4_K_M, 16 slots × 8k ctx | ~31GB | small | — |

On a 48GB GPU: loading and merging fit; training at these settings leaves ~4GB
and may OOM with longer context or a larger batch; a Q8_0 server with 16 × 8k
slots is tight (lower `-np`). Budget ~64GB+ host RAM for the load peak.


## Training pitfalls found on this run

- **`sequential` mixing was silently shuffled.** HF `Trainer` defaults to a
  `RandomSampler`; the mixer now sets `train_sampling_strategy="sequential"`.
  Runs before commit `31da523` were effectively concat.
- **Packed SFT trained on system prompts.** `train_on_responses_only` runs after
  packing and unmasks from an assistant marker to the next user marker, which
  spans the next conversation's system prompt. `sft.py` now builds labels per
  conversation before packing (commit `4599fa7`). Unsloth drops an
  `assistant_masks` column for pre-tokenized data, so the mask travels as
  `labels`.
- **Packing is worth it for short SFT data:** ~80 min vs ~6.5h (median sample
  211 tokens), GPU 95% vs 66%. Use `grad_acc: 1` to keep ~10 samples/update.
- **CPT → SFT via `adapter:`** keeps the CPT LoRA shape (alpha 32 here, the SFT
  recipe's 16 is ignored). `train.py --resume <run>/checkpoint-N` loads the
  model from the checkpoint, so it keeps that shape too (before 09-27 this
  needed a recipe with `adapter: ""` *and* `lora_alpha: 32`).
- Verify continuation with weights, not the trainable-param count: `lora_A`
  cosine vs the CPT adapter should be ~1 at the first SFT checkpoint.


## Eval pitfalls

- **Merged 4-bit MoE model = base model.** `merge_and_unload()` on the 4-bit
  Qwen3-MoE base generated exactly like the base (code_gen answered in
  JSX/Python). `load_model` now keeps adapters with `target_parameters`
  (expert LoRA) unmerged (commit `c44edd6`). Sanity-check any new model with
  adapter on / `disable_adapter()` / merged on a *training* prompt.
- **Unmerged HF generation is slow** (~30s/sample at batch 4). Raise
  `python script/eval/batch.py --batch-size 16`, or export to GGUF (below).
- **`gate.py` used to execute model code.** Its default was `check,run`, so every
  check-passing sample ran under `jac run` (30s timeout on the direct child only,
  no memory cap). The SFT eval is check-level (`docs/EVAL.md`), and these
  samples have no entry point anyway, so the default is now `check`; opt in with
  `--checks check,run`.


## GGUF export and eval (llama.cpp)

1. Merge into 16-bit, not the 4-bit model:
   `model.save_pretrained_merged(out, tok, save_method="merged_16bit")` on the
   loaded adapter (~57GB, ~10 min). Check a training prompt still gets the trained
   answer before converting.
2. Use Unsloth Studio's prebuilt llama.cpp (`/workspace/unsloth-studio/llama.cpp`:
   `convert_hf_to_gguf.py`, `build/bin/llama-server`, `build/bin/llama-quantize`)
   instead of building one. Its CUDA backend needs the CUDA 13 runtime from
   Studio's venv on `LD_LIBRARY_PATH`
   (`.../unsloth_studio/lib/python3*/site-packages/nvidia/cu13/lib`); without it
   `llama-server --list-devices` shows `(none)` and it silently runs on CPU
   (~600x slower prompt processing). The eval launchers set this and refuse to
   start without a CUDA device. (A self-built llama.cpp works too:
   `cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=120`; point
   `LLAMA_CPP` at it.)
3. Convert in the `jacllm` env without llama.cpp's requirements file (it pins
   torch): `PYTHONPATH=gguf-py python convert_hf_to_gguf.py <merged> --outtype q8_0`.
   Q4_K_M: `llama-quantize --allow-requantize <q8_0.gguf> <out> Q4_K_M` (18.6GB).
4. Eval: `bash script/eval/gguf_eval.sh <gguf> <tag> <limit>` (llama-server +
   `openrouter.py --base-url` + `gate.py`). About 5 samples/s at 16 parallel
   slots vs ~30s/sample for the unmerged HF adapter. Per-task x class pass rates:
   `python script/eval/compare/heatmap.py --tag <tag> --out <png>`.

On RunPod, nginx listens on `0.0.0.0:8081` and proxies to `8080`: don't serve on
8081, and don't trust a healthy port as proof your server started (the launchers
check their own server process after the health check).

Serving a GGUF to real agents (jac_coder, opencode, pi), VLM merges that keep the vision tower, and the
pitfalls found doing it: `docs/SERVING.md`.

Budget disk for the merge and each quant before starting: merged 57GB, Q8_0
32.5GB, Q4_K_M 18.6GB. If only Q4 is needed, don't keep Q8 around.


## Nitin function tests on a container

`bash script/eval/Nitin-test/run_gguf.sh <gguf> <tag> test` generates through
llama-server and grades as a non-root user. Things that broke on RunPod:

- **Every test errors under root.** jac's embedded postgres runs `initdb`, which
  refuses root. Grade as `jacgrader` (`useradd -m jacgrader`); `su -` also gives
  a clean env without `HF_TOKEN`. `/root` is `drwx------`, so that user runs the
  stdlib-only graders with the system Python, not the `jacllm` env.
- **`jac test` uses xdist `-n auto`:** 128 workers here, ~30GB and ~40s for one
  correct sample. `PYTEST_XDIST_AUTO_NUM_WORKERS=4` → ~1.4GB, ~5s.
- **`systemd-run --user --scope` exists but fails** (no user bus). The graders
  now probe it; without scopes, `eval_jac.py` caps each test with an RSS
  watchdog on its process group (RLIMIT_AS breaks jac's thread creation).
- Runaway samples, verified with planted cases: an infinite loop ends as
  `timeout`, runaway allocation as `test_fail`/`memory_cap`, and a spawned
  child process is killed with the group. Embedded postgres daemonizes out of
  the group, so `grade_stream.py` stops it and wipes its data dir between chunks
  and at the end (it once grew to 1.1TB). It reached ~6GB within a single
  20-sample chunk here, so grade one run at a time on a 30GB container disk.
- **`/dev/shm` can't hold it.** The RAM disk is mounted `noexec`, and jac
  unpacks postgres binaries into the same `~/.cache/jac/pg` directory, so
  `initdb` fails with `Permission denied` and every sample becomes
  `infra_error`.
