"""Turn assistant turns already trained by a shorter row into weight-0 context.

A row whose messages start with every message of another row from the same
source (system, user, tool results and calls all identical) keeps that prefix
as context, but its assistant turns get weight 0 so they are learned only once.
"""

import argparse, json
from pathlib import Path

# Functions ===============================================
def strip(message: dict) -> dict:
    return {k: v for k, v in message.items() if k != "weight"}

def prefix_owner(row: dict, rows: list[dict]) -> tuple[int, int] | None:
    """(index, length) of the longest other row that is an exact prefix of `row`."""
    best = None
    for j, other in enumerate(rows):
        n = len(other["messages"])
        if (other is row or other["meta"]["split_group"] != row["meta"]["split_group"]
                or other["tools"] != row["tools"] or n >= len(row["messages"])):
            continue
        if all(strip(a) == strip(b) for a, b in zip(row["messages"], other["messages"])):
            if best is None or n > best[1]:
                best = (j, n)
    return best

def zero_overlap(rows: list[dict]) -> list[dict]:
    report = []
    for i, row in enumerate(rows):
        owner = prefix_owner(row, rows)
        if owner is None:
            continue
        j, n = owner
        zeroed = 0
        for message in row["messages"][:n]:
            if message["role"] == "assistant" and message.get("weight", 1) != 0:
                message["weight"] = 0
                zeroed += 1
        row["meta"]["weight0_prefix_of"] = {"stage": rows[j]["meta"]["stage"], "messages": n}
        report.append({"row": i, "stage": row["meta"]["stage"], "group": row["meta"]["split_group"],
                       "prefix_row": j, "prefix_stage": rows[j]["meta"]["stage"],
                       "prefix_messages": n, "zeroed_turns": zeroed})
    return report

# Main ====================================================
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("src", type=Path, help="dataset dir holding train.jsonl")
    parser.add_argument("dst", type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in (args.src / "train.jsonl").open()]
    report = zero_overlap(rows)
    args.dst.mkdir(parents=True, exist_ok=True)
    with (args.dst / "train.jsonl").open("w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    stats = json.loads((args.src / "statistic.json").read_text())
    stats["overlap_policy"] = "Assistant turns in an exact same-source prefix of another row are weight 0."
    stats["weight0_prefix_rows"] = report
    (args.dst / "statistic.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n")
    for item in report:
        print(item)

if __name__ == "__main__":
    main()
