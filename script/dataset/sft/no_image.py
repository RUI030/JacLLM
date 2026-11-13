"""Synthetic counter-examples: a question about an image that is not there -> the model says it cannot see it."""

import hashlib, itertools, json, random, sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from dataset.pipeline import load_prompts, report, split_and_write

# Setting =================================================
DS_FORMAT = "chat"
DS_NAME   = "synthetic-v1"
SOURCE    = "synthetic"
TASK_TYPE = "no_image"
PER_CASE  = 15                    # records per case; kept small so refusing never outweighs the image-bearing trajectories
NO_SYSTEM = 0.3                   # share of records without a system prompt
OMITTED   = "[image attached at an earlier turn, omitted to save context]"   # the prod harness's own placeholder

DS_ROOT = f"{Path(__file__).resolve().parent}/../../../dataset"
OUT_DIR = f"{DS_ROOT}/sft/{TASK_TYPE}/{DS_NAME}"

PROMPT     = f"{Path(__file__).resolve().parent}/../template/prompt_template.json"
OUT_FORMAT = "jsonl"
VALID_SIZE = 0.1
SEED       = 3407

# A generic tool, not one of the prod harness's: these rows must not look like a trajectory sample.
TOOLS = [{"type": "function", "function": {
    "name": "screenshot", "description": "Capture a screenshot of the running app preview.",
    "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": []}}}]

# Functions ===============================================
def user_text(intro: str, body: str) -> str:
    return f"{intro}\n\n{body}" if intro else body


def build_case(case: str, combo: tuple, prompts: dict, rng: random.Random) -> tuple[list[dict], str | None]:
    """(messages after the system prompt, tools) of one case. Only the last assistant message is trained."""
    q, intro, extra = combo
    reply = rng.choice(prompts[f"no_image_reply_{case}"])
    if case == "missing":
        return [{"role": "user", "content": user_text(intro, q["q"])},
                {"role": "assistant", "content": reply.format(what=q["what"])}], None
    if case == "empty":
        return [{"role": "user", "content": user_text(intro, f"{extra}\n\n{q['q']}")},
                {"role": "assistant", "content": reply.format(what=q["what"], tag=extra)}], None
    if case == "omitted":
        return [{"role": "user", "content": user_text(intro, OMITTED)},
                {"role": "assistant", "content": "Thanks, I'll keep that in mind.", "weight": 0},
                {"role": "user", "content": f"Going back to that screenshot: {q['q'][0].lower()}{q['q'][1:]}"},
                {"role": "assistant", "content": reply.format(what=q["what"])}], None
    call = {"id": "call_1", "type": "function", "function": {"name": "screenshot", "arguments": "{}"}}
    return [{"role": "user", "content": f"Check the app preview. {q['q']}"},
            {"role": "assistant", "content": "", "tool_calls": [call], "weight": 0},
            {"role": "tool", "tool_call_id": "call_1", "content": extra},
            {"role": "assistant", "content": reply.format(what=q["what"])}], json.dumps(TOOLS)


def build_record(case: str, combo: tuple, prompts: dict, rng: random.Random) -> dict:
    msgs, tools = build_case(case, combo, prompts, rng)
    if rng.random() >= NO_SYSTEM:
        msgs = [{"role": "system", "content": rng.choice(prompts["system"])}, *msgs]
    fp = hashlib.md5(json.dumps([case, combo], sort_keys=True).encode()).hexdigest()[:12]
    rec = {"messages": msgs}
    if tools:
        rec["tools"] = tools
    rec["meta"] = {"source": SOURCE, "format": DS_FORMAT, "class": "none", "task_type": TASK_TYPE,
                   "fp": f"{case}#{fp}", "case": case}
    return rec


def generate(out_dir=OUT_DIR, format=OUT_FORMAT):
    prompts = load_prompts(PROMPT, "system", "no_image_question", "no_image_intro", "no_image_tags",
                           "no_image_tool_results", *(f"no_image_reply_{c}" for c in ("missing", "empty", "omitted", "tool")))
    rng   = random.Random(SEED)
    qs    = prompts["no_image_question"]
    cases = {"missing": itertools.product(qs, prompts["no_image_intro"][:-1], [None]),
             "empty":   itertools.product(qs, prompts["no_image_intro"], prompts["no_image_tags"]),
             "omitted": itertools.product(qs, prompts["no_image_intro"], [None]),
             "tool":    itertools.product(qs, [""], prompts["no_image_tool_results"])}
    records = []
    for case, combos in cases.items():
        combos = list(combos)
        for combo in rng.sample(combos, min(PER_CASE, len(combos))):
            records.append(build_record(case, combo, prompts, rng))
    rng.shuffle(records)
    counts = split_and_write(records, out_dir, VALID_SIZE, format)
    report(counts, out_dir)


# Run =====================================================
if __name__ == "__main__":
    generate()
