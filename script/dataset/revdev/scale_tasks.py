"""Prepare AST-grounded module tasks and executable oracles from three repositories."""

import argparse, hashlib, json, re, subprocess, sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils import jac_cli

# Setting =================================================
ROOT = Path('dataset/raw/revdev/scaleup_v1')
JAC = '/tmp/jac-0.34.27-linux-x86_64'

# Functions ===============================================
def specs() -> list[dict]:
    rows=[]
    def add(repo,name,deps,request,cases):
        rows.append(dict(repo=repo,name=name,deps=deps,request=request,cases=cases))
    add('mindcraft','clamp01',[], 'Clamp island coordinates to the inclusive range 0.08 through 0.92, leaving interior values unchanged.', ['clamp01(-1.0)','clamp01(0.08)','clamp01(0.5)','clamp01(0.92)','clamp01(8.0)'])
    add('mindcraft','sanitize_tools',['TOOLS'],'Filter tool IDs against TOOLS, remove duplicates while preserving first occurrence order, and default to breathe/name_it when nothing remains.', ['sanitize_tools([])','sanitize_tools(["breathe","bad","water","breathe"])','sanitize_tools(["bogus"])'])
    add('mindcraft','sanitize_intentions',[], 'Trim intentions, discard strings shorter than three characters, clip long strings to 90 characters then rstrip, deduplicate and retain at most three valid intentions in input order.', ['sanitize_intentions([])','sanitize_intentions([" a ","  abc  ","abc","def","ghi","jkl"])','sanitize_intentions(["x" * 100])'])
    add('mindcraft','is_crisis_language',[], 'Add a case-insensitive substring detector for these literal signals: kill myself, end my life, want to die, suicide, hurt myself, self harm, self-harm, can\'t go on, cannot go on, ending it all, no reason to live. Return a bool; this is a text matcher, not clinical classification.', ['is_crisis_language("I am okay")','is_crisis_language("I CANNOT GO ON")','is_crisis_language("mentions self-harm")','is_crisis_language("")'])
    add('mindcraft','theme_variants',['TRANSFORM_PAIRS'], 'Return ordered valid unique asset IDs for a theme. anxiety/default: dark_cloud,tangled_knot,fog_patch; overwhelm: tangled_knot,heavy_stone,fog_patch; sadness: heavy_stone,dark_cloud,windy_leaves; frustration: windy_leaves,tangled_knot,dark_cloud; uncertainty: fog_patch,windy_leaves,dark_cloud. Filter against TRANSFORM_PAIRS; if empty use the default three.', [f'theme_variants("{x}")' for x in ['anxiety','overwhelm','sadness','frustration','uncertainty','other']])
    common=['VOCAB_ANCHORS','BRAND_ALIASES','wr_strip_dose','wr_resolve_ingredient']
    add('alongside','wr_strip_dose',[], 'Strip a pasted regimen down to its initial name: after trimming, consume an initial letter followed by letters, spaces, hyphens or apostrophes, stop before dose digits or other characters, then trim. If no initial name matches, return the trimmed input.', ['wr_strip_dose("  Imatinib 400mg daily ")','wr_strip_dose("St John\'s Wort 100mg")','wr_strip_dose("400 mg")','wr_strip_dose("")'])
    add('alongside','wr_resolve_ingredient',common[:-1], 'Resolve the stripped lowercase ingredient name through BRAND_ALIASES first, then the ingredient entries of VOCAB_ANCHORS. Return the known key or empty string, without guessing.', ['wr_resolve_ingredient("GLEEVEC 400mg")','wr_resolve_ingredient("imatinib")','wr_resolve_ingredient("unknown123")'])
    add('alongside','wr_resolve_symptom',['VOCAB_ANCHORS'],'Resolve an exact symptom key using only symptom entries in VOCAB_ANCHORS. Return empty string on a miss; do not normalize or guess.', ['wr_resolve_symptom("fever")','wr_resolve_symptom("unknown")','wr_resolve_symptom("imatinib")','wr_resolve_symptom("Fever")'])
    add('alongside','wr_parse_regimen',common,'Parse nonempty trimmed lines of a regimen using wr_resolve_ingredient. Known lines become anchors with key/kind=ingredient/raw; unknown lines enter needs_review unchanged after trimming. Return both lists and preserve order.', ['wr_parse_regimen("  Gleevec 400mg\n\n unknown  ")','wr_parse_regimen("")','wr_parse_regimen("Zofran 4mg\nImatinib daily")'])
    add('alongside','wr_parse_threshold',['VOCAB_ANCHORS','wr_resolve_symptom'], 'Parse case-insensitive fever/temperature/pain/nausea followed later by over, above, greater than or > and a nonnegative integer or decimal. Normalize temperature to fever, resolve anchor_key with wr_resolve_symptom; return metric,anchor_key,operator=>,threshold float,raw original text. Return {} without a match.', ['wr_parse_threshold("call if fever over 100.4")','wr_parse_threshold("Temperature above 38")','wr_parse_threshold("within 2 hours after food")','wr_parse_threshold("pain greater than 4")'])
    add('alongside','wr_parse_timing',[], 'Parse case-insensitive within N minute(s)/hour(s) before/after food anywhere in text. Convert hours to minutes, return window_minutes,relation=before_food/after_food,raw. Return {} when there is no match.', ['wr_parse_timing("within 30 minutes after food")','wr_parse_timing("Within 2 HOURS BEFORE food")','wr_parse_timing("anything")','wr_parse_timing("within 0 minutes after food")'])
    add('alongside','wr_contains_emergency_phrase',['EMERGENCY_PHRASES'], 'Case-insensitively check whether any configured EMERGENCY_PHRASES literal substring occurs. This is text parsing, not a medical decision.', ['wr_contains_emergency_phrase("CALL 911 now")','wr_contains_emergency_phrase("call tomorrow")','wr_contains_emergency_phrase("go to the ER")','wr_contains_emergency_phrase("")'])
    add('alongside','wr_parse_instruction',['VOCAB_ANCHORS','EMERGENCY_PHRASES','wr_resolve_symptom','wr_contains_emergency_phrase','wr_parse_threshold','wr_parse_timing'], 'Classify text using existing parsers: threshold takes priority over timing; add kind and is_emergency to the selected parsed dict. Otherwise return kind=unstructured, raw original text and the emergency flag.', ['wr_parse_instruction("call 911 if fever over 100.4")','wr_parse_instruction("within 2 hours after food")','wr_parse_instruction("hello")'])
    add('alongside','wr_rank_conflict_candidates',[], 'Discard candidates with truthy last_examined. Stable-rank remaining entries: shared_anchor first, then reinforced_this_turn, then others. First budget entries become examine and the rest queue; return both lists and their counts. Missing flags are false; negative budgets examine nothing.', ['wr_rank_conflict_candidates([],2)','wr_rank_conflict_candidates([{"id":"a"},{"id":"b","shared_anchor":True},{"id":"c","reinforced_this_turn":True},{"id":"d","last_examined":"x"}],2)','wr_rank_conflict_candidates([{"id":"a"}],-1)'])
    add('aegis','contains_any',[], 'Return the original spelling of the first marker whose case-insensitive substring occurs in text; preserve marker order. Return empty string if none. Empty markers follow normal substring behavior.', ['contains_any("Alpha BETA",["beta","ALPHA"])','contains_any("xyz",["a","b"])','contains_any("",[])'])
    rules=[('rule_amount_within_auto_limit','payment amount exceeds max_auto_payment','EV-POLICY-LIMIT'),('rule_destination_matches_vendor_record','payment destination differs from verified_destination','EV-VENDOR-DEST'),('rule_no_secrets_in_memo','memo contains a case-insensitive marker from params.secret_markers','EV-UNTRUSTED-TEXT'),('rule_no_untrusted_instruction_override','uses_untrusted_input is true','EV-UNTRUSTED-TEXT,EV-INVOICE-TOTAL'),('rule_vendor_must_be_verified','vendor_status is not exactly verified','EV-VENDOR-STATUS')]
    for name,condition,ids in rules:
        cases=[]
        for pays,amount,dest,memo,untrusted,status in [('True',2000.0,'bad','SECRET','True','pending'),('True',50.0,'good','okay','False','verified'),('False',2000.0,'bad','SECRET','True','pending')]:
            call=f'{name}(BranchSim({amount},"{dest}","{memo}",{pays},{untrusted}), VerifiedFacts("good",50.0,"{status}",100.0), {{"secret_markers":["secret"]}})'
            cases += [f'{call}["violated"]',f'{call}["evidence_ids"]']
        add('aegis',name,['BranchSim','VerifiedFacts']+(['contains_any'] if 'secrets' in name else []),f'Return violated/reason/evidence_ids. Violate only when sim.pays and {condition}; use evidence IDs {ids} in that order. Otherwise false, empty reason and empty evidence list. Use a nonempty explanatory reason on violation.',cases)
    deps=['BranchSim','VerifiedFacts','contains_any']+[r[0] for r in rules]
    add('aegis','evaluate_rule',deps,'Dispatch amount_within_auto_limit, destination_matches_vendor_record, no_secrets_in_memo, no_untrusted_instruction_override, vendor_must_be_verified to their existing rule functions. Unknown rules pass with no evidence and a reason naming the unknown rule.', ['evaluate_rule("amount_within_auto_limit",BranchSim(200.0,"good","",True,False),VerifiedFacts("good",10.0,"verified",100.0),{})["violated"]','evaluate_rule("unknown",BranchSim(0.0,"","",False,False),VerifiedFacts("",0.0,"verified",0.0),{})["evidence_ids"]'])
    return rows


def prepare(root: Path) -> None:
    slices=json.loads((root/'private/slices.json').read_text())
    repos={name:row for name,row in zip(['mindcraft','alongside','aegis'],slices)}
    report=[]
    for index,spec in enumerate(specs()):
        info=repos[spec['repo']];source=Path(info['file']);lines=source.read_text().splitlines(keepends=True)
        entries={}
        for item in info['items']:
            names=item['names']
            if item['kind']=='GlobalVars':
                match=re.match(r'glob\s+(\w+)',item['code']);names=[match[1]] if match else []
            for name in names:entries[name]={**item,'source':''.join(lines[item['line']-1:item['end_line']])}
        target=entries[spec['name']];dep_code='import re;\n' if spec['repo']=='alongside' else ''
        dep_code+='\n'.join(entries[n]['source'] for n in spec['deps']) or '# No local dependencies.\n'
        imports=('import re;\n' if spec['repo']=='alongside' else '')
        if spec['deps']:imports+='import from dependency { '+', '.join(spec['deps'])+' }\n'
        signature=target['source'].split('{',1)[0].strip()
        app=imports+target['source'];stub=imports+signature+' { raise NotImplementedError(); }\n'
        path=(root/'private/tasks'/spec['name']).resolve();path.mkdir(parents=True,exist_ok=True)
        oracle=path/'oracle';oracle.mkdir(exist_ok=True)
        (oracle/'jac.toml').write_text('[project]\nname = "revdev-module"\nversion = "0.1.0"\njac-version = "==0.34.27"\n' + jac_cli.SERVER_TOML)
        (oracle/'dependency.jac').write_text(dep_code);(oracle/'app.jac').write_text(app)
        probe='import json;\nimport from app { '+spec['name']+' }\n'
        if spec['deps']:probe+='import from dependency { '+', '.join(spec['deps'])+' }\n'
        case_code = ','.join(c.replace(chr(10), chr(92)+'n') for c in spec['cases'])
        probe += 'with entry { values = [' + case_code + ']; print(json.dumps(values)); }' + chr(10)
        (oracle/'probe.jac').write_text(probe)
        result=jac_cli.execute(['run','probe.jac'],jac=JAC,cwd=oracle,timeout=60)
        (path/'oracle-execution.json').write_text(json.dumps(vars(result),indent=2))
        try:expected=json.loads(result.stdout.strip().splitlines()[-1]) if result.ok else None
        except (ValueError,IndexError):expected=None
        if expected is None:
            report.append({'name':spec['name'],'status':'oracle_failed'});continue
        expected_json=json.dumps(json.dumps(expected,ensure_ascii=False),ensure_ascii=False)
        test=probe.replace('print(json.dumps(values));',f'expected = json.loads({expected_json}); assert values == expected; print("REVDEV_CHECK_OK");')
        (oracle/'verify.jac').write_text(test)
        check=jac_cli.execute(['run','verify.jac'],jac=JAC,cwd=oracle,timeout=60)
        (path/'oracle-check.json').write_text(json.dumps(vars(check),indent=2))
        if not check.ok or 'REVDEV_CHECK_OK' not in check.stdout:
            report.append({'name':spec['name'],'status':'oracle_check_failed'});continue
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source.parent,text=True).strip()
        mode=('implement','resume','repair')[index%3]
        initial=stub if mode!='repair' else imports+signature+' { raise ValueError("unfinished migration"); }\n'
        plan={'files':[{'path':'dependency.jac','status':'done'},{'path':'app.jac','status':'pending'},{'path':'verify.jac','status':'done'}], 'dependency_graph':{'app.jac':['dependency.jac'] if spec['deps'] else []},'target':spec['name'],'signature':signature,'verify':'jac run verify.jac'}
        task={**spec,'mode':mode,'split':'valid' if spec['repo']=='aegis' else 'train','source_file':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'commit':commit,'span':{'line':target['line'],'end_line':target['end_line']},'signature':signature,'plan':plan,'initial_files':{'jac.toml':(oracle/'jac.toml').read_text(),'app.jac':initial,'dependency.jac':dep_code,'verify.jac':test,'.jaccoder/build_plan.json':json.dumps(plan,indent=2)},'reference_app':app}
        (path/'task.json').write_text(json.dumps(task,indent=2));report.append({'name':spec['name'],'status':'ready','mode':mode,'split':task['split'],'path':str(path/'task.json')})
        print(spec['name'],'ready',flush=True)
    (root/'private/tasks-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

# Run =====================================================
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=ROOT);prepare(parser.parse_args().root)
