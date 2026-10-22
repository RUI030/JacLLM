import random, re, sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from utils.io         import iter_sources
from utils.classifier import classify_structural as classify
from dataset.pipeline import chat_style, load_prompts, report, split_and_write

# Setting =================================================
DS_FORMAT    = "jac"
DS_NAME      = "Nitin-9k-py2jac-idiom"
SOURCE       = "code"
TASK_TYPE    = "code_completion"
JSON_KEYWORD = "jac"                    # JSONL mode: field holding the Jac source
FP_KEY       = "id"                     # JSONL mode: field to use as sample id (fp)

DS_ROOT = f"{Path(__file__).resolve().parent}/../../../dataset"
IN_DIR  = f"{DS_ROOT}/raw/{DS_FORMAT}/{DS_NAME}"
OUT_DIR = f"{DS_ROOT}/sft/{TASK_TYPE}/{DS_NAME}"

PROMPT     = f"{Path(__file__).resolve().parent}/../template/prompt_template.json"
OUT_FORMAT = "jsonl"
VALID_SIZE = 0.2
SEED       = 3407

DEF_RE = re.compile(r"^\s*def\s+\w+", re.M)

# Functions ===============================================
def split_at_def(source: str) -> tuple[str, str] | None:
    """Return (instruction_part, full_source) if a `def` line exists, else None.

    Instruction part = everything above the first `def` line PLUS the signature
    up to and including the opening `{`. Answer = the full source.
    """
    match = DEF_RE.search(source)
    if not match:
        return None
    brace = source.find("{", match.end())
    if brace == -1:
        return None
    head = source[: brace + 1].rstrip()
    return head, source.strip()

def build_record(fp: str, jac: str, prompts: dict, rng: random.Random) -> dict | None:
    parts = split_at_def(jac)
    if parts is None:
        return None
    head, full  = parts
    instruction = f"{rng.choice(prompts['code_completion'])}\n{head}".strip()
    system, wrap = chat_style(fp, prompts)
    return {
        "messages": [
            {"role": "system",    "content": system},
            {"role": "user",      "content": instruction},
            {"role": "assistant", "content": wrap(full)},
        ],
        "meta": {
            "source":    SOURCE,
            "format":    DS_FORMAT,
            "class":     classify(jac),
            "task_type": TASK_TYPE,
            "fp":        fp,
        },
    }

def jac2code_completion(in_dir=IN_DIR, out_dir=OUT_DIR, format=OUT_FORMAT):
    """Turn each Jac function file into an SFT record: docstring/signature-lead
    instruction with a sampled prefix; answer is the full file (in a ```jac block for the chat-interface share, see pipeline.chat_style)."""
    in_dir  = Path(in_dir)
    out_dir = Path(out_dir)
    format  = format.lower()

    raw_root = Path(f"{DS_ROOT}/raw/{DS_FORMAT}")
    samples  = [
        (fp, jac.strip())
        for fp, jac, _ in iter_sources(in_dir, raw_root, JSON_KEYWORD, FP_KEY)
    ]
    if not samples:
        raise FileNotFoundError(f"No samples found in: {in_dir}")

    prompts = load_prompts(PROMPT, "system", "system_chat", TASK_TYPE)
    rng     = random.Random(SEED)
    rng.shuffle(samples)
    records = [build_record(fp, jac, prompts, rng) for fp, jac in samples]
    records = [r for r in records if r is not None]

    counts = split_and_write(records, out_dir, VALID_SIZE, format)
    report(counts, out_dir)

# Run =====================================================
if __name__ == "__main__":
    match DS_FORMAT:
        case "jac":
            jac2code_completion()
        case _:
            raise ValueError(f"Dataset format not supported: {DS_FORMAT}")
