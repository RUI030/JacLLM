"""Compare revdev adapters on frozen new tasks and real JacCoder tool rollouts."""

import argparse, hashlib, json, re, sys, time

import jsonschema
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils import jac_cli
from dataset.revdev.claude_adapter import validate_call

# Setting =================================================
ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / 'dataset/raw/revdev/Mindcraft/m3/runs/claude_teacher_v2'
JAC = '/tmp/jac-0.34.27-linux-x86_64'
HARNESS = ROOT.parent / 'jacBuilder'
DISPATCH = ROOT / 'script/dataset/revdev/dispatch.jac'
SYSTEM = '''You are a Jac coding agent using JacCoder tools. Use the supplied tools directly.
Read existing definitions and imported dependencies before implementing callers. Reuse
unchanged reads already in this conversation; refresh a file if it changed. For a resumed
project inspect its saved plan and relevant source. Complete all planned scaffolds before
implementing bodies. Use raise NotImplementedError(); for scaffold bodies. Verify behavior
with actual tests. Never claim tests passed without a result. Tool write/edit automatically
checks Jac syntax; avoid immediately repeating that same check. Jac version is 0.34.27.
All paths must stay inside the given workspace. Do not install packages or access network.
'''

# Functions ===============================================
def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def dispatch(name: str, arguments: dict, workspace: Path, out: Path, phase='implement') -> dict:
    schemas = {t['function']['name']: t['function'] for t in json.loads((RUN/'tools.json').read_text())}
    validate_call({'kind':'tool','name':name,'args':arguments,'summary':''},schemas,workspace)
    out.mkdir(parents=True, exist_ok=True)
    call = out/'call.json'; result = out/'result.json'
    dump(call, {'name':name,'args':arguments,'workspace':str(workspace),'phase':phase})
    ex = jac_cli.execute(['run',str(DISPATCH)],jac=JAC,cwd=HARNESS,timeout=90,
        env={'REVDEV_CALL':str(call),'REVDEV_RESULT':str(result),'JACCODER_WEB_MODE':'1','REVDEV_JAC':JAC})
    dump(out/'execution.json',vars(ex))
    if not ex.ok or not result.exists():
        raise RuntimeError(f'JacCoder dispatch failed: {out}')
    return json.loads(result.read_text())


def read_history(workspace: Path, files: list[str], out: Path) -> list[dict]:
    history=[]
    for i,name in enumerate(files):
        args={'file_path':str(workspace/name),'offset':0,'limit':400}
        result=dispatch('read_file',args,workspace,out/str(i))
        history += [{'role':'assistant','content':'','tool_calls':[{'id':f'seed{i}','type':'function','function':{'name':'read_file','arguments':args}}]},
                    {'role':'tool','tool_call_id':f'seed{i}','content':result['content']}]
    return history


def setup(workspace: Path, files: dict) -> None:
    workspace.mkdir(parents=True,exist_ok=True)
    for name,content in files.items():
        p=workspace/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)


def prepare(out: Path) -> None:
    fixtures={
        'rates.jac':'def fee(cents: int) -> int { return cents // 10; }\n',
        'invoice.jac':'import from .rates { fee }\ndef total(cents: int) -> int { raise NotImplementedError(); }\n',
        'test_invoice.jac':'import from .invoice { total }\ntest "total" { assert total(100) == 110; assert total(0) == 0; }\n',
        '.jaccoder/build_plan.json':json.dumps({'files':['rates.jac','invoice.jac','test_invoice.jac'],'remaining':['implement total using fee','run test_invoice.jac']})}
    definitions=[
        ('dependency','Implement total(cents) as cents + fee(cents). invoice.jac has been read; rates.jac has not.', ['invoice.jac'],['read_file'],['rates.jac']),
        ('cached','Implement total(cents) as cents + fee(cents). The file contents below are complete and unchanged; Jac syntax is already known.', ['invoice.jac','rates.jac'],['edit_code','write_code'],['invoice.jac']),
        ('stale','Implement total(cents) using fee. After the reads below, rates.jac was changed by another developer. Its latest signature is unknown.', ['invoice.jac','rates.jac'],['read_file'],['rates.jac']),
        ('resume','Resume this project. The handoff only says total is unfinished. The saved plan is .jaccoder/build_plan.json; no files have been inspected in this session.', [],['read_file'],['.jaccoder/build_plan.json','invoice.jac']),
        ('verify','total is implemented and its automatic syntax check passed. test_invoice.jac exists. Verify behavior now before reporting success.', ['invoice.jac','rates.jac','test_invoice.jac'],['run_command'],[]),
        ('scaffold','Plan: rates.jac, invoice.jac, report.jac. Scaffold phase: report.jac is still missing. Create its import of total and def render(cents: int) -> str signature with a stub body. All other scaffolds exist; do not implement bodies yet.', ['invoice.jac'],['write_code'],['report.jac'])]
    cases=[]
    for name,request,reads,expected,paths in definitions:
        ws=(out/'fixtures'/name).resolve();files=dict(fixtures)
        if name=='verify':files['invoice.jac']=files['invoice.jac'].replace('raise NotImplementedError();','return cents + fee(cents);')
        setup(ws,files)
        messages=[{'role':'system','content':SYSTEM},{'role':'user','content':f'Workspace: {ws}\n{request}'}]
        messages+=read_history(ws,reads,out/'seed_results'/name)
        if name=='stale':
            (ws/'rates.jac').write_text('def fee(cents: int, premium: bool) -> int { return cents // 20 if premium else cents // 10; }\n')
            messages.append({'role':'user','content':'rates.jac changed after the last read. Continue from the current workspace.'})
        messages.append({'role':'user','content':'Take the next tool action now.'})
        cases.append({'id':name,'kind':'action','messages':messages,'expected_tools':expected,'expected_paths':paths,'workspace':str(ws)})
    for name,request in [('library','Build a local library loan tracker. Track books, borrowers and loans; reject lending a book already on loan, and support returns. Provide a simple UI and tests, no external services.'),('pantry','Build a pantry checklist with item names and quantities. Support adding, changing quantity, removing items, and filtering low stock. Keep data across restarts and provide a simple UI. No AI or external API is needed.')]:
        cases.append({'id':'plan_'+name,'kind':'plan','messages':[{'role':'system','content':'Plan a Jac application: files, public interfaces, dependencies, scaffold order and verification. Do not include implementation bodies.'},{'role':'user','content':request}]})
    rollout={'rates.jac':fixtures['rates.jac'],'invoice.jac':fixtures['invoice.jac'],'test_invoice.jac':fixtures['test_invoice.jac']}
    second={'labels.jac':'def clean(text: str) -> str { return text.strip().lower(); }\n','greeting.jac':'import from .labels { clean }\ndef greet(text: str) -> str { raise NotImplementedError(); }\n','test_greeting.jac':'import from .greeting { greet }\ntest "greet" { assert greet("  ADA  ") == "Hello ada"; assert greet(" ") == "Hello guest"; }\n'}
    rollouts=[{'id':'invoice','files':rollout,'target':'invoice.jac','dependency':'rates.jac','request':'Implement total(cents) using the existing fee function: return cents plus its fee. Inspect definitions before edits, preserve the dependency and verify with test_invoice.jac.','test':'test_invoice.jac','oracle':rollout['invoice.jac'].replace('raise NotImplementedError();','return cents + fee(cents);')},
        {'id':'greeting','files':second,'target':'greeting.jac','dependency':'labels.jac','request':'Implement greet(text) using the existing clean function. Return "Hello " plus the cleaned text, or "Hello guest" if it is empty. Inspect definitions before edits, preserve the dependency and verify with test_greeting.jac.','test':'test_greeting.jac','oracle':second['greeting.jac'].replace('raise NotImplementedError();','name: str = clean(text); return "Hello " + (name if name else "guest");')}]
    for case in rollouts:
        ws=(out/'oracle'/case['id']).resolve();setup(ws,case['files']);(ws/case['target']).write_text(case['oracle'])
        result=jac_cli.execute(['test',case['test']],jac=JAC,cwd=ws,timeout=40)
        dump(out/'oracle'/case['id']/'execution.json',vars(result))
        if not result.ok or '1 passed' not in result.stdout:raise RuntimeError(f'Fixture oracle failed: {case["id"]}')
    dump(out/'suite.json',{'cases':cases,'rollouts':rollouts,'note':'New synthetic behavioral probes, frozen before either model runs. Oracle code is evaluator-only; not supplied to models. Not a repository-held-out benchmark.'})
    print('Prepared',len(cases),'fixed prompts and',len(rollouts),'live tasks',flush=True)


def parse_calls(text: str, schemas: dict) -> list[dict]:
    calls=[]
    for block in re.findall(r'<tool_call>(.*?)</tool_call>',text,re.S):
        match=re.search(r'<function=([^>]+)>(.*?)</function>',block,re.S)
        if match:
            name,body=match.groups();args={}
            for key,value in re.findall(r'<parameter=([^>]+)>(.*?)</parameter>',body,re.S):
                value=value.strip('\n')
                typ=schemas.get(name,{}).get('parameters',{}).get('properties',{}).get(key,{}).get('type')
                if typ == 'boolean' and value in ('True','False','true','false'):
                    args[key]=value.lower() == 'true'
                else:
                    args[key]=json.loads(value) if typ in ('integer','number','boolean','array','object') else value
        else:
            data=json.loads(block);name=data['name'];args=data['arguments']
        calls.append({'name':name,'arguments':args})
    return calls


def run(out: Path, model_path: str, tag: str, feedback: bool = False) -> None:
    from utils.model import load_model
    import torch
    tools=json.loads((RUN/'tools.json').read_text());schemas={t['function']['name']:t['function'] for t in tools}
    suite=json.loads((out/'suite.json').read_text());dest=out/tag;dest.mkdir(parents=True,exist_ok=False)
    model,tok=load_model(model_path,16384,True)
    dump(dest/'config.json',{'model':model_path,'suite_sha256':hashlib.sha256((out/'suite.json').read_bytes()).hexdigest(),'feedback_rollouts':feedback,'greedy':True,'max_new_tokens':1024,'max_seq_length':16384,'tools_sha256':hashlib.sha256((RUN/'tools.json').read_bytes()).hexdigest()})
    def generate(messages,with_tools):
        inputs=tok.apply_chat_template(messages,tools=tools if with_tools else None,tokenize=True,add_generation_prompt=True,enable_thinking=False,return_tensors='pt',return_dict=True).to('cuda')
        n=inputs['input_ids'].shape[-1]
        if n+1024>16384:raise ValueError('Context would exceed budget; refusing truncation')
        started=time.time()
        with torch.inference_mode():output=model.generate(**inputs,max_new_tokens=1024,do_sample=False,repetition_penalty=1.05,use_cache=True,pad_token_id=tok.pad_token_id)
        ids=output[0,n:];raw=tok.decode(ids,skip_special_tokens=False)
        return {'prediction':raw,'prompt_tokens':n,'output_tokens':len(ids),'at_token_cap':len(ids)>=1024,'seconds':time.time()-started}
    records=[]
    for case in ([] if feedback else suite['cases']):
        row={'id':case['id'],'kind':case['kind'],**generate(case['messages'],case['kind']=='action')}
        if case['kind']=='action':
            try:
                calls=parse_calls(row['prediction'],schemas)
                for c in calls:validate_call({'kind':'tool','name':c['name'],'args':c['arguments'],'summary':''},schemas,Path(case['workspace']))
                row['calls']=calls;row['schema_valid']=bool(calls)
                row['behavior_pass']=bool(calls) and all(c['name'] in case['expected_tools'] and (not case['expected_paths'] or any(c['arguments'].get('file_path','').endswith('/'+p) for p in case['expected_paths'])) for c in calls)
                if case['id']=='verify':row['behavior_pass'] &= all('jac test' in c['arguments'].get('command','') for c in calls)
                if case['id']=='scaffold':row['behavior_pass'] &= all('raise NotImplementedError();' in c['arguments'].get('content','') for c in calls)
            except (ValueError,KeyError,TypeError) as ex:
                row.update(schema_valid=False,behavior_pass=False,parse_error=str(ex))
            except jsonschema.ValidationError as ex:
                row.update(schema_valid=False,behavior_pass=False,parse_error=ex.message)
        records.append(row);dump(dest/'predictions.json',records);print(tag,case['id'],row.get('behavior_pass','plan'),flush=True)
    for case in suite['rollouts']:
        ws=(dest/'workspaces'/case['id']).resolve();setup(ws,case['files'])
        policy = '\nrun_command permits only ls -la, pwd, cat of one workspace file, or jac check/test/build/run commands. Use read_file instead of sed. Set workdir to the workspace; no shell chaining or absolute alternate jac binaries. Denied calls return real adapter errors; correct them and continue.' if feedback else ''
        messages=[{'role':'system','content':SYSTEM+policy},{'role':'user','content':f'Workspace: {ws}\nFiles: {list(case["files"])}\n{case["request"]}'}];events=[];reads=set();read_counts={};writes=0;inspected=True;tested=False
        for step in range(6):
            row=generate(messages,True);event={'step':step,**row};events.append(event)
            try:
                calls=parse_calls(row['prediction'],schemas);event['calls']=calls
                if not calls:break
                messages.append({'role':'assistant','content':'','tool_calls':[{'id':f'{step}_{i}','type':'function','function':c} for i,c in enumerate(calls)]})
                observed_before_turn=set(reads)
                for i,c in enumerate(calls):
                    path=Path(c['arguments'].get('file_path','')).name
                    try:
                        result=dispatch(c['name'],c['arguments'],ws,dest/'tool_results'/case['id']/f'{step}_{i}')
                    except (ValueError, jsonschema.ValidationError) as ex:
                        if not feedback:raise
                        result={'executed':False,'origin':'adapter_validation','content':str(ex)}
                    event.setdefault('results',[]).append(result)
                    if result.get('executed'):
                        if c['name'] in ('edit_code','write_code'):
                            writes+=1;inspected &= {case['target'],case['dependency']} <= observed_before_turn
                        if c['name']=='read_file':reads.add(path);read_counts[path]=read_counts.get(path,0)+1
                        if c['name']=='run_command' and 'jac test' in c['arguments'].get('command',''):tested=True
                    messages.append({'role':'tool','tool_call_id':f'{step}_{i}','content':result['content']})
            except (ValueError,KeyError,TypeError,RuntimeError) as ex:
                event['execution_error']=str(ex);break
            except jsonschema.ValidationError as ex:
                event['execution_error']=ex.message;break
            finally:dump(dest/(case['id']+'-events.json'),events)
        # Evaluate in a fresh copy, restoring evaluator-owned test and dependency.
        check=(dest/'checks'/case['id']).resolve();setup(check,case['files']);(check/case['target']).write_text((ws/case['target']).read_text())
        result=jac_cli.execute(['test',case['test']],jac=JAC,cwd=check,timeout=40)
        dump(dest/(case['id']+'-check.json'),vars(result))
        row={'id':case['id'],'kind':'rollout','test_pass':result.ok and '1 passed' in result.stdout,'read_before_write':bool(writes) and inspected,'writes':writes,'agent_ran_tests':tested,'read_counts':read_counts,'steps':len(events)}
        records.append(row);dump(dest/'predictions.json',records);print(tag,row,flush=True)


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--prepare',action='store_true');p.add_argument('--model');p.add_argument('--tag');p.add_argument('--feedback-rollouts',action='store_true');args=p.parse_args()
    if args.prepare:prepare(args.out.resolve())
    else:run(args.out.resolve(),args.model,args.tag,args.feedback_rollouts)

# Run =====================================================
if __name__=='__main__':main()
