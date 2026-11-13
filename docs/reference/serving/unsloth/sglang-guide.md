> For the complete documentation index, see [llms.txt](https://unsloth.ai/docs/llms.txt). Markdown versions of documentation pages are available by appending `.md` to page URLs; this page is available as [Markdown](https://unsloth.ai/docs/basics/inference-and-deployment/sglang-guide.md).

# SGLang Deployment & Inference Guide

Guide on saving and deploying LLMs to SGLang for serving LLMs in production

You can serve any LLM or fine-tuned model via [SGLang](https://github.com/sgl-project/sglang) for low-latency, high-throughput inference. SGLang supports text, image/video model inference on any GPU setup, with support for some GGUFs.

### :computer:Installing SGLang

To install SGLang and Unsloth on NVIDIA GPUs, you can use the below in a virtual environment (which won't break your other Python libraries)

```shellscript
# OPTIONAL use a virtual environment
python -m venv unsloth_env
source unsloth_env/bin/activate

# Install Rust, outlines-core then SGLang
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env && sudo apt-get install -y pkg-config libssl-dev
pip install --upgrade pip && pip install uv
uv pip install "sglang" && uv pip install unsloth
```

For **Docker** setups run:

{% code overflow="wrap" %}

```shellscript
docker run --gpus all \
    --shm-size 32g \
    -p 30000:30000 \
    -v ~/.cache/huggingface:/root/.cache/huggingface \
    --env "HF_TOKEN=<secret>" \
    --ipc=host \
    lmsysorg/sglang:latest \
    python3 -m sglang.launch_server --model-path unsloth/Llama-3.1-8B-Instruct --host 0.0.0.0 --port 30000
```

{% endcode %}

### :bug:Debugging SGLang Installation issues

Note if you see the below, update Rust and outlines-core as specified in [#setting-up-sglang](#setting-up-sglang "mention")

{% code overflow="wrap" %}

```
hint: This usually indicates a problem with the package or the build environment.
  help: `outlines-core` (v0.1.26) was included because `sglang` (v0.5.5.post2) depends on `outlines` (v0.1.11) which depends on `outlines-core`
```

{% endcode %}

If you see a Flashinfer issue like below:

```
/home/daniel/.cache/flashinfer/0.5.2/100a/generated/batch_prefill_with_kv_cache_dtype_q_bf16_dtype_kv_bf16_dtype_o_bf16_dtype_idx_i32_head_dim_qk_64_head_dim_vo_64_posenc_0_use_swa_False_use_logits_cap_False_f16qk_False/batch_prefill_ragged_kernel_mask_1.cu:1:10: fatal error: flashinfer/attention/prefill.cuh: No such file or directory
    1 | #include <flashinfer/attention/prefill.cuh>
      |          ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
compilation terminated.
ninja: build stopped: subcommand failed.

Possible solutions:
1. set --mem-fraction-static to a smaller value (e.g., 0.8 or 0.7)
2. set --cuda-graph-max-bs to a smaller value (e.g., 16)
3. disable torch compile by not using --enable-torch-compile
4. disable CUDA graph by --disable-cuda-graph. (Not recommended. Huge performance loss)
Open an issue on GitHub https://github.com/sgl-project/sglang/issues/new/choose
```

Remove the flashinfer cache via `rm -rf .cache/flashinfer` and also the directory listed in the error message ie `rm -rf ~/.cache/flashinfer`

### :truck:Deploying SGLang models

To deploy any model like for example [unsloth/Llama-3.2-1B-Instruct](https://huggingface.co/unsloth/Llama-3.2-1B-Instruct), do the below in a separate terminal (otherwise it'll block your current terminal - you can also use tmux):

{% code overflow="wrap" %}

```shellscript
python3 -m sglang.launch_server \
    --model-path unsloth/Llama-3.2-1B-Instruct \
    --host 0.0.0.0 --port 30000
```

{% endcode %}

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2Fq3rBt5dn2PhrpvvfhSzo%2Fimage.png?alt=media&amp;token=e7a5170b-eabb-4a11-ae4b-f27a11213ae3" alt=""><figcaption></figcaption></figure>

You can then use the OpenAI Chat completions library to call the model (in another terminal or using tmux):

```python
# Install openai via pip install openai
from openai import OpenAI
import json
openai_client = OpenAI(
    base_url = "http://0.0.0.0:30000/v1",
    api_key = "sk-no-key-required",
)
completion = openai_client.chat.completions.create(
    model = "unsloth/Llama-3.2-1B-Instruct",
    messages = [{"role": "user", "content": "What is 2+2?"},],
)
print(completion.choices[0].message.content)
```

And you will get `2 + 2 = 4.`

### 🦥Deploying Unsloth finetunes in SGLang

After fine-tuning [Fine-tuning Guide](/docs/get-started/fine-tuning-llms-guide.md) or using our notebooks at [Unsloth Notebooks](/docs/get-started/unsloth-notebooks.md), you can save or deploy your models directly through SGLang within a single workflow. An example Unsloth finetuning script for eg:

```python
from unsloth import FastLanguageModel
import torch
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "unsloth/gpt-oss-20b",
    max_seq_length = 2048,
    load_in_4bit = True,
)
model = FastLanguageModel.get_peft_model(model)
```

**To save to 16-bit for SGLang, use:**

```python
model.save_pretrained_merged("finetuned_model", tokenizer, save_method = "merged_16bit")
## OR to upload to HuggingFace:
model.push_to_hub_merged("hf/model", tokenizer, save_method = "merged_16bit", token = "")
```

**To save just the LoRA adapters**, either use:

```python
model.save_pretrained("finetuned_model")
tokenizer.save_pretrained("finetuned_model")
```

Or just use our builtin function to do that:

```python
model.save_pretrained_merged("model", tokenizer, save_method = "lora")
## OR to upload to HuggingFace
model.push_to_hub_merged("hf/model", tokenizer, save_method = "lora", token = "")
```

### :railway\_car:gpt-oss-20b: Unsloth & SGLang Deployment Guide

Below is a step-by-step tutorial with instructions for training the [gpt-oss](/docs/models/gpt-oss-how-to-run-and-fine-tune.md)-20b using Unsloth and deploying it with SGLang. It includes performance benchmarks across multiple quantization formats.

{% stepper %}
{% step %}

#### Unsloth Fine-tuning and Exporting Formats

If you're new to fine-tuning, you can read our [guide](/docs/get-started/fine-tuning-llms-guide.md), or try the gpt-oss 20B finetuning notebook at [gpt-oss](/docs/models/gpt-oss-how-to-run-and-fine-tune.md) After training, you can export the model in multiple formats:

{% code overflow="wrap" %}

```python
model.save_pretrained_merged(
    "finetuned_model", 
    tokenizer, 
    save_method = "merged_16bit",
)
## For gpt-oss specific mxfp4 conversions:
model.save_pretrained_merged(
    "finetuned_model", 
    tokenizer, 
    save_method = "mxfp4", # (ONLY FOR gpt-oss otherwise choose "merged_16bit")
)
```

{% endcode %}
{% endstep %}

{% step %}

#### Deployment with SGLang

We saved our gpt-oss finetune to the folder "finetuned\_model", and so in a new terminal, we can launch the finetuned model as an inference endpoint with SGLang:

```shellscript
python -m sglang.launch_server \
    --model-path finetuned_model \
    --host 0.0.0.0 --port 30002
```

You might have to wait a bit on `Capturing batches (bs=1 avail_mem=20.84 GB):` !
{% endstep %}

{% step %}

#### Calling the inference endpoint:

To call the inference endpoint, first launch a new terminal. We then can call the model like below:

{% code overflow="wrap" %}

```python
from openai import OpenAI
import json
openai_client = OpenAI(
    base_url = "http://0.0.0.0:30002/v1",
    api_key = "sk-no-key-required",
)
completion = openai_client.chat.completions.create(
    model = "finetuned_model",
    messages = [{"role": "user", "content": "What is 2+2?"},],
)
print(completion.choices[0].message.content)

## OUTPUT ##
# <|channel|>analysis<|message|>The user asks a simple math question. We should answer 4. Also we should comply with policy. No issues.<|end|><|start|>assistant<|channel|>final<|message|>2 + 2 equals 4.
```

{% endcode %}
{% endstep %}
{% endstepper %}

### :gem:FP8 Online Quantization

To deploy models with FP8 online quantization which allows 30 to 50% more throughput and 50% less memory usage with 2x longer context length supports with SGLang, you can do the below:

{% code overflow="wrap" %}

```shellscript
python -m sglang.launch_server \
    --model-path unsloth/Llama-3.2-1B-Instruct \
    --host 0.0.0.0 --port 30002 \
    --quantization fp8 \
    --kv-cache-dtype fp8_e4m3
```

{% endcode %}

You can also use `--kv-cache-dtype fp8_e5m2` which has a larger dynamic range which might solve FP8 inference issues if you see them. Or use our pre-quantized float8 quants listed in <https://huggingface.co/unsloth/models?search=-fp8> or some are listed below:

{% embed url="<https://huggingface.co/unsloth/Llama-3.2-3B-FP8-Dynamic>" %}

{% embed url="<https://huggingface.co/unsloth/Llama-3.3-70B-Instruct-FP8-Dynamic>" %}

### ⚡Benchmarking SGLang

Below is some code you can run to test the performance speed of your finetuned model:

```shellscript
python -m sglang.launch_server \
    --model-path finetuned_model \
    --host 0.0.0.0 --port 30002
```

Then in another terminal or via tmux:

```shellscript
# Batch Size=8, Input=1024, Output=1024
python -m sglang.bench_one_batch_server \
    --model finetuned_model \
    --base-url http://0.0.0.0:30002 \
    --batch-size 8 \
    --input-len 1024 \
    --output-len 1024
```

You will see the benchmarking run like below:

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FhcGy7cwC2xFaPA7FcJJq%2Fimage.png?alt=media&amp;token=05687013-8af5-4731-8dae-b8cc05d44f21" alt=""><figcaption></figcaption></figure>

We used a B200x1 GPU with gpt-oss-20b and got the below results (\~2,500 tokens throughput)

| Batch/Input/Output | TTFT (s) | ITL (s) | Input Throughput | Output Throughput |
| ------------------ | -------- | ------- | ---------------- | ----------------- |
| 8/1024/1024        | 0.40     | 3.59    | 20,718.95        | 2,562.87          |
| 8/8192/1024        | 0.42     | 3.74    | 154,459.01       | 2,473.84          |

See <https://docs.sglang.ai/advanced_features/server_arguments.html> for server arguments for SGLang.

### :person\_running:SGLang Interactive Offline Mode

You can also use SGLang in offline mode (ie not a server) inside a Python interactive environment.

{% code overflow="wrap" %}

```python
import sglang as sgl
engine = sgl.Engine(model_path = "unsloth/Qwen3-0.6B", random_seed = 42)

prompt = "Today is a sunny day and I like"
sampling_params = {"temperature": 0, "max_new_tokens": 256}
outputs = engine.generate(prompt, sampling_params)["text"]
print(outputs)
engine.shutdown()
```

{% endcode %}

### :sparkler:GGUFs in SGLang

SGLang also interestingly supports GGUFs! **Qwen3 MoE is still under construction, but most dense models (Llama 3, Qwen 3, Mistral etc) are supported.**

First install the latest gguf python package via:

{% code overflow="wrap" %}

```shellscript
pip install -e "git+https://github.com/ggml-org/llama.cpp.git#egg=gguf&subdirectory=gguf-py" # install a python package from a repo subdirectory
```

{% endcode %}

Then for example in offline mode SGLang, you can do:

{% code overflow="wrap" %}

```python
from huggingface_hub import hf_hub_download
model_path = hf_hub_download(
    "unsloth/Qwen3-32B-GGUF",
    filename = "Qwen3-32B-UD-Q4_K_XL.gguf",
)
import sglang as sgl
engine = sgl.Engine(model_path = model_path, random_seed = 42)

prompt = "Today is a sunny day and I like"
sampling_params = {"temperature": 0, "max_new_tokens": 256}
outputs = engine.generate(prompt, sampling_params)["text"]
print(outputs)
engine.shutdown()
```

{% endcode %}

### :clapper:High throughput GGUF serving with SGLang

First download the specific GGUF file like below:

{% code overflow="wrap" %}

```python
from huggingface_hub import hf_hub_download
hf_hub_download("unsloth/Qwen3-32B-GGUF", filename="Qwen3-32B-UD-Q4_K_XL.gguf", local_dir=".")
```

{% endcode %}

Then serve the specific file `Qwen3-32B-UD-Q4_K_XL.gguf` and use `--served-model-name unsloth/Qwen3-32B` and also we need the HuggingFace compatible tokenizer via `--tokenizer-path`

```shellscript
python -m sglang.launch_server \
    --model-path Qwen3-32B-UD-Q4_K_XL.gguf \
    --host 0.0.0.0 --port 30002 \
    --served-model-name unsloth/Qwen3-32B \
    --tokenizer-path unsloth/Qwen3-32B
```


---

# Agent Instructions
This documentation is published with GitBook. GitBook is the documentation platform designed so that both humans and AI agents can read, navigate, and reason over technical content effectively. Learn more at gitbook.com.

## Querying This Documentation
If you need additional information that is not directly available in this page, you can query the documentation by asking a question.

Perform an HTTP GET request on the following URL with the `ask` and `goal` query parameters:

```
GET https://unsloth.ai/docs/basics/inference-and-deployment/sglang-guide.md?ask=<question>&goal=<user_goal>
```

`ask` is the immediate question: it should be specific, self-contained, and written in natural language.
`goal` is what the user is ultimately trying to achieve, the reason they need the answer. Sharing it helps GitBook give you a better, more relevant answer. A goal is most helpful when it describes the outcome the user wants rather than restating the question. For example, with `ask=how do I create an API token`, a goal like `automate deployments from our CI pipeline` lets GitBook tailor the answer to that use case.

The response will contain a direct answer to the question and relevant excerpts and sources from the documentation.

Use this mechanism when the answer is not explicitly present in the current page, you need clarification or additional context, or you want to retrieve related documentation sections.
