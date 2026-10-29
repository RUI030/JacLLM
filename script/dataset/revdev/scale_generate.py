"""Generate compact module trajectories with real Claude decisions and JacCoder execution."""

import argparse, hashlib, json, subprocess, sys, time
from pathlib import Path

import jsonschema
from transformers import AutoTokenizer

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils import jac_cli
from dataset.revdev.claude_adapter import DECISION_SCHEMA, execute_tool, validate_call, write_json
from dataset.revdev.checkpoint import save, restore
from dataset.revdev.export import event_rows
from dataset.trajectory.common import to_template_input
from dataset.pipeline import split_and_write
from dataset.statistics import generate_report

# Setting =================================================
PROJECT = Path(__file__).resolve().parents[3]
ROOT = PROJECT/'dataset/raw/revdev/scaleup_v1'
CAPTURE = PROJECT/'dataset/raw/revdev/Mindcraft/m3/private/teacher_prompt_v1'
HARNESS = PROJECT.parent/'jacBuilder'
JAC = Path('/tmp/jac-0.34.27-linux-x86_64')
RULES = '''This is a scoped module inside an existing Jac application, not a new UI build.
Only app.jac may be modified; dependency.jac and verify.jac are existing, evaluator-owned files.
Read .jaccoder/build_plan.json and relevant source. Read actual local dependency definitions
before using them; names alone do not establish a verified signature. Reuse unchanged reads.
read_file offset is ZERO-based: offset=0 includes the first line; an empty page does not mean
an empty file. Fix offset/limit when necessary. Never invent a dependency signature.
run_command permits only ls -la, pwd, cat of one workspace file, or jac check/test/build/run.
Use the given workspace as workdir, the pinned jac on PATH, no shell chaining/background jobs.
Write/edit automatically checks syntax; avoid repeating the same check. Run jac run verify.jac
for behavior and inspect its real result before finishing. Correct failures, preserve interfaces.
No packages, network, credentials, or paths outside the workspace. Do not read reference answers.
The saved plan is already complete; plan_build and skills loading are unavailable in this scope.
'''
TRANSPORT = '''\n# Scoped adapter execution protocol (takes precedence)
Return exactly one JSON object per turn: {"kind":"tool" or "final","name":tool name or "",
"args":tool arguments or {},"summary":short progress statement}. No markdown fences.
Only schemas in the user payload can be called; Claude built-in tools are disabled.
The next turn contains the actual tool result. Never invent successful executions.
'''
STUDENT = '''# JacCoder: JacHammer Application Builder
You are JacCoder, the application-builder agent for JacHammer. You build, extend, preview,
validate, and debug complete full-stack Jac applications yourself. Read, plan, write, run,
and verify directly. Be concise and action-oriented.
\n# Scoped module workflow\n'''+RULES+'\nCall the supplied tools directly; report only verified outcomes.\n'

# Functions ===============================================
def materialize(path: Path, files: dict) -> None:
    path.mkdir(parents=True,exist_ok=False)
    for name,content in files.items():
        file=path/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text(content)


def generate_task(task: dict, destination: Path, tools: list, teacher: str, max_steps: int) -> dict:
    destination.mkdir(parents=True,exist_ok=False)
    original=destination/'initial';materialize(original,task['initial_files'])
    schema_hash=hashlib.sha256(json.dumps(tools).encode()).hexdigest()
    save(original,destination/'checkpoint',run_id=task['name'],after_event_id='prepared-workspace',segment_index=0,
         reference_id=task['repo']+'@'+task['commit'],harness_schema_hash=schema_hash,
         environment_fingerprint={'jac':str(JAC)},completed_work=['Existing dependency, target scaffold and verification fixture'],remaining_work=[task['request']])
    workspace=destination/'workspace';restore(destination/'checkpoint',workspace)
    context={'request':'Finish this module in the existing application. '+task['request'],
             'workspace':str(workspace),'target':'app.jac','signature':task['signature'],
             'mode':task['mode'],'resume':'Read the saved plan and existing files; finish the pending function.',
             'tools':tools,'events':[]}
    if task['mode']=='repair':
        # Deterministic fault injection: real failing tool execution, excluded from loss.
        for name,args in [('run_command',{'command':'jac run verify.jac','workdir':str(workspace),'timeout':60,'background':False}),
                          ('read_file',{'file_path':str(workspace/'dependency.jac'),'offset':len(task['initial_files']['dependency.jac'].splitlines()),'limit':200})]:
            decision={'kind':'tool','name':name,'args':args,'summary':'Fixture preflight, not a teacher-selected action'}
            result=execute_tool({'workspace':str(workspace),'name':name,'args':args,'phase':'implement'},destination/f'seed-{len(context["events"])}',HARNESS,JAC)
            context['events'].append({'decision':decision,'result':result,'fixture_seed':True})
    opening={k:v for k,v in context.items() if k not in ('events','tools')}
    write_json(destination/'opening.json',opening)
    system_path=destination/'teacher-system.txt';system_path.write_text(teacher)
    schemas={t['function']['name']:t['function'] for t in tools};observed=set();verified=False
    cli=destination/'claude';cli.mkdir()
    for index in range(max_steps):
        step=destination/f'step-{index:03d}';step.mkdir()
        write_json(step/'request.json',context)
        result=subprocess.run(['claude','-p','--tools','','--system-prompt-file',str(system_path),
            '--output-format','json','--no-session-persistence','--setting-sources','','--strict-mcp-config','--disable-slash-commands'],
            input=json.dumps(context),cwd=cli,capture_output=True,text=True,timeout=240)
        (step/'claude.stdout.json').write_text(result.stdout);(step/'claude.stderr.txt').write_text(result.stderr)
        if result.returncode:raise RuntimeError(f'Claude exit {result.returncode}: {step}')
        envelope=json.loads(result.stdout)
        if envelope.get('is_error'):raise RuntimeError(f'Claude error: {step}')
        raw=envelope['result'].strip()
        if raw.startswith('```'):raw=raw.split('\n',1)[1].rsplit('```',1)[0]
        decision=json.loads(raw);write_json(step/'decision.json',decision)
        try:
            jsonschema.validate(decision,DECISION_SCHEMA)
            validate_call(decision,schemas,workspace)
            if decision['kind']=='final':
                if not verified:raise ValueError('Run jac run verify.jac successfully before finishing.')
                context['events'].append({'decision':decision});break
            name,args=decision['name'],decision['args']
            if name in ('write_code','edit_code'):
                if (workspace/args['file_path']).resolve()!=workspace/'app.jac':raise ValueError('Only app.jac may be modified for this scoped task.')
                needed={'target',*task['deps']}
                if not needed<=observed:raise ValueError('Inspect actual definitions first: '+', '.join(sorted(needed-observed)))
            actual=execute_tool({'workspace':str(workspace),'name':name,'args':args,'phase':'implement'},step,HARNESS,JAC)
            if name=='read_file':
                content=actual['content'];path=Path(args['file_path']).name
                if path=='app.jac' and task['name'] in content:observed.add('target')
                if path=='dependency.jac':observed.update(n for n in task['deps'] if n in content)
            if name in ('write_code','edit_code'):verified=False
            if name=='run_command' and args['command']=='jac run verify.jac' and 'REVDEV_CHECK_OK' in actual['content']:verified=True
        except (ValueError,jsonschema.ValidationError) as error:
            actual={'executed':False,'origin':'adapter_validation','content':str(error)}
            write_json(step/'rejection.json',actual)
        context['events'].append({'decision':decision,'result':actual})
        write_json(destination/'conversation.json',context)
        print(json.dumps({'task':task['name'],'step':index,'tool':decision['name'],'executed':actual.get('executed'),'summary':decision['summary']}),flush=True)
    write_json(destination/'conversation.json',context)
    # Replay actual decisions from the restorable starting state, then independent oracle check.
    replay=destination/'replay';restore(destination/'checkpoint',replay)
    statuses=[]
    for index,event in enumerate(context['events']):
        d=event['decision']
        if d['kind']=='final' or event.get('result',{}).get('executed') is False:continue
        arguments=json.loads(json.dumps(d['args']).replace(str(workspace),str(replay)))
        actual=execute_tool({'workspace':str(replay),'name':d['name'],'args':arguments,'phase':'implement'},destination/'replay-results'/str(index),HARNESS,JAC)
        signals=['REVDEV_CHECK_OK','SYNTAX ERRORS','TYPE ERRORS','[ERROR]']
        statuses.append(all((x in actual['content'])==(x in event['result']['content']) for x in signals))
    check=destination/'acceptance';materialize(check,task['initial_files'])
    (check/'app.jac').write_text((workspace/'app.jac').read_text())
    verdict=jac_cli.execute(['run','verify.jac'],jac=str(JAC),cwd=check,timeout=60)
    write_json(destination/'acceptance.json',vars(verdict))
    same=(replay/'app.jac').read_bytes()==(workspace/'app.jac').read_bytes()
    accepted=verified and same and all(statuses) and verdict.ok and 'REVDEV_CHECK_OK' in verdict.stdout
    report={'status':'accepted' if accepted else 'rejected','reference':task['repo']+'@'+task['commit'],
            'source_sha256':task['source_sha256'],'source_span':task['span'],'replay_calls':len(statuses),
            'replay_source_equal':same,'replay_statuses_equal':all(statuses),'verified':verified,'mode':task['mode'],'split':task['split']}
    write_json(destination/'validation.json',report)
    return report


def export(root: Path, tools: list, tokenizer) -> dict:
    train=[];valid=[];rejected=[];accepted=[]
    for path in sorted((root/'runs').glob('*/validation.json')):
        verdict=json.loads(path.read_text());run=path.parent
        if verdict['status']!='accepted':continue
        context=json.loads((run/'conversation.json').read_text());opening=json.loads((run/'opening.json').read_text());opening['workspace']='/workspace'
        rows=[{'role':'harness','mode':'system','content':STUDENT},{'role':'user','mode':'prompt','content':json.dumps(opening)}]
        for event in context['events']:
            events=event_rows([event])
            if event.get('fixture_seed') or event.get('result',{}).get('executed') is False:events[0]['weight']=0
            rows+=events
        # Only path strings are normalized; original calls and results remain in raw run.
        rows=json.loads(json.dumps(rows).replace(context['workspace'],'/workspace'))
        trajectory={'meta':{'tools':tools},'rows':rows};messages=to_template_input(trajectory,None)
        text=tokenizer.apply_chat_template(messages,tools=tools,tokenize=False)
        tokens=len(tokenizer(text,add_special_tokens=False)['input_ids'])
        if tokens>16384:rejected.append({'run':run.name,'tokens':tokens,'reason':'16k_cap'});continue
        for m in messages:
            for c in m.get('tool_calls',[]):c['function']['arguments']=json.dumps(c['function']['arguments'])
        record={'messages':messages,'tools':json.dumps(tools),'meta':{'source':'agent-synth','format':'jac','class':'function',
            'task_type':'revdev_resume' if verdict['mode']=='resume' else 'revdev_function','fp':str(run),'split_group':verdict['reference'].split('@')[0],
            'reference':verdict['reference'],'source_sha256':verdict['source_sha256'],'source_span':verdict['source_span'],
            'tokens':tokens,'validation':'accepted','variant':verdict['mode'],'transport':'claude_cli_json_to_function_calls',
            'context_projection':True,'system_transform':'scoped JacCoder module prompt v1; original full teacher prompt retained',
            'path_normalization':{context['workspace']:'/workspace'},'fixture_seed_loss_weight':0}}
        (train if verdict['split']=='train' else valid).append(record);accepted.append({'run':run.name,'split':verdict['split'],'tokens':tokens})
    for kind in ('revdev_function','revdev_resume'):
        out=PROJECT/'dataset/sft'/kind/'scaleup-v1'
        # Repo-based assignment is fixed before generation; shared writer handles JSONL output.
        training = [r for r in train if r['meta']['task_type']==kind]
        heldout = [r for r in valid if r['meta']['task_type']==kind]
        records = heldout + training
        fraction = min(1.0, (len(heldout) + 0.5) / len(records)) if heldout else 0.0
        counts = split_and_write(records, out, fraction)
        assert counts.get('valid', 0) == len(heldout)
        assert counts['train'] == len(training)
        generate_report(out)
    report={'accepted':accepted,'rejected':rejected,'train':len(train),'heldout':len(valid),'split_note':'Aegis held out by repository. Other two repos train-only. No eval probe tasks included.'}
    write_json(root/'export.json',report);return report


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--limit',type=int,default=0);p.add_argument('--max-steps',type=int,default=14);p.add_argument('--export-only',action='store_true');args=p.parse_args();root=args.root.resolve()
    tools=[t for t in json.loads((CAPTURE/'tools.json').read_text()) if t['function']['name'] in {'read_file','write_code','edit_code','run_command'}]
    teacher=(CAPTURE/'system.txt').read_text()+'\n'+RULES+TRANSPORT
    (root/'student-system.txt').write_text(STUDENT)
    write_json(root/'tools.json', tools)
    write_json(root/'prompt-provenance.json',{'teacher_base':str(CAPTURE),'teacher_sha256':hashlib.sha256(teacher.encode()).hexdigest(),'student_sha256':hashlib.sha256(STUDENT.encode()).hexdigest(),'tools_sha256':hashlib.sha256(json.dumps(tools).encode()).hexdigest(),'note':'Original schemas unchanged, supported four-tool subset; student prompt is explicitly scoped, not the original full system.'})
    if not args.export_only:
        tasks=[x for x in json.loads((root/'private/tasks-report.json').read_text()) if x['status']=='ready']
        if args.limit:tasks=tasks[:args.limit]
        for entry in tasks:
            destination=root/'runs'/entry['name']
            if destination.exists():continue
            task=json.loads(Path(entry['path']).read_text())
            try:report=generate_task(task,destination,tools,teacher,args.max_steps)
            except (RuntimeError,ValueError,subprocess.TimeoutExpired,jsonschema.ValidationError) as error:
                destination.mkdir(parents=True,exist_ok=True);report={'status':'interrupted','error':str(error)};write_json(destination/'validation.json',report)
            print(json.dumps({'task':entry['name'],**report}),flush=True)
            if report['status']=='interrupted':break
    tokenizer=AutoTokenizer.from_pretrained(str(PROJECT/'output/model/JacLLM-SFT-Ornith-9B-trajectory-bf16'),local_files_only=True)
    print(json.dumps(export(root,tools,tokenizer)),flush=True)

# Run =====================================================
if __name__=='__main__':main()
