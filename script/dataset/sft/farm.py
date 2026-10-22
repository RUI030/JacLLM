import json, random, sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from utils.classifier import classify_structural as classify
from dataset.pipeline import chat_style, load_prompts, report, split_and_write

# Setting =================================================
DS_FORMAT = "jac"
DS_NAME   = "Nitin-2k-farm"
SOURCE    = "agent"
TASK_TYPE = "farm"
FP_KEY    = "id"

DS_ROOT = f"{Path(__file__).resolve().parent}/../../../dataset"
IN_DIR  = f"{DS_ROOT}/raw/{DS_FORMAT}/{DS_NAME}"
OUT_DIR = f"{DS_ROOT}/sft/{TASK_TYPE}/{DS_NAME}"

PROMPT     = f"{Path(__file__).resolve().parent}/../template/prompt_template.json"
OUT_FORMAT = "jsonl"
VALID_SIZE = 0.2
SEED       = 3407

# Functions ===============================================
def build_record(fp: str, archetype: str, node: str, walkers: str,
                 prompts: dict, rng: random.Random) -> dict:
    prefix      = rng.choice(prompts[TASK_TYPE]).format(node=node)
    instruction = f"{prefix}\n\n```jac\n{archetype}\n```"
    system, wrap = chat_style(fp, prompts)
    return {
        "messages": [
            {"role": "system",    "content": system},
            {"role": "user",      "content": instruction},
            {"role": "assistant", "content": wrap(walkers)},
        ],
        "meta": {
            "source":    SOURCE,
            "format":    DS_FORMAT,
            "class":     classify(walkers),
            "task_type": TASK_TYPE,
            "fp":        fp,
        },
    }

def jsonl2farm(in_dir=IN_DIR, out_dir=OUT_DIR, format=OUT_FORMAT):
    """Build (schema, target-node) -> CRUD-walkers SFT records.

    Each source row supplies `archetype` (full node/edge schema), a target
    `node` name, and `walkers` (a public CRUD walker set for that node). We
    synthesize a user instruction from the schema + target-node name; the
    assistant answer is the walker block wrapped in ```jac ... ```.
    """
    in_dir  = Path(in_dir)
    out_dir = Path(out_dir)
    format  = format.lower()

    samples: list[tuple[str, str, str, str]] = []
    for jf in sorted(in_dir.rglob("*.jsonl")):
        with jf.open("r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                rec       = json.loads(line)
                archetype = (rec.get("archetype") or "").strip()
                walkers   = (rec.get("walkers")   or "").strip()
                node      = (rec.get("node")      or "").strip()
                if not (archetype and walkers and node):
                    continue
                fp = rec.get(FP_KEY) or f"{jf.name}#{idx}"
                samples.append((fp, archetype, node, walkers))
    if not samples:
        raise FileNotFoundError(f"No samples found in: {in_dir}")

    prompts = load_prompts(PROMPT, "system", "system_chat", TASK_TYPE)
    rng     = random.Random(SEED)
    rng.shuffle(samples)
    records = [build_record(fp, a, n, w, prompts, rng) for fp, a, n, w in samples]

    counts = split_and_write(records, out_dir, VALID_SIZE, format)
    report(counts, out_dir)

# Run =====================================================
if __name__ == "__main__":
    jsonl2farm()
