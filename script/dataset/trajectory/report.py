"""Harness-agnostic report on a folder of agent traces (.json/.jsonl, optionally .gz): fields, detected messages / tool calls / usage, length and tool distributions, charts."""

import argparse, gzip, hashlib, json, re, sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from dataset.inspect import _type_name

# Setting =================================================
OUT_NAME  = "report.md"           # written inside the input folder unless --out
IMG_DIR   = "img"                 # charts go next to the report: <report dir>/img/*.svg
ENUM_MAX  = 12                    # list a field's values when it has at most this many distinct ones,
ENUM_LEN  = 40                    # each at most this long,
ENUM_MIN  = 2                     # and each seen at least this often (a one-off string is user text, not an enum)
ID_KEY    = re.compile(r"(^|_)(id|uuid)$|Id$|_at$|^timestamp$", re.I)     # never enumerated
HEX_KEY   = re.compile(r"^[0-9a-f]{32,}$")                                # hash-keyed maps collapse to one path
SESS_KEY  = re.compile(r"^(session|conversation|thread)[_-]?id$", re.I)   # auto-detected grouping key
TEXT_SKIP = re.compile(r"(^|_)(id|uuid|type|role|url|format|signature|model|data|hash|status|reason|object|index|mime_type|media_type)$"
                       r"|Id$|_at$|^timestamp$", re.I)  # str leaves inside a message that are not model-visible text
IMG_TYPES = {"image", "image_url", "input_image"}
EDGES     = [16384, 32768, 49152, 65536, 131072, 262144]
PCTS      = [10, 25, 50, 75, 90, 99]
TOP_TOOLS = 30                    # tools shown in the charts (the tables list all)
INK, MUTED, GRID, SURFACE, SERIES = "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb", "#2a78d6"


# Functions ===============================================
# --- reading ---
def records(path: Path):
    """(file, record) pairs: a .json file is one record, a .jsonl line is one record."""
    opener = gzip.open if path.suffix == ".gz" else open
    stem = path.name.removesuffix(".gz")
    with opener(path, "rt", encoding="utf-8") as f:
        if stem.endswith(".jsonl"):
            for line in f:
                if line.strip():
                    yield json.loads(line)
        else:
            yield json.load(f)


def trace_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    pat = re.compile(r"\.jsonl?(\.gz)?$")
    return sorted(p for p in root.rglob("*") if p.is_file() and pat.search(p.name))


# --- generic field schema ---
class Field:
    """Everything observed at one JSON path."""
    def __init__(self):
        self.types   = Counter()
        self.n       = 0
        self.parents = 0
        self.values  = Counter()
        self.num     = []
        self.slen    = []


def norm_key(k: str) -> str:
    return "<hash>" if HEX_KEY.match(k) else k


def walk(x, path: str, fields: dict[str, Field]) -> None:
    f = fields.setdefault(path, Field())
    t = _type_name(x)
    f.types[t] += 1
    f.n += 1
    if isinstance(x, dict):
        for k in dict.fromkeys(norm_key(k) for k in x):  # ordered dedup: a set would reorder rows per PYTHONHASHSEED
            fields.setdefault(f"{path}.{k}", Field()).parents += 1
        for k, v in x.items():
            walk(v, f"{path}.{norm_key(k)}", fields)
    elif isinstance(x, list):
        for v in x:
            walk(v, f"{path}[]", fields)
    else:
        if t in ("int", "float"):
            f.num = [min(f.num[0], x), max(f.num[1], x)] if f.num else [x, x]
        if t == "str":
            f.slen = [min(f.slen[0], len(x)), max(f.slen[1], len(x))] if f.slen else [len(x), len(x)]
        if len(f.values) <= ENUM_MAX:
            f.values[x] += 1


def describe(path: str, f: Field) -> str:
    leaf = path.rsplit(".", 1)[-1].replace("[]", "")
    notes = []
    if f.num:
        notes.append(f"range {f.num[0]:g} … {f.num[1]:g}")
    if f.slen and f.types.get("str") == f.n:
        notes.append(f"len {f.slen[0]} … {f.slen[1]}")
    vals = {v: c for v, c in f.values.items() if v is not None and not isinstance(v, bool)}
    if (vals and len(f.values) <= ENUM_MAX and not ID_KEY.search(leaf)
            and all(len(str(v)) <= ENUM_LEN and c >= ENUM_MIN for v, c in vals.items())):
        notes.append(", ".join(f"`{v}` ×{c}" for v, c in sorted(vals.items(), key=lambda kv: (-kv[1], str(kv[0])))))
    if "bool" in f.types:
        b = {v: c for v, c in f.values.items() if isinstance(v, bool)}
        notes.append(", ".join(f"`{str(v).lower()}` ×{c}" for v, c in sorted(b.items(), key=lambda kv: -kv[1])))
    return "; ".join(notes)


def field_table(fields: dict[str, Field]) -> list[str]:
    rows = ["| path | type | present | count | values / range |", "|---|---|---|---|---|"]
    for path, f in fields.items():
        if "." not in path or path.endswith("[]"):
            pres = "—"
        else:
            total = fields[path.rsplit(".", 1)[0]].types["dict"]
            pres = f"{f.parents}/{total}" + ("" if f.parents == total else f" ({100 * f.parents / total:.0f}%)")
        types = " / ".join(sorted(f.types))
        rows.append(f"| `{path}` | {types} | {pres} | {f.n} | {describe(path, f)} |")
    return rows


# --- structure detection (each pattern is a documented wire format, reported with its hit count) ---
def as_tool_call(d: dict) -> tuple | None:
    """(pattern, name, args, id) for a tool call in OpenAI chat / Anthropic / OpenAI Responses shape."""
    fn = d.get("function")
    if isinstance(fn, dict) and "name" in fn and "arguments" in fn:
        return "openai `{function: {name, arguments}}`", fn["name"], fn["arguments"], d.get("id")
    if d.get("type") == "tool_use" and "name" in d:
        return "anthropic `{type: tool_use}`", d["name"], d.get("input"), d.get("id")
    if d.get("type") in ("function_call", "custom_tool_call") and "name" in d:
        return "responses `{type: function_call}`", d["name"], d.get("arguments", d.get("input")), d.get("call_id") or d.get("id")
    return None


def as_tool_result(d: dict) -> tuple | None:
    """(pattern, call id) for a tool result."""
    if d.get("role") == "tool":
        return "openai `{role: tool}`", d.get("tool_call_id")
    if d.get("type") == "tool_result":
        return "anthropic `{type: tool_result}`", d.get("tool_use_id")
    if d.get("type") in ("function_call_output", "custom_tool_call_output"):
        return "responses `{type: function_call_output}`", d.get("call_id")
    return None


def is_usage(d: dict) -> bool:
    return any(k in d for k in ("prompt_tokens", "completion_tokens", "input_tokens", "output_tokens"))


def usage_numbers(u: dict) -> tuple[str, int, int, int]:
    """(convention, context in, out, reasoning). OpenAI prompt_tokens already include cached tokens;
    Anthropic input_tokens exclude them, so the cache counters are added back."""
    num = lambda k, d=u: d.get(k) if isinstance(d.get(k), int) else 0
    out = num("completion_tokens") if "completion_tokens" in u else num("output_tokens")
    if "prompt_tokens" in u:
        conv, inp = "`prompt_tokens + completion_tokens`", num("prompt_tokens")
    elif "cache_read_input_tokens" in u or "cache_creation_input_tokens" in u:
        conv = "`input_tokens + cache_read_input_tokens + cache_creation_input_tokens + output_tokens`"
        inp = num("input_tokens") + num("cache_read_input_tokens") + num("cache_creation_input_tokens")
    else:
        conv, inp = "`input_tokens + output_tokens`", num("input_tokens")
    reason = num("reasoning_tokens")
    for k in ("completion_tokens_details", "output_tokens_details"):
        if not reason and isinstance(u.get(k), dict):
            reason = num("reasoning_tokens", u[k])
    return conv, inp, out, reason


def first_id(d: dict):
    """The parent's own id, used to count a usage block once when a log repeats it (one line per content block)."""
    return next((v for k, v in d.items() if isinstance(v, str) and re.search(r"(^|_)id$", k) and not k.startswith("parent")), None)


def scan(x, parent: dict | None, in_unit: bool, found: dict) -> None:
    """Collect message units, tool calls, tool results and usage blocks anywhere in a record."""
    if isinstance(x, list):
        for v in x:
            scan(v, parent, in_unit, found)
        return
    if not isinstance(x, dict):
        return
    tc = as_tool_call(x)
    tr = None if tc else as_tool_result(x)
    unit = not in_unit and (isinstance(x.get("role"), str) or tc is not None or tr is not None)
    if unit:
        found["units"].append(x)
    if tc:
        found["calls"].append(tc)
    if tr:
        found["results"].append((tr, x))
    if is_usage(x):
        found["usage"].append((x, parent))
        return
    skip = x.get("function") if tc and tc[0].startswith("openai") else None
    if not tc and "name" in x and any(k in x for k in ("arguments", "input", "args", "parameters")):
        found["unmatched"] += 1
    for v in x.values():
        if isinstance(v, (dict, list)) and v is not skip:
            scan(v, x, in_unit or unit, found)


def unit_key(u: dict, role: str) -> tuple[str, tuple]:
    """Identity of a message across history resends. A message holding tool calls/results is the same message
    wherever those ids recur; otherwise role + content + image references. Reasoning and harness metadata are left
    out on purpose: a harness may strip or add them when it resends history (prod tags resent messages with agent /
    tools_used / files_modified); the first version is measured and repeats are compared to it (`version_class`)."""
    f = {"units": [], "calls": [], "results": [], "usage": [], "unmatched": 0}
    scan(u, None, False, f)
    ids = tuple(c[3] for c in f["calls"] if c[3]) + tuple(r[1] for r, _ in f["results"] if r[1])
    if ids:
        return "ids", (role, ids)
    imgs: list = []
    body = text_of({k: u[k] for k in ("content", "output") if k in u}, "", Counter(), imgs)
    return "content", (role, hashlib.sha1(body.encode()).hexdigest(), tuple(imgs))


def text_of(x, key: str, keys: Counter, imgs: list) -> str:
    """Model-visible text under a unit: every str leaf whose key is not an id/type/url-like field.
    Image parts add a short digest of themselves to imgs instead of text."""
    if isinstance(x, str):
        if TEXT_SKIP.search(key):
            return ""
        keys[key] += len(x)
        return x
    if isinstance(x, list):
        return "".join(text_of(v, key, keys, imgs) for v in x)
    if isinstance(x, dict):
        if is_usage(x):
            return ""
        if x.get("type") in IMG_TYPES:
            imgs.append(img_ref(x))
            return ""
        return "".join(text_of(v, k, keys, imgs) for k, v in x.items())
    return ""


def img_ref(x: dict) -> str:
    """Identity of an image part: its url / data / file reference, so a resend that only changes side fields
    (prod adds or drops image_url.format) is the same picture. Falls back to the whole part."""
    refs = []
    def find(v, k=""):
        if isinstance(v, dict):
            for kk, vv in v.items():
                find(vv, kk)
        elif isinstance(v, list):
            for vv in v:
                find(vv, k)
        elif isinstance(v, str) and re.search(r"(^|_)(url|data|file_id|path)$", k):
            refs.append(v)
    find(x)
    return hashlib.sha1(json.dumps(refs or x, sort_keys=True).encode()).hexdigest()[:16]


def leaves(x, path: str = "$", out: dict | None = None) -> dict:
    """path -> short hash of each scalar leaf; kept for a unit's first version to diff its repeats against."""
    out = {} if out is None else out
    if isinstance(x, dict):
        for k, v in x.items():
            leaves(v, f"{path}.{k}", out)
    elif isinstance(x, list):
        for i, v in enumerate(x):
            leaves(v, f"{path}[{i}]", out)
        if not x:
            out[path] = "[]"
    else:
        out[path] = hashlib.sha1(json.dumps(x).encode()).hexdigest()[:12]
    return out


def version_class(old: dict, text: str, imgs: list) -> str:
    """How a repeat differs from the first version, judged on model-visible text and image references."""
    same_imgs, same_text = imgs == old["imgref"], text == old["text"]
    if same_text and same_imgs:
        return "same text and images, other fields differ"
    if same_imgs:
        if len(text) < len(old["text"]):
            return "text cut at the end" if old["text"].startswith(text) else "text shorter"
        return "text longer" if len(text) > len(old["text"]) else "text changed, same length"
    tail = "" if same_text else ", text changed"
    if set(imgs) < set(old["imgref"]):
        return "some images removed" + tail
    return ("images added" if set(imgs) > set(old["imgref"]) else "images changed") + tail


# --- stats helpers ---
def pct(xs: list, p: float):
    """Nearest-rank percentile of a sorted list."""
    return xs[min(len(xs) - 1, max(0, round(p / 100 * len(xs) + 0.5) - 1))]


def dist_table(rows: list[tuple[str, list]], per: str = "session") -> list[str]:
    """One row per metric; the distribution is over `per` items (one value each), named in the n column."""
    head = [f"per {per}", f"{per}s", "mean", "min", *(f"p{p}" for p in PCTS), "max", "sum"]
    L = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for name, xs in rows:
        xs = sorted(xs)
        if not xs:
            continue
        cells = [f"{sum(xs) / len(xs):,.0f}", f"{xs[0]:,}", *(f"{pct(xs, p):,}" for p in PCTS), f"{xs[-1]:,}", f"{sum(xs):,}"]
        L.append(f"| {name} | {len(xs)} | " + " | ".join(cells) + " |")
    return L


def bucket_table(rows: list[tuple[str, list]], edges: list[int]) -> list[str]:
    rows = [(n, xs) for n, xs in rows if xs]
    L = ["| ≤ length | " + " | ".join(n for n, _ in rows) + " |", "|---|" + "---|" * len(rows)]
    for e in edges:
        L.append(f"| {e:,} | " + " | ".join(f"{sum(x <= e for x in xs)}/{len(xs)} ({100 * sum(x <= e for x in xs) / len(xs):.0f}%)"
                                          for _, xs in rows) + " |")
    return L


# --- collection ---
def collect(files: list[Path], root: Path, session_key: str | None, size) -> dict:
    fields: dict[str, Field] = {}
    sess = defaultdict(lambda: defaultdict(int))     # session -> metric -> value
    units: dict[str, dict] = defaultdict(dict)       # session -> unit key -> first version seen (resends counted once)
    dedup = Counter()                                # repeats by how they were matched (ids / content)
    versions = Counter()                             # (role, how a repeat differs from the first version)
    diff_paths = Counter()                           # (role, repeat class, field path) that differs from the first version
    roles, call_pat, res_pat, usage_conv, text_keys = Counter(), Counter(), Counter(), Counter(), Counter()
    calls: dict = {}                                 # call id -> (name, session)
    tools = defaultdict(lambda: {"calls": 0, "sessions": set(), "args": [], "res": [], "err": 0, "flag": 0,
                                 "keys": defaultdict(Counter), "bad": 0, "res_img": 0})
    results: dict = {}                               # call id -> (size, error flag or None)
    seen_usage, noid = set(), Counter()
    rel = Counter()                                  # computed relations shown under the tables
    img_roles = Counter()                            # images by the role of the message carrying them
    n_rec = n_unmatched = dup_usage = 0
    for path in files:
        for rec in records(path):
            n_rec += 1
            walk(rec, "$", fields)
            sid = str(rec.get(session_key)) if session_key and isinstance(rec, dict) else str(path.relative_to(root) if root.is_dir() else path.name)
            S = sess[sid]
            S["records"] += 1
            found = {"units": [], "calls": [], "results": [], "usage": [], "unmatched": 0}
            scan(rec, None, False, found)
            n_unmatched += found["unmatched"]
            for u in found["units"]:
                keys, imgs = Counter(), []
                text = text_of(u, "", keys, imgs)
                role = u.get("role") if isinstance(u.get("role"), str) else ("assistant" if as_tool_call(u) else "tool")
                how, k = unit_key(u, role)
                old = units[sid].get(k)
                if old:
                    dedup[how] += 1
                    lv = leaves(u)
                    if lv == old["leaves"]:
                        versions[role, "identical"] += 1
                        continue
                    cls = version_class(old, text, imgs)
                    versions[role, cls] += 1
                    ol = old["leaves"]
                    changed = (lv.keys() ^ ol.keys()) | {q for q in lv.keys() & ol.keys() if lv[q] != ol[q]}
                    for q in dict.fromkeys(re.sub(r"\[\d+\]", "[]", q) for q in sorted(changed)):
                        diff_paths[role, cls, q] += 1
                    continue
                units[sid][k] = {"size": size(text), "imgs": len(imgs), "role": role, "keys": keys,
                                 "text": text, "imgref": imgs, "leaves": leaves(u)}
            for pat, name, args, cid in found["calls"]:
                if cid is not None and cid in calls:
                    continue
                if cid is None:
                    noid["call"] += 1
                else:
                    calls[cid] = name
                call_pat[pat] += 1
                t = tools[name]
                t["calls"] += 1
                t["sessions"].add(sid)
                s = args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)
                t["args"].append(size(s))
                try:
                    a = json.loads(args) if isinstance(args, str) else args
                except json.JSONDecodeError:
                    a = None
                if isinstance(a, dict):
                    for k, v in a.items():
                        t["keys"][k][_type_name(v)] += 1
                else:
                    t["bad"] += 1
                S["tool_calls"] += 1
            for (pat, cid), d in found["results"]:
                if cid is None:
                    noid["result"] += 1
                    continue
                if cid in results:
                    continue
                res_pat[pat] += 1
                rel["result is a message itself" if isinstance(d.get("role"), str) else "result nested inside a message"] += 1
                err = d["is_error"] if isinstance(d.get("is_error"), bool) else (d["status"] == "error" if isinstance(d.get("status"), str) else None)
                r_imgs: list = []
                results[cid] = (size(text_of(d, "", Counter(), r_imgs)), err, len(r_imgs))
                S["tool_results"] += 1
            for u, parent in found["usage"]:
                key = (first_id(parent), json.dumps(u, sort_keys=True)) if parent and first_id(parent) else None
                if key and key in seen_usage:
                    dup_usage += 1
                    continue
                if key:
                    seen_usage.add(key)
                conv, inp, out, reason = usage_numbers(u)
                usage_conv[conv] += 1
                if reason:
                    rel["usage with reasoning"] += 1
                    rel["usage with reasoning ≤ output"] += reason <= out
                S["api_calls"] += 1
                S["api_ctx"] = max(S["api_ctx"], inp + out)
                S["api_out"] += out
                S["api_reason"] += reason
                S["api_in_sum"] += inp
    for sid, us in units.items():
        S = sess[sid]
        for u in us.values():
            text_keys.update(u["keys"])
            roles[u["role"]] += 1
            S["messages"] += 1
            S["images"] += u["imgs"]
            img_roles[u["role"]] += u["imgs"]
            S["text"] += u["size"]
            if u["role"] == "assistant":
                S["output"] += u["size"]
    for cid, name in calls.items():
        if cid in results:
            sz, err, n_img = results[cid]
            tools[name]["res"].append(sz)
            tools[name]["res_img"] += n_img > 0
            if err is not None:
                tools[name]["flag"] += 1
                tools[name]["err"] += err
    return {"fields": fields, "sess": {k: sess[k] for k in sorted(sess)}, "tools": tools, "roles": roles,
            "call_pat": call_pat, "dedup": dedup, "versions": versions, "diff_paths": diff_paths, "rel": rel, "img_roles": img_roles, "res_pat": res_pat, "usage_conv": usage_conv, "text_keys": text_keys,
            "n_rec": n_rec, "n_unmatched": n_unmatched, "dup_usage": dup_usage, "noid": noid,
            "unpaired_calls": sum(cid not in results for cid in calls),
            "unpaired_results": sum(cid not in calls for cid in results)}


def detect_session_key(files: list[Path]) -> tuple[str | None, int, int]:
    """Top-level key that looks like a session id and is present in every dict record; else group by file."""
    hits, n = Counter(), 0
    for path in files:
        for rec in records(path):
            n += 1
            if isinstance(rec, dict):
                hits.update(k for k in rec if SESS_KEY.match(k) and rec[k] is not None)
    best = sorted(hits.items(), key=lambda kv: (-kv[1], kv[0]))
    return (best[0][0], best[0][1], n) if best and best[0][1] == n else (None, best[0][1] if best else 0, n)


# --- charts ---
def charts(out_dir: Path, sess: dict, tools: dict, unit: str, has_api: bool) -> list[tuple[str, str]]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"svg.hashsalt": "report", "svg.fonttype": "path", "font.size": 9, "axes.edgecolor": MUTED,
                         "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
                         "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True, "figure.facecolor": SURFACE,
                         "axes.facecolor": SURFACE, "axes.spines.top": False, "axes.spines.right": False})
    from matplotlib.ticker import FuncFormatter, LogLocator, MaxNLocator, NullFormatter, NullLocator
    out_dir.mkdir(parents=True, exist_ok=True)
    made = []

    def log_axis(axis):
        """Log scale ticks at 1/2/5 × 10^k, written as 500 / 2k / 1.5M instead of 2×10^4."""
        axis.set_major_locator(LogLocator(subs=(1, 2, 5)))
        axis.set_minor_formatter(NullFormatter())
        axis.set_major_formatter(FuncFormatter(
            lambda v, _: f"{v / 1e6:g}M" if v >= 1e6 else f"{v / 1e3:g}k" if v >= 1e3 else f"{v:g}"))

    def save(fig, name, caption):  # caption: the 1–2 sentences printed under the image in the report
        fig.tight_layout()
        fig.savefig(out_dir / f"{name}.svg", metadata={"Date": None})
        plt.close(fig)
        made.append((f"{out_dir.name}/{name}.svg", caption))

    def log_hist(xs, name, title, xlabel, caption, edges=None):
        xs = [x for x in xs if x > 0]
        if not xs:
            return
        lo, hi = min(xs), max(xs)
        k = 30
        bins = [lo * (hi / lo) ** (i / k) for i in range(k + 1)] if hi > lo else [lo * 0.9, lo * 1.1]
        fig, ax = plt.subplots(figsize=(7, 3))
        ax.hist(xs, bins=bins, color=SERIES, edgecolor=SURFACE, linewidth=1)
        ax.set_xscale("log")
        log_axis(ax.xaxis)
        shown = [e for e in edges or [] if lo <= e <= hi * 1.2]
        for e in shown:
            ax.axvline(e, color=MUTED, linewidth=0.8, linestyle="--")
        if shown:  # threshold labels ride on a top axis so they never sit on the bars
            top = ax.secondary_xaxis("top")
            top.set_xticks(shown, [f"{e // 1024}k\n≤{100 * sum(x <= e for x in xs) / len(xs):.0f}%" for e in shown])
            top.xaxis.set_minor_locator(NullLocator())
            top.tick_params(colors=MUTED, labelsize=7, length=0)
            top.spines["top"].set_visible(False)
        ax.set_title(title, loc="left", color=INK)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("sessions")
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.grid(axis="x", visible=False)
        save(fig, name, caption)

    S = list(sess.values())
    if has_api:
        log_hist([s["api_ctx"] for s in S], "session_api_context", "Longest single LLM request per session (API tokens)",
                 "tokens (log scale)", "Each bar counts sessions. x = the largest `input + output` of any one call in the "
                 "session, as the provider counted it (images and chat template included). Dashed lines: training lengths, "
                 "labelled with the share of sessions at or below them.", EDGES)
    log_hist([s["text"] for s in S], "session_text", f"All unique message text per session ({unit})", f"{unit} (log scale)",
             "Sum over the session's de-duplicated messages of every role and every agent, text only. It can exceed the "
             "longest request when a session has sub-agents or side requests that never share one context.",
             EDGES if unit == "tokens" else None)
    if has_api:
        log_hist([s["api_out"] for s in S], "session_api_output", "LLM output per session (API tokens, summed over calls)",
                 "tokens (log scale)", "Sum of the output count over every call in the session, every agent; reasoning "
                 "tokens are inside this number (checked under the Length table).")
    log_hist([s["output"] for s in S], "session_output", f"Assistant-written text per session ({unit})", f"{unit} (log scale)",
             "Text of the de-duplicated `role: assistant` messages (reply, reasoning, tool-call names and arguments), i.e. "
             "what an SFT run puts loss on. It is a subset of the unique text in the chart above.")
    log_hist([s["tool_calls"] for s in S], "session_tool_calls", "Tool calls per session", "tool calls (log scale)",
             "Each call counted once by its id, every agent included. Sessions with 0 calls are left out of a log axis.")

    names = sorted(tools, key=lambda n: (-tools[n]["calls"], n))[:TOP_TOOLS]
    if names:
        h = 0.6 + 0.22 * len(names)
        fig, ax = plt.subplots(figsize=(7, max(1.8, h)))
        vals = [tools[n]["calls"] for n in names]
        ax.barh(range(len(names)), vals, color=SERIES, height=0.7)
        ax.set_yticks(range(len(names)), names)
        ax.invert_yaxis()
        for i, v in enumerate(vals):
            ax.text(v, i, f" {v:,}", va="center", color=INK, fontsize=7)
        ax.set_title("Tool calls by tool, all sessions", loc="left", color=INK)
        ax.set_xlabel("calls")
        ax.grid(axis="y", visible=False)
        save(fig, "tool_calls", f"Number of calls per tool over the whole dataset (each call once, by id); top {TOP_TOOLS} "
             "tools shown, the table lists all.")

        with_res = [n for n in names if tools[n]["res"]]
        fig, ax = plt.subplots(figsize=(7, max(1.8, 0.6 + 0.22 * len(with_res))))
        for i, n in enumerate(with_res):
            r = sorted(tools[n]["res"])
            ax.plot([pct(r, 10), pct(r, 90)], [i, i], color=SERIES, linewidth=2, solid_capstyle="round")
            ax.plot([pct(r, 50)], [i], "o", color=SERIES, markersize=6, markeredgecolor=SURFACE)
            ax.plot([r[-1]], [i], "|", color=MUTED, markersize=8)
        ax.set_yticks(range(len(with_res)), with_res)
        ax.invert_yaxis()
        ax.set_xscale("log")
        log_axis(ax.xaxis)
        ax.set_title(f"Size of one tool result, per tool ({unit})", loc="left", color=INK)
        ax.set_xlabel(f"{unit} (log scale)")
        ax.grid(axis="y", visible=False)
        save(fig, "tool_result_size", "One row per tool: the bar spans p10–p90 of its result sizes, the dot is the "
             "median, the grey tick the largest. Text only; results that carry an image are counted in the table's "
             "`img results` column.")
    return made


# --- report ---
def notes(*lines: str) -> list[str]:
    """What the table above measures: one bullet per row / relation."""
    return ["", *(f"- {l}" for l in lines if l), ""]


def version_table(versions: Counter, diff_paths: Counter) -> list[str]:
    """Repeats of one message (same ids / content) vs its first version, before any is chosen for measuring."""
    if not versions:
        return []
    roles = sorted({r for r, _ in versions}, key=lambda r: -sum(c for (rr, _), c in versions.items() if rr == r))
    classes = sorted({c for _, c in versions}, key=lambda c: (c != "identical", -sum(n for (_, cc), n in versions.items() if cc == c), c))
    L = ["## Repeated messages", "",
         "| repeat vs first version | " + " | ".join(f"`{r}`" for r in roles) + " |", "|---|" + "---|" * len(roles),
         *(f"| {c} | " + " | ".join(str(versions[r, c]) for r in roles) + " |" for c in classes)]
    L += notes(
        "A repeat is a later copy of a message already seen in the same session (matched by tool-call/result ids, or "
        "by role + content + image references). Each copy is counted, so a message resent five times adds five.",
        "**identical**: every field equal. **same text and images, other fields differ**: the model-visible text and "
        "the image references are equal; only other fields changed (which ones: table below). **text cut at the end**: "
        "the repeat's text is a prefix of the first. **some images removed**: image references dropped, with or "
        "without a text change (e.g. a placeholder). **other rows**: as named.",
        "Ids are never reused by a regeneration (a new generation gets new ids), so a repeat is the same event shown "
        "again; whatever a harness changed on resend is listed here. Lengths and counts in this report use the first "
        "version.",
    )
    if diff_paths:
        top = sorted(diff_paths.items(), key=lambda kv: (-kv[1], kv[0]))[:2 * ENUM_MAX]
        L += ["| role | repeat vs first version | field that differs | repeats |", "|---|---|---|---|",
              *(f"| `{r}` | {k} | `{p}` | {c} |" for (r, k, p), c in top)]
        L += notes("For every non-identical row above: JSON paths (`$` = the message, `[]` = any list element) whose "
                   "value was added, removed or changed vs the first version; one repeat can list several paths. "
                   f"Top {2 * ENUM_MAX}.")
    return L


def render(root: Path, files: list[Path], data: dict, key_info: tuple, tok_name: str | None, figs: list) -> str:
    sess, tools, rel = data["sess"], data["tools"], data["rel"]
    S = list(sess.values())
    unit = "tokens" if tok_name else "chars"
    has_api = any(s["api_calls"] for s in S)
    key, key_hits, n = key_info
    n_calls = sum(t["calls"] for t in tools.values())
    col = lambda m: [s[m] for s in S]
    fig = {Path(p).stem: [f"![{Path(p).stem}]({p})", "", f"*{c}*", ""] for p, c in figs}
    figs_of = lambda *names: [line for k in names if k in fig for line in fig[k]]
    sub = sum(a <= b for a, b in zip(col("output"), col("text")))
    roles_img = ", ".join(f"`{r}` {c}" for r, c in sorted(data["img_roles"].items(), key=lambda kv: -kv[1]) if c)
    L = [
        f"# Trace report: `{root.name}`",
        "",
        f"Generated by `python script/dataset/trajectory/report.py`. Every number below is computed from the files; "
        "nothing is hand-written. Deterministic: files in sorted path order, nearest-rank percentiles, no timestamps, "
        f"no message text copied (field values are listed only when a field has at most {ENUM_MAX} distinct values, "
        f"each ≤ {ENUM_LEN} chars and seen ≥ {ENUM_MIN} times).",
        "",
        "## Input",
        "",
        f"- files: {len(files)} ({', '.join(f'`{e}` {c}' for e, c in sorted(Counter(''.join(p.suffixes[-2:]) for p in files).items()))}); "
        f"records: {data['n_rec']} (a `.json` file is one record, a `.jsonl` line is one record)",
        f"- session = records sharing `{key}` (in {key_hits}/{n} records)" if key else
        f"- session = one file (no top-level `session_id`-like key in every record; best had {key_hits}/{n})",
        f"- sessions: {len(sess)}",
        f"- text length unit: **{unit}**" + (f" (`{tok_name}` tokenizer, no special tokens; images, chat template and "
                                              "tool schemas not counted)" if tok_name else " (pass `--tokenizer` for tokens)"),
        "",
        "## Detected structure",
        "",
        "| what | rule | count |",
        "|---|---|---|",
        *(f"| message | `role: {r}` | {c} |" for r, c in sorted(data["roles"].items(), key=lambda kv: -kv[1])),
        *(f"| tool call | {p} | {c} |" for p, c in sorted(data["call_pat"].items())),
        *(f"| tool result | {p} | {c} |" for p, c in sorted(data["res_pat"].items())),
        *(f"| usage block | {p} | {c} |" for p, c in sorted(data["usage_conv"].items())),
        f"| usage block repeated under the same parent id (skipped) | | {data['dup_usage']} |",
        *(f"| repeated message, matched by {k} (counted once) | | {c} |" for k, c in sorted(data["dedup"].items())),
        f"| ⚠ dicts with `name` + `arguments`/`input` not matched as a tool call | | {data['n_unmatched']} |",
        f"| tool calls without an id (cannot pair or de-duplicate) | | {data['noid']['call']} |",
        f"| tool results without a call id | | {data['noid']['result']} |",
        f"| tool calls with no result | | {data['unpaired_calls']} |",
        f"| tool results with no call | | {data['unpaired_results']} |",
        *notes(
            "**message**: any object with a string `role`, counted once per session. The rule column is the role value.",
            "**tool call / tool result / usage block**: objects matching one of the fixed wire-format rules "
            "(`as_tool_call`, `as_tool_result`, `is_usage` in the script); the rule column names the format that matched. "
            "A usage block's rule is also the formula used for its context length.",
            "**De-duplication** (some harnesses resend the whole history every call): tool calls and results by their id; "
            "usage blocks by their parent's id; messages by the tool-call/result ids they hold, or, without ids, by role + "
            "content + image references. Reasoning and harness metadata are not part of a message's identity because "
            "resends may strip or add them. The first version seen is measured; how the repeats differ from it is in "
            "**Repeated messages** below.",
            "**⚠ row**: objects shaped like a tool call that no rule matched. Non-zero means a format the script does not "
            "know yet, so its tool counts are incomplete.",
            f"Tool results vs messages: {rel['result is a message itself']} results are messages themselves "
            f"(`role: tool`), {rel['result nested inside a message']} sit inside another message (e.g. Anthropic "
            "`tool_result` blocks in a user message). Either way their text is part of the message text below.",
        ),
        f"Keys whose string values were counted as message text ({unit[:-1]} length measured on their concatenation):",
        "",
        ", ".join(f"`{k or '(root)'}` {c:,} chars" for k, c in data["text_keys"].most_common()),
        "",
        "Every string under a message counts except keys that look like ids, types, urls, roles, signatures or base64 "
        "data. If a key here should not be model-visible text, the length numbers below include it.",
        "",
        *version_table(data["versions"], data["diff_paths"]),
        "## Sessions",
        "",
        *dist_table([("records", col("records")), ("messages", col("messages")), ("tool calls", col("tool_calls")),
                     ("tool results", col("tool_results")), ("images", col("images")),
                     *([("LLM calls (usage blocks)", col("api_calls"))] if has_api else [])]),
        *notes(
            "Each row is a distribution over sessions: one value per session, so `sessions` is how many values; `sum` "
            "is the dataset total.",
            "**records**: files (or `.jsonl` lines) in the session. **messages**: unique messages of every role and agent.",
            "**tool calls / tool results**: unique by id; a call can lack a result (see the structure table).",
            f"**images**: image parts inside unique messages; the same picture sent in two different messages counts "
            f"twice. By role: {roles_img or 'none'}." ,
            "**LLM calls**: unique usage blocks, i.e. requests the provider billed." if has_api else "",
        ),
        "## Length",
        "",
        *dist_table([(f"unique text ({unit})", col("text")), (f"assistant text ({unit})", col("output")),
                     *([("API final context", col("api_ctx")), ("API output", col("api_out")),
                        ("API output, reasoning", col("api_reason")), ("API input processed", col("api_in_sum"))]
                       if has_api else [])]),
        *notes(
            f"**unique text**: total text of the session's unique messages, every role and agent ({unit}). Not the "
            "length of any single request: sub-agents and side requests have their own contexts.",
            f"**assistant text**: the `role: assistant` part of unique text (replies, reasoning, tool-call arguments). "
            f"Subset of unique text (holds in {sub}/{len(S)} sessions).",
            "**API final context**: the largest `input + output` of one call, in the provider's tokenizer (images and "
            "chat template included). This is the longest sequence the model actually saw." if has_api else "",
            "**API output**: provider output tokens summed over every call. **API output, reasoning**: the reasoning "
            f"tokens the provider reports. reasoning ≤ output in {rel['usage with reasoning ≤ output']}/"
            f"{rel['usage with reasoning']} usage blocks that report reasoning, i.e. reasoning is counted inside API "
            "output, not on top of it" + ("." if rel["usage with reasoning ≤ output"] == rel["usage with reasoning"] else
            f", ⚠ except {rel['usage with reasoning'] - rel['usage with reasoning ≤ output']} blocks whose reported "
            "output is smaller than their reasoning.") if has_api else "",
            "**API input processed**: input tokens summed over every call. Each call re-reads the whole context, so "
            "this measures serving cost, not conversation length." if has_api else "",
            "API counts use the provider's tokenizer and include images; text counts use "
            f"{'`' + tok_name + '`' if tok_name else 'characters'} and exclude them, so the two families are not directly "
            "comparable." if has_api else "",
        ),
    ]
    if has_api or unit == "tokens":
        L += ["Sessions that fit a length (cumulative):", "",
              *bucket_table([*([("API final context", col("api_ctx"))] if has_api else []),
                             *([("unique text (tokens)", col("text"))] if unit == "tokens" else [])], EDGES),
              *notes("Each cell: sessions whose value is at or below the row's length / all sessions. Use the API column "
                     "to see whether whole sessions fit a training length without cutting."), ]
    L += figs_of("session_api_context", "session_text", "session_api_output", "session_output", "session_tool_calls")
    L += [
        "## Tools",
        "",
        "| tool | calls | share | sessions | args p50 | args max | result p50 | result p90 | result max | img results | errors |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    order = sorted(tools, key=lambda n: (-tools[n]["calls"], n))
    for name in order:
        t = tools[name]
        a, r = sorted(t["args"]), sorted(t["res"])
        rp = f"{pct(r, 50):,} | {pct(r, 90):,} | {r[-1]:,}" if r else "— | — | —"
        err = f"{t['err']}/{t['flag']}" if t["flag"] else "—"
        L.append(f"| `{name}` | {t['calls']} | {100 * t['calls'] / n_calls:.1f}% | {len(t['sessions'])}/{len(sess)} | "
                 f"{pct(a, 50):,} | {a[-1]:,} | {rp} | {t['res_img']} | {err} |")
    L += notes(
        f"One row per tool, {n_calls} calls over {len(tools)} tools in total. **calls**: unique by id. **share**: of all "
        "calls. **sessions**: sessions that used the tool at least once / all sessions.",
        f"**args**: size of one call's arguments ({unit}). **result**: size of one result's text ({unit}), paired to its "
        "call by id; images are not in this size.",
        "**img results**: results that carry at least one image. **errors**: results flagged `is_error: true` or "
        "`status: \"error\"` / results that carry such a flag (— = the format has no flag).",
    )
    L += figs_of("tool_calls", "tool_result_size")
    L += ["### Arguments",
          "",
          "| tool | argument | type | present |", "|---|---|---|---|"]
    for name in order:
        t = tools[name]
        keys = sorted(t["keys"], key=lambda k: (-sum(t["keys"][k].values()), k))
        bad = f" ({t['bad']} not a JSON object)" if t["bad"] else ""
        if not keys:
            L.append(f"| `{name}`{bad} | — | — | — |")
        for i, k in enumerate(keys):
            L.append(f"| {f'`{name}`{bad}' if i == 0 else ''} | `{k}` | {' / '.join(sorted(t['keys'][k]))} | "
                     f"{sum(t['keys'][k].values())}/{t['calls']} |")
    L += notes("Argument keys found after parsing each call's arguments as JSON (the export may not carry the tool "
               "schemas, so this is the observed shape). **present**: calls with the key / calls of the tool; below 100% "
               "means optional. **type**: JSON types seen for the value.")
    L += ["## Fields", "", *field_table(data["fields"]),
          *notes("Every JSON path in the records. `$` is one record, `[]` a list element, `<hash>` any hex-hash key.",
                 "**present**: containers holding the key / containers at the parent path (below 100% = optional "
                 "field). **count**: occurrences, list elements included.",
                 "**values / range**: numeric range, string length range, and the values themselves only for short "
                 "low-cardinality fields (rule at the top).")]
    return "\n".join(L)


def build_report(in_path: str, out: str | None = None, tokenizer: str | None = None,
                 session_key: str | None = None) -> Path:
    """Scan in_path (a folder or one file) and write the report (+ img/*.svg next to it). Returns the report path."""
    root = Path(in_path).resolve()
    files = trace_files(root)
    if not files:
        raise SystemExit(f"No .json/.jsonl(.gz) under {root}")
    out_path = Path(out).resolve() if out else (root if root.is_dir() else root.parent) / OUT_NAME
    files = [f for f in files if f != out_path]
    if session_key == "file":
        key_info = (None, 0, sum(1 for f in files for _ in records(f)))
    elif session_key:
        key_info = (session_key, -1, -1)
    else:
        key_info = detect_session_key(files)
    if tokenizer:
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained(tokenizer)
        tok.model_max_length = sys.maxsize  # counting only; silences the over-length warning
        size = lambda s: len(tok(s, add_special_tokens=False)["input_ids"]) if s else 0
    else:
        size = len
    data = collect(files, root if root.is_dir() else root.parent, key_info[0], size)
    has_api = any(s["api_calls"] for s in data["sess"].values())
    figs = charts(out_path.parent / IMG_DIR, data["sess"], data["tools"],
                  "tokens" if tokenizer else "chars", has_api)
    out_path.write_text(render(root, files, data, key_info, tokenizer, figs), encoding="utf-8")
    return out_path


# Run =====================================================
if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("in_path", help="folder of traces, or one .json/.jsonl(.gz) file")
    cli.add_argument("--out", default=None, help=f"report path (default: <folder>/{OUT_NAME})")
    cli.add_argument("--tokenizer", default=None, help="HF tokenizer id/path; lengths are chars without it")
    cli.add_argument("--session-key", default=None, help="top-level key that groups records into sessions, or 'file'")
    args = cli.parse_args()
    print(f"Wrote {build_report(args.in_path, args.out, args.tokenizer, args.session_key)}")
