"""Exercise the generated Mindcraft UI against a local verification server."""

import argparse, hashlib, json, re
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

# Functions ===============================================
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    errors = []
    actions = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path="/home/imrui/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome", headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            response = page.goto(args.url, wait_until="networkidle")
            assert response.status == 200
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
            page.screenshot(path=str(args.out / "working-app.png"), full_page=True)
            page.get_by_role("button", name="Reset island", exact=True).click()
            expect(page.get_by_text("Your island is empty", exact=True)).to_be_visible()
            actions.append("reset cleared island")
            page.get_by_label("How are you feeling?").fill("I want to kill myself")
            page.get_by_role("button", name="Add check-in", exact=True).click()
            expect(page.locator(".mc-crisis")).to_be_visible()
            expect(page.get_by_text("Your island is empty", exact=True)).to_be_visible()
            actions.append("crisis guidance shown without an entity")
            assert not errors, errors
        finally:
            paths = ("main.jac", "components/MindcraftApp.jac", "services/island.jac", "styles.css", "jac.toml")
            (args.out / "browser.json").write_text(json.dumps({"actions": actions, "page_errors": errors,
                "url": args.url, "workspace": str(args.workspace),
                "source_sha256": {p: hashlib.sha256((args.workspace / p).read_bytes()).hexdigest() for p in paths},
                "status": "passed" if len(actions) == 5 and not errors else "failed"}, indent=2))
            browser.close()
    print(json.dumps({"actions": actions, "page_errors": errors}))

# Run =====================================================
if __name__ == "__main__":
    main()
