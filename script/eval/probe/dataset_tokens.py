"""Measure full-context and loss-bearing tokens using the actual packed SFT mask."""

import argparse, json, statistics, sys
from pathlib import Path

import unsloth
from transformers import AutoTokenizer

sys.path.append(str(Path(__file__).resolve().parents[2]))
from train.sft import chat_inputs, tokenize_with_assistant_mask

# Functions ===============================================
def summarize(rows: list[dict]) -> dict:
    lengths = [r['tokens'] for r in rows]
    trained = [r['loss_tokens'] for r in rows]
    total, loss = sum(lengths), sum(trained)
    return {'records':len(rows),'total_tokens':total,'loss_tokens':loss,
            'mean_tokens':statistics.mean(lengths) if lengths else 0,
            'median_tokens':statistics.median(lengths) if lengths else 0,
            'mean_loss_tokens':statistics.mean(trained) if trained else 0,
            'loss_fraction':loss/total if total else 0,
            'min_tokens':min(lengths,default=0),'max_tokens':max(lengths,default=0)}


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--files',type=Path,nargs='+',required=True)
    p.add_argument('--tokenizer',default='output/model/JacLLM-SFT-Ornith-9B-trajectory-bf16')
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    tok=AutoTokenizer.from_pretrained(args.tokenizer,local_files_only=True)
    rows=[]
    for path in args.files:
        for i,line in enumerate(path.read_text().splitlines()):
            row=json.loads(line);messages,tools=chat_inputs(row)
            encoded=tokenize_with_assistant_mask(messages,tools,tok,1_000_000)
            n=len(encoded['input_ids']);loss=sum(x!=-100 for x in encoded['labels'])
            item={'file':str(path),'row':i,'task_type':row.get('meta',{}).get('task_type'),
                  'tokens':n,'loss_tokens':loss,'context_only_tokens':n-loss,
                  'eligible_16k':n<=16384,'eligible_64k':n<=65536,
                  'assistant_turns':sum(m['role']=='assistant' for m in messages)}
            rows.append(item)
            print(json.dumps(item),flush=True)
    report={'tokenizer':args.tokenizer,'mask':'train.sft.tokenize_with_assistant_mask; no truncation; weight=0 excluded',
            'all':summarize(rows),'eligible_16k':summarize([r for r in rows if r['eligible_16k']]),
            'by_task':{kind:summarize([r for r in rows if r['task_type']==kind]) for kind in sorted({r['task_type'] for r in rows})},'rows':rows}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))

# Run =====================================================
if __name__=='__main__':main()
