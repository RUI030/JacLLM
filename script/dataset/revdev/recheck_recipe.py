"""Independently recheck a revdev recipe before spending teacher calls.

Checks the plan renders, only the target Jac version is mentioned, the recorded
acceptance hash matches, which planned files are byte-identical to recorded
source hashes, and that `jac check main.jac` plus the acceptance tests pass on a
fresh copy of the preflight slice.
"""

import argparse, hashlib, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from dataset.revdev.plan_md import render, validate_rendered

# Setting =================================================
RECIPES = Path(__file__).resolve().parent / "recipes"
JAC = Path.home() / ".local/bin/jac"
TARGET = "0.36.1"

# Functions ===============================================
def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str], cwd: Path) -> str:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=300,
                            env={**os.environ, "JAC_TEST_NATIVE": "1", "JAC_TEST_JOBS": "0"})
    return result.stdout + result.stderr


def recheck(slug: str, preflight: Path) -> dict:
    recipe = RECIPES / slug
    task = json.loads((recipe / "task.json").read_text())
    plan = json.loads((recipe / "plan.json").read_text())
    provenance = json.loads((recipe / "provenance.json").read_text())
    validate_rendered(render(plan, task["request"]), plan)
    versions = set(re.findall(r"\b(\d+\.\d+\.\d+)\b", json.dumps([task, plan])))
    acceptance = recipe / "reference_acceptance.jac"
    known = {}
    for key in ("source_files_sha256", "slice_files_sha256"):
        known.update({digest: name for name, digest in provenance.get(key, {}).items()})
    fresh = Path(tempfile.mkdtemp(prefix=f"revdev-recheck-{slug}-"))
    files = {}
    for row in plan["files"]:
        target = fresh / row["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(preflight / row["path"], target)
        files[row["path"]] = known.get(sha(target), "new_or_edited")
    shutil.copyfile(acceptance, fresh / "revdev_acceptance.jac")
    check = run([str(JAC), "check", "main.jac"], fresh)
    test = run([str(JAC), "test", "revdev_acceptance.jac"], fresh)
    ran = re.search(r"Ran (\d+) tests?", test)
    return {"slug": slug, "plan": "ok", "versions_ok": versions <= {TARGET},
            "acceptance_sha_ok": sha(acceptance) == provenance.get("independent_acceptance_sha256"),
            "layers": sorted({row["layer"] for row in plan["files"]}),
            "ai_required": plan["ui"].get("ai_required"),
            "by_llm_files": [p for p in files if (fresh / p).suffix == ".jac" and "by llm" in (fresh / p).read_text()],
            "py_lines": sum(len((fresh / p).read_text().splitlines()) for p in files if p.endswith(".py")),
            "files": files, "check_ok": bool(re.search(r"\b\d+ passed", check)) and not re.search(r"\b\d+ failed", check),
            "tests_ran": int(ran.group(1)) if ran else 0,
            "tests_ok": bool(ran) and "\nOK" in test and "FAILED" not in test,
            "fresh_dir": str(fresh)}

# Main ====================================================
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slugs", nargs="+")
    parser.add_argument("--preflight", default="/tmp/revdev-{slug}-preflight",
                        help="preflight directory pattern holding the original slice")
    args = parser.parse_args()
    for slug in args.slugs:
        print(json.dumps(recheck(slug, Path(args.preflight.format(slug=slug))), indent=1))

if __name__ == "__main__":
    main()
