import argparse, json, random, sys, textwrap
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from utils.classifier    import classify_structural as classify
from dataset.parser.repo import body_spans, iter_repo_files, iter_repos, strip_bodies
from dataset.pipeline    import load_prompts, report, split_and_write

# Setting =================================================
DS_FORMAT = "repo"
DS_NAME   = "Rui-jacapp-scaffold"
SOURCE    = "code"
TASK_TYPE = "scaffold2impl"
FP_KEY    = "id"

DS_ROOT = f"{Path(__file__).resolve().parent}/../../../dataset"
IN_DIR  = f"{DS_ROOT}/raw/repo"
OUT_DIR = f"{DS_ROOT}/sft/{TASK_TYPE}/{DS_NAME}"

PROMPT     = f"{Path(__file__).resolve().parent}/../template/prompt_template.json"
OUT_FORMAT = "jsonl"
VALID_SIZE = 0.2
SEED       = 3407
MIN_CHARS  = 120                        # skip trivial files (tiny stubs)

MAX_TOKENS  = None                      # None: one record per file, no length cap (--max-token)
ANSWER_MODE = "auto"                    # over-long files: full | decls | auto (full, then decls)
TOKENIZER   = "ornith-ai/Ornith-1.5-9B" # counts tokens with its chat template
PARTIAL_KEY = {"full": "scaffold2impl_partial_full", "decls": "scaffold2impl_partial_decls"}

# Functions ===============================================
def build_record(fp: str, scaffold: str, impl: str,
                 prompts: dict, rng: random.Random) -> dict:
    instruction = f"{rng.choice(prompts[TASK_TYPE])}\n\n```jac\n{scaffold}\n```"
    answer      = f"```jac\n{impl}\n```"
    return {
        "messages": [
            {"role": "system",    "content": rng.choice(prompts["system"])},
            {"role": "user",      "content": instruction},
            {"role": "assistant", "content": answer},
        ],
        "meta": {
            "source":    SOURCE,
            "format":    DS_FORMAT,
            "class":     classify(impl),
            "task_type": TASK_TYPE,
            "fp":        fp,
        },
    }

def head_label(source: str, span: tuple[int, int, int]) -> str:
    """One-line declaration head for the prompt, e.g. `def:pub load(x: int) -> list`."""
    head_start, open_at, _ = span
    return " ".join(source[head_start:open_at].split())[:160]

def declaration(source: str, span: tuple[int, int, int]) -> str:
    """Full source of one declaration (head + body), dedented."""
    head_start, _, close = span
    line_start = source.rfind("\n", 0, head_start) + 1
    return textwrap.dedent(source[line_start:close]).strip()

def build_partial_record(fp: str, source: str, scaffold: str, spans: list, group: list[int],
                         mode: str, system: str, template: str) -> dict:
    """Scaffold in; implement only `group` (indices into `spans`).

    mode=full : answer is the whole file with only `group` filled in.
    mode=decls: answer is only the `group` declarations, fully implemented.
    """
    names  = "\n".join(f"- `{head_label(source, spans[i])}`" for i in group)
    prefix = template.replace("{names}", names)
    if mode == "full":
        answer = strip_bodies(source, keep=set(group)).strip()
    else:
        answer = "\n\n".join(declaration(source, spans[i]) for i in group)
    return build_record(fp, scaffold, answer, {TASK_TYPE: [prefix], "system": [system]}, random.Random(0))

def split_file(fp: str, source: str, scaffold: str, prompts: dict, rng: random.Random,
               n_tokens, max_tokens: int, answer_mode: str) -> tuple[list[dict], str | None]:
    """Records for one file under `max_tokens`, or ([], reason) when it cannot fit.

    Bodies are packed greedily in file order: each record fills the largest run of
    consecutive bodies whose record still fits. `auto` tries `full`, then `decls`.
    """
    record = build_record(fp, scaffold, source, prompts, rng)
    if n_tokens(record) <= max_tokens:
        return [record], None

    spans  = body_spans(source)
    system = rng.choice(prompts["system"])
    modes  = ["full", "decls"] if answer_mode == "auto" else [answer_mode]
    bare   = n_tokens(build_record(fp, scaffold, "", {TASK_TYPE: [""], "system": [system]}, rng))
    if bare > max_tokens:
        return [], f"scaffold alone is {bare} tokens"
    reason = None
    for mode in modes:
        template = rng.choice(prompts[PARTIAL_KEY[mode]])
        groups, group = [], []
        for i in range(len(spans)):
            trial = build_partial_record(fp, source, scaffold, spans, group + [i], mode, system, template)
            if n_tokens(trial) <= max_tokens:
                group.append(i)
                continue
            if not group:               # one body alone does not fit in this mode
                reason = f"{mode}: body '{head_label(source, spans[i])[:60]}' too long"
                groups = None
                break
            groups.append(group)
            group = [i]
            if n_tokens(build_partial_record(fp, source, scaffold, spans, group, mode, system, template)) > max_tokens:
                reason = f"{mode}: body '{head_label(source, spans[i])[:60]}' too long"
                groups = None
                break
        if groups is None:
            continue
        groups.append(group)
        records = []
        for k, g in enumerate(groups):
            rec = build_partial_record(f"{fp}#part{k}", source, scaffold, spans, g, mode, system, template)
            rec["meta"].update({"part": k, "n_parts": len(groups), "answer_mode": mode})
            records.append(rec)
        return records, None
    return [], reason

def token_counter(tokenizer_name: str):
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(tokenizer_name)
    def n_tokens(record: dict) -> int:
        text = tok.apply_chat_template(record["messages"], tokenize=False)
        return len(tok(text, add_special_tokens=False)["input_ids"])
    return n_tokens

def repo2scaffold2impl(in_dir=IN_DIR, out_dir=OUT_DIR, format=OUT_FORMAT,
                       max_tokens=MAX_TOKENS, answer_mode=ANSWER_MODE):
    """One SFT record per non-trivial `.jac` file: scaffold in, implementation out.

    With `max_tokens`, files whose record is too long are split into several
    partial-fill records (see `split_file`); files that still cannot fit are
    listed in `rejected.jsonl`.
    """
    in_dir  = Path(in_dir)
    out_dir = Path(out_dir)
    format  = format.lower()

    repos = list(iter_repos(in_dir))
    if not repos:
        raise FileNotFoundError(f"No repos found in: {in_dir}")

    samples: list[tuple[str, str, str]] = []
    for key, repo_root in repos:
        for path in iter_repo_files(repo_root):
            if path.suffix != ".jac":
                continue
            try:
                source = path.read_text(encoding="utf-8").strip()
            except (UnicodeDecodeError, OSError):
                continue
            if len(source) < MIN_CHARS:
                continue
            scaffold = strip_bodies(source).strip()
            if scaffold == source or "{ ... }" not in scaffold:
                continue                # nothing to fill; skip
            rel = path.relative_to(repo_root).as_posix()
            samples.append((f"{key}::{rel}", scaffold, source))
    if not samples:
        raise FileNotFoundError(f"No fillable Jac scaffolds found under: {in_dir}")

    rng = random.Random(SEED)
    rng.shuffle(samples)
    if max_tokens is None:
        prompts = load_prompts(PROMPT, "system", TASK_TYPE)
        records = [build_record(fp, sc, im, prompts, rng) for fp, sc, im in samples]
        rejected = []
    else:
        prompts  = load_prompts(PROMPT, "system", TASK_TYPE, *PARTIAL_KEY.values())
        n_tokens = token_counter(TOKENIZER)
        records, rejected = [], []
        for fp, sc, im in samples:
            recs, reason = split_file(fp, im, sc, prompts, rng, n_tokens, max_tokens, answer_mode)
            records.extend(recs)
            if reason:
                rejected.append({"fp": fp, "reason": reason})
        rng.shuffle(records)            # parts of one file don't stay adjacent

    counts = split_and_write(records, out_dir, VALID_SIZE, format)
    with (out_dir / "rejected.jsonl").open("w", encoding="utf-8") as f:
        for row in rejected:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    report(counts, out_dir)
    if max_tokens is not None:
        n_split = len({r["meta"]["fp"].split("#part")[0] for r in records if "part" in r["meta"]})
        print(f"  max_tokens={max_tokens}: {n_split} files split into parts, "
              f"{len(rejected)} files rejected (see rejected.jsonl)")

# Run =====================================================
if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--max-token", dest="max_tokens", type=int, default=MAX_TOKENS,
                     help="cap per record (chat-template tokens); split or drop longer files")
    cli.add_argument("--answer-mode", choices=["full", "decls", "auto"], default=ANSWER_MODE,
                     help="answer shape for split files: whole file or only filled declarations")
    args = cli.parse_args()
    repo2scaffold2impl(max_tokens=args.max_tokens, answer_mode=args.answer_mode)
