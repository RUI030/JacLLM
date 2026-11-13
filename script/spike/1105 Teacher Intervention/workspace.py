"""The student's tools (read_file, write_code, edit_code, delete_code, run_command, and the lookups list_files,
grep_search, find_symbol, analyze_project) on a real directory shown as /workspace.

Results mimic JacCoder's wording (jacBuilder jac_coder/tool/read/filesystem.impl.jac) so they look like the
training trajectories. Every call returns an Outcome: the text the student sees, and whether it failed and why
(the detector's input). run_command takes an allowlist of programs; `jac` goes through utils/jac_cli.py.
"""

import re, shlex, subprocess, sys
from dataclasses import dataclass
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils import jac_cli

from spike_utils import SPIKE, WS

# Setting =================================================
PROGRAMS     = {"jac", "ls", "cat", "pwd", "find", "wc", "mkdir", "echo", "head", "tail", "grep", "tree", "true"}
JAC_SUBCMDS  = {"check", "test", "run", "build", "format", "fmt", "lint", "--version", "guide", "clean", "dot",
                "install", "add", "remove", "retheme"}   # as in prod: shadcn installs (`jac install --shadcn x`) and theming
SERVERS      = {"start", "serve"}              # never return; the harness has no preview
NO_SERVER    = "There is no server or browser here: verify behavior with test blocks and `jac test`."
MAX_OUTPUT   = 12000                           # chars of command output kept (tail)
CMD_TIMEOUT  = 180
MEM_LIMIT    = 4 * 1024 ** 3
SKIP_DIRS    = {".jac", "node_modules", "__pycache__", ".git"}   # build caches, not the student's sources
ERROR_LINE   = re.compile(r"error\[(E\d+)\]:\s*(.+?)\n\s*-->\s*([^\s:]+):(\d+):(\d+)")
HOME         = str(Path.home())
RUNTIME      = re.compile(re.escape(HOME) + r"/\.cache/jac/rt/[0-9a-f-]+")    # jac's bundled Python, in tracebacks
CUT_PATH     = re.compile(r"(/[^\s'\"]*?)\.\.\.")                         # a path pytest truncated with "..."
LOOKUP       = SPIKE / "lookup.jac"            # find_symbol / analyze_project on jaclang's CodeIntelligence
MAX_LISTED   = 200                             # entries per listing, as in JacCoder
SCRATCH      = re.compile(r"^(?:tmp|temp|scratch|debug)(?:[_\-.\d]|$)", re.I)   # one-off probe files, e.g. tmp_check.jac


@dataclass
class Outcome:
    text: str                  # tool result shown to the student
    failed: bool = False
    kind: str = ""             # failure class, e.g. jac_errors, not_found, refused, command_failed
    key: str = ""              # where it failed (file or command); same kind + key = "the same place"


# Functions ===============================================
def scrub(text: str, root: Path) -> str:
    """Host paths -> what the student sees: the workspace as /workspace, jac's runtime as <jac-runtime>, home as ~."""
    text = text.replace(str(root), WS)
    cut = lambda m: len(m.group(1)) > 1 and (str(root).startswith(m.group(1)) or HOME.startswith(m.group(1)))
    text = CUT_PATH.sub(lambda m: WS + "/..." if cut(m)
                        else m.group(0), text)
    return RUNTIME.sub("<jac-runtime>", text).replace(HOME, "~")


class Workspace:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def real(self, path: str) -> Path | None:
        """Student path (absolute under /workspace, or relative to it) -> real path, None if it escapes."""
        rel = path[len(WS):].lstrip("/") if path == WS or path.startswith(WS + "/") else (None if path.startswith("/") else path)
        if rel is None:
            return None
        p = (self.root / rel).resolve()
        return p if p == self.root or self.root in p.parents else None

    def shown(self, text: str) -> str:
        return scrub(text, self.root)

    def dispatch(self, name: str, args: dict) -> Outcome:
        fn = {"read_file": self.read_file, "write_code": self.write_code, "edit_code": self.edit_code,
              "delete_code": self.delete_code, "run_command": self.run_command, "list_files": self.list_files,
              "grep_search": self.grep_search, "find_symbol": self.find_symbol,
              "analyze_project": self.analyze_project}.get(name)
        if fn is None:
            return Outcome(f"Error: unknown tool {name}", True, "bad_call", name)
        try:
            out = fn(**args)
            out.text = self.shown(out.text)            # every result, including jac check output after a write
            return out
        except TypeError as ex:                    # missing or unexpected arguments
            return Outcome(f"Error: invalid arguments for {name}: {ex}", True, "bad_call", name)

    def read_file(self, file_path: str, offset: int = 0, limit: int = 2000) -> Outcome:
        p = self.real(file_path)
        if p is None:
            return Outcome(f"Error: {file_path} is outside {WS}", True, "outside_workspace", file_path)
        if not p.is_file():
            return Outcome(f"Error: file not found: {file_path}", True, "not_found", file_path)
        lines = p.read_text(errors="replace").splitlines()
        start = max(int(offset), 0)
        body = "\n".join(f"{i + 1}: {l}" for i, l in enumerate(lines[start:start + int(limit)], start))
        return Outcome(body or "(empty file)")

    # Lookups: JacCoder's wording (filesystem.impl.jac list_files, search.impl.jac grep_search, jac_analyzer.impl.jac);
    # a lookup never fails a turn except on a bad path, since "not found" is an answer.
    def directory(self, directory: str) -> tuple[Path | None, Outcome | None]:
        d = self.real(directory or WS)
        if d is None:
            return None, Outcome(f"Error: {directory} is outside {WS}", True, "outside_workspace", directory)
        if not d.is_dir():
            return None, Outcome(f"Error: Directory not found: {directory}", True, "not_found", directory)
        return d, None

    def visible(self, p: Path) -> bool:
        return not SKIP_DIRS & set(p.relative_to(self.root).parts)

    def list_files(self, directory: str = WS, pattern: str = "**/*") -> Outcome:
        d, err = self.directory(directory)
        if err:
            return err
        try:
            entries = sorted(str(f) + ("/" if f.is_dir() else "") for f in d.glob(pattern or "**/*")
                             if (f.is_file() or f.is_dir()) and self.visible(f))
        except (ValueError, NotImplementedError) as ex:
            return Outcome(f"Error: {ex}", True, "bad_call", directory)
        if not entries:
            return Outcome(f"Nothing matching '{pattern}' in {directory} (directory is empty)")
        more = f"\n\n... and {len(entries) - MAX_LISTED} more ({len(entries)} total)" if len(entries) > MAX_LISTED else ""
        return Outcome("\n".join(entries[:MAX_LISTED]) + more)

    def grep_search(self, pattern: str, path: str = WS, file_pattern: str = "", max_results: int = 50) -> Outcome:
        if not pattern:
            return Outcome("Error: pattern is required", True, "bad_call", "grep_search")
        p = self.real(path or WS)
        if p is None:
            return Outcome(f"Error: {path} is outside {WS}", True, "outside_workspace", path)
        if not p.exists():
            return Outcome(f"Error: Path not found: {path}", True, "not_found", path)
        cmd = ["grep", "-rn", "-E", "--color=never", *(f"--exclude-dir={x}" for x in sorted(SKIP_DIRS))]
        cmd += ["--include", file_pattern] if file_pattern else []
        try:
            r = subprocess.run(cmd + ["-m", str(int(max_results or 50)), pattern, str(p)], stdin=subprocess.DEVNULL,
                               capture_output=True, text=True, timeout=15)
        except subprocess.TimeoutExpired:
            return Outcome("Error: Search timed out after 15 seconds", True, "command_failed", "grep_search")
        out = r.stdout.strip()
        return Outcome(out[:MAX_OUTPUT] if out else f"No matches for '{pattern}' in {path}")

    def lookup(self, args: list[str]) -> str:
        res = self.jac(["run", str(LOOKUP), *args], timeout=120)
        lines = [l for l in res.stdout.splitlines() if not l.startswith("WARNING - postgres")]
        return "\n".join(lines).strip()[:MAX_OUTPUT] or "Analysis failed: no output"

    def find_symbol(self, name: str, directory: str = WS) -> Outcome:
        if not name:
            return Outcome("Error: symbol name is required.", True, "bad_call", "find_symbol")
        d, err = self.directory(directory)
        if err:
            return Outcome(f"Error: valid directory is required (got: '{directory}').", True, err.kind, directory)
        return Outcome(self.lookup(["symbol", name, str(d)]))

    def analyze_project(self, directory: str = WS) -> Outcome:
        d, err = self.directory(directory)
        return err or Outcome(self.lookup(["analyze", str(d)]))

    def jac(self, args: list[str], timeout: int, cwd: Path | None = None) -> jac_cli.JacResult:
        """Every jac call: the project's jac.toml keeps `[build] default_codespace = "server"` (CLAUDE.md: without it
        jac 0.36.1 lowers plain functions to native and returns wrong values), added if the student's file lacks it."""
        p = self.root / "jac.toml"
        text = p.read_text(errors="replace") if p.is_file() else ""
        if not re.search(r"(?m)^\s*default_codespace\s*=", text):
            if re.search(r"(?m)^\[build\]\s*$", text):
                text = re.sub(r"(?m)^\[build\]\s*$", '[build]\ndefault_codespace = "server"', text, count=1)
            else:
                text = text.rstrip() + ("\n\n" if text.strip() else "") + jac_cli.SERVER_TOML
            p.write_text(text)
        return jac_cli.execute(args, timeout=timeout, cwd=cwd or self.root, mem_limit_bytes=MEM_LIMIT, merge_stderr=True)

    def jac_errors(self, p: Path) -> list[tuple[str, str]]:
        """(heading, line) per hard error of `jac check` on one file; warnings are not shown, as in JacCoder."""
        res = self.jac(["check", str(p.relative_to(self.root))], timeout=120)
        if res.ok:
            return []
        out = res.stdout
        errs = [("SYNTAX ERRORS" if code.startswith("E0") else "TYPE ERRORS", f"{f}:{ln}:{col} - {code} {msg.strip()}")
                for code, msg, f, ln, col in ERROR_LINE.findall(out)]
        return errs or [("OTHER ERRORS", self.shown(out.strip())[-1500:] or "jac check failed")]

    def checked(self, p: Path, msg: str, file_path: str) -> Outcome:
        if p.suffix != ".jac":
            return Outcome(msg)
        errs = self.jac_errors(p)
        if not errs:
            return Outcome(msg)
        for heading in ("SYNTAX ERRORS", "TYPE ERRORS", "OTHER ERRORS"):
            shown = [l for h, l in errs if h == heading][:10]
            if shown:
                msg += f"\n\n{heading}:\n" + "\n".join(shown)
        return Outcome(msg + "\nFix errors before continuing.", True, "jac_errors", file_path)

    def write_code(self, file_path: str, content: str) -> Outcome:
        p = self.real(file_path)
        if p is None:
            return Outcome(f"Error: {file_path} is outside {WS}", True, "outside_workspace", file_path)
        if p.suffix != ".md" and "```" in content:     # project rule: files hold only their code, no Markdown fence
            return Outcome(f"Error: the content for {p.name} contains a Markdown ``` fence. Write only the file's "
                           "code, without fences.", True, "fence_in_file", file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return self.checked(p, f"OK: {p.name} ({len(content.splitlines())} lines)", file_path)

    def edit_code(self, file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> Outcome:
        p = self.real(file_path)
        if p is None:
            return Outcome(f"Error: {file_path} is outside {WS}", True, "outside_workspace", file_path)
        if not p.is_file():
            return Outcome(f"Error: file not found: {file_path}", True, "not_found", file_path)
        if p.suffix != ".md" and "```" in new_string:
            return Outcome(f"Error: new_string for {p.name} contains a Markdown ``` fence. Write only code.",
                           True, "fence_in_file", file_path)
        if not old_string:                          # both as in JacCoder's edit_file (filesystem.impl.jac)
            return Outcome("Error: old_string is required", True, "bad_call", file_path)
        if old_string == new_string:
            return Outcome("Error: old_string and new_string must be different", True, "noop_edit", file_path)
        content = p.read_text()
        count = content.count(old_string)
        if count == 0:
            return Outcome("Error: old_string not found in file. Make sure it matches exactly (including "
                           "whitespace/indentation).", True, "edit_mismatch", file_path)
        if count > 1 and not replace_all:
            return Outcome(f"Error: old_string found {count} times. Use replace_all=true or provide more context to "
                           "make the match unique.", True, "edit_mismatch", file_path)
        p.write_text(content.replace(old_string, new_string) if replace_all else content.replace(old_string, new_string, 1))
        n = count if replace_all else 1
        return self.checked(p, f"OK: {p.name} ({n} edit{'s' if n > 1 else ''})", file_path)

    def delete_code(self, file_path: str) -> Outcome:
        """JacCoder's delete_file wording (jac_coder/tool/read/filesystem.impl.jac)."""
        p = self.real(file_path)
        if p is None:
            return Outcome(f"Error: {file_path} is outside {WS}", True, "outside_workspace", file_path)
        if not p.exists():
            return Outcome(f"File does not exist: {file_path} (already deleted or never existed)", False, "", file_path)
        if not p.is_file():
            return Outcome(f"Error: {file_path} is not a file (cannot delete directories with this tool)", True,
                           "bad_call", file_path)
        p.unlink()
        return Outcome(f"OK: Deleted {p.name}")

    def run_command(self, command: str, workdir: str = WS, timeout: int = CMD_TIMEOUT, background: bool = False) -> Outcome:
        cwd = self.real(workdir)
        if cwd is None:
            return Outcome(f"Error: workdir {workdir} is outside {WS}", True, "outside_workspace", workdir)
        if background:
            return Outcome("Error: background processes are not available in this environment. " + NO_SERVER, True,
                           "refused", command)
        command = re.sub(r"\s*2>&1", "", command)   # stderr is always merged into the output
        try:
            lex = shlex.shlex(command.replace(WS, str(self.root)), posix=True, punctuation_chars=True)
            lex.whitespace_split = True
            tokens = list(lex)
        except ValueError as ex:
            return Outcome(f"Error: cannot parse command: {ex}", True, "refused", command)
        # [(op_before, argv, pipe_filters)]: segments joined by && / ; ; each may pipe into head/tail/grep/wc
        segments, cur, op = [], [], ""
        for t in tokens + [";"]:
            if t in ("&&", ";", "||"):
                if cur:
                    segments.append((op, cur))
                cur, op = [], t
            elif t in ("&", ">", ">>", "<", "|&", "(", ")"):
                return Outcome(f"Error: '{t}' is not allowed; run one plain command (pipes into head/tail/grep/wc are fine)."
                               + (" " + NO_SERVER if t == "&" else ""), True, "refused", command)
            else:
                cur.append(t)
        out, code = [], 0
        for op, seg in segments:
            if (op == "&&" and code != 0) or (op == "||" and code == 0):
                continue
            pipes = [[]]
            for t in seg:
                pipes.append([]) if t == "|" else pipes[-1].append(t)
            refusal = self.refused(pipes)
            if refusal:
                return Outcome(refusal, True, "refused", command)
            text, code = self.run_argv(pipes[0], cwd, min(int(timeout or CMD_TIMEOUT), CMD_TIMEOUT))
            for flt in pipes[1:]:
                text = self.filter(flt, text)
            out.append(text)
        text = self.shown("\n".join(out))[-MAX_OUTPUT:]
        last = segments[-1][1]
        key = " ".join(last[:2] if last[0] == "jac" else last[:3])   # `jac test a.jac` and `jac test b.jac` = one place
        return Outcome(text or "(no output)", code != 0, "command_failed" if code else "", key)

    def refused(self, pipes: list[list[str]]) -> str:
        argv = pipes[0]
        if not argv or argv[0] not in PROGRAMS:
            return (f"Error: '{argv[0] if argv else ''}' is not available in this environment. Allowed: "
                    + ", ".join(sorted(PROGRAMS)) + ". There is no network access.")
        if argv[0] == "jac" and len(argv) > 1 and argv[1] in SERVERS:
            return "Error: long-running servers are not available here. " + NO_SERVER
        if argv[0] == "jac" and (len(argv) < 2 or argv[1] not in JAC_SUBCMDS):
            return "Error: unsupported jac subcommand; use check, test, run, build, format, lint, install, add, remove or retheme."
        for flt in pipes[1:]:
            if not flt or flt[0] not in ("head", "tail", "grep", "wc"):
                return "Error: only head, tail, grep and wc can follow a pipe."
        return ""

    def run_argv(self, argv: list[str], cwd: Path, timeout: int) -> tuple[str, int]:
        if argv[0] == "jac":
            res = self.jac(argv[1:], timeout, cwd)
            if res.timed_out:
                return res.stdout + f"\n[timed out after {timeout}s]", 124
            return res.stdout, res.returncode if res.returncode is not None else 1
        for a in argv[1:]:                         # program arguments that are paths must stay inside the workspace
            if a.startswith("/") and self.real(self.shown(a)) is None:
                return f"Error: {self.shown(a)} is outside {WS}", 1
        r = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.stdout + r.stderr, r.returncode

    def filter(self, argv: list[str], text: str) -> str:
        lines = text.splitlines()
        n = next((int(a.lstrip("-n")) for a in argv[1:] if a.lstrip("-n").isdigit()), 10)
        if argv[0] == "head":
            return "\n".join(lines[:n])
        if argv[0] == "tail":
            return "\n".join(lines[-n:])
        if argv[0] == "wc":
            return str(len(lines))
        pats = [a for a in argv[1:] if not a.startswith("-")]
        return "\n".join(l for l in lines if pats and re.search(pats[0], l)) if pats else text

    def jac_files(self) -> list[Path]:
        return sorted(p for p in self.root.rglob("*.jac") if p.is_file() and not SKIP_DIRS & set(p.relative_to(self.root).parts[:-1]))

    def scratch_files(self) -> list[Path]:
        """One-off probe files the student wrote to try something (tmp_check.jac, debug.py, anything in scratch/).
        Checks that should stay belong in test blocks; these must be deleted before the task is done."""
        return sorted(p for p in self.root.rglob("*") if p.is_file()
                      and not SKIP_DIRS & set(rel := p.relative_to(self.root).parts)
                      and (SCRATCH.match(p.name) or "scratch" in rel[:-1]))

    def test_targets(self) -> list[Path]:
        """What `jac test` runs to cover every `test` block (jac-testing skill): a module with in-file test blocks
        itself, and for a `<mod>.test.jac` annex its base `<mod>.jac` (an annex is not a standalone module)."""
        targets = []
        for p in self.jac_files():
            if p.name.endswith(".impl.jac") or not re.search(r'(?m)^\s*test\s+["\']', p.read_text(errors="replace")):
                continue
            base = p.with_name(p.name.removesuffix(".test.jac") + ".jac") if p.name.endswith(".test.jac") else p
            targets.append(base if base.is_file() else p)
        return sorted(set(targets))

    def acceptance(self) -> tuple[bool, str]:
        """Harness check before accepting "done": no scratch files are left, every .jac file passes `jac check`, and
        `jac test` passes on every module that has test blocks (in the module or in its `.test.jac` annex)."""
        files = self.jac_files()
        if not files:
            return False, "No .jac files exist yet."
        left = [self.shown(str(p)) for p in self.scratch_files()]
        problems = ([f"Scratch files are still in the workspace: {', '.join(left)}. Delete each with delete_code; a "
                     "check worth keeping goes into a test block (in the module or its `.test.jac` annex) instead."]
                    if left else [])
        problems += [f"{p.relative_to(self.root)}: " + "; ".join(l for _, l in errs[:3])
                    for p in files if (errs := self.jac_errors(p))]
        tests = self.test_targets()
        for t in tests:
            res = self.jac(["test", str(t.relative_to(self.root))], CMD_TIMEOUT)
            if not res.ok:
                problems.append(f"jac test {t.relative_to(self.root)} failed\n" + self.shown(res.stdout)[-1500:])
        if not tests:
            problems.append("No Jac `test` block covers the acceptance criteria. Add test blocks to a module, or to a "
                            "`<module>.test.jac` annex next to it, and run `jac test <module>.jac`.")
        return not problems, "\n".join(problems)
