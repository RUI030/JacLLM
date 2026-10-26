import random, re, sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from utils.classifier    import classify_structural as classify
from dataset.parser.repo import NON_JAC_CODE, iter_repo_files, iter_repos
from dataset.pipeline    import report, split_and_write

# Setting =================================================
DS_FORMAT    = "repo"
DS_NAME      = "Rui-jacapp-5"
SOURCE       = "code"
TARGET_CHARS = 14000                    # ~4k tokens at ~3.5 chars/token

DS_ROOT = f"{Path(__file__).resolve().parent}/../../../dataset"
IN_DIR  = f"{DS_ROOT}/raw/repo"
OUT_DIR = f"{DS_ROOT}/cpt/{DS_NAME}"

OUT_FORMAT = "jsonl"
VALID_SIZE = 0.0                        # CPT: no train/valid split
SEED       = 3407
DATA_EXTS  = {".json", ".yaml", ".yml", ".txt"}   # data / config dumps (package-lock, topojson fixtures)

# Functions ===============================================
TOP_DECL = re.compile(
    r"^(?=\s*(?:import\b|glob\b|def(?::\w+)?\b|walker(?::\w+)?\b|"
    r"node(?::\w+)?\b|edge(?::\w+)?\b|obj(?::\w+)?\b|enum(?::\w+)?\b|"
    r"impl\b|with\s+entry\b|test\b|class\b))",
    re.MULTILINE,
)

def split_jac_by_decl(source: str, max_chars: int) -> list[str]:
    """Split a large .jac file at top-level declaration boundaries."""
    starts = [m.start() for m in TOP_DECL.finditer(source)]
    if len(starts) < 2:
        return hard_split(source, max_chars)
    starts.append(len(source))
    parts: list[str] = []
    buf = ""
    for i in range(len(starts) - 1):
        seg = source[starts[i]:starts[i + 1]]
        if buf and len(buf) + len(seg) > max_chars:
            parts.append(buf); buf = seg
        else:
            buf += seg
    if buf:
        parts.append(buf)
    # one declaration longer than max_chars (a big client component) is cut at lines: CPT truncates at max_seq_length
    return [q for p in parts if p.strip() for q in (hard_split(p, max_chars) if len(p) > max_chars else [p])]

def hard_split(source: str, max_chars: int) -> list[str]:
    """Fallback line-boundary split for non-Jac or decl-less content."""
    lines, parts, buf, size = source.splitlines(keepends=True), [], [], 0
    for line in lines:
        if size + len(line) > max_chars and buf:
            parts.append("".join(buf)); buf, size = [], 0
        buf.append(line); size += len(line)
    if buf:
        parts.append("".join(buf))
    return parts

def file_pieces(path: Path, source: str, max_chars: int) -> list[str]:
    if len(source) <= max_chars:
        return [source]
    if path.suffix == ".jac":
        return split_jac_by_decl(source, max_chars)
    return hard_split(source, max_chars)

def build_repo_chunks(repo_root: Path, target_chars: int) -> list[dict]:
    """Pack files under `repo_root` into <=target_chars chunks with headers."""
    repo_name = repo_root.name
    chunks: list[dict] = []
    body: list[str] = []
    files: list[str] = []
    size = 0

    def flush():
        nonlocal body, files, size
        if not body:
            return
        chunks.append({
            "text":  f"# repo: {repo_name}\n" + "".join(body),
            "files": list(files),
        })
        body, files, size = [], [], 0

    for path in iter_repo_files(repo_root):
        if path.suffix in NON_JAC_CODE or path.suffix in DATA_EXTS:     # CPT teaches Jac; css / html / md / toml stay
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if not source.strip():
            continue
        rel = path.relative_to(repo_root).as_posix()
        for piece in file_pieces(path, source, target_chars):
            block = f"\n# file: {rel}\n{piece.rstrip()}\n"
            if size and size + len(block) > target_chars:
                flush()
            body.append(block); files.append(rel); size += len(block)
    flush()
    return chunks

def build_record(fp: str, chunk: dict) -> dict:
    return {
        "text": chunk["text"],
        "meta": {
            "source": SOURCE,
            "format": DS_FORMAT,
            "class":  classify(chunk["text"]),
            "fp":     fp,
            "files":  chunk["files"],
            "chars":  len(chunk["text"]),
        },
    }

def repo2cpt(in_dir=IN_DIR, out_dir=OUT_DIR, format=OUT_FORMAT):
    """Emit one CPT record per packed chunk across every repo under `in_dir`."""
    in_dir  = Path(in_dir)
    out_dir = Path(out_dir)
    format  = format.lower()

    repos = list(iter_repos(in_dir))
    if not repos:
        raise FileNotFoundError(f"No repos found in: {in_dir}")

    samples: list[tuple[str, dict]] = []
    for key, repo_root in repos:
        for i, chunk in enumerate(build_repo_chunks(repo_root, TARGET_CHARS)):
            samples.append((f"{key}::chunk_{i:04d}", chunk))

    rng = random.Random(SEED)
    rng.shuffle(samples)
    records = [build_record(fp, ch) for fp, ch in samples]

    counts = split_and_write(records, out_dir, VALID_SIZE, format)
    report(counts, out_dir)

# Run =====================================================
if __name__ == "__main__":
    match DS_FORMAT:
        case "repo":
            repo2cpt()
        case _:
            raise ValueError(f"Dataset format not supported: {DS_FORMAT}")
