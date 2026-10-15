

"""Generate a machine-readable report for a JSONL dataset directory."""

import argparse, json, math
from collections import Counter
from pathlib import Path


PROPERTY_VALUES = {
    "format": ["jac", "markdown", "repo", "session", "diff"],
    "class": ["function", "graph", "osp", "fullstack"],
    "source": ["code", "docs", "article", "agent", "other"],
}
SPLITS = ("train", "valid")
CHARS_PER_TOKEN = 4  # rough token estimate: chars / 4
LENGTH_BINS = [100, 200, 500, 1000, 2000, 5000, 10000]  # char upper-bounds; last bucket = ">last"


def sample_text(sample):
    """Return the text the model sees from a CPT or SFT sample (message contents, tool-call
    names + arguments, and the `tools` schema of tool-use rows)."""
    if isinstance(sample.get("text"), str):
        return sample["text"]

    parts = []
    for message in sample.get("messages") or []:
        if not isinstance(message, dict):
            continue
        parts.append(message.get("content") or message.get("context") or "")
        for call in message.get("tool_calls") or []:
            function = call.get("function", {})
            arguments = function.get("arguments", "")
            parts += [function.get("name", ""), arguments if isinstance(arguments, str) else json.dumps(arguments)]
    tools = sample.get("tools")
    if tools:
        parts.append(tools if isinstance(tools, str) else json.dumps(tools))
    return "\n".join(parts)


def empty_property_counts():
    return {
        name: Counter({value: 0 for value in values})
        for name, values in PROPERTY_VALUES.items()
    }


def length_statistics(lengths):
    """Calculate dependency-free character-length statistics."""
    if not lengths:
        return {
            "unit": "characters",
            "avg": 0,
            "median": 0,
            "std": 0,
            "min": 0,
            "max": 0,
            "total": 0,
        }

    ordered = sorted(lengths)
    count = len(ordered)
    avg = sum(ordered) / count
    middle = count // 2
    median = (
        ordered[middle]
        if count % 2
        else (ordered[middle - 1] + ordered[middle]) / 2
    )
    variance = sum((length - avg) ** 2 for length in ordered) / count

    return {
        "unit": "characters",
        "avg": round(avg, 2),
        "median": median,
        "std": round(math.sqrt(variance), 2),
        "min": ordered[0],
        "max": ordered[-1],
        "total": sum(ordered),
    }


def length_histogram(lengths, bins=LENGTH_BINS):
    counts = [0] * (len(bins) + 1)
    for x in lengths:
        for i, edge in enumerate(bins):
            if x <= edge:
                counts[i] += 1
                break
        else:
            counts[-1] += 1
    labels = [f"<={bins[0]}"]
    labels += [f"{bins[i-1]+1}-{bins[i]}" for i in range(1, len(bins))]
    labels += [f">{bins[-1]}"]
    return dict(zip(labels, counts))


def read_split(ds_dir, split):
    files = sorted(Path(ds_dir).glob(f"{split}*.jsonl"))
    for file_path in files:
        with file_path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"Invalid JSON in {file_path}, line {line_number}: {error}"
                    ) from error


def summarize_split(ds_dir, split):
    lengths = []
    properties = empty_property_counts()
    combinations = Counter()

    for sample in read_split(ds_dir, split):
        lengths.append(len(sample_text(sample)))
        meta = sample.get("meta") or {}
        values = {
            name: str(meta.get(name, "unknown"))
            for name in PROPERTY_VALUES
        }

        for name, value in values.items():
            properties[name][value] += 1
        combinations[(values["format"], values["class"], values["source"])] += 1

    count = len(lengths)
    length_report = length_statistics(lengths)

    combination_report = [
        {
            "format": format_name,
            "class": class_name,
            "source": source_name,
            "count": combination_count,
        }
        for (format_name, class_name, source_name), combination_count
        in sorted(combinations.items())
    ]

    return {
        "count": count,
        "tokens_est": length_report["total"] // CHARS_PER_TOKEN,
        "length": length_report,
        "histogram": length_histogram(lengths),
        "property": {
            name: dict(sorted(counts.items()))
            for name, counts in properties.items()
        },
        "combinations": combination_report,
    }


def generate_report(ds_dir, write=True):
    """Return the train/valid report of ds_dir; with `write`, also save it as statistic.json."""
    ds_dir = Path(ds_dir)
    if not ds_dir.is_dir():
        raise NotADirectoryError(f"Dataset directory not found: {ds_dir}")

    report = {
        split: summarize_split(ds_dir, split)
        for split in SPLITS
    }
    if write:
        output_file = Path(f"{ds_dir}/statistic.json")
        with output_file.open("w", encoding="utf-8") as file:
            json.dump(report, file, indent=4, ensure_ascii=False)
            file.write("\n")
        print(f"Report saved to {output_file}")

    return report


def dataset_dirs(root):
    """root itself if it holds train/valid JSONL, else every such directory below it."""
    root = Path(root)
    if any(next(root.glob(f"{split}*.jsonl"), None) for split in SPLITS):
        return [root]
    return sorted({p.parent for split in SPLITS for p in root.rglob(f"{split}*.jsonl")})


def print_summary(reports):
    """One row per dataset: rows and estimated tokens (chars / CHARS_PER_TOKEN) per split."""
    header = f"{'dataset':<48} {'train':>8} {'valid':>7} {'tokens_est':>12} {'avg_tok':>8}"
    print(header)
    print("-" * len(header))
    total_rows = total_tokens = 0
    for name, report in reports:
        rows   = sum(report[s]["count"] for s in SPLITS)
        tokens = sum(report[s]["tokens_est"] for s in SPLITS)
        total_rows, total_tokens = total_rows + rows, total_tokens + tokens
        avg = tokens // rows if rows else 0
        print(f"{name:<48} {report['train']['count']:>8,} {report['valid']['count']:>7,} {tokens:>12,} {avg:>8,}")
    print("-" * len(header))
    print(f"{'TOTAL':<48} {total_rows:>16,} {total_tokens:>12,}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate statistics for train/valid JSONL dataset files."
    )
    parser.add_argument("DS_DIR", nargs="+",
                        help="dataset directories, or parents to scan for them (e.g. dataset/sft)")
    parser.add_argument("--no-write", action="store_true",
                        help="only print the token-estimate table, don't (re)write statistic.json")
    args = parser.parse_args()

    reports = []
    for root in args.DS_DIR:
        for ds_dir in dataset_dirs(root):
            reports.append((str(ds_dir), generate_report(ds_dir, write=not args.no_write)))
    print_summary(reports)


if __name__ == "__main__":
    main()
