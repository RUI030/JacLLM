> For the complete documentation index, see [llms.txt](https://unsloth.ai/docs/llms.txt). Markdown versions of documentation pages are available by appending `.md` to page URLs; this page is available as [Markdown](https://unsloth.ai/docs/integrations/connections.md).

# Connect API Providers & Model Servers to Unsloth

Learn how to run models from OpenAI, Anthropic, Ollama, llama.cpp, vLLM, and other providers through a single local UI interface with [Unsloth](/docs/desktop.md), an open-source repo for running and training LLMs. You can also connect your ChatGPT/Codex subscription directly to Unsloth.

Whether your model is running through Unsloth’s inference or your own remote OpenAI-compatible endpoint, you can give it access to Unsloth’s full suite of tools, including web search, code execution, deep research, and more.

{% columns %}
{% column %}
Once connected, you can run models with code execution, tool-calling, image generation, and other features in the same Unsloth chat interface used for both local and cloud models.

Unsloth uniquely supports [prompt caching](#prompt-caching) (to save you many tokens without accuracy degradation) while preserving access to provider-native capabilities, such as OpenAI’s built-in [web search](#web-search-and-thinking) and [code execution](#code-execution).
{% endcolumn %}

{% column %}
{% embed url="<https://github.com/user-attachments/assets/70456395-e016-4273-8256-35adb206267e>" %}
{% endcolumn %}
{% endcolumns %}

### Connections

Connections fall into two groups: hosted API providers that run models for you, and model servers that you run or control.

**Cloud Providers -** Hosted APIs that use an account API key:

| Connection      | Capabilities                            | Setup guide                                                       |
| --------------- | --------------------------------------- | ----------------------------------------------------------------- |
| ChatGPT / Codex | Image, search, code, think              | [OpenAI →](/docs/integrations/connections/openai.md)              |
| OpenAI          | Image, search, code, think              | [OpenAI →](/docs/integrations/connections/openai.md)              |
| Anthropic       | Image, search, code, think              | [Anthropic →](/docs/integrations/connections/anthropic-claude.md) |
| OpenRouter      | Many hosted models through one API key. | [OpenRouter →](/docs/integrations/connections/openrouter.md)      |

**Model Servers -** Inference servers running locally, on your network, or on your remote machine:

| Server    | Description                  | Guide                                                                                                     |
| --------- | ---------------------------- | --------------------------------------------------------------------------------------------------------- |
| Llama.cpp | Efficient GGUF model serving | [Llama.cpp →](/docs/integrations/connections/connect-llama.cpp-to-unsloth-run-ggufs-with-llama-server.md) |
| vLLM      | High-throughput serving      | [vLLM →](/docs/integrations/connections/vllm.md)                                                          |
| Ollama    | Simple local model server    | [Ollama →](/docs/integrations/connections/ollama.md)                                                      |

### Quickstart

To run an external provider's model, add an API key and select which models Unsloth should show. In this example, we’ll use [OpenAI](https://platform.openai.com/api-keys). The same setup works for Anthropic, and other providers.

{% stepper %}
{% step %}

#### Setup Unsloth

The easiest way to get started is by installing the [Unsloth Desktop](/docs/desktop.md) app. It supports [MacOS](/docs/get-started/install/mac.md), Linux, [Windows](/docs/get-started/install/windows-installation.md), [NVIDIA](/docs/get-started/install/pip-install.md), [AMD](/docs/get-started/install/amd.md), Intel and CPU setups.

<a href="https://unsloth.ai/download" class="button primary" data-icon="down-to-bracket">Download Unsloth</a>

* <i class="fa-apple">:apple:</i> [Download for macOS](https://unsloth.ai/download/mac)
* <i class="fa-windows">:windows:</i> [Download for Windows](https://unsloth.ai/download/windows)
* <i class="fa-linux">:linux:</i> [Download for Linux](https://unsloth.ai/download/linux)

Or, if you prefer manual installation:

**MacOS, Linux, WSL:**

```bash
curl -fsSL https://unsloth.ai/install.sh | sh
```

**Windows PowerShell:**

```bash
irm https://unsloth.ai/install.ps1 | iex
```

[See here](/docs/desktop.md#get-started) for more detailed instructions
{% endstep %}

{% step %}

#### Create API

Create a new API key from the provider’s dashboard and copy it.

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FPTauJusYHSZXfrRVPRRF%2Funsloth_openai_api.gif?alt=media&amp;token=54ae6d0f-57d8-41c5-b40d-168fad73482a" alt=""><figcaption></figcaption></figure>
{% endstep %}

{% step %}

#### Setup Unsloth

Now we will need to install and setup [Unsloth](/docs/new/studio.md), which will enable you to run the cloud models in a UI interface. [See here](/docs/new/studio/install.md) for more detailed instructions.

{% endstep %}

{% step %}

#### Configure Connections

Next, connect your provider to Unsloth.

1. Open **Settings** → **Connections**, then click **Add Connection.**
2. Select the provider you want to add, then paste the API key you copied earlier.
3. Click **Reload Models** to refresh the list with models available to your account.
4. Choose the models you want to enable, then hit save.&#x20;

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2Fcw5I5BX3fx8Kf5LDUwl0%2Funsloth_cloud_provider_setup.gif?alt=media&amp;token=8babf957-7486-4a8d-ab5e-6d3b36a2b3ba" alt=""><figcaption></figcaption></figure>
{% endstep %}

{% step %}

#### Ready to Chat

The models you enabled will now appear under **Connected** in the **Select Model** dropdown.

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FgKCJ3zsZzZuDqBAigsfG%2FScreenshot%202026-05-26%20at%201.31.03%E2%80%AFAM.png?alt=media&amp;token=c8df4285-ba69-4091-8978-e4197f6a12d2" alt="" width="563"><figcaption></figcaption></figure>

Unsloth dynamically exposes compatible reasoning levels and generation controls for different models.
{% endstep %}
{% endstepper %}

### Connect a Model Server

Use this flow for [**llama.cpp**](/docs/integrations/connections/connect-llama.cpp-to-unsloth-run-ggufs-with-llama-server.md), [**vLLM**](/docs/integrations/connections/vllm.md), and [**Ollama**](/docs/integrations/connections/ollama.md). Start or locate the server you want to connect. &#x20;

{% tabs %}
{% tab title="llama.cpp " %}
Start `llama-server` with the model you want to serve:

```bash
llama-server \
  --model /path/to/model.gguf \
  --host 0.0.0.0 \
  --port 8080
```

This exposes an API endpoint at: `http://localhost:8080/v1`

To require an API key, add:

```bash
--api-key 1234-myapi-key
```

{% endtab %}

{% tab title="vLLM" %}
Start the `vLLM` server with the model you want to serve:

```bash
  vllm serve unsloth/gemma-4-26B-A4B-it \
  --dtype auto \
```

To require an API key, add:

```bash
  --api-key token-abc123
```

This exposes an API endpoint at: `http://localhost:8000/v1`
{% endtab %}

{% tab title="Ollama" %}
Start `Ollama`, then pull the model you want to use:

```bash
ollama serve
ollama pull qwen3:14b
```

This exposes an API endpoint at: `http://localhost:11434/v1`
{% endtab %}
{% endtabs %}

{% columns %}
{% column %}
Now we can connect the model server. Open **Settings → Connections**, then click **Add Provider**.

Select llama.cpp, vLLM, or Ollama then Paste the server **Base URL**.

* llama.cpp example: `http://localhost:8080/v1`
* Ollama example: `http://localhost:11434/v1`
  {% endcolumn %}

{% column %}

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2F4PC8ybPZgdcdhOWkduFR%2Fimage.png?alt=media&amp;token=00956d7e-4d26-462d-b5a4-17cfb9717aaf" alt="" width="375"><figcaption></figcaption></figure></div>
{% endcolumn %}
{% endcolumns %}

Click **Load Models** to fetch available model IDs, or enter model IDs manually if your server does not expose `/models`.

Then, after you click **Add Provider,** The models you enabled will now appear under **External** in the **Select Model** dropdown.

### Code Execution

When enabled, supported OpenAI and Anthropic models can run code in a provider sandbox to solve problems, analyse data, and work with files.\
\
Anthropic models use Claude’s provider-side Code execution tool. OpenAI uses reusable containers, which you can create, delete, and select from **Code Execution** settings. Select the same container in a new thread to continue with its files and state.

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2F4W9Zq684jCgJy9kGvrkk%2FScreenshot%202026-05-26%20at%206.10.12%E2%80%AFAM.png?alt=media&amp;token=c7b6a106-1a22-4120-a22d-f9ad8a9471c7" alt="" width="563"><figcaption></figcaption></figure></div>

### Prompt Caching

Prompt caching reduces latency and cost when requests reuse the same long prefix. It is supported for compatible providers and servers, including OpenAI, Anthropic, and llama.cpp. Use the **Prompt caching** setting in the side panel to control caching behaviour for supported connections.

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2Fq4csmTX5rS9isMkNkhTX%2FPrompt%20Caching%20Diagram%20(1).png?alt=media&amp;token=ade433bf-5eaf-4146-a266-525a85a6c98d" alt="" width="375"><figcaption></figcaption></figure>

For llama.cpp, prompt caching is enabled by default and can be disabled when starting `llama-server` with:

```bash
--no-cache-prompt
```

### Web Search & Thinking

Provider-side web search is available for supported models from OpenAI, Anthropic, OpenRouter, Mistral, Gemini, and Kimi. The Think control adapts to the selected model: some models use an on/off toggle, while reasoning-effort models use model specific thinking levels.

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FC0Ed4kzN9h6c0ogEn6NT%2Fwebsearch%20api.png?alt=media&amp;token=d3335222-1d9e-4021-9bf9-734c6acf1fc0" alt="" width="563"><figcaption></figcaption></figure></div>

### Image Generation

Just like GPT and Gemini, Unsloth also supports image generation. You can directly edit an image by clicking the “Edit Image” button and entering a new prompt to refine or regenerate it. Images are generated automatically when requested, but you can toggle this behavior off. A download button is also available, allowing you to save the image in its original full resolution.

<div><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2F5ZLU2BY19MN4yiYLx2Br%2FScreenshot%202026-05-26%20at%206.04.34%E2%80%AFAM.png?alt=media&amp;token=44327a8f-c14d-4541-9a02-f19f375b4326" alt=""><figcaption></figcaption></figure> <figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FDQ1bJ5KF8CiyItrfOrIt%2FScreenshot%202026-05-26%20at%206.06.07%E2%80%AFAM.png?alt=media&amp;token=ff6b00bc-0a2f-4375-a454-49429cf839f2" alt=""><figcaption></figcaption></figure></div>

### Troubleshooting

If a provider fails to connect, check that the API key belongs to the selected provider and has access to the model you chose.

If a model does not appear after clicking **Reload Models**, it may not be available for your account. You can still use Unsloth’s default model list or choose another model.


---

# Agent Instructions
This documentation is published with GitBook. GitBook is the documentation platform designed so that both humans and AI agents can read, navigate, and reason over technical content effectively. Learn more at gitbook.com.

## Querying This Documentation
If you need additional information that is not directly available in this page, you can query the documentation by asking a question.

Perform an HTTP GET request on the following URL with the `ask` and `goal` query parameters:

```
GET https://unsloth.ai/docs/integrations/connections.md?ask=<question>&goal=<user_goal>
```

`ask` is the immediate question: it should be specific, self-contained, and written in natural language.
`goal` is what the user is ultimately trying to achieve, the reason they need the answer. Sharing it helps GitBook give you a better, more relevant answer. A goal is most helpful when it describes the outcome the user wants rather than restating the question. For example, with `ask=how do I create an API token`, a goal like `automate deployments from our CI pipeline` lets GitBook tailor the answer to that use case.

The response will contain a direct answer to the question and relevant excerpts and sources from the documentation.

Use this mechanism when the answer is not explicitly present in the current page, you need clarification or additional context, or you want to retrieve related documentation sections.
