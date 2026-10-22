import random, sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from utils.io         import iter_sources
from utils.classifier import classify_structural as classify
from dataset.pipeline import chat_style, load_prompts, report, split_and_write

# Setting =================================================
DS_FORMAT    = "jac"
DS_NAME      = "Nitin-3k-js2jac-idiom"
SOURCE       = "code"
TASK_TYPE    = "js2jac"
JSON_KEYWORD = "jac"                    # JSONL mode: field holding the Jac target
FP_KEY       = "id"                     # JSONL mode: field to use as sample id (fp)
JS_KEY       = "js"                     # JSONL mode: field holding the JS/TS source
STATUS_KEY   = "status_in"              # JSONL mode: field indicating record validity
STATUS_OK    = "convertible"            # keep only records whose STATUS_KEY equals this

DS_ROOT = f"{Path(__file__).resolve().parent}/../../../dataset"
IN_DIR  = f"{DS_ROOT}/raw/{DS_FORMAT}/{DS_NAME}"
OUT_DIR = f"{DS_ROOT}/sft/{TASK_TYPE}/{DS_NAME}"

PROMPT     = f"{Path(__file__).resolve().parent}/../template/prompt_template.json"
OUT_FORMAT = "jsonl"
VALID_SIZE = 0.2
SEED       = 3407

# Functions ===============================================
def build_record(fp: str, js: str, jac: str, prompts: dict, rng: random.Random) -> dict:
    instruction = f"{rng.choice(prompts[TASK_TYPE])}\n```ts\n{js}\n```"
    system, wrap = chat_style(fp, prompts)
    return {
        "messages": [
            {"role": "system",    "content": system},
            {"role": "user",      "content": instruction},
            {"role": "assistant", "content": wrap(jac)},
        ],
        "meta": {
            "source":    SOURCE,
            "format":    DS_FORMAT,
            "class":     classify(jac),
            "task_type": TASK_TYPE,
            "fp":        fp,
        },
    }

def jsonl2js2jac(in_dir=IN_DIR, out_dir=OUT_DIR, format=OUT_FORMAT):
    """Turn (js, jac) pairs into SFT records with a js2jac conversion prompt."""
    in_dir  = Path(in_dir)
    out_dir = Path(out_dir)
    format  = format.lower()

    raw_root = Path(f"{DS_ROOT}/raw/{DS_FORMAT}")
    samples: list[tuple[str, str, str]] = []  # (fp, js, jac)
    for fp, jac, extras in iter_sources(in_dir, raw_root, JSON_KEYWORD, FP_KEY, (JS_KEY, STATUS_KEY)):
        if extras.get(STATUS_KEY) != STATUS_OK:
            continue
        js  = (extras.get(JS_KEY) or "").strip()
        jac = jac.strip()
        if not js or not jac:
            continue
        samples.append((fp, js, jac))
    if not samples:
        raise ValueError(f"No convertible (js, jac) pairs found in: {in_dir}")

    prompts = load_prompts(PROMPT, "system", "system_chat", TASK_TYPE)
    rng     = random.Random(SEED)
    rng.shuffle(samples)
    records = [build_record(fp, js, jac, prompts, rng) for fp, js, jac in samples]

    counts = split_and_write(records, out_dir, VALID_SIZE, format)
    report(counts, out_dir)

# Run =====================================================
if __name__ == "__main__":
    jsonl2js2jac()
