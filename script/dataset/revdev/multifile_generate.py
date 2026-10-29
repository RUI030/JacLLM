"""Generate and replay real JacCoder trajectories over genuine multifile repos."""

import argparse, hashlib, json, re, shutil, subprocess, sys
from pathlib import Path

import jsonschema

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils import jac_cli
from dataset.revdev.checkpoint import save, restore, workspace_files
from dataset.revdev.claude_adapter import DECISION_SCHEMA, execute_tool, validate_call, write_json
from dataset.revdev.export import event_rows
from dataset.trajectory.common import to_template_input
from dataset.pipeline import split_and_write
from dataset.statistics import generate_report

# Setting =================================================
PROJECT = Path(__file__).resolve().parents[3]
ROOT = PROJECT / 'dataset/raw/revdev/multifile_v1'
CAPTURE = PROJECT / 'dataset/raw/revdev/Mindcraft/m3/private/teacher_prompt_v1'
HARNESS = PROJECT.parent / 'jacBuilder'
JAC = Path('/tmp/jac-0.34.27-linux-x86_64')
SOURCES = {
    'a2pulse_editor': {
        'repo': PROJECT / 'dataset/raw/repo/JacHackA2Tech/A2Tech360__A2-Pulse',
        'targets': ['services/brief_dates.jac', 'services/brief_editor.jac'],
        'inspect': ['services/brief_dates.test.jac', 'services/brief_editor.test.jac'],
        'dependencies': ['services/speakable.jac', 'services/brief_narrative.jac', 'services/pulse_llm.jac'],
        'command': 'jac test services/brief_editor.jac', 'pass_marker': '23 passed',
        'extra_tests': [('services/brief_dates.jac', '4 passed')],
        'request': 'Complete A2-Pulse’s weekly brief date helpers and editor service. The editor turns ranked local items into a spoken brief, using an optional LLM and a deterministic template fallback. Week labels must use the correct Monday, and all final text must be speakable. Keep the public interfaces compatible with the existing services and satisfy the repository’s original tests without editing them.',
        'plan': 'Read the existing brief_dates and brief_editor tests. First implement services/brief_dates.jac with brief_monday, brief_day_index, and brief_week_label. Before implementing services/brief_editor.jac, read the completed date helper and its existing dependencies speakable.jac, brief_narrative.jac, and pulse_llm.jac. Preserve editor exports repeated_reason, strongest_first, template_brief, editor_items_text, edit_brief, and the LLM prompt interface. Verify jac test services/brief_editor.jac; it discovers both dates and editor tests.',
        'split': 'valid', 'validation_level': 'behavior_tested',
    },
    'a2pulse_speech': {
        'repo': PROJECT / 'dataset/raw/repo/JacHackA2Tech/A2Tech360__A2-Pulse',
        'targets': ['services/speakable.jac', 'services/brief_narrative.jac'],
        'inspect': ['services/speakable.test.jac', 'services/brief_narrative.test.jac'],
        'command': 'jac test services/brief_narrative.jac', 'pass_marker': '28 passed',
        'extra_tests': [('services/speakable.jac', '21 passed')],
        'request': 'Implement A2-Pulse’s spoken brief pipeline in the existing service package. Convert raw event text into clean text-to-speech wording, then compose a natural weekly narrative from ranked items. Preserve the public speakable/word_count and narrative_brief/natural_when interfaces. Keep the existing tests and seed data unchanged.',
        'plan': 'Read both existing service tests. First create services/speakable.jac with speakable(text, ref) and word_count(text) plus the text normalization helpers needed by the tests. Then read that completed file and create services/brief_narrative.jac, importing speakable and word_count; expose narrative_brief and natural_when and preserve grouping, spoken times, reasons, prices and word-count behavior. Verify jac test services/brief_narrative.jac, which discovers both service test modules.',
        'split': 'valid', 'validation_level': 'behavior_tested',
    },
    'ghostboard': {
        'repo': PROJECT / 'dataset/raw/repo/JacHackSpring/NIKHILJAISWAL123__GhostBoard',
        'targets': ['models.jac', 'server.jac'],
        'inspect': ['client.jac', 'main.jac'],
        'command': 'jac check server.jac', 'pass_marker': '1 passed',
        'request': 'Complete the shared graph models and server API for the existing GhostBoard application. The client imports the model types and server functions. Define the executive, metrics, crisis, and report data structures, then implement the server functions and walkers that use them. Keep the interfaces compatible with client.jac.',
        'plan': 'Read client.jac and main.jac to identify the imported interfaces. Create models.jac first with ExecutiveStatus, Severity, Executive, SystemMetrics, Crisis, IntelligenceReport, and graph edges. Create server.jac second; import those models and expose the public APIs get_executives, get_system_metrics, and trigger_orchestration, plus the orchestration and sync walkers and graph initialization. Verify jac check server.jac.',
        'split': 'train', 'validation_level': 'compile_only',
    },
    'orbitron': {
        'repo': PROJECT / 'dataset/raw/repo/JacHackSpring/orbitronsystems__ori-Jac-Demo',
        'targets': ['pages/WelcomePage.jac', 'index.jac'],
        'inspect': ['main.jac', 'pages/OnboardingPage.jac'],
        'command': 'jac check main.jac', 'pass_marker': '1 passed',
        'request': 'Complete the Orbitron ERP welcome route in the existing application. Add a welcome page that introduces the fleet dashboard and links to onboarding. Wire it through the existing router while preserving the /onboarding and /dashboard routes. Keep the public page and ClientApp signatures compatible with existing imports.',
        'plan': 'Create pages/WelcomePage.jac exporting page() -> JsxElement, then index.jac exporting ClientApp() -> JsxElement. Inspect main.jac and the existing pages first. The router must import the new welcome page and existing onboarding/dashboard pages. Verify jac check main.jac.',
        'split': 'train', 'validation_level': 'compile_only',
    },
    'a2pulse_dates': {
        'repo': PROJECT / 'dataset/raw/repo/JacHackA2Tech/A2Tech360__A2-Pulse',
        'targets': ['services/brief_dates.jac'],
        'inspect': ['services/brief_dates.test.jac'],
        'command': 'jac test services/brief_dates.jac', 'pass_marker': '4 passed',
        'request': 'Implement the shared brief-week date helpers in services/brief_dates.jac for the existing A2-Pulse application. Weekdays use the current Monday, weekends use the upcoming Monday. Day indices are relative to that Monday and the spoken week label names it. Preserve the public signatures and satisfy the existing tests without editing them.',
        'plan': 'Read services/brief_dates.test.jac, then create services/brief_dates.jac with brief_monday, brief_day_index and brief_week_label. Inspect the tests before writing. Verify jac test services/brief_dates.jac.',
        'split': 'valid', 'validation_level': 'behavior_tested',
    },
}
RULES = '''This is a scoped existing Jac repo. You may write only the target paths named in the user payload.
Read the saved .jaccoder/build_plan.json and the listed existing files before writing.
Use read_file offset=0 for the first line. Reuse unchanged reads; do not invent source contents.
Create every target file in dependency order. Keep any existing tests unchanged.
For a dependent target, read its newly written dependency and existing imported modules before writing it.
The pinned Jac version is 0.34.27. run_command allows only bounded jac check/test/build/run,
ls -la, pwd, and cat of one local file. Use the exact verification command in the plan.
A write/edit checks syntax; inspect the real result, fix errors, then run the verification command.
All paths and commands stay in the workspace; no network, packages, secrets or background jobs.
The visible plan is complete; plan_build and skill tools are unavailable in this adapter.
'''
TRANSPORT = '''\nReturn exactly one JSON object per turn: {"kind":"tool" or "final","name":tool name or "",
"args":tool arguments or {},"summary":short observable progress}. No markdown. Built-in tools are
unavailable. Only supplied schemas can be called. The next turn supplies the actual tool result.\n'''
STUDENT = '# JacCoder: JacHammer Application Builder\nCall the supplied tools directly.\n' + RULES

# Functions ===============================================
def load_recipe(path: Path) -> str:
    """Register one reviewable repository task without changing generator code."""
    spec = json.loads(path.read_text())
    required = {'name', 'repo', 'targets', 'inspect', 'command', 'pass_marker',
                'request', 'plan', 'split', 'validation_level', 'source_globs'}
    missing = required - spec.keys()
    if missing:
        raise ValueError(f'Missing task fields: {sorted(missing)}')
    name = spec.pop('name')
    if not isinstance(name, str) or not name.replace('_', '').isalnum() or name in SOURCES:
        raise ValueError('Task name must be new and alphanumeric with underscores.')
    repo = (PROJECT / spec['repo']).resolve()
    raw_root = (PROJECT / 'dataset/raw/repo').resolve()
    if not repo.is_relative_to(raw_root) or not repo.is_dir():
        raise ValueError('Task repo must be an existing raw/repo directory.')
    for key in ('targets', 'inspect', 'dependencies'):
        if not isinstance(spec.get(key, []), list):
            raise ValueError(f'{key} must be a list.')
        for item in spec.get(key, []):
            if not isinstance(item, str) or Path(item).is_absolute() or '..' in Path(item).parts:
                raise ValueError(f'Invalid {key} path: {item}')
            if not (repo / item).is_file():
                raise ValueError(f'Reference file missing: {item}')
    if len(spec['targets']) < 2 or len(set(spec['targets'])) != len(spec['targets']):
        raise ValueError('A multifile task needs at least two distinct targets.')
    target_dependencies = spec.get('target_dependencies', {})
    if not isinstance(target_dependencies, dict):
        raise ValueError('target_dependencies must be a mapping.')
    for target, dependencies in target_dependencies.items():
        if target not in spec['targets'] or not isinstance(dependencies, list):
            raise ValueError('Target dependency must name a planned target and list.')
        if any(dependency not in spec['targets'][:spec['targets'].index(target)]
               for dependency in dependencies):
            raise ValueError('Target dependencies must precede their dependent target.')
    if not isinstance(spec['source_globs'], list) or not spec['source_globs']:
        raise ValueError('source_globs must list the files to preserve in the workspace.')
    if not all(isinstance(p, str) and not Path(p).is_absolute() and '..' not in Path(p).parts
               for p in spec['source_globs']):
        raise ValueError('source_globs must contain relative patterns.')
    if spec['split'] not in {'train', 'valid'} or spec['validation_level'] != 'behavior_tested':
        raise ValueError('External tasks require a split and original behavior tests.')
    if not spec['command'].startswith('jac test ') or not spec['pass_marker'].endswith(' passed'):
        raise ValueError('External tasks require jac test and an exact passed marker.')
    if spec.get('oracle_probe'):
        probe = (PROJECT / spec['oracle_probe']).resolve()
        if not probe.is_relative_to(Path(__file__).resolve().parent / 'fixtures') or not probe.is_file():
            raise ValueError('Oracle probe must be an existing revdev fixture.')
    for target, fragments in spec.get('source_fragments', {}).items():
        if target not in spec['targets'] or not isinstance(fragments, list) or not all(
                isinstance(fragment, str) and fragment for fragment in fragments):
            raise ValueError('Source fragments must name target files and nonempty text.')
    spec['repo'] = repo
    SOURCES[name] = spec
    return name


def prepare(name: str, run: Path, tools: list[dict]) -> tuple[dict, Path]:
    spec = SOURCES[name]
    repo = spec['repo'].resolve()
    source = run / 'reference'
    source.mkdir()
    if spec.get('source_globs'):
        allowed = set()
        for pattern in spec['source_globs']:
            allowed.update(p.relative_to(repo).as_posix() for p in repo.glob(pattern)
                           if p.is_file() and p.resolve().is_relative_to(repo))
    elif name == 'a2pulse_dates':
        allowed = {'services/brief_dates.jac', 'services/brief_dates.test.jac', 'jac.toml'}
    elif name == 'a2pulse_speech':
        allowed = {'services/speakable.jac', 'services/brief_narrative.jac',
                   'services/speakable.test.jac', 'services/brief_narrative.test.jac',
                   'services/seed_data.jac'}
    elif name == 'a2pulse_editor':
        allowed = {'services/brief_dates.jac', 'services/brief_editor.jac',
                   'services/brief_dates.test.jac', 'services/brief_editor.test.jac',
                   'services/speakable.jac', 'services/brief_narrative.jac',
                   'services/pulse_llm.jac', 'services/llm_env.jac'}
    else:
        allowed = {p.relative_to(repo).as_posix() for p in repo.rglob('*')
                   if p.is_file() and p.suffix in {'.jac', '.css'}} | {'jac.toml'}
    for relative in sorted(allowed):
        original = repo / relative
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if original.is_file(): shutil.copy2(original, target)
    required_source = set(spec['targets'] + spec['inspect'] + spec.get('dependencies', []))
    absent = sorted(path for path in required_source if not (source / path).is_file())
    if absent:
        raise ValueError(f'Task slice omits required source files: {absent}')
    if not (source / 'jac.toml').exists():
        (source / 'jac.toml').write_text(jac_cli.SERVER_TOML)
    files = [p for p in source.rglob('*') if p.is_file()]
    hashes = {p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    preflight_workspace = run / 'preflight-workspace'
    shutil.copytree(source, preflight_workspace)
    baseline = jac_cli.execute(spec['command'].split()[1:], jac=str(JAC), cwd=preflight_workspace, timeout=180)
    shutil.rmtree(preflight_workspace)
    write_json(run / 'preflight.json', {'repo': str(repo), 'commit': commit,
        'command': spec['command'], 'jac': str(JAC), 'result': vars(baseline),
        'passed': baseline.ok and passed(baseline.stdout + baseline.stderr, spec['pass_marker'])})
    if not baseline.ok or not passed(baseline.stdout + baseline.stderr, spec['pass_marker']):
        raise ValueError(f'Reference baseline failed; see {run / "preflight.json"}')
    workspace = run / 'initial'
    shutil.copytree(source, workspace)
    for path in spec['targets']:
        (workspace / path).unlink()
    if jac_cli.SERVER_TOML not in (workspace / 'jac.toml').read_text():
        (workspace / 'jac.toml').write_text((workspace / 'jac.toml').read_text() + '\n' + jac_cli.SERVER_TOML)
    plan = {'files': [{'path': p, 'status': 'pending'} for p in spec['targets']],
            'inspect': spec['inspect'], 'dependency_order': spec['targets'], 'verify': spec['command'],
            'description': spec['plan']}
    (workspace / '.jaccoder').mkdir()
    write_json(workspace / '.jaccoder/build_plan.json', plan)
    write_json(run / 'source-manifest.json', {'repo': str(repo), 'sha256': hashes,
        'commit': commit,
        'targets': spec['targets'], 'validation_level': spec['validation_level'],
        'normalized_config': name in {'ghostboard', 'a2pulse_speech', 'a2pulse_editor'},
        'jac': str(JAC), 'harness_tools_sha256': hashlib.sha256(json.dumps(tools).encode()).hexdigest()})
    write_json(run / 'task.json', {'schema_version': 1, 'name': name, 'repo': str(repo),
        'commit': commit, 'targets': spec['targets'], 'inspect': spec['inspect'],
        'dependencies': spec.get('dependencies', []), 'target_dependencies': spec.get('target_dependencies', {}),
        'dependency_order': spec['targets'], 'verify': spec['command'],
        'validation_level': spec['validation_level'], 'split': spec['split'],
        'reference_sha256': hashes})
    save(workspace, run / 'checkpoint', run_id=name, after_event_id='prepared', segment_index=0,
         reference_id=str(repo), harness_schema_hash=hashlib.sha256(json.dumps(tools).encode()).hexdigest(),
         environment_fingerprint={'jac': str(JAC), 'harness': str(HARNESS)},
         completed_work=['Reference files copied; target paths removed'], remaining_work=[spec['request']])
    return spec, repo


def passed(content: str, marker: str) -> bool:
    return marker in content and not any(s in content for s in (' FAILED ', ' failed in ', 'SYNTAX ERRORS', 'TYPE ERRORS', '[ERROR]'))


def decode_decision(raw: str, step: Path) -> dict:
    """Accept only a valid JSON decision plus redundant closing braces; retain evidence."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        decision, end = json.JSONDecoder().raw_decode(raw)
        suffix = raw[end:].strip()
        if not suffix or set(suffix) != {'}'}:
            raise
        write_json(step / 'transport-normalization.json', {'reason': 'redundant_closing_brace',
            'raw_sha256': hashlib.sha256(raw.encode()).hexdigest(), 'removed_suffix': suffix,
            'parsed_prefix_sha256': hashlib.sha256(raw[:end].encode()).hexdigest()})
        return decision


def archive_artifact(path: Path, label: str) -> None:
    if not path.exists():
        return
    target = path.with_name(label)
    index = 2
    while target.exists():
        target = path.with_name(f'{label}-{index}')
        index += 1
    path.rename(target)


def run_task(name: str, max_steps: int, resume: bool = False, repair: bool = False,
             finalize: bool = False) -> dict:
    run = ROOT / 'runs' / name
    tools = [t for t in json.loads((CAPTURE / 'tools.json').read_text())
             if t['function']['name'] in {'read_file', 'write_code', 'edit_code', 'run_command'}]
    if resume or repair or finalize:
        last_step = sorted(run.glob('step-*'))[-1]
        recoverable_response = (last_step / 'claude.stdout.json').is_file() and not (last_step / 'decision.json').exists()
        if resume and (not ((run / 'interruption.json').is_file() or recoverable_response)
                       or (run / 'validation.json').exists()):
            raise ValueError('Only an interrupted, unvalidated task may resume.')
        if repair and (not (run / 'validation.json').is_file()
                       or json.loads((run / 'validation.json').read_text())['status'] != 'rejected'):
            raise ValueError('Only a rejected task may be repaired.')
        if finalize and ((run / 'validation.json').exists() or not (run / 'conversation.json').exists()):
            raise ValueError('Only a completed but unvalidated task may be finalized.')
        spec, repo = SOURCES[name], SOURCES[name]['repo'].resolve()
        opening = json.loads((run / 'opening.json').read_text())
        workspace = Path(opening['workspace'])
        if not workspace.is_dir():
            raise ValueError('Interrupted workspace is missing.')
        last_request = sorted(run.glob('step-*/request.json'))[-1]
        context = json.loads((run / 'conversation.json').read_text()) if (run / 'conversation.json').is_file() else json.loads(last_request.read_text())
        first_step = max(int(p.name.split('-')[1]) for p in run.glob('step-*')) + 1
        if repair:
            write_json(run / 'conversation-before-repair.json', context)
            if not context['events'] or context['events'][-1]['decision']['kind'] != 'final':
                raise ValueError('Rejected repair requires a final teacher decision.')
            context['events'].pop()
            feedback = {
                'source': 'independent_reference_validation',
                'original_tests': '13 passed',
                'access_contract': 'Reference ContextNotice and Affects both return AccessLevel.READ; generated source uses WRITE.',
                'mixed_notice_oracle': 'Reference overall state is current when at least one notice is current; generated source returned needs_recheck.',
                'checker_baseline': 'Jac 0.34.27 reports E1032 for AccessLevel.READ in the original context_models.jac too. Match reference diagnostics, and rerun original tests after fixing behavior.'}
            context['review_feedback'] = feedback
            context['repair_feedback_after'] = len(context['events'])
            for artifact in ('validation.json', 'acceptance.json'):
                (run / artifact).rename(run / artifact.replace('.json', '-before-repair.json'))
            for artifact in ('replay', 'replay-results'):
                if (run / artifact).exists():
                    (run / artifact).rename(run / f'{artifact}-before-repair')
            if (run / 'acceptance').exists():
                (run / 'acceptance').rename(run / 'acceptance-before-repair')
            write_json(run / 'conversation.json', context)
        if finalize:
            if not context['events'] or context['events'][-1]['decision']['kind'] != 'final':
                raise ValueError('No final teacher decision to validate.')
            for artifact in ('replay', 'replay-results', 'acceptance'):
                archive_artifact(run / artifact, f'{artifact}-pre-finalize')
            first_step = max_steps
        if (run / 'interruption.json').is_file():
            (run / 'interruption.json').rename(run / f'interruption-before-step-{first_step}.json')
    else:
        run.mkdir(parents=True, exist_ok=False)
        spec, repo = prepare(name, run, tools)
        workspace = run / 'workspace'
        restore(run / 'checkpoint', workspace)
        opening = {'request': spec['request'], 'workspace': str(workspace), 'targets': spec['targets'],
                   'plan': '.jaccoder/build_plan.json', 'jac_version': '0.34.27', 'validation_level': spec['validation_level']}
        write_json(run / 'opening.json', opening)
        system = (CAPTURE / 'system.txt').read_text() + '\n' + RULES + TRANSPORT
        (run / 'teacher-system.txt').write_text(system)
        context = {**opening, 'tools': tools, 'events': []}
        first_step = 0
    cli = run / 'claude'; cli.mkdir(exist_ok=True)
    schemas = {t['function']['name']: t['function'] for t in tools}
    inspected = set(); observed_after_write = set(); written = set(); verified = False; finished = finalize
    for event in context['events']:
        decision = event['decision']; result = event.get('result', {})
        if decision['kind'] != 'tool' or not result.get('executed'): continue
        if decision['name'] == 'read_file':
            path = Path(decision['args']['file_path']).resolve().relative_to(workspace).as_posix()
            inspected.add(path)
            if path in written: observed_after_write.add(path)
        elif decision['name'] in {'write_code', 'edit_code'}:
            path = Path(decision['args']['file_path']).resolve().relative_to(workspace).as_posix()
            if (workspace / path).is_file() and not result['content'].startswith(('BLOCKED:', 'ERROR:', 'FAILED')):
                written.add(path); observed_after_write.discard(path)
            verified = False
        elif decision['name'] == 'run_command' and decision['args']['command'] == spec['command']:
            verified = passed(result['content'], spec['pass_marker'])
    if resume:
        previous_step = run / f'step-{first_step-1:03d}'
        response_file = previous_step / 'claude.stdout.json'
        if response_file.is_file() and not (previous_step / 'decision.json').exists():
            envelope = json.loads(response_file.read_text())
            if not envelope.get('is_error'):
                raw = envelope['result'].strip()
                if raw.startswith('```'): raw = raw.split('\n', 1)[1].rsplit('```', 1)[0]
                recovered = decode_decision(raw, previous_step)
                jsonschema.validate(recovered, DECISION_SCHEMA)
                validate_call(recovered, schemas, workspace)
                if recovered['kind'] != 'final' or not verified or written != set(spec['targets']):
                    raise ValueError('Only a complete final decision may be recovered without dispatch.')
                write_json(previous_step / 'decision.json', recovered)
                context['events'].append({'decision': recovered})
                write_json(run / 'conversation.json', context)
                finished = True
                first_step = max_steps
    for i in range(first_step, max_steps):
        step = run / f'step-{i:03d}'; step.mkdir()
        write_json(step / 'request.json', context)
        try:
            response = subprocess.run(['claude', '-p', '--tools', '', '--system-prompt-file', str(run / 'teacher-system.txt'),
                '--output-format', 'json', '--no-session-persistence', '--setting-sources', '', '--strict-mcp-config', '--disable-slash-commands'],
                input=json.dumps(context), cwd=cli, capture_output=True, text=True, timeout=240)
        except subprocess.TimeoutExpired as error:
            (step / 'claude.stdout.partial').write_bytes(error.stdout or b'')
            (step / 'claude.stderr.partial').write_bytes(error.stderr or b'')
            write_json(run / 'interruption.json', {'step': i, 'reason': 'claude_timeout',
                'timeout_seconds': 240, 'executed_decision': False,
                'stdout': str(step / 'claude.stdout.partial'), 'stderr': str(step / 'claude.stderr.partial')})
            raise RuntimeError(f'Claude timed out at {step}') from error
        (step / 'claude.stdout.json').write_text(response.stdout)
        (step / 'claude.stderr.txt').write_text(response.stderr)
        if response.returncode:
            write_json(run / 'interruption.json', {'step': i, 'reason': 'claude_exit',
                'returncode': response.returncode, 'stdout': str(step / 'claude.stdout.json'),
                'stderr': str(step / 'claude.stderr.txt'), 'executed_decision': False})
            raise RuntimeError(f'Claude exited {response.returncode} at {step}')
        envelope = json.loads(response.stdout)
        if envelope.get('is_error'):
            write_json(run / 'interruption.json', {'step': i, 'reason': 'claude_api_error',
                'api_error': envelope.get('result'), 'executed_decision': False,
                'stdout': str(step / 'claude.stdout.json'), 'stderr': str(step / 'claude.stderr.txt')})
            raise RuntimeError(f'Claude error at {step}')
        raw = envelope['result'].strip()
        if raw.startswith('```'): raw = raw.split('\n', 1)[1].rsplit('```', 1)[0]
        try:
            decision = decode_decision(raw, step)
        except (ValueError, json.JSONDecodeError) as error:
            write_json(run / 'interruption.json', {'step': i, 'reason': 'malformed_decision',
                'error': str(error), 'stdout': str(step / 'claude.stdout.json'),
                'executed_decision': False})
            raise
        write_json(step / 'decision.json', decision)
        try:
            jsonschema.validate(decision, DECISION_SCHEMA)
            validate_call(decision, schemas, workspace)
            if decision['kind'] == 'final':
                if not verified or written != set(spec['targets']): raise ValueError('Complete both target files and run the planned verification first.')
                context['events'].append({'decision': decision}); finished = True; break
            tool, args = decision['name'], decision['args']
            if tool in ('write_code', 'edit_code'):
                path = (workspace / args['file_path']).resolve().relative_to(workspace).as_posix()
                if path not in spec['targets']: raise ValueError('Only planned target files may be edited.')
                if not set(spec['inspect']) <= inspected or '.jaccoder/build_plan.json' not in inspected:
                    raise ValueError('Read the plan and existing dependency files before writing.')
                for dependency in spec.get('target_dependencies', {}).get(path, []):
                    if dependency not in observed_after_write:
                        raise ValueError(f'Read the newly written {dependency} before implementing {path}.')
                if path in spec.get('target_dependencies', {}) and not set(spec.get('dependencies', [])) <= inspected:
                    raise ValueError('Read the listed existing dependencies before implementing the dependent target.')
                if name == 'a2pulse_speech' and path == 'services/brief_narrative.jac' and 'services/speakable.jac' not in observed_after_write:
                    raise ValueError('Read the newly written services/speakable.jac before implementing its dependent narrative module.')
                if name == 'a2pulse_editor' and path == 'services/brief_editor.jac':
                    if 'services/brief_dates.jac' not in observed_after_write:
                        raise ValueError('Read the newly written services/brief_dates.jac before implementing the editor.')
                    if not set(spec['dependencies']) <= inspected:
                        raise ValueError('Read existing speakable.jac, brief_narrative.jac, and pulse_llm.jac before implementing the editor.')
            actual = execute_tool({'workspace': str(workspace), 'name': tool, 'args': args, 'phase': 'implement'}, step, HARNESS, JAC)
            if tool == 'read_file' and actual.get('executed'):
                read_path = (workspace / args['file_path']).resolve().relative_to(workspace).as_posix()
                inspected.add(read_path)
                if read_path in written: observed_after_write.add(read_path)
            if tool in ('write_code', 'edit_code'):
                if actual.get('executed') and (workspace / path).is_file() and not actual['content'].startswith(('BLOCKED:', 'ERROR:', 'FAILED')):
                    written.add(path)
                    observed_after_write.discard(path)
                verified = False
            if tool == 'run_command' and args['command'] == spec['command']:
                verified = actual.get('executed', False) and passed(actual['content'], spec['pass_marker'])
        except (ValueError, jsonschema.ValidationError) as error:
            actual = {'executed': False, 'origin': 'adapter_validation', 'content': str(error)}
            write_json(step / 'rejection.json', actual)
        context['events'].append({'decision': decision, 'result': actual})
        write_json(run / 'conversation.json', context)
        print(json.dumps({'task': name, 'step': i, 'tool': decision['name'], 'executed': actual.get('executed'), 'verified': verified}), flush=True)
    write_json(run / 'conversation.json', context)
    replay = run / 'replay'; restore(run / 'checkpoint', replay)
    replay_equal = True; replay_calls = 0
    for i, event in enumerate(context['events']):
        decision = event['decision']; result = event.get('result', {})
        if decision['kind'] == 'final' or result.get('executed') is False: continue
        args = json.loads(json.dumps(decision['args']).replace(str(workspace), str(replay)))
        again = execute_tool({'workspace': str(replay), 'name': decision['name'], 'args': args, 'phase': 'implement'},
                             run / 'replay-results' / str(i), HARNESS, JAC)
        replay_calls += 1
        replay_equal &= again.get('executed') == result.get('executed')
        for marker in (spec['pass_marker'], 'FAILED', '[ERROR]', 'SYNTAX ERRORS', 'TYPE ERRORS'):
            replay_equal &= (marker in again['content']) == (marker in result['content'])
    for path in spec['targets']:
        replay_equal &= (replay / path).is_file() and (workspace / path).is_file()
        if (replay / path).is_file() and (workspace / path).is_file():
            replay_equal &= (replay / path).read_bytes() == (workspace / path).read_bytes()
    acceptance = run / 'acceptance'; shutil.copytree(run / 'initial', acceptance)
    for path in spec['targets']:
        if (workspace / path).is_file():
            (acceptance / path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(workspace / path, acceptance / path)
    verdict = jac_cli.execute(spec['command'].split()[1:], jac=str(JAC), cwd=acceptance, timeout=120)
    independent = {path: vars(jac_cli.execute(['check', path], jac=str(JAC), cwd=acceptance, timeout=120))
                   if (acceptance / path).is_file() else {'ok': False, 'error': 'target file missing'}
                   for path in spec['targets'] + (spec['inspect'] if name == 'ghostboard' else [])}
    reference_checks = {path: vars(jac_cli.execute(['check', path], jac=str(JAC), cwd=run / 'reference', timeout=120))
                        for path in independent}
    def diagnostic_codes(result: dict) -> list[str]:
        return sorted(re.findall(r'error\[(E\d+)\]', result.get('stdout', '') + result.get('stderr', '')))
    checks_ok = all(check.get('returncode') == reference_checks[path]['returncode']
                    and diagnostic_codes(check) == diagnostic_codes(reference_checks[path])
                    for path, check in independent.items())
    fragment_results = {}
    for path, fragments in spec.get('source_fragments', {}).items():
        reference_text = (run / 'reference' / path).read_text()
        generated_text = (acceptance / path).read_text()
        fragment_results[path] = {fragment: {'reference_count': reference_text.count(fragment),
            'generated_count': generated_text.count(fragment)} for fragment in fragments}
    fragments_ok = all(values['reference_count'] > 0 and values['generated_count'] == values['reference_count']
                       for rows in fragment_results.values() for values in rows.values())
    probe_results = {}
    probe_ok = True
    if spec.get('oracle_probe'):
        fixture = PROJECT / spec['oracle_probe']
        oracle_reference = run / 'oracle-reference'
        shutil.copytree(run / 'reference', oracle_reference, ignore=shutil.ignore_patterns('.jac', '.pytest_cache'))
        shutil.copy2(fixture, oracle_reference / 'revdev_oracle.jac')
        shutil.copy2(fixture, acceptance / 'revdev_oracle.jac')
        expected = jac_cli.execute(['run', 'revdev_oracle.jac'], jac=str(JAC), cwd=oracle_reference, timeout=120)
        observed = jac_cli.execute(['run', 'revdev_oracle.jac'], jac=str(JAC), cwd=acceptance, timeout=120)
        probe_results = {'reference': vars(expected), 'generated': vars(observed),
                         'fixture_sha256': hashlib.sha256(fixture.read_bytes()).hexdigest()}
        probe_ok = expected.ok and observed.ok and expected.stdout == observed.stdout
        shutil.rmtree(oracle_reference)
    extra = {path: vars(jac_cli.execute(['test', path], jac=str(JAC), cwd=acceptance, timeout=120,
                                        env={'JAC_TEST_JOBS': '0'})) for path, _marker in spec.get('extra_tests', [])}
    extra_ok = all(result['returncode'] == 0 and passed(result['stdout'] + result['stderr'], marker)
                   for path, marker in spec.get('extra_tests', []) for result in [extra[path]])
    write_json(run / 'acceptance.json', {'planned': vars(verdict), 'independent_target_checks': independent,
                                          'reference_target_checks': reference_checks, 'source_fragments': fragment_results,
                                          'oracle_probe': probe_results, 'extra_tests': extra})
    accepted = (finished and verified and written == set(spec['targets']) and replay_equal
                and verdict.ok and passed(verdict.stdout + verdict.stderr, spec['pass_marker'])
                and checks_ok and fragments_ok and probe_ok and extra_ok)
    report = {'status': 'accepted' if accepted else 'rejected', 'validation_level': spec['validation_level'],
              'written_files': sorted(written), 'replay_calls': replay_calls, 'replay_equal': replay_equal,
              'teacher_verified': verified, 'finished': finished, 'acceptance_ok': verdict.ok,
              'independent_target_checks_ok': checks_ok, 'source_fragments_ok': fragments_ok,
              'oracle_probe_ok': probe_ok, 'extra_tests_ok': extra_ok,
              'source': str(repo), 'source_sha256': hashlib.sha256(json.dumps(json.loads((run / 'source-manifest.json').read_text())['sha256'], sort_keys=True).encode()).hexdigest()}
    write_json(run / 'validation.json', report)
    return report


def finalize_existing(name: str) -> dict:
    """Recompute a verdict after a reporting crash from persisted execution evidence."""
    run = ROOT / 'runs' / name
    spec = SOURCES[name]
    context = json.loads((run / 'conversation.json').read_text())
    workspace, replay, acceptance = (run / part for part in ('workspace', 'replay', 'acceptance'))
    finished = any(event['decision']['kind'] == 'final' for event in context['events'])
    written = set()
    verified = False
    replay_equal = True
    replay_calls = 0
    for i, event in enumerate(context['events']):
        decision = event['decision']
        if decision['kind'] == 'final': continue
        result = event['result']
        if decision['name'] in {'write_code', 'edit_code'}:
            path = Path(decision['args']['file_path']).resolve().relative_to(workspace).as_posix()
            if result.get('executed') and (workspace / path).is_file() and not result['content'].startswith(('BLOCKED:', 'ERROR:', 'FAILED')):
                written.add(path)
            verified = False
        if decision['name'] == 'run_command' and decision['args']['command'] == spec['command']:
            verified = result.get('executed', False) and passed(result['content'], spec['pass_marker'])
        if result.get('executed') is False: continue
        repeated = json.loads((run / 'replay-results' / str(i) / 'result.json').read_text())
        replay_calls += 1
        replay_equal &= repeated.get('executed') == result.get('executed')
        for marker in (spec['pass_marker'], 'FAILED', '[ERROR]', 'SYNTAX ERRORS', 'TYPE ERRORS'):
            replay_equal &= (marker in repeated['content']) == (marker in result['content'])
    for path in spec['targets']:
        replay_equal &= (workspace / path).is_file() and (replay / path).is_file()
        if (workspace / path).is_file() and (replay / path).is_file():
            replay_equal &= (workspace / path).read_bytes() == (replay / path).read_bytes()
    planned = jac_cli.execute(spec['command'].split()[1:], jac=str(JAC), cwd=acceptance, timeout=120)
    checked = {}
    for path in spec['targets'] + (spec['inspect'] if name == 'ghostboard' else []):
        checked[path] = (vars(jac_cli.execute(['check', path], jac=str(JAC), cwd=acceptance, timeout=120))
                         if (acceptance / path).is_file() else {'error': 'target file missing'})
    checks_ok = all(c.get('returncode') == 0 and passed(c.get('stdout', '') + c.get('stderr', ''), '1 passed')
                    for c in checked.values())
    write_json(run / 'acceptance.json', {'planned': vars(planned), 'independent_target_checks': checked})
    accepted = (finished and verified and written == set(spec['targets']) and replay_equal
                and planned.ok and passed(planned.stdout + planned.stderr, spec['pass_marker']) and checks_ok)
    manifest = json.loads((run / 'source-manifest.json').read_text())
    report = {'status': 'accepted' if accepted else 'rejected', 'validation_level': spec['validation_level'],
              'written_files': sorted(written), 'replay_calls': replay_calls, 'replay_equal': replay_equal,
              'teacher_verified': verified, 'finished': finished, 'acceptance_ok': planned.ok,
              'independent_target_checks_ok': checks_ok, 'source': manifest['repo'],
              'source_sha256': hashlib.sha256(json.dumps(manifest['sha256'], sort_keys=True).encode()).hexdigest(),
              'recovered_from_persisted_evidence': True}
    write_json(run / 'validation.json', report)
    return report


def export() -> dict:
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(str(PROJECT / 'output/model/JacLLM-SFT-Ornith-9B-trajectory-bf16'), local_files_only=True)
    tools = [t for t in json.loads((CAPTURE / 'tools.json').read_text())
             if t['function']['name'] in {'read_file', 'write_code', 'edit_code', 'run_command'}]
    records = {'train': [], 'valid': []}
    long_records = {'train': [], 'valid': []}
    for name, spec in SOURCES.items():
        run = ROOT / 'runs' / name
        if not (run / 'validation.json').exists(): continue
        verdict = json.loads((run / 'validation.json').read_text())
        if verdict['status'] != 'accepted': continue
        context = json.loads((run / 'conversation.json').read_text())
        opening = json.loads((run / 'opening.json').read_text())
        opening['workspace'] = '/workspace'
        rows = [{'role': 'harness', 'mode': 'system', 'content': STUDENT},
                {'role': 'user', 'mode': 'prompt', 'content': json.dumps(opening)}]
        for index, event in enumerate(context['events']):
            if index == context.get('repair_feedback_after'):
                rows.append({'role': 'user', 'mode': 'prompt',
                             'content': json.dumps(context['review_feedback'], ensure_ascii=False)})
            rows += event_rows([event])
        rows = json.loads(json.dumps(rows).replace(context['workspace'], '/workspace'))
        messages = to_template_input({'meta': {'tools': tools}, 'rows': rows}, None)
        text = tokenizer.apply_chat_template(messages, tools=tools, tokenize=False)
        tokens = len(tokenizer(text, add_special_tokens=False)['input_ids'])
        if tokens > 65536:
            write_json(run / 'export-rejection.json', {'reason': '64k cap', 'tokens': tokens}); continue
        for message in messages:
            for call in message.get('tool_calls', []): call['function']['arguments'] = json.dumps(call['function']['arguments'])
        record = {'messages': messages, 'tools': json.dumps(tools), 'meta': {
            'source': 'agent-synth', 'format': 'jac', 'class': 'fullstack' if name in {'orbitron', 'ghostboard'} else 'function',
            'task_type': 'revdev_multifile', 'fp': str(run), 'split_group': str(spec['repo']),
            'validation': 'accepted', 'validation_level': spec['validation_level'], 'tokens': tokens,
            'transport': 'claude_cli_json_to_function_calls', 'context_projection': True,
            'path_normalization': {context['workspace']: '/workspace'}}}
        if tokens <= 16384:
            records[spec['split']].append(record)
        else:
            long_records[spec['split']].append(record)
            write_json(run / 'export-64k.json', {'dataset': 'behavior-64k-v1', 'split': spec['split'],
                                                  'tokens': tokens, 'cap': 65536})
            write_json(run / 'export-rejection.json', {'reason': '16k smoke cap', 'tokens': tokens,
                                                        'exported_to': f'behavior-64k-v1/{spec["split"]}.jsonl'})
    out = PROJECT / 'dataset/sft/revdev_multifile/smoke-v1'
    all_records = records['valid'] + records['train']
    fraction = (len(records['valid']) + 0.5) / len(all_records) if records['valid'] else 0.0
    counts = split_and_write(all_records, out, fraction)
    assert counts['train'] == len(records['train']) and counts.get('valid', 0) == len(records['valid'])
    generate_report(out)
    report = {'train': len(records['train']), 'valid': len(records['valid']), 'records': len(all_records)}
    write_json(ROOT / 'export.json', report)
    if any(long_records.values()):
        long_out = PROJECT / 'dataset/sft/revdev_multifile/behavior-64k-v1'
        long_all = long_records['valid'] + long_records['train']
        fraction = (len(long_records['valid']) + 0.5) / len(long_all) if long_records['valid'] else 0.0
        long_counts = split_and_write(long_all, long_out, fraction)
        assert long_counts['train'] == len(long_records['train']) and long_counts.get('valid', 0) == len(long_records['valid'])
        generate_report(long_out)
        write_json(ROOT / 'export-64k.json', {'train': len(long_records['train']),
            'valid': len(long_records['valid']), 'records': len(long_all), 'cap': 65536})
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', default='all')
    parser.add_argument('--recipe', type=Path, help='JSON task artifact for a new repo')
    parser.add_argument('--max-steps', type=int, default=18)
    parser.add_argument('--finalize-existing', action='store_true')
    parser.add_argument('--resume-existing', action='store_true')
    parser.add_argument('--repair-existing', action='store_true')
    parser.add_argument('--finalize-unvalidated', action='store_true')
    parser.add_argument('--recheck-existing', action='store_true')
    args = parser.parse_args()
    if args.recipe:
        loaded = load_recipe(args.recipe)
        if args.task == 'all': args.task = loaded
    if args.task != 'all' and args.task not in SOURCES:
        parser.error(f'Unknown task: {args.task}')
    ROOT.mkdir(parents=True, exist_ok=True)
    names = list(SOURCES) if args.task == 'all' else [args.task]
    for name in names:
        run = ROOT / 'runs' / name
        if args.recheck_existing and (run / 'validation.json').exists():
            verdict = json.loads((run / 'validation.json').read_text())
            if verdict['status'] != 'rejected':
                raise ValueError('Only rejected runs may be rechecked.')
            archive_artifact(run / 'validation.json', 'validation-before-recheck.json')
            archive_artifact(run / 'acceptance.json', 'acceptance-before-recheck.json')
            result = run_task(name, args.max_steps, finalize=True)
            print(json.dumps({'task': name, **result}), flush=True)
            continue
        if args.finalize_unvalidated and run.exists() and not (run / 'validation.json').exists():
            result = run_task(name, args.max_steps, finalize=True)
            print(json.dumps({'task': name, **result}), flush=True)
            continue
        incomplete_response = (any(p.is_file() and not (p.parent / 'decision.json').exists()
                                   for p in run.glob('step-*/claude.stdout.json'))
                               if run.exists() else False)
        if args.resume_existing and ((run / 'interruption.json').exists() or incomplete_response) and not (run / 'validation.json').exists():
            result = run_task(name, args.max_steps, resume=True)
            print(json.dumps({'task': name, **result}), flush=True)
            continue
        if args.repair_existing and (run / 'validation.json').exists():
            result = run_task(name, args.max_steps, repair=True)
            print(json.dumps({'task': name, **result}), flush=True)
            continue
        if args.finalize_existing and (ROOT / 'runs' / name).exists() and not (ROOT / 'runs' / name / 'validation.json').exists():
            print(json.dumps({'task': name, **finalize_existing(name)}), flush=True)
            continue
        if (ROOT / 'runs' / name).exists(): continue
        result = run_task(name, args.max_steps)
        print(json.dumps({'task': name, **result}), flush=True)
    print(json.dumps(export()), flush=True)

# Run =====================================================
if __name__ == '__main__': main()
