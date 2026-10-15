# Dataset
This folder contains dataset for finetuning LLM for Jac. Using Hugging Face format.
Where each dataset comes from: see `DATA_SOURCE.md`.

| Folder   | Purpose                  | Example          |
| -------- | ------------------------ | ---------------- |
| `raw`    | all unprocessed raw data |                  |
| `CPT`    | sequence of text         | `{"text":"..."}` |
| `SFT`    | Instruction respond pairs| Message format   |

| Format       | Explain                 | CPT | SFT |
| ------------ | ----------------------- | --- | --- |
| **jac**      | Single `.jac` code file | ⭕  | ⭕  |
| **markdown** | markdown files          | ⭕  | ⭕  |
| **repo**     | fullstack jac with docs | ⭕  | ⭕  |
| **session**  | Claude code sessions    |     | ⭕  |
| **diff**     | git diff                |     | ⭕  |

| Class         | Keywords                |
| ------------- | ----------------------- |
| **fullstack** | JSX, cl                 |
| **osp**       | walker, spawn           |
| **graph**     | node, edge              |
| **function**  | Others just basic jac   |
Not sure if we can use some tools to make more accurate classification

**SFT Task Type**
| Task Type           | Explain                                  | is_code |
| ------------------- | ---------------------------------------- | ------- |
| **code_completion** | code completion                          | ⭕      |
| **fim**             | fill in middle style (TODO)              | ⭕      |
| **py2jac**          | convert python to jac                    | ⭕      |
| **js2jac**          | convert JS to jac                        | ⭕      |
| **mcq**             | multiple choice questions                |         |
| **qa**              | answer jac concepts                      |         |
| **diff**            | given v1 and commit message, complete v2 | ⭕      |
| **session**         | Claude code session history for training |         |
| **code_fix**        | given task, broken code and compiler error, output the fixed code | ⭕      |
| **test_gen**        | given a Jac program, write a `test` suite that passes `jac test` | ⭕      |
| **tool_fim**        | agent trajectory (pi tools): find a stubbed Jac body in a repo, fill it with `edit`, `jac check` | ⭕      |
Is code means we can run jac check, jac run,...etc as validation gate.
\<TODO\> May have small set of code that has test bench
Current code may not have `with entry {}` block

# Format
## JSONL
### CPT - Continual Pre-trainning
Continual pretraining is a kind of unsupervised learning
* **Mandatory fields**
The minimum set of field required to run the training script.
```json
{"text":"YOUR_TRAINING_DATA"}
```
* **Optional fields**
Metadata, used for dataset statistics
```json
{
    "text": "YOUR_TRAINING_DATA",
    "meta": 
    {
        "source": ["code", "docs", "article", "agent", "other"],
        "format": ["jac", "markdown", "repo", "session", "diff"],
        "class":  ["function", "osp", "fullstack"]
    }
}
```

### SFT - Supervised Fine-tuning
The minimum set of field required to run the training script.
```json
{
    "messages":
    [
        {"role": "system", "context": "You are a jac lang master who help user build their jac app"},
        {"role": "user", "context": "INSTRUCTION_HERE"},
        {"role": "assistant", "context": "RESPONSE_HERE"},
    ]
}
```
* **Optional fields**
Metadata, used for dataset statistics, same as CPT.
```json
{
    "messages":[],
    "meta": []
}
```

# Format
More system and instruction templates are available at `script/dataset/template/prompt_template.json` It is better to have template for each dataset.
## Jac Function
### CPT
The following code should be in the `"text"` column.
* **Specify Jac Lang in comment**
```python
# Language: Jac
"""
Describe what does this function do.
"""
def function_name(var1 : type, var2: type) -> {
    # The complete function here
    a = 100;
}
```

### SFT
No system prompt here since the data are short.
* **Code completion**:
```json
"messages":
    [
        {"role": "user", "context": "Please implement the following Jac function based on it's docstring and signature:
        \```jac
        \"""
        Function: Fibonacci
        \"""
        def fib(n:int) -> list[int] 
        \```
        "},
        {"role": "assistant", "context": "
        \```jac
        def fib(n:int) -> list[int] {
            res: list[int] = [1,1];
            if (n<3) return res[:n];
            else {
                i = 2;
                while (i<n) {
                    res.append(res[i-1]+res[i-2]);
                    i++;
                }
            }
            return res;
        }
        \```
        "},
    ]
```

## Markdown
### CPT
Chunk the data by header or paragraph, the following content will be in `"text"` column
* **Entire file:**
```markdown
---
file: jacdocs/concepts/node_and_graph.md
title: Node
tags: [tag1, tag2]
---
# Node and Graph
## Node
A node in jac is....

```
* **Chunk**:
```markdown
> Document: `docs/graph_and_node.md` > Graph and Node (Header 1) > Node (Header 2) ...
## Node
A node in jac is....

```

### SFT
Part of the data will include system prompt. (see `script/dataset/template/prompt_template.json`)
QA set genrated by Opus.
* Conceptual QA
* Coding example
<!-- * Syntax Rules / Docs Lookup
* Docs to Example -->
```json
"messages":
    [
        {"role": "system", "context": "You are a jac lang master who help user build their jac app"},
        {"role": "user", "context": "QUESTION_GENERATED_BY_OPUS"},
        {"role": "assistant", "context": "ANSWER_GENERATED_BY_OPUS"},
    ]
```

## Repo
> Under construction. Go orange :'<

## Git Diff
> Under construction. Go orange :'<

## Session
> Under construction. Go orange :'<

## Code Fix
Source: `jac-data-gen/data/osp_repair/code_fix.jsonl` (1,004 rows). A model's failed OSP attempt paired with a
verified passing version of the same task (`jac check` + `jac test` PASS). The error is the real compiler output.
Rows over 4k tokens are dropped.
### SFT
```json
"messages":
    [
        {"role": "system", "content": "SYSTEM_PROMPT"},
        {"role": "user", "content": "TASK\n```jac\nBROKEN_CODE\n```\nCompiler error:\n```\nERROR\n```\nFix the program."},
        {"role": "assistant", "content": "```jac\nFIXED_CODE\n```"}
    ]
```

## Test Gen
Source: `jac-data-gen/data/osp_repair/test_fix.jsonl` (1,449 rows). Uses the program and its verified passing
test suite (`fixed_tests`); the broken test attempt is not used. Tests are LLM-written from the problem + program,
not snapshots of program output, so they may also appear in CPT.
### SFT
```json
"messages":
    [
        {"role": "system", "content": "SYSTEM_PROMPT"},
        {"role": "user", "content": "Write Jac tests for this program:\n```jac\nPROGRAM\n```"},
        {"role": "assistant", "content": "```jac\nTEST_SUITE\n```"}
    ]
```

## Tool FIM
Source: `raw/repo/` (all 35 apps), producer `script/dataset/sft/tool_fim.py`, dataset `sft/tool_fim/repo-all-pi`.
One or more Jac bodies in a repo file are replaced by `# TODO: implement`; the row is a synthesized
[pi](https://github.com/badlogic/pi-mono) agent trajectory that fills them. Tool results are real (the producer runs
`rg`, reads the file and runs `jac check` on the stubbed copy), and replay byte-identical through pi 1.0.4.
System prompt and tool schemas are pi's own (`script/dataset/trajectory/harness/pi.json`), so the eval must run pi
with the same flags (`--no-mcp --no-context-files --no-skills --no-extensions --no-prompt-templates`).

Trajectory: (`rg` to locate the file) → `read` → (`rg` + `read` for up to 2 cross-file symbols the body uses) →
`edit` (oldText = stub, newText = original body) → `jac check FILE 2>&1 | tail -n 3` → one-line reply.

| Variant | Prompt key (`prompt_template.json`) | Train rows | What differs |
| ------- | ----------------------------------- | ---------- | ------------ |
| path    | `tool_fim`        | 1,843 (386 with cross-file lookup) | prompt names file and symbol; starts with `read` |
| no path | `tool_fim_nopath` | 607 (117 with cross-file lookup)   | prompt names only the symbol; starts with `rg -n "def:pub NAME\b"` |
| multi   | `tool_fim_multi`  | 31                                 | 2–3 holes in one file, one `edit` call with several edits |

### SFT
`tools` and `tool_calls[].function.arguments` are JSON strings (Arrow can't hold the varying schemas);
`script/train/sft.py` parses them before the chat template. Trained tokens: every assistant turn (reply text +
tool call + `<|im_end|>`). Masked: system prompt + tool schemas, user, tool results. `weight: 0` masks an assistant turn.
```json
{
    "messages":
    [
        {"role": "system", "content": "PI_SYSTEM_PROMPT (cwd = /workspace/<repo>)"},
        {"role": "user", "content": "jac/walkers/get_stamps.jac has a stubbed-out `run`. Write the implementation so it fits the rest of the codebase."},
        {"role": "assistant", "content": "Reading jac/walkers/get_stamps.jac first.", "weight": 1,
         "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "read", "arguments": "{\"path\": \"jac/walkers/get_stamps.jac\"}"}}]},
        {"role": "tool", "tool_call_id": "call_1", "content": "FILE_WITH_STUB"},
        ...
        {"role": "assistant", "content": "`run` implemented. `jac check jac/walkers/get_stamps.jac` passes.", "weight": 1}
    ],
    "tools": "[{\"type\": \"function\", \"function\": {\"name\": \"read\", ...}}, bash, edit, write]",
    "meta": {"task_type": "tool_fim", "harness": "pi", "repo": "JacHackA2Tech/AgenticPortfolioX__POR-Jac-Enforced",
             "file": "jac/walkers/get_stamps.jac", "holes": ["run"], "tool_calls": 5, "tokens": 2228, "fp": "..."}
}
```

### Examples (train rows, rendered)
**path + cross-file lookup** (`get_stamps.jac#run`)
````
user:      jac/walkers/get_stamps.jac has a stubbed-out `run`. Write the implementation so it fits the rest of the codebase.
assistant: Reading jac/walkers/get_stamps.jac first.
           read {"path": "jac/walkers/get_stamps.jac"}
tool:      import from jac.schemas.nodes { Asset }
           import from jac.schemas.edges { StampedBy }

           walker:pub GetStamps {
               can run with Asset entry {
                   # TODO: implement
               }
           }
assistant: Let me check `StampedBy`.
           bash {"command": "rg -n \"edge(:\\w+)? StampedBy\\b\" -g \"*.jac\" ."}
tool:      ./jac/schemas/edges.jac:13:edge StampedBy {}
assistant: read {"path": "jac/schemas/edges.jac", "offset": 13, "limit": 3}
tool:      edge StampedBy {}
           edge MintedAs {}
assistant: edit {"path": "jac/walkers/get_stamps.jac", "edits": [{"oldText": "    can run with Asset entry {\n        # TODO: implement\n    }",
                 "newText": "    can run with Asset entry {\n        stamps: list[dict[str, any]] = [];\n        for s in [here ->:StampedBy:->] { ... }\n        report {\"stamps\": stamps};\n    }"}]}
tool:      Successfully replaced 1 block(s) in jac/walkers/get_stamps.jac.
assistant: Checking the file.
           bash {"command": "jac check jac/walkers/get_stamps.jac 2>&1 | tail -n 3"}
tool:        → run 'jac guide jac-types' for guidance

           ============================== 1 passed in 0.44s ===============================
assistant: `run` implemented. `jac check jac/walkers/get_stamps.jac` passes.
````

**no path** (`lib/utils.jac#cn`)
````
user:      Find `cn` and fill in its body.
assistant: Locating `cn`.
           bash {"command": "rg -n \"def:pub cn\\b\" -g \"*.jac\" ."}
tool:      ./lib/utils.jac:4:def:pub cn(*inputs: any) -> str {
assistant: Let me look at the file.
           read {"path": "lib/utils.jac"}
tool:      import from "clsx" { clsx }
           import from "tailwind-merge" { twMerge }

           def:pub cn(*inputs: any) -> str {
               # TODO: implement
           }
assistant: Implementing it now.
           edit {"path": "lib/utils.jac", "edits": [{"oldText": "def:pub cn(*inputs: any) -> str {\n    # TODO: implement\n}",
                 "newText": "def:pub cn(*inputs: any) -> str {\n    return twMerge(clsx(inputs));\n}"}]}
tool:      Successfully replaced 1 block(s) in lib/utils.jac.
assistant: bash {"command": "jac check lib/utils.jac 2>&1 | tail -n 3"}
tool:      ... 1 passed in 0.42s ...
assistant: `cn` implemented. `jac check lib/utils.jac` passes.
````

**multi** (`logs/treeUtils.jac#findNode+subagentRefFor`)
````
user:      logs/treeUtils.jac has several unimplemented bodies. Implement:
           - `findNode`
           - `subagentRefFor`
assistant: Reading logs/treeUtils.jac first.
           read {"path": "logs/treeUtils.jac"}
tool:      FILE_WITH_TWO_STUBS
assistant: edit {"path": "logs/treeUtils.jac", "edits": [{"oldText": "STUB_1", "newText": "BODY_1"}, {"oldText": "STUB_2", "newText": "BODY_2"}]}
tool:      Successfully replaced 2 block(s) in logs/treeUtils.jac.
assistant: Checking the file.
           bash {"command": "jac check logs/treeUtils.jac 2>&1 | tail -n 3"}
tool:      ... 1 passed in 0.60s ...
assistant: Done: implemented `findNode`, `subagentRefFor` in logs/treeUtils.jac; the file type-checks.
````
Reply text before a tool call is sampled from `SAY_*` in the producer; about half are empty (tool call only).
