import json, random, sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from utils.classifier import classify_structural as classify
from utils.jac_block  import first_jac_block
from dataset.pipeline import report, split_and_write

# Setting =================================================
DS_FORMAT = "jac"
DS_NAME   = "Nitin-1k-osp"
SOURCE    = "agent"
TASK_TYPE = "osp"
FP_KEY    = "id"                        # JSONL mode: field to use as sample id (fp)

DS_ROOT = f"{Path(__file__).resolve().parent}/../../../dataset"
IN_DIR  = f"{DS_ROOT}/raw/{DS_FORMAT}/{DS_NAME}"
OUT_DIR = f"{DS_ROOT}/sft/{TASK_TYPE}/{DS_NAME}"

OUT_FORMAT = "jsonl"
VALID_SIZE = 0.2
SEED       = 3407

# Functions ===============================================
def build_record(fp: str, messages: list, jac_code: str) -> dict:
    return {
        "messages": messages,
        "meta": {
            "source":    SOURCE,
            "format":    DS_FORMAT,
            "class":     classify(jac_code),
            "task_type": TASK_TYPE,
            "fp":        fp,
        },
    }

def jsonl2osp(in_dir=IN_DIR, out_dir=OUT_DIR, format=OUT_FORMAT):
    """Pass osp `messages` rows through with an 80/20 train/valid split.

    Source rows are already SFT-shaped (user + assistant ```jac``` block) and
    validator-gated (`compiler_pass=True, test_pass=True`); this script only
    adds the JacLLM `meta` block and splits.
    """
    in_dir  = Path(in_dir)
    out_dir = Path(out_dir)
    format  = format.lower()

    samples: list[tuple[str, list, str]] = []
    for jf in sorted(in_dir.rglob("*.jsonl")):
        with jf.open("r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                messages = rec.get("messages") or []
                if not messages:
                    continue
                assistant = next(
                    (m.get("content", "") for m in reversed(messages) if m.get("role") == "assistant"),
                    "",
                )
                jac_code = first_jac_block(assistant) or assistant.strip()
                if not jac_code:
                    continue
                fp = rec.get(FP_KEY) or f"{jf.name}#{idx}"
                samples.append((fp, messages, jac_code))
    if not samples:
        raise FileNotFoundError(f"No samples found in: {in_dir}")

    rng = random.Random(SEED)
    rng.shuffle(samples)
    records = [build_record(fp, msgs, code) for fp, msgs, code in samples]

    counts = split_and_write(records, out_dir, VALID_SIZE, format)
    report(counts, out_dir)

# Run =====================================================
if __name__ == "__main__":
    jsonl2osp()
