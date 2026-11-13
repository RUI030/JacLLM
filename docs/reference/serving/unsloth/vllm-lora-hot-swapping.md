> For the complete documentation index, see [llms.txt](https://unsloth.ai/docs/llms.txt). Markdown versions of documentation pages are available by appending `.md` to page URLs; this page is available as [Markdown](https://unsloth.ai/docs/basics/inference-and-deployment/vllm-guide/lora-hot-swapping-guide.md).

# LoRA Hot Swapping Guide

### :shaved\_ice: vLLM LoRA Hot Swapping / Dynamic LoRAs

To enable LoRA serving for at most 4 LoRAs at 1 time (these are hot swapped / changed), first set the environment flag to allow hot swapping:

```bash
export VLLM_ALLOW_RUNTIME_LORA_UPDATING=True
```

Then, serve it with LoRA support:

```bash
export VLLM_ALLOW_RUNTIME_LORA_UPDATING=True
vllm serve unsloth/Llama-3.1-8B-Instruct \
    --quantization fp8 \
    --kv-cache-dtype fp8 \
    --gpu-memory-utilization 0.8 \
    --max-model-len 65536 \
    --enable-lora \
    --max-loras 4 \
    --max-lora-rank 64
```

To load a LoRA dynamically (set the lora name as well), do:

```bash
curl -X POST http://localhost:8000/v1/load_lora_adapter \
    -H "Content-Type: application/json" \
    -d '{
        "lora_name": "LORA_NAME",
        "lora_path": "/path/to/LORA"
    }'
```

To remove it from the pool:

```bash
curl -X POST http://localhost:8000/v1/unload_lora_adapter \
    -H "Content-Type: application/json" \
    -d '{
        "lora_name": "LORA_NAME"
    }'
```

For example when finetuning with Unsloth:

{% code overflow="wrap" %}

```python
from unsloth import FastLanguageModel
import torch
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "unsloth/Llama-3.1-8B-Instruct",
    max_seq_length = 2048,
    load_in_4bit = True,
)
model = FastLanguageModel.get_peft_model(model)
```

{% endcode %}

Then after training, we save the LoRAs:

```python
model.save_pretrained("finetuned_lora")
tokenizer.save_pretrained("finetuned_lora")
```

We can then load the LoRA:

{% code overflow="wrap" %}

```bash
curl -X POST http://localhost:8000/v1/load_lora_adapter \
    -H "Content-Type: application/json" \
    -d '{
        "lora_name": "LORA_NAME_finetuned_lora",
        "lora_path": "finetuned_lora"
    }'
```

{% endcode %}


---

# Agent Instructions
This documentation is published with GitBook. GitBook is the documentation platform designed so that both humans and AI agents can read, navigate, and reason over technical content effectively. Learn more at gitbook.com.

## Querying This Documentation
If you need additional information that is not directly available in this page, you can query the documentation by asking a question.

Perform an HTTP GET request on the following URL with the `ask` and `goal` query parameters:

```
GET https://unsloth.ai/docs/basics/inference-and-deployment/vllm-guide/lora-hot-swapping-guide.md?ask=<question>&goal=<user_goal>
```

`ask` is the immediate question: it should be specific, self-contained, and written in natural language.
`goal` is what the user is ultimately trying to achieve, the reason they need the answer. Sharing it helps GitBook give you a better, more relevant answer. A goal is most helpful when it describes the outcome the user wants rather than restating the question. For example, with `ask=how do I create an API token`, a goal like `automate deployments from our CI pipeline` lets GitBook tailor the answer to that use case.

The response will contain a direct answer to the question and relevant excerpts and sources from the documentation.

Use this mechanism when the answer is not explicitly present in the current page, you need clarification or additional context, or you want to retrieve related documentation sections.
