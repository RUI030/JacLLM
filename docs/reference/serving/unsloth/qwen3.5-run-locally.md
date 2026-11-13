> For the complete documentation index, see [llms.txt](https://unsloth.ai/docs/llms.txt). Markdown versions of documentation pages are available by appending `.md` to page URLs; this page is available as [Markdown](https://unsloth.ai/docs/models/qwen3.5.md).

# Qwen3.5 - How to Run Locally

Run the new Qwen3.5 LLMs including Medium: Qwen3.5-35B-A3B, 27B, 122B-A10B, Small: Qwen3.5-0.8B, 2B, 4B, 9B and 397B-A17B on your local device!

Qwen3.5 is Alibaba’s new model family, including Qwen3.5-**35B**-A3B, **27B**, **122B**-A10B and **397B**-A17B and the new **Small** series: Qwen3.5-0.8B, 2B, 4B and 9B. The multimodal hybrid reasoning LLMs deliver the strongest performances for their sizes. They support **256K context** across 201 languages, have **thinking** + **non-**&#x74;hinking, and excel in agentic coding, vision, chat, and long-context tasks. The 35B and 27B models work on a 22GB Mac / RAM device. See all [GGUFs here](https://huggingface.co/collections/unsloth/qwen35).

<a href="/pages/JcwJOcoquFknfeDFxM7k#qwen3.5-inference-tutorials" class="button primary">Run Qwen3.5 Tutorials</a><a href="/docs/models/qwen3.5/fine-tune.md" class="button secondary">Fine-tune Qwen3.5</a>

{% hint style="success" %}
**Mar 17 Update:** You can now run Qwen3.5 in [**Unsloth Studio**](#unsloth-studio-guide).

**Mar 5 Update:** Redownload Qwen3.5-**35B**, **27B**, **122B** and **397B**.

* All GGUFs now updated with an **improved quantization** algorithm.
* All use our **new imatrix data**. See some improvements in chat, coding, long context, and tool-calling use-cases.
* **Tool-calling improved** following our chat template fixes. **Fix is universal** and applies to **any** Qwen3.5 format and **any** uploader.
* [**Check new GGUF benchmarks**](/docs/models/qwen3.5/gguf-benchmarks.md) **for Unsloth performance results + our** [**MXFP4 investigation**](/docs/models/qwen3.5/gguf-benchmarks.md#id-1-some-tensors-are-very-sensitive-to-quantization)**.**
* We're retiring MXFP4 layers from 3 Qwen3.5 GGUFs: Q2\_K\_XL, Q3\_K\_XL and Q4\_K\_XL.
  {% endhint %}

All uploads use Unsloth [Dynamic 2.0](/docs/basics/dynamic-3.0-ggufs.md) for SOTA quantization performance - so 4-bit has important layers upcasted to 8 or 16-bit. Thank you Qwen for providing Unsloth with day zero access. You can also [**fine-tune** Qwen3.5](/docs/models/qwen3.5/fine-tune.md) with Unsloth.

{% hint style="info" %}
To enable or disable thinking see [#how-to-enable-or-disable-reasoning-and-thinking](#how-to-enable-or-disable-reasoning-and-thinking "mention").Qwen3.5 Small models disables by default.
{% endhint %}

### :gear: Usage Guide

**Table: Inference hardware requirements** (units = total memory: RAM + VRAM, or unified memory)

<table><thead><tr><th>Qwen3.5</th><th>3-bit</th><th>4-bit</th><th width="128">6-bit</th><th>8-bit</th><th>BF16</th></tr></thead><tbody><tr><td><a href="#qwen3.5-small-0.8b-2b-4b-9b"><strong>0.8B</strong></a> <strong>+</strong> <a href="#qwen3.5-small-0.8b-2b-4b-9b"><strong>2B</strong></a></td><td>3 GB</td><td>3.5 GB</td><td>5 GB</td><td>7.5 GB</td><td>9 GB</td></tr><tr><td><a href="#qwen3.5-small-0.8b-2b-4b-9b"><strong>4B</strong></a></td><td>4.5 GB</td><td>5.5 GB</td><td>7 GB</td><td>10 GB</td><td>14 GB</td></tr><tr><td><a href="#qwen3.5-small-0.8b-2b-4b-9b"><strong>9B</strong></a></td><td>5.5 GB</td><td>6.5 GB</td><td>9 GB</td><td>13 GB</td><td>19 GB</td></tr><tr><td><a href="#qwen3.5-27b"><strong>27B</strong></a></td><td>14 GB</td><td>17 GB</td><td>24 GB</td><td>30 GB</td><td>54 GB</td></tr><tr><td><a href="#qwen3.5-35b-a3b"><strong>35B-A3B</strong></a></td><td>17 GB</td><td>22 GB</td><td>30 GB</td><td>38 GB</td><td>70 GB</td></tr><tr><td><a href="#qwen3.5-122b-a10b"><strong>122B-A10B</strong></a></td><td>60 GB</td><td>70 GB</td><td>106 GB</td><td>132 GB</td><td>245 GB</td></tr><tr><td><a href="#qwen3.5-397b-a17b"><strong>397B-A17B</strong></a></td><td>180 GB</td><td>214 GB</td><td>340 GB</td><td>512 GB</td><td>810 GB</td></tr></tbody></table>

{% hint style="success" %}
For best performance, make sure your total available memory (VRAM + system RAM) exceeds the size of the quantized model file you’re downloading. If it doesn’t, llama.cpp can still run via SSD/HDD offloading, but inference will be slower.
{% endhint %}

Between **27B** and **35B-A3B**, use 27B if you want slightly more accurate results and can't fit in your device. Go for 35B-A3B if you want much faster inference.

### Recommended Settings

* **Maximum context window:** `262,144` (can be extended to 1M via YaRN)
* `presence_penalty = 0.0 to 2.0` default this is off, but to reduce repetitions, you can use this, however using a higher value may result in **slight decrease in performance**
* **Adequate Output Length**: `32,768` tokens for most queries

{% hint style="info" %}
If you're getting gibberish, your context length might be set too low. Or try using `--cache-type-k bf16 --cache-type-v bf16` which might help.
{% endhint %}

As Qwen3.5 is hybrid reasoning, thinking and non-thinking mode have different settings:

#### Thinking mode:

| General tasks                     | Precise coding tasks (e.g. WebDev) |
| --------------------------------- | ---------------------------------- |
| temperature = 1.0                 | temperature = 0.6                  |
| top\_p = 0.95                     | top\_p = 0.95                      |
| top\_k = 20                       | top\_k = 20                        |
| min\_p = 0.0                      | min\_p = 0.0                       |
| presence\_penalty = 1.5           | presence\_penalty = 0.0            |
| repeat\_penalty = disabled or 1.0 | repeat\_penalty = disabled or 1.0  |

{% columns %}
{% column %}
Thinking mode for general tasks:

{% code overflow="wrap" %}

```bash
temperature=1.0, top_p=0.95, top_k=20, min_p=0.0, presence_penalty=1.5, repetition_penalty=1.0
```

{% endcode %}
{% endcolumn %}

{% column %}
Thinking mode for precise coding tasks:

{% code overflow="wrap" %}

```bash
temperature=0.6, top_p=0.95, top_k=20, min_p=0.0, presence_penalty=0.0, repetition_penalty=1.0
```

{% endcode %}
{% endcolumn %}
{% endcolumns %}

#### Instruct (non-thinking) mode settings:

| General tasks                     | Reasoning tasks                   |
| --------------------------------- | --------------------------------- |
| temperature = 0.7                 | temperature = 1.0                 |
| top\_p = 0.8                      | top\_p = 0.95                     |
| top\_k = 20                       | top\_k = 20                       |
| min\_p = 0.0                      | min\_p = 0.0                      |
| presence\_penalty = 1.5           | presence\_penalty = 1.5           |
| repeat\_penalty = disabled or 1.0 | repeat\_penalty = disabled or 1.0 |

{% hint style="warning" %}
To [disable thinking / reasoning](#how-to-enable-or-disable-reasoning-and-thinking), use `--chat-template-kwargs '{"enable_thinking":false}'`

If you're on **Windows** Powershell, use: `--chat-template-kwargs "{\"enable_thinking\":false}"`

Use 'true' and 'false' interchangeably.

**For Qwen3.5 0.8B, 2B, 4B and 9B, reasoning is disabled by default**. To enable it, use: `--chat-template-kwargs '{"enable_thinking":true}'`
{% endhint %}

{% columns %}
{% column %}
Instruct (non-thinking) for general tasks:

{% code overflow="wrap" %}

```bash
temperature=0.7, top_p=0.8, top_k=20, min_p=0.0, presence_penalty=1.5, repetition_penalty=1.0
```

{% endcode %}
{% endcolumn %}

{% column %}
Instruct (non-thinking) for reasoning tasks:

{% code overflow="wrap" %}

```bash
temperature=1.0, top_p=0.95, top_k=20, min_p=0.0, presence_penalty=1.5, repetition_penalty=1.0
```

{% endcode %}
{% endcolumn %}
{% endcolumns %}

## Qwen3.5 Inference Tutorials:

Because Qwen3.5 comes in many different sizes, we'll be using Dynamic 4-bit `MXFP4_MOE` GGUF variants for all inference workloads. Click below to navigate to designated model instructions:

<a href="/docs/models/qwen3.5.md#unsloth-studio-guide" class="button primary">Run in Unsloth Studio</a><a href="#qwen3.5-35b-a3b" class="button secondary">Qwen3.5-35B-A3B</a><a href="#qwen3.5-27b" class="button secondary">27B</a><a href="#qwen3.5-122b-a10b" class="button secondary">122B-A10B</a><a href="#qwen3.5-397b-a17b" class="button secondary">397B-A17B</a><a href="#qwen3.5-small-0.8b-2b-4b-9b" class="button secondary">Small (0.8B - 9B)</a>

**Unsloth Dynamic GGUF uploads:**

| [Qwen3.5-**35B-A3B**](https://huggingface.co/unsloth/Qwen3.5-35B-A3B-GGUF) | [Qwen3.5-**27B**](https://huggingface.co/unsloth/Qwen3.5-27B-GGUF) | [Qwen3.5-**122B-A10B**](https://huggingface.co/unsloth/Qwen3.5-122B-A10B-GGUF) | [Qwen3.5-**397B-A17B**](https://huggingface.co/unsloth/Qwen3.5-397B-A17B-GGUF) |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------ |
| [Qwen3.5-**0.8B**](https://huggingface.co/unsloth/Qwen3.5-0.8B-GGUF)       | [Qwen3.5-**2B**](https://huggingface.co/unsloth/Qwen3.5-2B-GGUF)   | [Qwen3.5-**4B**](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF)               | [Qwen3.5-**9B**](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF)               |

{% hint style="warning" %}
`presence_penalty = 0.0 to 2.0` default this is off, but to reduce repetitions, you can use this, however using a higher value may result in **slight decrease in performance.**

**Currently no Qwen3.5 GGUF works in Ollama due to separate mmproj vision files. Use llama.cpp compatible backends.**
{% endhint %}

## 🦥 Unsloth Studio Guide

Qwen3.5 can be run and fine-tuned in [Unsloth Desktop](/docs/desktop.md), our new open-source desktop UI for local AI. Unsloth Studio lets you run models locally on **MacOS, Windows**, Linux and:

{% columns %}
{% column %}

* Search, download, [run GGUFs](/docs/new/studio.md#run-models-locally) and safetensor models
* [**Self-healing** tool calling](/docs/new/studio.md#execute-code--heal-tool-calling) + **web search**
* [**Code execution**](/docs/new/studio.md#run-models-locally) (Python, Bash)
* [Automatic inference](https://unsloth.ai/docs/desktop#feature-deep-dive) parameter tuning (temp, top-p, etc.)
* Fast CPU + GPU inference via llama.cpp
* [Train LLMs](/docs/new/studio.md#no-code-training) 2x faster with 70% less VRAM
  {% endcolumn %}

{% column %}

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FFeQ0UUlnjXkDdqhcWglh%2Fskinny%20studio%20chat.png?alt=media&amp;token=c2ee045f-c243-4024-a8e4-bb4dbe7bae79" alt=""><figcaption></figcaption></figure></div>
{% endcolumn %}
{% endcolumns %}

{% stepper %}
{% step %}

#### Install Unsloth

The easiest way to get started is by downloading the [Unsloth Desktop app](/docs/desktop.md). Works on [macOS](/docs/get-started/install/mac.md), [Windows](/docs/get-started/install/windows-installation.md), and [Linux](/docs/get-started/install/linux.md).

<a href="https://unsloth.ai/download" class="button primary" data-icon="down-to-bracket">Download Unsloth</a>

* <i class="fa-apple">:apple:</i> [Download for macOS](https://unsloth.ai/download/mac)
* <i class="fa-windows">:windows:</i> [Download for Windows](https://unsloth.ai/download/windows)
* <i class="fa-linux">:linux:</i> [Download for Linux](https://unsloth.ai/download/linux)

Or, if you prefer to install manually:

**MacOS, Linux, WSL:**

```bash
curl -fsSL https://unsloth.ai/install.sh | sh
```

**Windows PowerShell:**

```bash
irm https://unsloth.ai/install.ps1 | iex
```

{% hint style="success" %}
**Installation will be quick and take approx 1-2 mins.**
{% endhint %}
{% endstep %}

{% step %}

#### Launch Unsloth

**MacOS, Linux, WSL and Windows:**

```bash
unsloth studio -H 0.0.0.0 -p 8888
```

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2Fd1yMMNa65Ccz50Ke0E7r%2FScreenshot%202026-03-17%20at%2012.32.38%E2%80%AFAM.png?alt=media&amp;token=9369cfe7-35b1-4955-b8cb-42f7ecb43780" alt="" width="375"><figcaption></figcaption></figure></div>

**Then open `http://localhost:8888` in your browser.**
{% endstep %}

{% step %}

#### Search and download Qwen3.5

On first launch you will need to create a password to secure your account and sign in again later. Then go to the [Unsloth Chat](/docs/new/studio/chat.md) tab and search for Qwen3.5 in the search bar and download your desired model and quant.

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FfQAcYOCryMEa6CMPdpt7%2FScreenshot%202026-03-17%20at%2012.35.11%E2%80%AFAM.png?alt=media&amp;token=d9215f41-5f43-47d4-9fa7-020282bb4663" alt="" width="375"><figcaption></figcaption></figure></div>
{% endstep %}

{% step %}

#### Run Qwen3.5

Inference parameters should be auto-set when using Unsloth Studio, however you can still change it manually. You can also edit the context length, chat template and other settings.

For more information, you can view our [Unsloth Studio inference guide](/docs/new/studio/chat.md).

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FXPQGEEr1YoKofrTatAKK%2Ftoolcallingif.gif?alt=media&amp;token=25d68698-fb13-4c46-99b2-d39fb025df08" alt="" width="563"><figcaption></figcaption></figure></div>
{% endstep %}
{% endstepper %}

## 🦙 Llama.cpp Guides

### Qwen3.5-35B-A3B

For this guide we will be utilizing Dynamic 4-bit which works great on a 24GB RAM / Mac device for fast inference. Because the model is only around 72GB at full F16 precision, we won't need to worry much about performance. GGUF: [Qwen3.5-35B-A3B-GGUF](https://huggingface.co/unsloth/Qwen3.5-35B-A3B-GGUF)

For these tutorials, we will using [llama.cpp](llama.cpphttps://github.com/ggml-org/llama.cpp) for fast local inference, especially if you have a CPU.

{% stepper %}
{% step %}
Obtain the latest `llama.cpp` **on** [**GitHub here**](https://github.com/ggml-org/llama.cpp). You can follow the build instructions below as well. Change `-DGGML_CUDA=ON` to `-DGGML_CUDA=OFF` if you don't have a GPU or just want CPU inference. **For Apple Mac / Metal devices**, set `-DGGML_CUDA=OFF` then continue as usual - Metal support is on by default.

```bash
apt-get update
apt-get install pciutils build-essential cmake curl libcurl4-openssl-dev -y
git clone https://github.com/ggml-org/llama.cpp
cmake llama.cpp -B llama.cpp/build \
    -DBUILD_SHARED_LIBS=OFF -DGGML_CUDA=ON
cmake --build llama.cpp/build --config Release -j --clean-first --target llama-cli llama-mtmd-cli llama-server llama-gguf-split
cp llama.cpp/build/bin/llama-* llama.cpp
```

{% endstep %}

{% step %}
If you want to use `llama.cpp` directly to load models, you can do the below: (:Q4\_K\_M) is the quantization type. You can also download via Hugging Face (point 3). This is similar to `ollama run` . Use `export LLAMA_CACHE="folder"` to force `llama.cpp` to save to a specific location. The model has a maximum of 256K context length.

Follow one of the specific commands below, according to your use-case:

**Thinking mode:**

Precise coding tasks (e.g. WebDev):

```bash
export LLAMA_CACHE="unsloth/Qwen3.5-35B-A3B-GGUF"
./llama.cpp/llama-cli \
    -hf unsloth/Qwen3.5-35B-A3B-GGUF:UD-Q4_K_XL \
    --temp 0.6 \
    --top-p 0.95 \
    --top-k 20 \
    --min-p 0.00
```

General tasks:

```bash
export LLAMA_CACHE="unsloth/Qwen3.5-35B-A3B-GGUF"
./llama.cpp/llama-cli \
    -hf unsloth/Qwen3.5-35B-A3B-GGUF:UD-Q4_K_XL \
    --temp 1.0 \
    --top-p 0.95 \
    --top-k 20 \
    --min-p 0.00
```

**Non-thinking mode:**

General tasks:

```bash
export LLAMA_CACHE="unsloth/Qwen3.5-35B-A3B-GGUF"
./llama.cpp/llama-server \
    -hf unsloth/Qwen3.5-35B-A3B-GGUF:UD-Q4_K_XL \
    --temp 0.7 \
    --top-p 0.8 \
    --top-k 20 \
    --min-p 0.00 \
    --chat-template-kwargs '{"enable_thinking":false}'
```

Reasoning tasks:

```bash
export LLAMA_CACHE="unsloth/Qwen3.5-35B-A3B-GGUF"
./llama.cpp/llama-server \
    -hf unsloth/Qwen3.5-35B-A3B-GGUF:UD-Q4_K_XL \
    --temp 1.0 \
    --top-p 0.95 \
    --top-k 20 \
    --min-p 0.00 \
    --chat-template-kwargs '{"enable_thinking":false}'
```

{% endstep %}

{% step %}
Download the model via (after installing `pip install huggingface_hub hf_transfer` ). You can choose Q4\_K\_M or other quantized versions like `UD-Q4_K_XL` . We recommend using at least 2-bit dynamic quant `UD-Q2_K_XL` to balance size and accuracy. If downloads get stuck, see: [Hugging Face Hub, XET debugging](/docs/basics/troubleshooting-and-faqs/hugging-face-hub-xet-debugging.md)

```bash
hf download unsloth/Qwen3.5-35B-A3B-GGUF \
    --local-dir unsloth/Qwen3.5-35B-A3B-GGUF \
    --include "*mmproj-F16*" \
    --include "*UD-Q4_K_XL*" # Use "*UD-Q2_K_XL*" for Dynamic 2bit
```

{% endstep %}

{% step %}
Then run the model in conversation mode:

{% code overflow="wrap" %}

```bash
./llama.cpp/llama-cli \
    --model unsloth/Qwen3.5-35B-A3B-GGUF/Qwen3.5-35B-A3B-UD-Q4_K_XL.gguf \
    --mmproj unsloth/Qwen3.5-35B-A3B-GGUF/mmproj-F16.gguf \
    --temp 1.0 \
    --top-p 0.95 \
    --min-p 0.00 \
    --top-k 20
```

{% endcode %}
{% endstep %}
{% endstepper %}

### Qwen3.5 Small (0.8B • 2B • 4B • 9B)

{% hint style="warning" %}
**For Qwen3.5 0.8B, 2B, 4B and 9B,** [**reasoning is disabled**](#how-to-enable-or-disable-reasoning-and-thinking) **by default**. To enable it, use: `--chat-template-kwargs '{"enable_thinking":true}'`

On Windows use: `--chat-template-kwargs "{\"enable_thinking\":true}"`
{% endhint %}

For the Qwen3.5 Small series, because they're so small, all you need to do is change the model name in the scripts to desired variant. For this specific guide we'll be using the 9B parameter variant. To run them all in near full precision, you'll just need 12GB of RAM / VRAM / unified memory device. GGUFs:

| [Qwen3.5-**0.8B**](https://huggingface.co/unsloth/Qwen3.5-0.8B-GGUF) | [Qwen3.5-**2B**](https://huggingface.co/unsloth/Qwen3.5-2B-GGUF) | [Qwen3.5-**4B**](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF) | [Qwen3.5-**9B**](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF) |
| -------------------------------------------------------------------- | ---------------------------------------------------------------- | ---------------------------------------------------------------- | ---------------------------------------------------------------- |

{% stepper %}
{% step %}
Obtain the latest `llama.cpp` **on** [**GitHub here**](https://github.com/ggml-org/llama.cpp). You can follow the build instructions below as well. Change `-DGGML_CUDA=ON` to `-DGGML_CUDA=OFF` if you don't have a GPU or just want CPU inference.

```bash
apt-get update
apt-get install pciutils build-essential cmake curl libcurl4-openssl-dev -y
git clone https://github.com/ggml-org/llama.cpp
cmake llama.cpp -B llama.cpp/build \
    -DBUILD_SHARED_LIBS=OFF -DGGML_CUDA=ON
cmake --build llama.cpp/build --config Release -j --clean-first --target llama-cli llama-mtmd-cli llama-server llama-gguf-split
cp llama.cpp/build/bin/llama-* llama.cpp
```

{% endstep %}

{% step %}
If you want to use `llama.cpp` directly to load models, you can do the below: (:Q4\_K\_XL) is the quantization type. You can also download via Hugging Face (point 3). This is similar to `ollama run` . Use `export LLAMA_CACHE="folder"` to force `llama.cpp` to save to a specific location. The model has a maximum of 256K context length.

Follow one of the specific commands below, according to your use-case:

{% hint style="success" %}
**To use another variant other than 9B, you can change the '9B' to: 0.8B, 2B or 4B etc.**
{% endhint %}

**Thinking mode (disabled by default)**

{% hint style="danger" %}
Qwen3.5 Small models disable thinking by default. Use llama-server to enable it.
{% endhint %}

```bash
export LLAMA_CACHE="unsloth/Qwen3.5-9B-GGUF"
./llama.cpp/llama-server \
    -hf unsloth/Qwen3.5-9B-GGUF:UD-Q4_K_XL \
    --temp 0.6 \
    --top-p 0.95 \
    --top-k 20 \
    --min-p 0.00 \
    --alias "unsloth/Qwen3.5-9B-GGUF" \
    --port 8001 \
    --chat-template-kwargs '{"enable_thinking":true}'
```

General tasks:

```bash
export LLAMA_CACHE="unsloth/Qwen3.5-9B-GGUF"
./llama.cpp/llama-server \
    -hf unsloth/Qwen3.5-9B-GGUF:UD-Q4_K_XL \
    --temp 1.0 \
    --top-p 0.95 \
    --top-k 20 \
    --min-p 0.00 \
    --alias "unsloth/Qwen3.5-9B-GGUF" \
    --port 8001 \
    --chat-template-kwargs '{"enable_thinking":true}'
```

{% hint style="success" %}
**To use another variant other than 9B, you can change the '9B' to: 0.8B, 2B or 4B etc.**
{% endhint %}

**Non-thinking mode is already on by default**

General tasks:

```bash
export LLAMA_CACHE="unsloth/Qwen3.5-9B-GGUF"
./llama.cpp/llama-cli \
    -hf unsloth/Qwen3.5-9B-GGUF:UD-Q4_K_XL \
    --temp 0.7 \
    --top-p 0.8 \
    --top-k 20 \
    --min-p 0.00
```

Reasoning tasks:

```bash
export LLAMA_CACHE="unsloth/Qwen3.5-9B-GGUF"
./llama.cpp/llama-cli \
    -hf unsloth/Qwen3.5-9B-GGUF:UD-Q4_K_XL \
    --temp 1.0 \
    --top-p 0.95 \
    --top-k 20 \
    --min-p 0.00
```

{% endstep %}

{% step %}
Download the model via (after installing `pip install huggingface_hub hf_transfer` ). You can choose Q4\_K\_M or other quantized versions like `UD-Q4_K_XL` . We recommend using at least 2-bit dynamic quant `UD-Q2_K_XL` to balance size and accuracy. If downloads get stuck, see: [Hugging Face Hub, XET debugging](/docs/basics/troubleshooting-and-faqs/hugging-face-hub-xet-debugging.md)

```bash
hf download unsloth/Qwen3.5-9B-GGUF \
    --local-dir unsloth/Qwen3.5-9B-GGUF \
    --include "*mmproj-F16*" \
    --include "*UD-Q4_K_XL*" # Use "*UD-Q2_K_XL*" for Dynamic 2bit
```

{% endstep %}

{% step %}
Then run the model in conversation mode:

{% code overflow="wrap" %}

```bash
./llama.cpp/llama-cli \
    --model unsloth/Qwen3.5-9B-GGUF/Qwen3.5-9B-UD-Q4_K_XL.gguf \
    --mmproj unsloth/Qwen3.5-9B-GGUF/mmproj-F16.gguf \
    --temp 1.0 \
    --top-p 0.95 \
    --min-p 0.00 \
    --top-k 20
```

{% endcode %}
{% endstep %}
{% endstepper %}

### Qwen3.5-27B

For this guide we will be utilizing Dynamic 4-bit which works great on a 18GB RAM / Mac device for fast inference. GGUF: [Qwen3.5-27B-GGUF](https://huggingface.co/unsloth/Qwen3.5-27B-GGUF)

{% stepper %}
{% step %}
Obtain the latest `llama.cpp` **on** [**GitHub here**](https://github.com/ggml-org/llama.cpp). You can follow the build instructions below as well. Change `-DGGML_CUDA=ON` to `-DGGML_CUDA=OFF` if you don't have a GPU or just want CPU inference.

```bash
apt-get update
apt-get install pciutils build-essential cmake curl libcurl4-openssl-dev -y
git clone https://github.com/ggml-org/llama.cpp
cmake llama.cpp -B llama.cpp/build \
    -DBUILD_SHARED_LIBS=OFF -DGGML_CUDA=ON
cmake --build llama.cpp/build --config Release -j --clean-first --target llama-cli llama-mtmd-cli llama-server llama-gguf-split
cp llama.cpp/build/bin/llama-* llama.cpp
```

{% endstep %}

{% step %}
If you want to use `llama.cpp` directly to load models, you can do the below: (:Q4\_K\_M) is the quantization type. You can also download via Hugging Face (point 3). This is similar to `ollama run` . Use `export LLAMA_CACHE="folder"` to force `llama.cpp` to save to a specific location. The model has a maximum of 256K context length.

Follow one of the specific commands below, according to your use-case:

**Thinking mode:**

Precise coding tasks (e.g. WebDev):

```bash
export LLAMA_CACHE="unsloth/Qwen3.5-27B-GGUF"
./llama.cpp/llama-cli \
    -hf unsloth/Qwen3.5-27B-GGUF:UD-Q4_K_XL \
    --temp 0.6 \
    --top-p 0.95 \
    --top-k 20 \
    --min-p 0.00
```

General tasks:

```bash
export LLAMA_CACHE="unsloth/Qwen3.5-27B-GGUF"
./llama.cpp/llama-cli \
    -hf unsloth/Qwen3.5-27B-GGUF:UD-Q4_K_XL \
    --temp 1.0 \
    --top-p 0.95 \
    --top-k 20 \
    --min-p 0.00
```

**Non-thinking mode:**

General tasks:

```bash
export LLAMA_CACHE="unsloth/Qwen3.5-27B-GGUF"
./llama.cpp/llama-server \
    -hf unsloth/Qwen3.5-27B-GGUF:UD-Q4_K_XL \
    --temp 0.7 \
    --top-p 0.8 \
    --top-k 20 \
    --min-p 0.00 \
    --chat-template-kwargs '{"enable_thinking":false}'
```

Reasoning tasks:

```bash
export LLAMA_CACHE="unsloth/Qwen3.5-27B-GGUF"
./llama.cpp/llama-server \
    -hf unsloth/Qwen3.5-27B-GGUF:UD-Q4_K_XL \
    --temp 1.0 \
    --top-p 0.95 \
    --top-k 20 \
    --min-p 0.00 \
    --chat-template-kwargs '{"enable_thinking":false}'
```

{% endstep %}

{% step %}
Download the model via (after installing `pip install huggingface_hub hf_transfer` ). You can choose `MXFP4_MOE` or other quantized versions like `UD-Q4_K_XL` . We recommend using at least 2-bit dynamic quant `UD-Q2_K_XL` to balance size and accuracy. If downloads get stuck, see: [Hugging Face Hub, XET debugging](/docs/basics/troubleshooting-and-faqs/hugging-face-hub-xet-debugging.md)

```bash
hf download unsloth/Qwen3.5-27B-GGUF \
    --local-dir unsloth/Qwen3.5-27B-GGUF \
    --include "*mmproj-F16*" \
    --include "*UD-Q4_K_XL*" # Use "*UD-Q2_K_XL*" for Dynamic 2bit
```

{% endstep %}

{% step %}
Then run the model in conversation mode:

{% code overflow="wrap" %}

```bash
./llama.cpp/llama-cli \
    --model unsloth/Qwen3.5-27B-GGUF/Qwen3.5-27B-UD-Q4_K_XL.gguf \
    --mmproj unsloth/Qwen3.5-27B-GGUF/mmproj-F16.gguf \
    --temp 1.0 \
    --top-p 0.95 \
    --min-p 0.00 \
    --top-k 20
```

{% endcode %}
{% endstep %}
{% endstepper %}

### Qwen3.5-122B-A10B

For this guide we will be utilizing Dynamic 4-bit which works great on a 70GB RAM / Mac device for fast inference. GGUF: [Qwen3.5-122B-A10B-GGUF](https://huggingface.co/unsloth/Qwen3.5-122B-A10B-GGUF)

{% stepper %}
{% step %}
Obtain the latest `llama.cpp` **on** [**GitHub here**](https://github.com/ggml-org/llama.cpp). You can follow the build instructions below as well. Change `-DGGML_CUDA=ON` to `-DGGML_CUDA=OFF` if you don't have a GPU or just want CPU inference.

```bash
apt-get update
apt-get install pciutils build-essential cmake curl libcurl4-openssl-dev -y
git clone https://github.com/ggml-org/llama.cpp
cmake llama.cpp -B llama.cpp/build \
    -DBUILD_SHARED_LIBS=OFF -DGGML_CUDA=ON
cmake --build llama.cpp/build --config Release -j --clean-first --target llama-cli llama-mtmd-cli llama-server llama-gguf-split
cp llama.cpp/build/bin/llama-* llama.cpp
```

{% endstep %}

{% step %}
If you want to use `llama.cpp` directly to load models, you can do the below: (:Q4\_K\_M) is the quantization type. You can also download via Hugging Face (point 3). This is similar to `ollama run` . Use `export LLAMA_CACHE="folder"` to force `llama.cpp` to save to a specific location. The model has a maximum of 256K context length.

Follow one of the specific commands below, according to your use-case:

**Thinking mode:**

Precise coding tasks (e.g. WebDev):

```bash
export LLAMA_CACHE="unsloth/Qwen3.5-122B-A10B-GGUF"
./llama.cpp/llama-cli \
    -hf unsloth/Qwen3.5-122B-A10B-GGUF:UD-Q4_K_XL \
    --temp 0.6 \
    --top-p 0.95 \
    --top-k 20 \
    --min-p 0.00
```

General tasks:

```bash
export LLAMA_CACHE="unsloth/Qwen3.5-122B-A10B-GGUF"
./llama.cpp/llama-cli \
    -hf unsloth/Qwen3.5-122B-A10B-GGUF:UD-Q4_K_XL \
    --temp 1.0 \
    --top-p 0.95 \
    --top-k 20 \
    --min-p 0.00
```

**Non-thinking mode:**

General tasks:

```bash
export LLAMA_CACHE="unsloth/Qwen3.5-122B-A10B-GGUF"
./llama.cpp/llama-server \
    -hf unsloth/Qwen3.5-122B-A10B-GGUF:UD-Q4_K_XL \
    --temp 0.7 \
    --top-p 0.8 \
    --top-k 20 \
    --min-p 0.00 \
    --chat-template-kwargs '{"enable_thinking":false}'
```

Reasoning tasks:

```bash
export LLAMA_CACHE="unsloth/Qwen3.5-122B-A10B-GGUF"
./llama.cpp/llama-server \
    -hf unsloth/Qwen3.5-122B-A10B-GGUF:UD-Q4_K_XL \
    --temp 1.0 \
    --top-p 0.95 \
    --top-k 20 \
    --min-p 0.00 \
    --chat-template-kwargs '{"enable_thinking":false}'
```

{% endstep %}

{% step %}
Download the model via (after installing `pip install huggingface_hub hf_transfer` ). You can choose `MXFP4_MOE` (dynamic 4bit) or other quantized versions like `UD-Q4_K_XL` . We recommend using at least 2-bit dynamic quant `UD-Q2_K_XL` to balance size and accuracy. If downloads get stuck, see: [Hugging Face Hub, XET debugging](/docs/basics/troubleshooting-and-faqs/hugging-face-hub-xet-debugging.md)

```bash
hf download unsloth/Qwen3.5-122B-A10B-GGUF \
    --local-dir unsloth/Qwen3.5-122B-A10B-GGUF \
    --include "*mmproj-F16*" \
    --include "*UD-Q4_K_XL*" # Use "*UD-Q2_K_XL*" for Dynamic 2bit
```

{% endstep %}

{% step %}
Then run the model in conversation mode:

{% code overflow="wrap" %}

```bash
./llama.cpp/llama-cli \
    --model unsloth/Qwen3.5-122B-A10B-GGUF/UD-Q4_K_XL/Qwen3.5-122B-A10B-UD-Q4_K_XL-00001-of-00003.gguf \
    --mmproj unsloth/Qwen3.5-122B-A10B-GGUF/mmproj-F16.gguf \
    --temp 0.6 \
    --top-p 0.95 \
    --top-k 20 \
    --min-p 0.00
```

{% endcode %}
{% endstep %}
{% endstepper %}

### Qwen3.5-397B-A17B

Qwen3.5-397B-A17B is in the same performance tier as Gemini 3 Pro, Claude Opus 4.5, and GPT-5.2. The full 397B checkpoint is \~807GB on disk, but via [Unsloth's 397B GGUFs](https://huggingface.co/unsloth/Qwen3.5-397B-A17B-GGUF) you can run:

* **3-bit**: fits on **192GB RAM** systems (e.g., a 192GB Mac)
* **4-bit (MXFP4)**: fits on **256GB RAM**. Unsloth **4-bit dynamic** **UD-Q4\_K\_XL** is **\~214GB on disk** - loads directly on a **256GB M3 Ultra**
* Runs on a **single 24GB GPU + 256GB system RAM** via **MoE offloading**, reaching **25+ tokens/s**
* **8-bit** needs **\~512GB RAM/VRAM**

{% hint style="info" %}
See [397B quantization benchmarks](#unsloth-gguf-benchmarks) on how Unsloth GGUFs perform.
{% endhint %}

{% stepper %}
{% step %}
Obtain the latest `llama.cpp` **on** [**GitHub here**](https://github.com/ggml-org/llama.cpp). You can follow the build instructions below as well. Change `-DGGML_CUDA=ON` to `-DGGML_CUDA=OFF` if you don't have a GPU or just want CPU inference.

```bash
apt-get update
apt-get install pciutils build-essential cmake curl libcurl4-openssl-dev -y
git clone https://github.com/ggml-org/llama.cpp
cmake llama.cpp -B llama.cpp/build \
    -DBUILD_SHARED_LIBS=OFF -DGGML_CUDA=ON
cmake --build llama.cpp/build --config Release -j --clean-first --target llama-cli llama-mtmd-cli llama-server llama-gguf-split
cp llama.cpp/build/bin/llama-* llama.cpp
```

{% endstep %}

{% step %}
If you want to use `llama.cpp` directly to load models, you can do the below: (:Q4\_K\_M) is the quantization type. You can also download via Hugging Face (point 3). This is similar to `ollama run` . Use `export LLAMA_CACHE="folder"` to force `llama.cpp` to save to a specific location. Remember the model has only a maximum of 256K context length.

Follow this for **thinking** mode:

```bash
export LLAMA_CACHE="unsloth/Qwen3.5-397B-A17B-GGUF"
./llama.cpp/llama-cli \
    -hf unsloth/Qwen3.5-397B-A17B-GGUF:UD-Q4_K_XL \
    --temp 0.6 \
    --top-p 0.95 \
    --top-k 20 \
    --min-p 0.00
```

Follow this for **non-thinking** mode:

```bash
export LLAMA_CACHE="unsloth/Qwen3.5-397B-A17B-GGUF"
./llama.cpp/llama-server \
    -hf unsloth/Qwen3.5-397B-A17B-GGUF:UD-Q4_K_XL \
    --temp 0.7 \
    --top-p 0.8 \
    --top-k 20 \
    --min-p 0.00 \
    --chat-template-kwargs '{"enable_thinking":false}'
```

{% endstep %}

{% step %}
Download the model via (after installing `pip install huggingface_hub hf_transfer` ). You can choose `MXFP4_MOE` (dynamic 4bit) or other quantized versions like `UD-Q4_K_XL` . We recommend using at least 2-bit dynamic quant `UD-Q2_K_XL` to balance size and accuracy. If downloads get stuck, see: [Hugging Face Hub, XET debugging](/docs/basics/troubleshooting-and-faqs/hugging-face-hub-xet-debugging.md)

```bash
hf download unsloth/Qwen3.5-397B-A17B-GGUF \
    --local-dir unsloth/Qwen3.5-397B-A17B-GGUF \
    --include "*mmproj-F16*" \
    --include "*UD-Q4_K_XL" # Use "*UD-Q2_K_XL*" for Dynamic 2bit
```

{% endstep %}

{% step %}
You can edit `--threads 32` for the number of CPU threads, `--n-gpu-layers 2` for GPU offloading on how many layers. Try adjusting it if your GPU goes out of memory. Also remove it if you have CPU only inference.

{% code overflow="wrap" %}

```bash
./llama.cpp/llama-cli \
    --model unsloth/Qwen3.5-397B-A17B-GGUF/UD-Q4_K_XL/Qwen3.5-397B-A17B-UD-Q4_K_XL-00001-of-00006.gguf \
    --mmproj unsloth/Qwen3.5-397B-A17B-GGUF/mmproj-F16.gguf \
    --temp 0.6 \
    --top-p 0.95 \
    --top-k 20 \
    --min-p 0.00
```

{% endcode %}
{% endstep %}
{% endstepper %}

### 👾 LM Studio Guide

For this guide, we'll be using [LM Studio](https://lmstudio.ai/), a unified UI interface for running LLMs. The '💡Thinking' and 'Non-thinking' toggle may not appear by default so we'll need some extra steps to get it working.

{% stepper %}
{% step %}
Download [LM Studio](https://lmstudio.ai/download) for your device. Then open Model Search, search for 'unsloth/qwen3.5', and download the GGUF (quant) that you desire.

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2F7H0N7guLeBxQJzMTQeJ4%2FScreenshot%202026-03-05%20at%203.59.09%E2%80%AFAM.png?alt=media&amp;token=3f3c6c7d-e249-409c-b95b-106e430205ee" alt="" width="563"><figcaption></figcaption></figure></div>
{% endstep %}

{% step %}
**Thinking Toggle instructions:** After downloading, Open your Terminal / PowerShell and try: `lms --help`. Then if LM Studio appears normally with many commands, run:

{% code overflow="wrap" expandable="true" %}

```bash
lms get unsloth/qwen3.5-4b
```

{% endcode %}

This will get a yaml file which enables your GGUF to have the '💡Thinking' and 'Non-thinking' toggle appear. You can change  `4b` to the desired quant you'd like to have.

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FDXrygqUv9LcTo9pkjotZ%2FScreenshot%202026-03-05%20at%204.04.31%E2%80%AFAM.png?alt=media&amp;token=1e860fc4-1015-4a71-8151-2d8646f76a6d" alt="" width="563"><figcaption></figcaption></figure></div>

Otherwise, you can go to [our LM Studio page](https://lmstudio.ai/unsloth) and download the specific yaml file.
{% endstep %}

{% step %}
Restart LM Studio, then load your downloaded model (with the specific thinking toggle you downloaded). You should now see the Thinking toggle enabled. Don't forget to set the [correct parameters](#recommended-settings).&#x20;

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FuGDncmuDdnaPL9gXwqNM%2FScreenshot%202026-03-05%20at%204.21.55%E2%80%AFAM.png?alt=media&amp;token=40ddffe8-bf9c-46de-b0d1-d6b760bbb6a4" alt=""><figcaption></figcaption></figure></div>
{% endstep %}
{% endstepper %}

### 🦙 Llama-server serving & OpenAI's completion library

To deploy Qwen3.5-397B-A17B for production, we use `llama-server` In a new terminal say via tmux, deploy the model via:

{% code overflow="wrap" %}

```bash
./llama.cpp/llama-server \
--model unsloth/Qwen3.5-35B-A3B-GGUF/Qwen3.5-35B-A3B-UD-Q4_K_XL.gguf \
    --mmproj unsloth/Qwen3.5-35B-A3B-GGUF/mmproj-F16.gguf \
    --alias "unsloth/Qwen3.5-35B-A3B" \
    --temp 0.6 \
    --top-p 0.95 \
    --top-k 20 \
    --min-p 0.00 \
    --port 8001
```

{% endcode %}

Then in a new terminal, after doing `pip install openai`, do:

{% code overflow="wrap" %}

```python
from openai import OpenAI
import json
openai_client = OpenAI(
    base_url = "http://127.0.0.1:8001/v1",
    api_key = "sk-no-key-required",
)
completion = openai_client.chat.completions.create(
    model = "unsloth/Qwen3.5-397B-A17B",
    messages = [{"role": "user", "content": "Create a Snake game."},],
)
print(completion.choices[0].message.content)
```

{% endcode %}

### :thinking: How to enable or disable reasoning & thinking

{% columns %}
{% column %}
For the below commands, you can use '`true`' and '`false`' interchangeably.

[**Unsloth Studio**](#unsloth-studio-guide) automatically has a 'Think' Toggle for thinking models.

To have Think toggle for LM Studio, [read our guide](#lm-studio-guide).
{% endcolumn %}

{% column %}

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2Fj34CUWyxrf0ZxZj4Dn4Z%2Fcurrent%20weather%20in%20amazon.png?alt=media&amp;token=c0688e60-8d7d-4273-87af-25332fbd540c" alt=""><figcaption><p>Unsloth Studio has Think toggle by default</p></figcaption></figure></div>
{% endcolumn %}
{% endcolumns %}

{% hint style="info" %}
To **disable** thinking / reasoning, use within llama-server:

```
    --chat-template-kwargs '{"enable_thinking":false}'
```

If you're on **Windows** or Powershell, use: `--chat-template-kwargs "{\"enable_thinking\":false}"`
{% endhint %}

{% hint style="info" %}
To **enable** thinking / reasoning, use within llama-server:

```
    --chat-template-kwargs '{"enable_thinking":true}'
```

If you're on **Windows** or Powershell, use: `--chat-template-kwargs "{\"enable_thinking\":true}"`
{% endhint %}

{% hint style="danger" %}
**For Qwen3.5 0.8B, 2B, 4B and 9B, reasoning is disabled by default**. To enable it, use: `--chat-template-kwargs '{"enable_thinking":true}'`

And on Windows or Powershell: `--chat-template-kwargs "{\"enable_thinking\":true}"`
{% endhint %}

As an example for Qwen3.5-9B to enable thinking (default is disabled):

```bash
./llama.cpp/llama-server \
    --model unsloth/Qwen3.5-9B-GGUF/Qwen3.5-9B-BF16.gguf \
    --alias "unsloth/Qwen3.5-9B-GGUF" \
    --temp 0.6 \
    --top-p 0.95 \
    --top-k 20 \
    --min-p 0.00 \
    --port 8001 \
    --chat-template-kwargs '{"enable_thinking":true}'
```

And then in Python:

```python
from openai import OpenAI
import json
openai_client = OpenAI(
    base_url = "http://127.0.0.1:8001/v1",
    api_key = "sk-no-key-required",
)
completion = openai_client.chat.completions.create(
    model = "unsloth/Qwen3.5-9B-GGUF",
    messages = [{"role": "user", "content": "What is 2+2?"},],
)
print(completion.choices[0].message.content)
print(completion.choices[0].message.reasoning_content)
```

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FXmr4SuoHKcBOgYJi4S9D%2Fimage.png?alt=media&amp;token=3d2a52d8-0734-47cc-9658-e8d096d42b2f" alt=""><figcaption></figcaption></figure>

### 👨‍💻 OpenAI Codex & Claude Code <a href="#claude-codex" id="claude-codex"></a>

To run the model via local coding agentic workloads, you can [follow our guide](#claude-codex). Use the `llama-server` we just set up just then, and set the model name to the exact id it reports at `GET /v1/models` (the `--alias` value above, e.g. `unsloth/Qwen3.5-9B-GGUF`). Follow the correct Qwen3.5 parameters and usage instructions.

{% columns %}
{% column %}
{% content-ref url="/pages/w020xJgdCTBtTvfHtvye" %}
[Claude Code](/docs/basics/claude-code.md)
{% endcontent-ref %}
{% endcolumn %}

{% column %}
{% content-ref url="/pages/PCjZ57h5pE0QccKyJMYD" %}
[OpenAI Codex](/docs/basics/codex.md)
{% endcontent-ref %}
{% endcolumn %}
{% endcolumns %}

After following the instructions for Claude Code for example you will see:

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2Fup2DMSMPjNR8BM9pgR0v%2Fimage.png?alt=media&amp;token=152e9ee0-2491-4379-af18-8fca0789b19d" alt="" width="563"><figcaption></figcaption></figure>

We can then ask say `Create a Python game for Chess` :

<div><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2F9TfMAoKSdMpb8OHKNnHH%2Fimage.png?alt=media&amp;token=771df3aa-91ab-4c1e-8676-1830058001ca" alt="" width="563"><figcaption></figcaption></figure> <figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FWP3lI5mQW2EHB79qqgDz%2Fimage.png?alt=media&amp;token=55cf3189-e100-419c-a615-024b45948284" alt="" width="563"><figcaption></figcaption></figure> <figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2Fn8DZddDODQZGCP8giKYY%2Fimage.png?alt=media&amp;token=996c8cb9-d199-4045-90f0-408690e02667" alt="" width="563"><figcaption></figcaption></figure></div>

### :hammer:Tool Calling with Qwen3.5

See [Tool Calling Guide](/docs/basics/tool-calling-guide-for-local-llms.md) for more details on how to do tool calling. In a new terminal (if using tmux, use CTRL+B+D), we create some tools like adding 2 numbers, executing Python code, executing Linux functions and much more:

{% code expandable="true" %}

```python
import json, subprocess, random
from typing import Any
def add_number(a: float | str, b: float | str) -> float:
    return float(a) + float(b)
def multiply_number(a: float | str, b: float | str) -> float:
    return float(a) * float(b)
def subtract_number(a: float | str, b: float | str) -> float:
    return float(a) - float(b)
def write_a_story() -> str:
    return random.choice([
        "A long time ago in a galaxy far far away...",
        "There were 2 friends who loved sloths and code...",
        "The world was ending because every sloth evolved to have superhuman intelligence...",
        "Unbeknownst to one friend, the other accidentally coded a program to evolve sloths...",
    ])
def terminal(command: str) -> str:
    if "rm" in command or "sudo" in command or "dd" in command or "chmod" in command:
        msg = "Cannot execute 'rm, sudo, dd, chmod' commands since they are dangerous"
        print(msg); return msg
    print(f"Executing terminal command `{command}`")
    try:
        return str(subprocess.run(command, capture_output = True, text = True, shell = True, check = True).stdout)
    except subprocess.CalledProcessError as e:
        return f"Command failed: {e.stderr}"
def python(code: str) -> str:
    data = {}
    exec(code, data)
    del data["__builtins__"]
    return str(data)
MAP_FN = {
    "add_number": add_number,
    "multiply_number": multiply_number,
    "subtract_number": subtract_number,
    "write_a_story": write_a_story,
    "terminal": terminal,
    "python": python,
}
tools = [
    {
        "type": "function",
        "function": {
            "name": "add_number",
            "description": "Add two numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {
                        "type": "string",
                        "description": "The first number.",
                    },
                    "b": {
                        "type": "string",
                        "description": "The second number.",
                    },
                },
                "required": ["a", "b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "multiply_number",
            "description": "Multiply two numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {
                        "type": "string",
                        "description": "The first number.",
                    },
                    "b": {
                        "type": "string",
                        "description": "The second number.",
                    },
                },
                "required": ["a", "b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "subtract_number",
            "description": "Subtract two numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {
                        "type": "string",
                        "description": "The first number.",
                    },
                    "b": {
                        "type": "string",
                        "description": "The second number.",
                    },
                },
                "required": ["a", "b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_a_story",
            "description": "Writes a random story.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "terminal",
            "description": "Perform operations from the terminal.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command you wish to launch, e.g `ls`, `rm`, ...",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "python",
            "description": "Call a Python interpreter with some Python code that will be ran.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The Python code to run",
                    },
                },
                "required": ["code"],
            },
        },
    },
]
```

{% endcode %}

We then use the below functions (copy and paste and execute) which will parse the function calls automatically and call the OpenAI endpoint for any model:

{% code overflow="wrap" expandable="true" %}

```python
from openai import OpenAI
def unsloth_inference(
    messages,
    temperature = 0.6,
    top_p = 0.95,
    top_k = 20,
    min_p = 0.00,
    repetition_penalty = 1.0,
):
    messages = messages.copy()
    openai_client = OpenAI(
        base_url = "http://127.0.0.1:8001/v1",
        api_key = "sk-no-key-required",
    )
    model_name = next(iter(openai_client.models.list())).id
    print(f"Using model = {model_name}")
    has_tool_calls = True
    original_messages_len = len(messages)
    while has_tool_calls:
        print(f"Current messages = {messages}")
        response = openai_client.chat.completions.create(
            model = model_name,
            messages = messages,
            temperature = temperature,
            top_p = top_p,
            tools = tools if tools else None,
            tool_choice = "auto" if tools else None,
            extra_body = {"top_k": top_k, "min_p": min_p, "repetition_penalty" :repetition_penalty,}
        )
        tool_calls = response.choices[0].message.tool_calls or []
        content = response.choices[0].message.content or ""
        tool_calls_dict = [tc.to_dict() for tc in tool_calls] if tool_calls else tool_calls
        messages.append({"role": "assistant", "tool_calls": tool_calls_dict, "content": content,})
        for tool_call in tool_calls:
            fx, args, _id = tool_call.function.name, tool_call.function.arguments, tool_call.id
            out = MAP_FN[fx](**json.loads(args))
            messages.append({"role": "tool", "tool_call_id": _id, "name": fx, "content": str(out),})
        else:
            has_tool_calls = False
    return messages
```

{% endcode %}

After launching Qwen3.5 via `llama-server` like in [#deploy-with-llama-server-and-openais-completion-library](#deploy-with-llama-server-and-openais-completion-library "mention") or see [Tool Calling Guide](/docs/basics/tool-calling-guide-for-local-llms.md) for more details, we then can do some tool calls.

## 📊 Benchmarks

### Unsloth GGUF Benchmarks

We updated Qwen3.5-35B Unsloth Dynamic quants **being SOTA** on nearly all bits. We did over 150 KL Divergence benchmarks, totally **9TB of GGUFs**. We uploaded all research artifacts. We also fixed a **tool calling** chat template **bug** (affects all quant uploaders)

* All GGUFs now updated with an **improved quantization** algorithm.
* All use our **new imatrix data**. See some improvements in chat, coding, long context, and tool-calling use-cases.
* Qwen3.5-35B-A3B GGUFs are updated to use new fixes (112B, 27B still converting, re-download once they are updated)
* **99.9% KL Divergence shows SOTA** on Pareto Frontier for UD-Q4\_K\_XL, IQ3\_XXS & more.
* **Retiring MXFP4** from all GGUF quants: Q2\_K\_XL, Q3\_K\_XL and Q4\_K\_XL, except for pure MXFP4\_MOE.

<div><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FeynyrSMxDkkw0zl0haJH%2FCode_Generated_Image(10).png?alt=media&amp;token=c62eef1c-fdd7-4838-8f69-bab227b56e23" alt=""><figcaption><p>35B-A3B - KLD benchmarks (lower is better)</p></figcaption></figure> <figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2F1XLNe1MoxtF1ODs5gDej%2F122b%20final.png?alt=media&amp;token=9eee5d8d-f16c-4c3f-8e36-18856e5609aa" alt=""><figcaption><p>122B-A10B - KLD benchmarks (lower is better)</p></figcaption></figure></div>

**READ OUR DETAILED QWEN3.5 ANALYSIS + BENCHMARKS HERE:**

{% content-ref url="/pages/jb9Bhr7e6quGvUmcIcZe" %}
[Qwen3.5 GGUF Benchmarks](/docs/models/qwen3.5/gguf-benchmarks.md)
{% endcontent-ref %}

#### Qwen3.5-397B-A17B Benchmarks

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2F1oo4wA5EB6z3uWhEK9iF%2FHB2gDSgWEAAF5Sr.png?alt=media&amp;token=82216bf7-4f44-49d6-b98b-51ad5f956ca3" alt="" width="563"><figcaption></figcaption></figure>

[Benjamin Marie (third-party) benchmarked](https://x.com/bnjmn_marie/status/2025951400119751040/photo/1) **Qwen3.5-397B-A17B** using Unsloth GGUFs on a **750-prompt mixed suite** (LiveCodeBench v6, MMLU Pro, GPQA, Math500), reporting both **overall accuracy** and **relative error increase** (how much more often the quantized model makes mistakes vs. the original).

**Key results (accuracy; change vs. original; relative error increase):**

* **Original weights:** **81.3%**
* **UD-Q4\_K\_XL:** **80.5%** *(−0.8 points; +4.3% relative error increase)*
* **UD-Q3\_K\_XL:** **80.7%** *(−0.6 points; +3.5% relative error increase)*

`UD-Q4_K_XL` and `UD-Q3_K_XL` stay extremely close to the original, **well under a 1-point accuracy drop** on this suite, which Ben insinuates that you can **sharply reduce memory footprint** (**\~500 GB less**) with little to no practical loss on the tested tasks.

**How to choose:** Q3 scoring slightly higher than Q4 here is completely plausible as normal run-to-run variance at this scale, so treat **Q3 and Q4 as effectively similar quality** in this benchmark:

* Pick **Q3** if you want the **smallest footprint / best memory savings**
* Pick **Q4** if you want a **slightly more conservative** option with **similar** results

All listed quants utilize our dynamic metholodgy. Even `UD-IQ2_M` uses a the same methodology of dynamic however the conversion process is different to `UD-Q2-K-XL` where K-XL is usually faster than `UD-IQ2_M` even though it's bigger, so that is why `UD-IQ2_M` may perform better than `UD-Q2-K-XL`.

### Official Qwen Benchmarks

#### Qwen3.5-35B-A3B, 27B and 122B-A10B Benchmarks

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FgRKh7QnQWxdxsaal64RE%2Fqwen3.5_middle_size_score.png?alt=media&amp;token=0d314ef8-20a4-4a06-8a36-fdeff7192c2b" alt=""><figcaption></figcaption></figure>

#### Qwen3.5-4B and 9B Benchmarks

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FYfZwIWZJD3le86I8mPIS%2Fqwen3.5_small_size_score(1).png?alt=media&amp;token=095334eb-6ad3-4610-b685-c76e13957e6e" alt=""><figcaption></figcaption></figure>

#### Qwen3.5-397B-A17B Benchmarks

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FFoWc77o90b32jEuCw48W%2Fqwen3.5_397b_a17b_score.png?alt=media&amp;token=76e4dc26-d9bd-4106-bc1c-0ef20e066128" alt=""><figcaption></figcaption></figure>


---

# Agent Instructions
This documentation is published with GitBook. GitBook is the documentation platform designed so that both humans and AI agents can read, navigate, and reason over technical content effectively. Learn more at gitbook.com.

## Querying This Documentation
If you need additional information that is not directly available in this page, you can query the documentation by asking a question.

Perform an HTTP GET request on the following URL with the `ask` and `goal` query parameters:

```
GET https://unsloth.ai/docs/models/qwen3.5.md?ask=<question>&goal=<user_goal>
```

`ask` is the immediate question: it should be specific, self-contained, and written in natural language.
`goal` is what the user is ultimately trying to achieve, the reason they need the answer. Sharing it helps GitBook give you a better, more relevant answer. A goal is most helpful when it describes the outcome the user wants rather than restating the question. For example, with `ask=how do I create an API token`, a goal like `automate deployments from our CI pipeline` lets GitBook tailor the answer to that use case.

The response will contain a direct answer to the question and relevant excerpts and sources from the documentation.

Use this mechanism when the answer is not explicitly present in the current page, you need clarification or additional context, or you want to retrieve related documentation sections.
