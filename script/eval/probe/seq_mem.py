"""Peak VRAM / host RAM of one SFT step (forward + backward + 8-bit AdamW) at several sequence lengths, on random tokens."""

import argparse, resource, sys, time
from pathlib import Path

from unsloth import FastLanguageModel   # must precede transformers to enable optimizations
import torch

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
import train.sft as sft
from train.utils import load_trainable

# Setting =================================================
LENGTHS = [4096, 8192, 12288, 16384]
LOSS_FRACTION = 0.5                     # share of tokens that carry loss (assistant part)

# Functions ===============================================
def gb(x: float) -> float:
    return round(x / 1024 ** 3, 2)


def cgroup_peak() -> str:
    """memory.peak of this process's cgroup (systemd-run scope): RSS plus pinned and page-cache pages charged to it."""
    try:
        rel = Path("/proc/self/cgroup").read_text().strip().split("::")[-1]
        return f"{gb(int(Path(f'/sys/fs/cgroup{rel}/memory.peak').read_text()))} GB"
    except (OSError, ValueError):
        return "n/a"


def step(model, opt, length: int, vocab: int) -> None:
    ids    = torch.randint(1000, vocab - 1, (1, length), device="cuda")
    labels = ids.clone()
    labels[:, : int(length * (1 - LOSS_FRACTION))] = -100
    loss = model(input_ids=ids, labels=labels).loss
    loss.backward()
    opt.step()
    opt.zero_grad(set_to_none=True)
    torch.cuda.synchronize()


# Run =====================================================
if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--base", default=sft.default_config()["base_model"])
    cli.add_argument("--lengths", type=int, nargs="+", default=LENGTHS)
    cli.add_argument("--rank", type=int, default=sft.default_config()["lora_rank"])
    cli.add_argument("--grad-checkpt", choices=["true", "unsloth"], default=None,
                     help="true = checkpoints on GPU, unsloth = offload them to host RAM (default: sft config)")
    args = cli.parse_args()

    cfg = {**sft.default_config(), "base_model": args.base, "max_seq_length": max(args.lengths), "lora_rank": args.rank}
    if args.grad_checkpt:
        cfg["grad_checkpt"] = True if args.grad_checkpt == "true" else "unsloth"
    model, tok = load_trainable(cfg)
    model.train()
    import bitsandbytes as bnb
    opt   = bnb.optim.AdamW8bit([p for p in model.parameters() if p.requires_grad], lr=1e-5)
    vocab = model.config.get_text_config().vocab_size if hasattr(model.config, "get_text_config") else model.config.vocab_size
    print(f"loaded: {gb(torch.cuda.max_memory_allocated())} GB VRAM, vocab {vocab}, grad_checkpt={cfg['grad_checkpt']}, rank {args.rank}", flush=True)
    for n in sorted(args.lengths):
        torch.cuda.reset_peak_memory_stats()
        t = time.time()
        try:
            step(model, opt, n, vocab)
        except torch.cuda.OutOfMemoryError:
            print(f"{n:>6} tokens: OOM (peak so far {gb(torch.cuda.max_memory_allocated())} GB)", flush=True)
            break
        print(f"{n:>6} tokens: VRAM peak {gb(torch.cuda.max_memory_allocated())} GB (reserved {gb(torch.cuda.max_memory_reserved())}), "
              f"host RSS peak {gb(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)} GB, "
              f"cgroup peak {cgroup_peak()}, {time.time() - t:.1f}s", flush=True)
        torch.cuda.empty_cache()
