"""Render a grounded JacCoder manifest as a student-facing development plan."""

import argparse
import json
from pathlib import Path


def jac_modules(plan: dict, module_only: bool = True) -> list[dict]:
    return [row for row in plan["files"] if not module_only or row["path"].endswith(".jac")]


def render(plan: dict, request: str = "", *, module_only: bool = True) -> str:
    files = jac_modules(plan, module_only)
    ids = {row["path"]: f"M{index}" for index, row in enumerate(files, 1)}
    lines = ["# Implementation plan", "", "## Goal", "",
             request or "Build the requested application.", "",
             "## Module relationships", "", "```mermaid", "flowchart LR"]
    for row in files:
        lines.append(f'    {ids[row["path"]]}["{row["path"]}"]')
    for consumer, providers in plan["dependency_graph"].items():
        if consumer not in ids:
            continue
        for provider in providers:
            if provider in ids:
                lines.append(f"    {ids[provider]} --> {ids[consumer]}")
    lines += ["```", "", "An arrow points from a provider to a module that imports it.", "",
              ]
    if module_only:
        for heading, rows in (("Frontend modules (.jac)",
                               [row for row in files if row["layer"] in {"page", "shell", "client", "component"}]),
                              ("Backend modules (.jac)",
                               [row for row in files if row["layer"] not in {"page", "shell", "client", "component"}])):
            lines += [f"## {heading}", ""]
            for row in rows:
                exports = ", ".join(f"`{name}`" for name in row["exports"]) or "—"
                lines.append(f'- `{row["path"]}` — {row["purpose"]} Public interface: {exports}.')
            lines.append("")
    lines += ["## Jac module build order" if module_only else "## Files and build order", "",
              "| Order | File | Responsibility | Imports from this app | Public interface |",
              "| ---: | --- | --- | --- | --- |"]
    for index, row in enumerate(files, 1):
        imports = ", ".join(row["imports_from_plan"]) or "—"
        exports = ", ".join(f"`{name}`" for name in row["exports"]) or "—"
        purpose = row["purpose"].replace("|", "\\|")
        lines.append(f'| {index if module_only else row["write_order"]} | `{row["path"]}` | {purpose} | {imports} | {exports} |')
    lines.append("")
    if module_only:
        support = [row["purpose"] for row in plan["files"] if row["layer"] == "config"]
        if support:
            lines += ["## Build support", ""] + [f"- {purpose}" for purpose in support] + [""]
    signatures = [(row["path"], row.get("signatures")) for row in files if row.get("signatures")]
    if signatures:
        lines += ["", "## Planned signatures", ""]
        for path, content in signatures:
            lines += [f"### `{path}`", ""]
            if isinstance(content, dict):
                lines += [f"- `{name}`: {signature}" for name, signature in content.items()]
            elif isinstance(content, list):
                lines += [f"- `{signature}`" for signature in content]
            lines.append("")
    lines += ["## Verification", ""]
    verify = plan["verify"]
    for key, value in verify.items():
        if isinstance(value, list):
            value = "; ".join(value)
        lines.append(f"- **{key}:** {value}")
    lines += ["", "## Execution notes", "",
              "Create the planned Jac modules with imports and public signatures before filling in bodies. "
              "Set up project configuration and styling as needed during scaffolding. "
              "Read a dependency when its current interface is needed; reuse earlier reads while it is unchanged. "
              "Record evidence-based revisions here and rerun the affected checks.", ""]
    return "\n".join(lines)


def validate_rendered(markdown: str, plan: dict, *, module_only: bool = True) -> None:
    """Check the plan carries every planned Jac module and dependency edge."""
    if "```mermaid\nflowchart LR\n" not in markdown:
        raise ValueError("Plan has no Mermaid module graph")
    files = jac_modules(plan, module_only)
    ids = {row["path"]: f"M{index}" for index, row in enumerate(files, 1)}
    if module_only:
        for heading in ("## Frontend modules (.jac)", "## Backend modules (.jac)"):
            if heading not in markdown:
                raise ValueError("Plan omits module section: " + heading)
    for path, node in ids.items():
        if f'{node}["{path}"]' not in markdown or f"`{path}`" not in markdown:
            raise ValueError("Plan omits file: " + path)
    for consumer, providers in plan["dependency_graph"].items():
        if consumer not in ids:
            continue
        for provider in providers:
            if provider in ids and f"{ids[provider]} --> {ids[consumer]}" not in markdown:
                raise ValueError(f"Plan omits dependency: {provider} -> {consumer}")
    if module_only:
        graph = markdown.split("```mermaid\n", 1)[1].split("```", 1)[0]
        for row in plan["files"]:
            if not row["path"].endswith(".jac") and row["path"] in graph:
                raise ValueError("Non-Jac support file appears as a module: " + row["path"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--task", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    request = json.loads(args.task.read_text())["request"] if args.task else ""
    markdown = render(plan, request)
    validate_rendered(markdown, plan)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(markdown)


if __name__ == "__main__":
    main()
