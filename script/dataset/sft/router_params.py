"""JacHammer-format SFT rows that fix or extend manual-<Router> routing (route parameters read with useParams, <Link>,
useNavigate, a catch-all route, the @jac/runtime import) in small jac 0.34.28 apps, with real JacHammer tool results."""

import hashlib, json, random, shutil, subprocess, sys, tempfile
from collections import Counter
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from utils.classifier import classify_structural as classify
from dataset.pipeline import report
from dataset.parser.jachammer import JAC, JACBUILDER, call, fake_root, result, run_tools, session_parts, turn, user_text
from dataset.parser.jachammer_apps import DOMAINS, TASKS, app, expand, fix_steps

# Setting =================================================
DS_NAME     = "router_params_v1"
SOURCE      = "synthetic-router"
TASK_TYPE   = "jac_route_fix"
JAC_VERSION = "0.34.28"
ROOT        = Path(__file__).resolve().parents[3]
TEMPLATE    = JACBUILDER / "assets/templates/empty.jacpack"   # what JacHammer creates a new project from
SHADCN      = ["input"]                                        # installed on top of the template's button, card
OUT_DIR     = ROOT / f"output/sft/{TASK_TYPE}/{DS_NAME}"       # not under dataset/: moved there once reviewed
SEED        = 3407


# Functions ===============================================
def template(dst: Path) -> Path:
    """A fresh project from JacHammer's empty template, as `jac create --use` makes it, plus SHADCN components."""
    env = {"PATH": f"{JAC.parent}:/usr/bin:/bin", "HOME": str(Path.home())}
    subprocess.run([str(JAC), "create", "prj_template", "--use", str(TEMPLATE), "--force", "--skip"], cwd=dst, env=env,
                   check=True, capture_output=True, timeout=300, stdin=subprocess.DEVNULL)
    prj = dst / "prj_template"
    subprocess.run([str(JAC), "install", "--shadcn", *SHADCN], cwd=prj, env=env, check=True, capture_output=True,
                   timeout=300, stdin=subprocess.DEVNULL)
    shutil.rmtree(prj / ".jac", ignore_errors=True)
    return prj


def jobs() -> list[tuple[dict, str]]:
    """Every (domain, task) pair; stay_on_form needs a domain with an add form."""
    return [(d, t) for d in DOMAINS for t in TASKS if t != "stay_on_form" or d["form"]]


def materialize(base: Path, dst: Path, files: dict[str, str]) -> None:
    shutil.copytree(base, dst)
    for f in dst.glob("components/*.jac"):                     # the template ships no app components
        f.unlink()
    for rel, text in files.items():
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        (dst / rel).write_text(text)


def resolve(x, root: str):
    if isinstance(x, str):
        return x.replace("@ROOT@", root)
    if isinstance(x, dict):
        return {k: resolve(v, root) for k, v in x.items()}
    return x


def build_row(job: dict, sys_prompt: str, wrapper: str, project: str, tools: list[dict]) -> dict:
    fake = fake_root()
    msgs = [{"role": "system", "content": sys_prompt},
            {"role": "user", "content": [{"type": "text", "text": user_text(wrapper, project, fake, job["request"])}]}]
    for c, res in zip(job["calls"], job["results"]):
        k = call(c["name"], resolve(c["args"], fake))
        msgs += [turn(c.get("say", ""), c["why"], k, c.get("weight", 1)), result(k, res.replace(job["root"], fake))]
    d, task = job["domain"], job["task"]
    fp = hashlib.sha1(f"{DS_NAME}/{d['key']}/{task}".encode()).hexdigest()[:16]
    return {"messages": msgs, "tools": json.dumps(tools),
            "meta": {"source": SOURCE, "format": "trajectory", "class": classify("\n".join(job["final"].values())),
                     "task_type": TASK_TYPE, "fp": fp, "jac_version": JAC_VERSION, "data_version": DS_NAME,
                     "domain": d["key"], "task": task, "layout": d["layout"], "lookup": d["lookup"],
                     "trained_turns": sum(1 for c in job["calls"] if c.get("weight", 1))}}


def run_jobs(base: Path, tmp: Path, specs: list[dict]) -> list[dict]:
    """Run every spec's calls with JacHammer's own tools on its start state; check each ends at the complete app."""
    for i, s in enumerate(specs):
        s["root"] = str(tmp / f"prj_{i:03d}")
        materialize(base, Path(s["root"]), s["start"])
    outs = run_tools([{"op": "session", "root": s["root"], "calls": [{"name": c["name"], "args": resolve(c["args"], s["root"])}
                                                                    for c in s["calls"]]} for s in specs])
    for s, res in zip(specs, outs):
        s["results"] = res
        for rel, text in s["final"].items():
            assert (Path(s["root"]) / rel).read_text() == text, (s["domain"]["key"], s["task"], rel)
    return specs


def router_params(out_dir: Path = OUT_DIR) -> None:
    rng = random.Random(SEED)
    sys_prompt, wrapper, project, tools = session_parts()
    specs = []
    for d, task in jobs():
        start, request = TASKS[task](d)
        final = app(d)
        specs.append({"domain": d, "task": task, "start": start, "final": final, "request": request,
                      "calls": expand(fix_steps(d, task, rng), start, final)})
    with tempfile.TemporaryDirectory(prefix="router-ws-") as t:
        base = template(Path(t))
        specs = run_jobs(base, Path(t), specs)
        bad = [(s["task"], r[:200]) for s in specs for r in s["results"] if "ERRORS" in r or r.startswith("Error")]
        assert not bad, bad
        rows = [build_row(s, sys_prompt, wrapper, project, tools) for s in specs]
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "train.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    report({"train": len(rows)}, out_dir)
    print(Counter(r["meta"]["task"] for r in rows))


# Run =====================================================
if __name__ == "__main__":
    router_params()
