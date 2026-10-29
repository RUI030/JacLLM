"""Run the untouched Orbitron reference in an isolated workspace and probe routes."""

import argparse, json, shutil, subprocess, sys, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils import jac_cli

# Setting =================================================
PROJECT = Path(__file__).resolve().parents[3]
REPO = PROJECT / 'dataset/raw/repo/JacHackSpring/orbitronsystems__ori-Jac-Demo'
JAC = Path('/tmp/jac-0.34.27-linux-x86_64')
PLAYWRIGHT = Path('/home/imrui/.hermes/hermes-agent/node_modules/playwright')
CHROME = Path('/home/imrui/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome')
ROUTES = ('/', '/onboarding', '/dashboard')

# Functions ===============================================
def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def http_status(port: int, route: str = '/') -> tuple[int | None, str]:
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}{route}', timeout=3) as response:
            return response.status, response.read(2000).decode('utf-8', errors='replace')
    except urllib.error.HTTPError as error:
        return error.code, str(error)
    except Exception as error:
        return None, f'{type(error).__name__}: {error}'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=150)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    workspace = out / 'reference'
    shutil.copytree(REPO, workspace, ignore=shutil.ignore_patterns('.git', '.jac', '.jaccoder', '.jac-server.log'))
    port = jac_cli.free_port()
    write_json(out / 'setup.json', {'source': str(REPO), 'jac': str(JAC), 'port': port,
                                   'routes': ROUTES, 'workspace': str(workspace),
                                   'playwright': str(PLAYWRIGHT), 'chrome': str(CHROME)})
    reachable = False
    client_ready = False
    with ThreadPoolExecutor(max_workers=1) as pool:
        server = pool.submit(jac_cli.execute, ['start', 'main.jac', '--port', str(port), '--no-dev'],
                             timeout=args.timeout, cwd=workspace, jac=str(JAC))
        deadline = time.monotonic() + min(args.timeout - 10, 120)
        observations = []
        while time.monotonic() < deadline:
            status, detail = http_status(port)
            observations.append({'seconds': round(args.timeout - (deadline - time.monotonic()) - 10, 1),
                                 'status': status, 'detail': detail[:160]})
            if status is not None:
                reachable = True
            if status == 200:
                client_ready = True
                break
            if server.done(): break
            time.sleep(2)
        write_json(out / 'http-poll.json', {'http_reachable': reachable, 'client_ready': client_ready,
                                           'observations': observations})
        if reachable:
            browser_js = out / 'browser.cjs'
            browser_js.write_text('''const fs = require('fs');
const { chromium } = require(process.argv[2]);
(async () => {
  const browser = await chromium.launch({executablePath: process.argv[3], headless: true,
    args: ['--no-sandbox', '--disable-gpu']});
  const rows = [];
  for (const route of ['/', '/onboarding', '/dashboard']) {
    const page = await browser.newPage({viewport: {width: 1280, height: 800}});
    const errors = [];
    page.on('pageerror', error => errors.push(String(error)));
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    let status = null, navigationError = null;
    try {
      const response = await page.goto('http://127.0.0.1:' + process.argv[4] + route,
        {waitUntil: 'networkidle', timeout: 25000});
      status = response && response.status();
      await page.waitForTimeout(1500);
    } catch (error) { navigationError = String(error); }
    const text = (await page.locator('body').innerText().catch(() => '')).slice(0, 3000);
    const html = (await page.content().catch(() => '')).slice(0, 3000);
    const screenshot = 'route_' + (route === '/' ? 'root' : route.slice(1)) + '.png';
    await page.screenshot({path: process.argv[5] + '/' + screenshot}).catch(() => {});
    rows.push({route, status, url: page.url(), title: await page.title().catch(() => ''),
      body_text: text, html_prefix: html, errors, navigationError, screenshot});
    await page.close();
  }
  await browser.close();
  fs.writeFileSync(process.argv[5] + '/browser.json', JSON.stringify(rows, null, 2));
})().catch(error => { console.error(error); process.exit(1); });
''')
            probe = subprocess.run(['node', str(browser_js), str(PLAYWRIGHT), str(CHROME), str(port), str(out)],
                                   capture_output=True, text=True, timeout=90)
            write_json(out / 'playwright-process.json', {'returncode': probe.returncode,
                       'stdout': probe.stdout, 'stderr': probe.stderr})
        result = server.result()
        write_json(out / 'jac-start.json', vars(result))
    print(json.dumps({'http_reachable': reachable, 'client_ready': client_ready,
                      'jac_start_returncode': result.returncode,
                      'jac_start_timed_out': result.timed_out,
                      'browser_result': str(out / 'browser.json') if (out / 'browser.json').exists() else None}), flush=True)


# Run =====================================================
if __name__ == '__main__':
    main()
