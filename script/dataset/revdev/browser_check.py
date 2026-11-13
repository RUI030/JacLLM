"""Exercise a generated revdev UI in Chromium and record source hashes."""

import argparse, hashlib, json, re
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

# Setting =================================================
SOURCES = {
    "mindcraft": ("main.jac", "components/MindcraftApp.jac", "services/island.jac", "styles.css", "jac.toml"),
    "weekly_brief": ("jac.toml", "main.jac", "services/brief_dates.jac", "components/WeekPlanner.jac", "styles.css"),
}


# Functions ===============================================
def check_mindcraft(page, out: Path) -> list[str]:
    actions = []
    expect(page.get_by_text("Your island is empty", exact=True)).to_be_visible()
    actions.append("empty island rendered")
    page.get_by_label("How are you feeling?").fill("I feel anxious about tomorrow")
    page.get_by_role("button", name="Add check-in", exact=True).click()
    place = page.get_by_role("button", name=re.compile("^Place ")).first
    expect(place).to_be_visible()
    place.click()
    expect(page.get_by_label("What matters to you here?")).to_be_visible()
    actions.append("check-in created and placed")
    page.get_by_role("button", name="breathe", exact=True).click()
    page.get_by_label("What matters to you here?").fill("Connection")
    page.get_by_label("One concrete next action").fill("Call a friend")
    page.get_by_role("button", name="Commit intention", exact=True).click()
    expect(page.locator(".mc-path")).to_contain_text("Call a friend")
    actions.append("interaction and intention persisted in path")
    page.screenshot(path=str(out / "working-app.png"), full_page=True)
    page.get_by_role("button", name="Reset island", exact=True).click()
    expect(page.get_by_text("Your island is empty", exact=True)).to_be_visible()
    actions.append("reset cleared island")
    page.get_by_label("How are you feeling?").fill("I want to kill myself")
    page.get_by_role("button", name="Add check-in", exact=True).click()
    expect(page.locator(".mc-crisis")).to_be_visible()
    expect(page.get_by_text("Your island is empty", exact=True)).to_be_visible()
    actions.append("crisis guidance shown without an entity")
    return actions


def check_weekly_brief(page) -> list[dict]:
    expect(page.get_by_role("heading", name=re.compile("weekly brief planner", re.I))).to_be_visible()
    expect(page.get_by_test_id("current-label")).to_be_visible()
    flows = []
    for chosen, monday, index, label in (
        ("2026-09-26", "2026-09-28", -2, "Monday, September 28, 2026"),
        ("2026-09-30", "2026-09-28", 2, "Monday, September 28, 2026"),
    ):
        page.locator('input[type="date"]').fill(chosen)
        page.get_by_role("button", name=re.compile("Preview (brief )?week", re.I)).click()
        page.wait_for_function("""([day, expectedMonday, expectedIndex, expectedLabel]) => {
            const preview = document.querySelector('[data-testid="preview-label"]')?.closest('section');
            return preview?.textContent?.includes(day) && preview?.textContent?.includes(expectedMonday) &&
              document.querySelector('[data-testid="preview-index"]')?.textContent === String(expectedIndex) &&
              document.querySelector('[data-testid="preview-label"]')?.textContent === expectedLabel;
        }""", arg=[chosen, monday, index, label])
        flows.append({"date": chosen, "monday": monday, "day_index": index, "label": label})
    return flows


def scripted_spec(path: Path, workspace: Path) -> dict:
    """Load a bounded browser flow; source and behavior checks are mandatory."""
    spec = json.loads(path.read_text())
    sources = spec.get("source_files", [])
    steps = spec.get("steps", [])
    if not sources or not steps:
        raise ValueError("Scripted browser checks need source_files and steps")
    if not any(step.get("op") in {"fill", "click", "select_option"} for step in steps):
        raise ValueError("Scripted browser checks need a user action")
    if not any(step.get("op") in {"expect_text", "expect_visible", "expect_count"} for step in steps):
        raise ValueError("Scripted browser checks need an observed result")
    for source in sources:
        relative = Path(source)
        if relative.is_absolute() or ".." in relative.parts or not (workspace / relative).is_file():
            raise ValueError(f"Invalid browser source file: {source}")
    for step in steps:
        if step.get("op") not in {"fill", "click", "select_option", "expect_text", "expect_visible", "expect_count"}:
            raise ValueError(f"Unsupported browser operation: {step.get('op')}")
        if not isinstance(step.get("selector"), str) or not step["selector"]:
            raise ValueError("Every browser step needs a CSS selector")
        if step["op"] in {"fill", "select_option"} and not isinstance(step.get("value"), str):
            raise ValueError(f"{step['op']} needs a string value")
        if step["op"] == "expect_text" and not isinstance(step.get("text"), str):
            raise ValueError("expect_text needs a string text")
        if step["op"] == "expect_count" and (not isinstance(step.get("count"), int)
                                              or step["count"] < 0):
            raise ValueError("expect_count needs a nonnegative integer count")
    return spec


def check_scripted(page, spec: dict) -> list[dict]:
    completed = []
    for step in spec["steps"]:
        locator = page.locator(step["selector"])
        operation = step["op"]
        if operation == "fill":
            locator.fill(step["value"])
        elif operation == "select_option":
            locator.select_option(step["value"])
        elif operation == "click":
            locator.click()
        elif operation == "expect_text":
            expect(locator).to_contain_text(step["text"])
        elif operation == "expect_count":
            expect(locator).to_have_count(step["count"])
        else:
            expect(locator).to_be_visible()
        completed.append(step)
    return completed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--scenario", choices=(*SOURCES, "scripted"), default="mindcraft")
    parser.add_argument("--spec", type=Path, help="JSON browser steps for --scenario scripted")
    args = parser.parse_args()
    spec = scripted_spec(args.spec, args.workspace) if args.scenario == "scripted" and args.spec else None
    if args.scenario == "scripted" and spec is None:
        parser.error("--scenario scripted requires --spec")
    args.out.mkdir(parents=True, exist_ok=True)
    errors = []
    actions = []
    flows = []
    status = "failed"
    failure = ""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path="/home/imrui/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome",
            headless=True, args=["--no-sandbox", "--disable-gpu"])
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            response = page.goto(args.url, wait_until="networkidle")
            assert response and response.status == 200, f"GET {args.url}: {response.status if response else None}"
            if args.scenario == "mindcraft":
                actions = check_mindcraft(page, args.out)
            elif args.scenario == "weekly_brief":
                flows = check_weekly_brief(page)
                page.screenshot(path=str(args.out / "working-app.png"), full_page=True)
            else:
                actions = check_scripted(page, spec)
                page.screenshot(path=str(args.out / "working-app.png"), full_page=True)
            assert not errors, errors
            status = "passed"
        except Exception as exc:
            failure = str(exc)
            raise
        finally:
            paths = spec["source_files"] if spec else SOURCES[args.scenario]
            evidence = {"status": status, "scenario": args.scenario, "actions": actions,
                        "flows": flows, "page_errors": errors, "failure": failure, "url": args.url,
                        "workspace": str(args.workspace),
                        "source_sha256": {p: hashlib.sha256((args.workspace / p).read_bytes()).hexdigest()
                                          for p in paths}}
            if spec:
                evidence["spec_sha256"] = hashlib.sha256(args.spec.read_bytes()).hexdigest()
                evidence["spec_name"] = spec.get("name", "")
            (args.out / "browser.json").write_text(json.dumps(evidence, indent=2) + "\n")
            browser.close()
    print(json.dumps(evidence))


# Run =====================================================
if __name__ == "__main__":
    main()
