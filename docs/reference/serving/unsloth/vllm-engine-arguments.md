> For the complete documentation index, see [llms.txt](https://unsloth.ai/docs/llms.txt). Markdown versions of documentation pages are available by appending `.md` to page URLs; this page is available as [Markdown](https://unsloth.ai/docs/basics/inference-and-deployment/vllm-guide/vllm-engine-arguments.md).

# vLLM Engine Arguments

vLLM engine arguments, flags, options for serving models on vLLM.

<table><thead><tr><th width="212.9000244140625">Argument</th><th>Example and use-case</th></tr></thead><tbody><tr><td><strong><code>--gpu-memory-utilization</code></strong></td><td>Default 0.9. How much VRAM usage vLLM can use. Reduce if going out of memory. Try setting this to 0.95 or 0.97.</td></tr><tr><td><strong><code>--max-model-len</code></strong></td><td>Set maximum sequence length. Reduce this if going out of memory! For example set <strong><code>--max-model-len 32768</code></strong> to use only 32K sequence lengths.</td></tr><tr><td><strong><code>--quantization</code></strong></td><td>Use fp8 for dynamic float8 quantization. Use this in tandem with <strong><code>--kv-cache-dtype</code></strong> fp8 to enable float8 KV cache as well.</td></tr><tr><td><strong><code>--kv-cache-dtype</code></strong></td><td>Use <code>fp8</code> for float8 KV cache to reduce memory usage by 50%.</td></tr><tr><td><strong><code>--port</code></strong></td><td>Default is 8000. How to access vLLM's localhost ie http://localhost:8000</td></tr><tr><td><strong><code>--api-key</code></strong></td><td>Optional - Set the password (or no password) to access the model.</td></tr><tr><td><strong><code>--tensor-parallel-size</code></strong></td><td>Default is 1. Splits model across tensors. Set this to how many GPUs you are using - if you have 4, set this to 4. 8, then 8. You should have NCCL, otherwise this might be slow.</td></tr><tr><td><strong><code>--pipeline-parallel-size</code></strong></td><td>Default is 1. Splits model across layers. Use this with <strong><code>--pipeline-parallel-size</code></strong> where TP is used within each node, and PP is used across multi-node setups (set PP to number of nodes)</td></tr><tr><td><strong><code>--enable-lora</code></strong></td><td>Enables LoRA serving. Useful for serving Unsloth finetuned LoRAs.</td></tr><tr><td><strong><code>--max-loras</code></strong></td><td>How many LoRAs you want to serve at 1 time. Set this to 1 for 1 LoRA, or say 16. This is a queue so LoRAs can be hot-swapped.</td></tr><tr><td><strong><code>--max-lora-rank</code></strong></td><td>Maximum rank of all LoRAs. Possible choices are <code>8</code>, <code>16</code>, <code>32</code>, <code>64</code>, <code>128</code>, <code>256</code>, <code>320</code>, <code>512</code></td></tr><tr><td><strong><code>--dtype</code></strong></td><td>Allows <code>auto</code>, <code>bfloat16</code>, <code>float16</code> Float8 and other quantizations use a different flag - see <code>--quantization</code></td></tr><tr><td><strong><code>--tokenizer</code></strong></td><td>Specify the tokenizer path like <code>unsloth/gpt-oss-20b</code> if the served model has a different tokenizer.</td></tr><tr><td><strong><code>--hf-token</code></strong></td><td>Add your HuggingFace token if needed for gated models</td></tr><tr><td><strong><code>--swap-space</code></strong></td><td>Default is 4GB. CPU offloading usage. Reduce if you have VRAM, or increase for low memory GPUs.</td></tr><tr><td><strong><code>--seed</code></strong></td><td>Default is 0 for vLLM</td></tr><tr><td><strong><code>--disable-log-stats</code></strong></td><td>Disables logging like throughput, server requests.</td></tr><tr><td><strong><code>--enforce-eager</code></strong></td><td>Disables compilation. Faster to load, but slower for inference.</td></tr><tr><td><strong><code>--disable-cascade-attn</code></strong></td><td>Useful for Reinforcement Learning runs for vLLM &#x3C; 0.11.0, as Cascade Attention was slightly buggy on A100 GPUs (Unsloth fixes this)</td></tr></tbody></table>

### :tada:Float8 Quantization

For example to host Llama 3.3 70B Instruct (supports 128K context length) with Float8 KV Cache and quantization, try:

```bash
vllm serve unsloth/Llama-3.3-70B-Instruct \
    --quantization fp8 \
    --kv-cache-dtype fp8 \
    --gpu-memory-utilization 0.97 \
    --max-model-len 65536
```

### :shaved\_ice:LoRA Hot Swapping / Dynamic LoRAs

To enable LoRA serving for at most 4 LoRAs at 1 time (these are hot swapped / changed), first set the environment flag to allow hot swapping:

See our [LoRA Hot Swapping Guide](/docs/basics/inference-and-deployment/vllm-guide/lora-hot-swapping-guide.md) for more details.


---

# Agent Instructions
This documentation is published with GitBook. GitBook is the documentation platform designed so that both humans and AI agents can read, navigate, and reason over technical content effectively. Learn more at gitbook.com.

## Querying This Documentation
If you need additional information that is not directly available in this page, you can query the documentation by asking a question.

Perform an HTTP GET request on the following URL with the `ask` and `goal` query parameters:

```
GET https://unsloth.ai/docs/basics/inference-and-deployment/vllm-guide/vllm-engine-arguments.md?ask=<question>&goal=<user_goal>
```

`ask` is the immediate question: it should be specific, self-contained, and written in natural language.
`goal` is what the user is ultimately trying to achieve, the reason they need the answer. Sharing it helps GitBook give you a better, more relevant answer. A goal is most helpful when it describes the outcome the user wants rather than restating the question. For example, with `ask=how do I create an API token`, a goal like `automate deployments from our CI pipeline` lets GitBook tailor the answer to that use case.

The response will contain a direct answer to the question and relevant excerpts and sources from the documentation.

Use this mechanism when the answer is not explicitly present in the current page, you need clarification or additional context, or you want to retrieve related documentation sections.
