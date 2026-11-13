> For the complete documentation index, see [llms.txt](https://unsloth.ai/docs/llms.txt). Markdown versions of documentation pages are available by appending `.md` to page URLs; this page is available as [Markdown](https://unsloth.ai/docs/basics/api.md).

# How to use Unsloth as an API endpoint

You can run **local LLMs** with tools like [Claude Code](/docs/basics/claude-code.md) and [Codex](/docs/basics/codex.md) by connecting those tools to Unsloth’s **OpenAI-compatible API endpoint**. This lets you run models like [Qwen](/docs/models/qwen3.6.md) and [Gemma](/docs/models/gemma-4.md) locally for agentic coding. Unsloth also has beneficial features such as self-healing **tool calling**, **code execution**, and **web search**.

Unsloth makes it easy to deploy a fast API inference endpoint that provides:

* [**Self-healing tool calling**](/docs/new/studio/chat.md#auto-healing-tool-calling), which helps reduce broken or malformed tool calls by 50%
* [**Code execution**](/docs/new/studio/chat.md#code-execution) support, allowing Bash and Python execution for more accurate code outputs.
* **Advanced** [**Web search**](/docs/new/studio/chat.md#advanced-web-search) that visits and actually reads webpages to gather in-depth info.
* [**Automatic inference** settings](/docs/new/studio/chat.md#auto-parameter-tuning) for GGUF models (temp, top-k etc.)

{% columns %}
{% column %}
Models loaded in Unsloth (including GGUFs) are exposed as an **authenticated API** via `llama-server`. A long API key is generated for security reasons like how OpenAI provides one.

Your **local models** can then be used directly in your preferred AI agent, SDK, or chat client. Unsloth speaks two dialects on the same port. Both support streaming, tool calling (OpenAI `tools` / Anthropic `tools`), and vision inputs:
{% endcolumn %}

{% column %}

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FgCthbL3uUmrNgxFBePK5%2Fimage.png?alt=media&amp;token=060dbc41-6fd5-496d-ba00-0ba13fde86ff" alt=""><figcaption></figcaption></figure>
{% endcolumn %}
{% endcolumns %}

Whether your model is running through Unsloth’s inference or your own remote OpenAI-compatible endpoint, you can give it access to Unsloth’s full suite of tools, including web search, code execution, deep research, and more.

* **Anthropic-compatible `/v1/messages`**  for Claude Code, OpenClaw, the Anthropic SDK, and any client that expects the Messages API.
* **OpenAI-compatible `/v1/chat/completions`** and **`/v1/responses`** for the OpenAI SDK, OpenCode, Cursor, Continue, Cline, Open WebUI, SillyTavern, and any OpenAI-compatible tool.

### ⚡ Quickstart

{% stepper %}
{% step %}

#### Download Unsloth

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

{% endstep %}

{% step %}

#### Install

1. Open the Unsloth installer (`.dmg`, `.exe` files)
2. Drag Unsloth to Applications for Mac or complete setup for Windows.
3. Launch the app and wait for installation to complete
   {% endstep %}

{% step %}

#### Choose a model

Open 'Select model' dropdown ontop or 'Model hub' tab, choose a model and a quantization that fits your device, then download it. Once it finishes, start chatting - no setup required.

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FNCEVgKLJI0goPqjgcg9B%2Fmodel%20hub%20models.png?alt=media&amp;token=533b5e3c-a901-4b33-963e-4a703cc9d5a6" alt="" width="563"><figcaption></figcaption></figure>
{% endstep %}

{% step %}

#### Unsloth is now ready

To start chatting, type a message and press Enter.

* **Create an API key.** Click your **Unsloth** avatar in the bottom-left → **Settings** → **API** → type a key name → **Create**. Copy the `sk-unsloth-…` value that appears. Unsloth only shows it once.
* **Point your client at Unsloth.** Use `http://localhost:PORT` as the base URL and your `sk-unsloth-…` key for auth. Jump to the recipe for your tool below.

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FpAGvwjGD0iVMZKBoyu7m%2Fgreeennn.png?alt=media&amp;token=d17a5528-8375-444c-9aff-f9e9f7903bcd" alt="" width="563"><figcaption></figcaption></figure>
{% endstep %}
{% endstepper %}

### 🔑 Creating an API key

1. Open the sidebar, click your **Unsloth** avatar at the bottom-left.
2. Go to **Settings** → **API** (globe :globe\_with\_meridians: icon).
3. Enter a friendly name (e.g. `claude-code-macbook`). Set an expiry (optional)
4. Click **Create**.
5. **Copy the key.** Unsloth stores only a hash and you won't be able to view it again.

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FR7fhygHCl5RwG4P1MSoS%2Fimage.png?alt=media&amp;token=e2781a00-7fe5-4831-9fdb-a57234843b34" alt="" width="563"><figcaption></figcaption></figure></div>

All keys start with the `sk-unsloth-` prefix. Revoke a key from the same page at any time. Requests made with a revoked key will fail with `401 Unauthorized`.

{% hint style="warning" %}
Treat your API key like a password. Anyone with the key and network access to your Unsloth instance can send requests to your loaded model.
{% endhint %}

### ⏳ Model Loading

{% stepper %}
{% step %}

#### Select Model

Before using the API, load a model from the **Select model** dropdown in the top-left corner of the Chat page.

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FuZqd6tcZ5LgMSh4ZND5x%2Fexport-1778505117710-24fps.gif?alt=media&amp;token=9defec95-5404-4654-9c33-67be967c9820" alt=""><figcaption></figcaption></figure>

In this guide, we’ll use:

`unsloth/gemma-4-26B-A4B-it-GGUF` with the recommended `UD-Q4_K_XL` quantization.
{% endstep %}

{% step %}

#### Test the Model

Before using the Client, send a quick message:

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2F2Ivilke0aJX8AHWDwSmr%2Fimage.png?alt=media&amp;token=9f9380b9-f963-4861-a17b-fd0fe16684d4" alt="" width="563"><figcaption></figcaption></figure></div>

{% hint style="info" %}
This confirms that the model loaded correctly and is ready to respond.
{% endhint %}
{% endstep %}

{% step %}

#### **Unsloth API key**

In Unsloth, open **Settings → API** to view or create your API key.

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FAZwaRmBVPpXA2SFhMGW9%2Fexport-1778506924396-30fps.gif?alt=media&amp;token=96f3f1a7-fce4-4508-b1b0-e8b6294dc423" alt=""><figcaption></figcaption></figure>

Treat your API key like a password and avoid exposing it in screenshots or repositories.
{% endstep %}
{% endstepper %}

### <i class="fa-terminal">:terminal:</i> Unsloth run command

1. **Install or update Unsloth Studio.** Earlier versions don't expose the external API. See Installation.
2. **Load a GGUF model.** load a GGUF model using the run command. This will also load the UI on the default port. The endpoint URL and API Key will be printed out to the console , ready for you to be used with your client of choice.

   ```bash
   unsloth run --model unsloth/Qwen3.8-27B-GGUF-GGUF:UD-Q4_K_XL
       --temp 1.0 \
       --top-p 0.95 \
       --top-k 20 \
       --min-p 0.0 \
       --chat-template-kwargs '{"reasoning_effort":"medium"}'
   ```

Adjust settings as necessary.

#### Loading a model from the CLI

You can load a model and have an API key created for you automatically using the `unsloth` CLI tool. When the model finishes loading, the endpoint URL and API key are printed to your console. Copy them into your client of choice and you're ready to go.

#### Before you start

Make sure you're on a recent version of Unsloth Studio as earlier versions don't expose the external API. See [installation](/docs/new/studio/install.md).

#### The quick way

Open a terminal and load a GGUF model:

```bash
unsloth run --model unsloth/gemma-4-26B-A4B-it-GGUF:UD-Q4_K_XL
```

This starts the server on the default port, loads the UI, and prints your endpoint URL and API key.

#### How the model name works

You can point at a model in a few different ways. Pick the one you find easiest:

```bash
# Combined: repo and quantization variant in one string (recommended — shortest)
unsloth run --model unsloth/gemma-4-26B-A4B-it-GGUF:UD-Q4_K_XL

# Separate: repo and variant as two flags (the older style, still works)
unsloth run --model unsloth/gemma-4-26B-A4B-it-GGUF --gguf-variant UD-Q4_K_XL

# Using -hf / --hf-repo (matches llama.cpp's spelling, handy if you're coming from there)
unsloth run -hf unsloth/gemma-4-26B-A4B-it-GGUF:UD-Q4_K_XL
```

### Tuning the run (optional)

You don't need any of this for a basic load, but `unsloth run` supports many llama-server runtime flags for customizing performance, memory usage, context length, generation behavior, networking, and tool access.

Additional flags are forwarded directly to the underlying inference server, and your values override Unsloth's defaults. If there are no settings/sampling flags set, Unsloth automatically selects the best/recommended settings for the model including context length, temperature etc.

#### Control reasoning behavior

Some reasoning-capable models support additional flags for controlling thinking and reasoning behavior.

```bash
# Disable reasoning / thinking output
unsloth run \
  --model unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL \
  --reasoning on  \
  --reasoning-effort medium
```

Reasoning effort and flags depends on what the model supports.

#### Adjust generation behavior

Sampling settings control how creative, focused, or deterministic the model behaves during generation.

```bash
# Lower randomness and improve reproducibility
unsloth run \
  --model unsloth/Qwen3-1.7B-GGUF \
  --temp 0.6 \
  --seed 42
```

Lower temperature values usually produce more stable outputs, while top-p, top-k, min-p, and repeat penalty settings further control token selection and repetition.

```bash
# Tune token selection and repetition behavior
unsloth run \
  --model unsloth/Qwen3-1.7B-GGUF \
  --top-p 0.95 \
  --top-k 20 \
  --min-p 0.05 \
  --repeat-penalty 1.1
```

#### Increase context length and CPU threads

Useful if you're working with large projects, long chats, or agent workflows that need more memory.

```bash
# Use a larger context window and more CPU threads
unsloth run \
  --model unsloth/gemma-4-26B-A4B-it-GGUF:UD-Q4_K_XL \
  -c 131072 \
  --threads 32
```

#### Expose the API on your local network

By default, Unsloth only runs locally on your machine. You can expose the API to other devices on your network by binding to `0.0.0.0`.

```bash
# Allow LAN devices to connect
unsloth run \
  --model unsloth/gemma-4-26B-A4B-it-GGUF:UD-Q4_K_XL \
  -H 0.0.0.0 \
  -p 8888
```

#### Enable or disable server-side tools

Control whether tools like web search and code execution are exposed by the inference server.

```bash
# Explicitly enable tools
unsloth run \
  --model unsloth/gemma-4-26B-A4B-it-GGUF:UD-Q4_K_XL \
  --enable-tools
```

```bash
# Explicitly disable tools
unsloth run \
  --model unsloth/gemma-4-26B-A4B-it-GGUF:UD-Q4_K_XL \
  --disable-tools
```

Unsloth supports most llama-server runtime flags, including context sizing, GPU layers, threading, sampling, networking, and tool configuration.

See the [llama-server](https://github.com/ggml-org/llama.cpp/tree/master/tools/server) documentation for the full list of supported runtime flags.

#### **Server-side tool policy**

`unsloth run` controls whether server-side tools (web search, code execution, etc.) are exposed by the inference server. Defaults are based on the bind address:

* **`127.0.0.1` (localhost)** — tools **on** by default. Only your machine can reach the server.
* **`0.0.0.0` or any non-loopback address** — tools **off** by default. A leaked API key on a network-exposed server means arbitrary code execution on the host.

**Flags:**

* `--enable-tools` / `--disable-tools` — force on or off. On `0.0.0.0`, `--enable-tools` shows a y/N security prompt.
* `--yes` / `-y` — skip the prompt (for automation).

The resolved policy is a process-level hard override — individual requests cannot bypass it via `enable_tools=true` in the request body.

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FeIJIvZl7HvOCjtVPm3en%2Funsloth_run_model.png?alt=media&amp;token=84c45c38-78a9-4b55-b9b7-08bad9dc6238" alt=""><figcaption></figcaption></figure></div>

### 🌐 Endpoints

Unsloth exposes its API on the port it started on, typically `http://localhost:8000` or `http://localhost:8888`.

Authenticate with an `Authorization: Bearer sk-unsloth-…` header on every request. Endpoint availability depends on your Unsloth version, backend, and model.

**Chat and text**

| Endpoint                    | Purpose                                                                                    |
| --------------------------- | ------------------------------------------------------------------------------------------ |
| `POST /v1/chat/completions` | OpenAI-compatible chat completions, including streaming and tool calling.                  |
| `POST /v1/responses`        | OpenAI-compatible Responses API for Codex and other compatible clients.                    |
| `POST /v1/messages`         | Anthropic-compatible Messages API for Claude Code, OpenClaw, and other compatible clients. |
| `POST /v1/completions`      | Text completions without chat formatting. Requires a GGUF or MLX model.                    |

For Responses requests, send conversation history in `input`. Server-managed history through `previous_response_id` or `conversation` is unsupported.

**Models, embeddings, and token counting**

| Endpoint                         | Purpose                                                                                          |
| -------------------------------- | ------------------------------------------------------------------------------------------------ |
| `GET /v1/models`                 | List loaded and locally available models. Check `loaded` to identify models currently in memory. |
| `GET /v1/models/{model_id}`      | Get metadata for a model.                                                                        |
| `GET /v1/props`                  | Read llama-server-compatible server properties.                                                  |
| `POST /v1/embeddings`            | Generate embeddings using a loaded embedding GGUF or Unsloth’s configured embedding model.       |
| `POST /v1/chat/count_tokens`     | Count prompt tokens for OpenAI-format messages.                                                  |
| `POST /v1/messages/count_tokens` | Count input tokens for Anthropic-format messages.                                                |

**Images**

| Endpoint                      | Purpose                                                          |
| ----------------------------- | ---------------------------------------------------------------- |
| `POST /v1/images/generations` | Generate images from a prompt using a supported diffusion model. |

**Audio**

| Endpoint                        | Purpose                                                                                                               |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `POST /v1/audio/speech`         | OpenAI-compatible text-to-speech.                                                                                     |
| `POST /v1/audio/generate`       | Generate speech from chat-format messages; returns base64 WAV audio.                                                  |
| `POST /v1/audio/transcriptions` | Transcribe an uploaded audio file.                                                                                    |
| `POST /v1/audio/translations`   | Translate speech in an uploaded audio file to English.                                                                |
| `POST /v1/audio/inputs`         | Upload audio for reuse. Send audio as the raw request body.                                                           |
| `POST /v1/audio/run`            | Run an audio workflow, such as cloning, editing, conversion, music generation, or separation, depending on the model. |

Stored audio inputs support `GET /v1/audio/inputs/{input_id}/file` and `DELETE /v1/audio/inputs/{input_id}`.

Manage saved voices through `GET` or `POST /v1/audio/voices`, `PATCH` or `DELETE /v1/audio/voices/{voice_id}`, and `GET /v1/audio/voices/{voice_id}/file`.

**Video**

| Endpoint                            | Purpose                          |
| ----------------------------------- | -------------------------------- |
| `POST /v1/videos`                   | Create a video generation job.   |
| `GET /v1/videos`                    | List video jobs.                 |
| `GET /v1/videos/{video_id}`         | Get a job’s status and metadata. |
| `GET /v1/videos/{video_id}/content` | Download a completed video.      |
| `DELETE /v1/videos/{video_id}`      | Delete a video job.              |

Image, audio, and video generation require models that support the requested task.

**Structured decisions**

| Endpoint             | Purpose                                             |
| -------------------- | --------------------------------------------------- |
| `POST /v1/systemone` | Answer structured questions using the Decision API. |

Enable the Decision API in **Settings → API** and select a decision model first. Requests use `state` and named `questions`, with question types `noul`, `choice`, or `score`.

**Explore your local API**

Open `http://localhost:8888/docs` for Unsloth’s generated interactive API reference, or `/openapi.json` for its machine-readable schema. Replace `8888` with your Unsloth port.

This reference reflects your installed version and includes internal Unsloth routes. Some compatibility routes are hidden, and manually parsed request bodies may not have complete schemas.

See [Curl & HTTP](https://unsloth.ai/docs/integrations/connect-curl-and-http-to-unsloth) for request examples.

### 🖇️ Connecting your client

Unsloth enables you run local LLMs via most frameworks including [Claude Code](/docs/basics/claude-code.md), [Codex](/docs/basics/codex.md), [OpenClaw](/docs/integrations/openclaw.md), [OpenCode](/docs/integrations/opencode.md) and more. Click the specific tools below for a guide:

{% columns %}
{% column width="50%" %}
{% content-ref url="/pages/w020xJgdCTBtTvfHtvye" %}
[Claude Code](/docs/basics/claude-code.md)
{% endcontent-ref %}

{% content-ref url="/pages/PCjZ57h5pE0QccKyJMYD" %}
[OpenAI Codex](/docs/basics/codex.md)
{% endcontent-ref %}

{% content-ref url="/pages/1cwX0SOqPoqLx7fQ2sIS" %}
[Curl & HTTP](/docs/integrations/connect-curl-and-http-to-unsloth.md)
{% endcontent-ref %}
{% endcolumn %}

{% column width="50%" %}
{% content-ref url="/pages/CwQEpEmkKPmyEYdnEngt" %}
[OpenClaw](/docs/integrations/openclaw.md)
{% endcontent-ref %}

{% content-ref url="/pages/qaA8ZjTxsH2GTuBOHyra" %}
[OpenCode](/docs/integrations/opencode.md)
{% endcontent-ref %}

{% content-ref url="/pages/viZvzp58ObzZkXtCm0qv" %}
[Python SDK](/docs/integrations/connect-python-sdk-to-unsloth.md)
{% endcontent-ref %}
{% endcolumn %}
{% endcolumns %}

To reach this endpoint from another machine, launch with `unsloth studio --secure`. Unsloth stays bound to localhost and publishes itself on a free Cloudflare HTTPS URL; use that URL in place of `http://127.0.0.1:8888` as your client's base URL. Note that server-sent events do not survive a Cloudflare quick tunnel, so set `stream: false` when calling over one.

### 🧰 Tool calling

Both endpoints support function / tool calling in their native format, plus an Unsloth-specific shorthand for Unsloth's built-in tools.

**OpenAI-style tools:** send `tools` and `tool_choice` to `/v1/chat/completions` exactly as you would with OpenAI. Claude Code (via `/v1/messages`), opencode, Cursor, Continue, and Cline all work out of the box.

**Anthropic-style tools:** send `tools` (with `input_schema`) and `tool_choice` to `/v1/messages` exactly as you would with Claude.

Unsloth server side tools: Unsloth can execute Python, web search, and bash *server-side* and stream the results back as `tool_result` events. Opt in by adding these extra fields to either endpoint:

```json
{
  "messages": [{"role": "user", "content": "What is 123 * 456? Use Python."}],
  "stream": true,
  "enable_tools": true,
  "enabled_tools": ["python", "web_search","terminal"],
  "session_id": "my-session"
}
```

The model sees each tool's output on its next turn. For deeper coverage (schemas, streaming events, chaining), see .

{% hint style="info" %}
If you're using the Anthropic `/v1/messages` endpoint, `tool_choice` maps cleanly: Anthropic `auto` → OpenAI `auto`, Anthropic `any` → OpenAI `required`, Anthropic `{type: "tool", name: "x"}` → OpenAI `{type: "function", function: {name: "x"}}`, Anthropic `none` → OpenAI `none`.
{% endhint %}

### 📈 API monitor

Every call through this endpoint is listed live in Unsloth, in two places:

The API monitor side panel opens itself in the corner as soon as API-key traffic arrives. It summarizes the active model, live requests, errors and average latency.

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FqbcbkrU9tnkg5VCnDzCz%2Fimage.png?alt=media&amp;token=733b2b37-4e57-48c6-b826-9f356d648344" alt=""><figcaption></figcaption></figure></div>

Press "Expand to full monitor" or go to Settings>API Monitor to navigate to the full **API** page where model loading, prompts, responses, token counts, time-to-first-token, throughput, and error messages are displayed in the monitor.

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FfjIh57Mb278c072g27nk%2Fimage.png?alt=media&amp;token=3a236c7c-1f00-430b-92f3-42799346aa3c" alt="" width="563"><figcaption></figcaption></figure></div>

### ❔ Troubleshooting

**`401 Unauthorized`** :  either the `Authorization` header is missing or the key is wrong. Keys must be passed as `Authorization: Bearer sk-unsloth-…`. If you lost the key, create a new one from **Settings → API.** Unsloth doesn't show old keys after creation.

**`Lost connection to the model server`** : Unsloth couldn't reach the underlying llama.cpp server. Usually the model finished loading but crashed, or the model tab was closed inside Unsloth. Reload the model from **New Chat** and retry.

**Claude Code shows the default Anthropic model, not my local one** :  check all three env vars are exported in the **same** shell where you run `claude`:

```bash
echo $ANTHROPIC_BASE_URL
echo $ANTHROPIC_AUTH_TOKEN
echo $ANTHROPIC_MODEL
```

Then run `/model` inside Claude Code to confirm. On Windows PowerShell use `$env:ANTHROPIC_BASE_URL` etc.

**`stream: true` returns a single JSON blob instead of SSE** :  make sure you're hitting the right path (`/v1/messages` or `/v1/chat/completions`) and that your HTTP client is actually consuming the response as a stream, not buffering it.

**I can't find the name of the model to add to opencode (or OpenClaw / any other client)** : ask Unsloth directly. `GET /v1/models` returns the exact model ID you need to plug into the client's "Model ID" field:

```bash
curl http://localhost:8888/v1/models \
  -H "Authorization: Bearer sk-unsloth-xxxxxxxxxxxx"
```

You'll get back a JSON payload of the form `{"data": [{"id": "gemma-4-26B-A4B-it-GGUF", ...}]}`. Copy the `id` value, that's the string opencode's **Model ID** field (left column) and OpenClaw's `models[].id` expect. The display name on the right is whatever you want users to see.

**Tool calls aren't executed** :  The model needs to support tool calling for client-side tools (`tools` / `tool_choice`). For Unsloth's built-in tools, remember to set `enable_tools: true` **and** list the ones you want in `enabled_tools` (e.g. `["python", "web_search"]`).

* **My client reports a connection error.** Open the API monitor. No row for the call means it never reached Unsloth, compare your client's base URL against the **Base URL** shown at the top of that page.
* **The reply is cut short.** Check **Context used** on the request in the API monitor. Near 100%, or a stop reason of `length`, means the context window filled rather than the model failing.


---

# Agent Instructions
This documentation is published with GitBook. GitBook is the documentation platform designed so that both humans and AI agents can read, navigate, and reason over technical content effectively. Learn more at gitbook.com.

## Querying This Documentation
If you need additional information that is not directly available in this page, you can query the documentation by asking a question.

Perform an HTTP GET request on the following URL with the `ask` and `goal` query parameters:

```
GET https://unsloth.ai/docs/basics/api.md?ask=<question>&goal=<user_goal>
```

`ask` is the immediate question: it should be specific, self-contained, and written in natural language.
`goal` is what the user is ultimately trying to achieve, the reason they need the answer. Sharing it helps GitBook give you a better, more relevant answer. A goal is most helpful when it describes the outcome the user wants rather than restating the question. For example, with `ask=how do I create an API token`, a goal like `automate deployments from our CI pipeline` lets GitBook tailor the answer to that use case.

The response will contain a direct answer to the question and relevant excerpts and sources from the documentation.

Use this mechanism when the answer is not explicitly present in the current page, you need clarification or additional context, or you want to retrieve related documentation sections.
