"""Build grounded M2 task and planning artifacts; never expose reference code."""

import argparse
import hashlib
import json
from pathlib import Path


RECIPE = Path(__file__).parent / "recipes" / "pm_mvp.json"
PLAN_KEYS = {"schema_version", "ui", "files", "write_order", "dependency_graph",
             "remove_from_template", "verify", "build_log", "confidence", "assumption"}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def symbol_for(key: str, symbols: list[dict]) -> dict:
    """Resolve an explicit file/name hint; require overload disambiguation."""
    path, hint = key.split("::", 1)
    name = hint.split("(", 1)[0]
    matches = [s for s in symbols if s["file"] == path and s["name"] == name
               and ("(" not in hint or s["signature"].startswith("def:pub " + hint))]
    if len(matches) != 1:
        raise ValueError(f"Evidence must identify one symbol: {key} ({len(matches)} matches)")
    return matches[0]


def evidence_for(key: str, symbols: list[dict], files: dict[str, dict]) -> dict:
    symbol = symbol_for(key, symbols)
    source = files[symbol["file"]]
    return {"source_file": symbol["file"], "source_sha256": source["sha256"],
            "symbol_id": symbol["id"], "symbol_kind": symbol["kind"],
            "signature": symbol["signature"], "span": symbol["span"]}


def validate_plan(plan: dict, recipe: dict) -> None:
    """Enforce the captured JacCoder contract and topological dependencies."""
    if set(plan) != PLAN_KEYS:
        raise ValueError(f"JacCoder plan key mismatch: {set(plan) ^ PLAN_KEYS}")
    rows = plan["files"]
    if not 4 <= len(rows) <= 8:
        raise ValueError("First build exceeds JacCoder file budget")
    paths = [f["path"] for f in rows]
    if len(paths) != len(set(paths)) or paths != plan["write_order"]:
        raise ValueError("Write order must list each planned file once")
    if plan["schema_version"] != "1" or plan["build_log"]["overall_status"] != "pending":
        raise ValueError("Unexpected JacCoder plan schema or status")
    owners = {}
    for i, f in enumerate(rows, 1):
        if f["write_order"] != i or f["status"] != "pending":
            raise ValueError(f"Invalid file position/status: {f['path']}")
        if f["path"].startswith("components/ui/"):
            raise ValueError("Shadcn primitives must be installed, not authored")
        for name in f["exports"]:
            if name in owners:
                raise ValueError(f"Ambiguous planned export: {name}")
            owners[name] = f["path"]
    for i, f in enumerate(rows):
        expected = []
        for name in f["imports_from_plan"]:
            provider = owners.get(name)
            if provider not in paths[:i]:
                raise ValueError(f"{f['path']} imports {name} before its provider")
            if provider not in expected:
                expected.append(provider)
        if plan["dependency_graph"][f["path"]] != expected:
            raise ValueError(f"Incorrect dependency graph for {f['path']}")
    if plan["ui"]["auth_required"] != recipe["ui"]["auth_required"] or plan["ui"]["ai_required"] != recipe["ui"]["ai_required"]:
        raise ValueError("Pilot scope requirements changed")
    page_exports = {p["name"] for p in plan["ui"]["pages"]}
    if page_exports != {f["exports"][0] for f in rows if f["layer"] == "page"}:
        raise ValueError("Page routes do not match planned page exports")
    if plan["verify"]["flow"] not in owners:
        raise ValueError("Verification flow has no service export")
    if plan["remove_from_template"]:
        raise ValueError("Template removals require a captured template listing")
    if any("{" in f["purpose"] or "}" in f["purpose"] for f in rows):
        raise ValueError("File purpose contains implementation syntax")
    if not recipe["features"]:
        raise ValueError("No grounded features")


def build(manifest: dict, recipe: dict, task: dict) -> tuple[dict, dict, dict]:
    files = {f["path"]: f for f in manifest["files"] if f["selected"]}
    symbols = manifest["symbols"]
    if manifest["baseline"]["state"] != "passed":
        raise ValueError("Reference baseline did not pass")
    feature_evidence = {}
    for feature in recipe["features"]:
        feature_evidence[feature["name"]] = [evidence_for(k, symbols, files) for k in feature["evidence"]]
    order = [f["path"] for f in recipe["files"]]
    owners = {name: f["path"] for f in recipe["files"] for name in f["exports"]}
    graph, plan_files, oracle_files = {}, [], []
    for i, row in enumerate(recipe["files"], 1):
        deps = list(dict.fromkeys(owners[name] for name in row["imports_from_plan"]))
        graph[row["path"]] = deps
        plan_files.append({k: row[k] for k in ("path", "layer", "purpose", "exports", "imports_from_plan")}
                          | {"write_order": i, "status": "pending"})
        source_files = []
        for path in row["file_evidence"]:
            if path not in files:
                raise ValueError(f"Missing source file: {path}")
            source_files.append({"path": path, "sha256": files[path]["sha256"]})
        sigs = [evidence_for(k, symbols, files) for k in row["signature_evidence"]]
        if not source_files or (not sigs and row["layer"] not in {"config", "asset"}):
            raise ValueError(f"File lacks evidence: {row['path']}")
        oracle_files.append(plan_files[-1] | {"signatures": sigs, "source_files": source_files,
                                                 "dependency_group": i})
    plan = {
        "schema_version": "1", "ui": recipe["ui"], "files": plan_files,
        "write_order": order, "dependency_graph": graph, "remove_from_template": [],
        "verify": recipe["verify"],
        "build_log": {"overall_status": "pending", "last_action": "", "issues": [], "learnings": []},
        "confidence": 0.82,
        "assumption": recipe.get("assumption", "The initial build uses the selected JacCoder workspace and runtime.")
    }
    validate_plan(plan, recipe)
    opaque_reference = "ref_" + hashlib.sha256(
        manifest["reference"]["reference_id"].encode()).hexdigest()[:12]
    visible = {
        "schema_version": "1", "task_id": task["task_id"],
        "reference_id": opaque_reference,
        "request": task["request"], "workspace_kind": recipe.get("workspace_kind", "pinned_template"),
        "acceptance": task["acceptance"],
        "constraints": recipe.get("constraints", ["Use a Jac fullstack application."]),
    }
    oracle = {
        "schema_version": "1", "task_id": task["task_id"], "plan_schema": "jaccoder.build_plan.v1",
        "scope": recipe["scope"], "features": [f["name"] for f in recipe["features"]],
        "files": oracle_files, "dependency_graph": graph, "write_order": order,
        "verification": recipe["verify"],
        "evidence": {"reference_id": manifest["reference"]["reference_id"],
                     "tree_sha256": manifest["reference"]["tree_sha256"],
                     "jac_version": manifest["toolchain"]["jac_version"],
                     "features": feature_evidence},
    }
    return visible, oracle, plan


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--recipe", type=Path, default=RECIPE)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    manifest, recipe = read_json(args.manifest), read_json(args.recipe)
    for task in recipe["tasks"]:
        visible, oracle, plan = build(manifest, recipe, task)
        target = args.out / task["task_id"]
        write_json(target / "visible" / "task.json", visible)
        write_json(target / "private" / "oracle_plan.json", oracle)
        write_json(target / "private" / "planning_target.json", plan)
        print(f"{task['task_id']}: {len(plan['files'])} files, {len(oracle['features'])} features")


if __name__ == "__main__":
    main()
