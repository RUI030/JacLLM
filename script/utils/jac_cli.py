"""Thin wrappers around the `jac` CLI: check / run / build / start / test / py2jac."""

import os, re, shutil, signal, socket, subprocess, tempfile, time, urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

JAC             = "jac"
DEFAULT_TIMEOUT = 30
START_BOOT      = 5
HTTP_TIMEOUT    = 10
RSS_POLL        = 0.5                                   # seconds between RSS-watchdog samples
PG_DIR          = Path(os.environ.get("JAC_CACHE_HOME", "~/.cache/jac")).expanduser() / "pg" / "main"
SERVER_TOML     = '[build]\ndefault_codespace = "server"\n'   # plain functions otherwise lower to native (wrong results in 0.36.1)
TEST_LINE       = re.compile(r"^[^\s:]+\.jac::(.+?)\s+(PASSED|FAILED|ERROR)\b", re.M)
FAIL_SECTION    = re.compile(r"^_{3,} (.+?) _{3,}$")             # pytest failure-section header
WARNING_CODE    = re.compile(r"warning\[(W\d+)\]")
INFRA_ERROR     = re.compile(
    r"embedded postgres|postgres not ready|could not connect to (?:the )?database|"
    r"connection to server.*failed|initdb|database system is starting up|"
    r"No space left on device|too many clients already",
    re.I,
)


@dataclass
class JacResult:
    returncode: int | None
    stdout: str
    stderr: str
    ms: float
    timed_out: bool = False
    mem_capped: bool = False
    launch_error: str | None = None

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def infra_error(self) -> bool:
        """Grader-side failure (launch, postgres), not something the code under test did."""
        return self.launch_error is not None or bool(INFRA_ERROR.search(self.stdout + self.stderr))

    def text(self) -> str:
        return (self.stderr or self.stdout).strip()


@contextmanager
def jac_tempfile(source: str, suffix: str = ".jac"):
    """Write source to a temporary file (.jac unless `suffix` says otherwise); unlink on exit."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    ) as fp:
        fp.write(source)
        path = Path(fp.name)
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)


@contextmanager
def jac_workspace(files: dict[str, str]):
    """Write {relpath: text} into a temp dir and yield it; remove the dir on exit."""
    root = Path(tempfile.mkdtemp(prefix="jacws_"))
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


_SCOPES_OK: bool | None = None


def scopes_available() -> bool:
    """True iff `systemd-run --user --scope` works here (probed once; containers lack a user bus)."""
    global _SCOPES_OK
    if _SCOPES_OK is None:
        exe = shutil.which("systemd-run")
        _SCOPES_OK = bool(exe) and subprocess.run(
            [exe, "--user", "--scope", "--quiet", "--collect", "true"],
            capture_output=True, timeout=15,
        ).returncode == 0
    return _SCOPES_OK


def group_rss_bytes(pgid: int) -> int:
    """Resident memory summed over every live process in process group `pgid`."""
    page, total = os.sysconf("SC_PAGE_SIZE"), 0
    for entry in os.scandir("/proc"):
        if not entry.name.isdigit():
            continue
        try:
            with open(f"/proc/{entry.name}/stat") as f:
                fields = f.read().rsplit(")", 1)[1].split()
            if int(fields[2]) != pgid:            # after comm: state ppid pgrp ...
                continue
            with open(f"/proc/{entry.name}/statm") as f:
                total += int(f.read().split()[1]) * page
        except (OSError, IndexError, ValueError):
            continue                               # process exited mid-scan
    return total


def execute(
    args: list[str],
    timeout: float = DEFAULT_TIMEOUT,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    mem_limit_bytes: int | None = None,
    merge_stderr: bool = False,
) -> JacResult:
    """Run `jac <args>` in its own process group, with a timeout and an optional memory cap.

    On timeout the whole group is SIGKILLed, so children spawned by the code under
    test die too. The memory cap is a per-call cgroup (`systemd-run --user --scope`,
    MemoryMax, no swap) when scopes work, else an RSS watchdog on the group.
    RLIMIT_AS is not used: jac reserves enough virtual memory that a 12GB cap fails
    thread creation on correct code. jac's embedded postgres daemonizes out of the
    group and is not counted; start it outside any cap (`start_pg`) so an OOM kill
    of one scope cannot take it down. `merge_stderr` interleaves stderr into stdout
    as a terminal shows it (`2>&1`); `stderr` is then empty.
    """
    cmd, rss_cap = [JAC, *args], None
    if mem_limit_bytes and scopes_available():
        cmd = ["systemd-run", "--user", "--scope", "--quiet", "--collect",
               "-p", f"MemoryMax={mem_limit_bytes}", "-p", "MemorySwapMax=0",
               "-p", "OOMPolicy=kill", *cmd]
    elif mem_limit_bytes:
        rss_cap = mem_limit_bytes
    full_env = {**os.environ, **(env or {})}
    start = time.perf_counter()
    elapsed = lambda: (time.perf_counter() - start) * 1000
    try:
        proc = subprocess.Popen(
            cmd, cwd=cwd, env=full_env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT if merge_stderr else subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as exc:
        return JacResult(None, "", "", elapsed(), launch_error=str(exc))

    deadline = start + timeout
    while True:
        try:
            out, err = proc.communicate(timeout=RSS_POLL if rss_cap else max(deadline - time.perf_counter(), 0.01))
            break
        except subprocess.TimeoutExpired:
            over = rss_cap is not None and group_rss_bytes(proc.pid) > rss_cap
            if over or time.perf_counter() >= deadline:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                out, err = proc.communicate()
                return JacResult(proc.returncode, out, err or "", elapsed(), timed_out=not over, mem_capped=over)
    # A cgroup OOM kill surfaces as SIGKILL on the scope's main process.
    return JacResult(proc.returncode, out, err or "", elapsed(),
                     mem_capped=bool(mem_limit_bytes) and proc.returncode == -signal.SIGKILL)


def invoke(args, timeout: int = DEFAULT_TIMEOUT, cwd: str | None = None) -> tuple[bool, str]:
    """Run `jac <args>`; return (ok, stderr_or_stdout). ok iff exit code 0."""
    res = execute(args, timeout, cwd)
    if res.timed_out:
        return False, "timeout"
    return res.ok, res.text()


def check(source: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[bool, str]:
    """Static type check via `jac check`."""
    with jac_tempfile(source) as p:
        return invoke(["check", str(p)], timeout)


def check_warnings(source: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[bool, list[str]]:
    """`jac check` in a server-codespace workspace; return (no errors, warning codes in order)."""
    with jac_workspace({"main.jac": source, "jac.toml": SERVER_TOML}) as ws:
        res = execute(["check", "main.jac"], timeout, ws)
    return res.ok and not res.timed_out, WARNING_CODE.findall(res.stdout + res.stderr)


def py2jac(source: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[bool, str]:
    """Python source -> Jac via `jac tool py2jac`; return (ok, jac source or error text)."""
    with jac_tempfile(source, ".py") as p:
        res = execute(["tool", "py2jac", str(p)], timeout)
    if res.timed_out:
        return False, "timeout"
    return res.ok and bool(res.stdout.strip()), res.stdout if res.ok else res.text()


def check_path(path: str | Path, cwd: str | Path | None = None,
               timeout: int = DEFAULT_TIMEOUT) -> tuple[bool, str]:
    """`jac check` on a file that already sits in a workspace."""
    return invoke(["check", str(path)], timeout, cwd)


def test(
    path: str | Path,
    cwd: str | Path | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    mem_limit_bytes: int | None = None,
) -> tuple[JacResult, dict[str, bool]]:
    """`jac test <path> -v` serially; return the raw result and {test name: passed}.

    JAC_TEST_JOBS=0: the default xdist fan-out starts one worker per core (slower
    and GBs of RAM per call). Names come from the per-test `-v` lines
    (`tests.jac::<name> PASSED|FAILED|ERROR`); a file-level `ERROR tests.jac - ...`
    gives no verdict, so the name is simply missing from the dict.
    """
    res = execute(["test", str(path), "-v"], timeout, cwd,
                  env={"JAC_TEST_JOBS": "0"}, mem_limit_bytes=mem_limit_bytes)
    return res, {name: verdict == "PASSED" for name, verdict in TEST_LINE.findall(res.stdout)}


def failure_messages(stdout: str) -> dict[str, str]:
    """{test name: first `E   ` line of its failure section} from `jac test -v` output.

    e.g. "AssertionError: expected=1 actual=3" when the test's assert carries a
    message, or "IndexError: list index out of range" when the code crashed.
    """
    out, name = {}, None
    for line in stdout.splitlines():
        m = FAIL_SECTION.match(line)
        if m:
            name = m.group(1)
        elif name and line.startswith("E ") and name not in out:
            out[name] = line[1:].strip()
        elif line.startswith("=") and "short test summary" in line:
            break
    return out


def pg_size_bytes() -> int:
    """Disk used by jac's embedded-postgres data dir."""
    return sum(f.stat().st_size for f in PG_DIR.rglob("*") if f.is_file()) if PG_DIR.exists() else 0


def purge_pg(wait: float = 20) -> None:
    """Stop jac's embedded postgres and wipe its data dir; the next `jac` call re-inits it.

    `jac test` creates about one database per test block on every run and never
    drops them (~8MB each, plus WAL; it once reached 1.1TB). Call only while no
    `jac` process is running. Fast shutdown is SIGINT to the postmaster.
    """
    pid_file = PG_DIR / "postmaster.pid"
    if pid_file.is_file():
        try:
            pid = int(pid_file.read_text().splitlines()[0])
            os.kill(pid, signal.SIGINT)
            for _ in range(int(wait / 0.25)):
                os.kill(pid, 0)
                time.sleep(0.25)
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, ValueError, IndexError):
            pass                                   # already gone, or a stale pid file
    shutil.rmtree(PG_DIR, ignore_errors=True)


def start_pg() -> None:
    """Start the embedded postgres from this process (no cap) with a trivial `jac test`."""
    files = {"jac.toml": SERVER_TOML, "t.jac": 'test "up" { assert True; }\n'}
    with jac_workspace(files) as ws:
        execute(["test", "t.jac"], 120, ws, env={"JAC_TEST_JOBS": "0"})


def run(source: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[bool, str]:
    """Execute via `jac run`."""
    with jac_tempfile(source) as p:
        return invoke(["run", str(p)], timeout)


def build(source: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[bool, str]:
    """Compile via `jac build`."""
    with jac_tempfile(source) as p:
        return invoke(["build", str(p)], timeout)


def free_port() -> int:
    """Ask the OS for an unused TCP port."""
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def start_http_check(
    source: str,
    path: str = "/",
    boot: float = START_BOOT,
    timeout: float = HTTP_TIMEOUT,
) -> tuple[bool, str]:
    """Spin up `jac start`, hit `path`, return (ok, detail)."""
    with jac_tempfile(source) as p:
        port = free_port()
        proc = subprocess.Popen(
            [JAC, "start", str(p), "--port", str(port)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            time.sleep(boot)
            try:
                url = f"http://127.0.0.1:{port}{path}"
                with urllib.request.urlopen(url, timeout=timeout) as resp:
                    return resp.status == 200, f"status={resp.status}"
            except Exception as exc:
                return False, f"{type(exc).__name__}: {exc}"
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
