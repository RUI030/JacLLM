> For the complete documentation index, see [llms.txt](https://unsloth.ai/docs/llms.txt). Markdown versions of documentation pages are available by appending `.md` to page URLs; this page is available as [Markdown](https://unsloth.ai/docs/integrations/connect-python-sdk-to-unsloth.md).

# Connect Python SDK to Unsloth

Guide to calling Unsloth's local API from Python using the official OpenAI or Anthropic SDKs including streaming, vision, function calling, and Unsloth's built-in server-side tools.

Unsloth serves three OpenAI-compatible dialects at the same base URL. Chat Completions, Responses, and Anthropic Messages,  so every mainstream Python SDK works against it. \
\
You change only the `base_url` and `api_key`  on the client; everything else (streaming, tool calling, vision, structured output) behaves the way the SDK documents. This page covers the two SDKs most developers reach for first: the official **OpenAI Python SDK** and the official **Anthropic Python SDK**.

{% hint style="info" %}
If you're not sure what URL / key / model name to use, read the API overview first. It walks you through starting, loading a model, and creating an `sk-unsloth-…` key.
{% endhint %}

### 🔑 Prerequisites

Before you run any of the snippets below you'll need:

* **Unsloth running locally** with a model loaded (note the port: typically `8000` or `8888`).
* **An `sk-unsloth-…` API key** created from **Settings → API**.
* **A model name.** The name of the GGUF model inside Unsloth (e.g. `qwen-local`, `unsloth/Qwen3.6-27B-GGUF`). If you forget it, run:

  ```bash
  curl http://localhost:8888/v1/models -H "Authorization: Bearer sk-unsloth-…"
  ```

  and copy the `id` field.

Set the key as an env var so you never paste it into code:

```bash
export UNSLOTH_STUDIO_AUTH_TOKEN=sk-unsloth-xxxxxxxxxxxx
```

#### 🤖 OpenAI SDK

Unsloth's `/v1/chat/completions` endpoint is a drop-in for the OpenAI Python SDK. The client treats Unsloth like any other OpenAI-compatible provider.

**1. Install the SDK:**

```bash
pip install openai
```

**2. Create a client** pointed at Unsloth:

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8888/v1",              # your unsloth port + /v1
    api_key=os.environ["UNSLOTH_STUDIO_AUTH_TOKEN"],     # your sk-unsloth-… key
)
```

#### Basic chat completion

```python
response = client.chat.completions.create(
    model="default",                               # the name you gave the model in unsloth or default
    messages=[
        {"role": "user", "content": "Give me two facts about Paris"}
    ],
)
print(response.choices[0].message.content)
```

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FZkxVYS7fcvwXZ8AxvaBF%2FScreenshot%202026-04-22%20at%202.38.44%E2%80%AFAM.png?alt=media&amp;token=06dece4e-dade-4c2d-bcdb-7c946cdd1290" alt=""><figcaption></figcaption></figure>

#### Streaming

Set `stream=True` and iterate over the returned generator:

```python
stream = client.chat.completions.create(
    model="qwen-local",
    messages=[{"role": "user", "content": "Write a haiku about locally-run LLMs."}],
    stream=True,
)
for chunk in stream:
    if chunk.choices:
        delta = chunk.choices[0].delta.content
        if delta:
            print(delta, end="", flush=True)
```

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2F0eItNT5zanSB8rXY4QHn%2Fopenai_streaming.png?alt=media&amp;token=2922bbf3-69da-409f-b954-76b6259233f8" alt=""><figcaption></figcaption></figure>

#### Images (vision)

Attach an image as an `image_url` content part. Unsloth accepts either an HTTP(S) URL or a `data:` base64 URI:

```python
import base64
from pathlib import Path

img_b64 = base64.b64encode(Path("test.jpg").read_bytes()).decode()

response = client.chat.completions.create(
    model="default",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                },
                {"type": "text", "text": "What's in this image?"},
            ],
        }
    ],
)
print(response.choices[0].message.content)
```

{% hint style="info" %}
The loaded model must be multimodal. If you load a text-only model, the vision request will succeed structurally but the model won't be able to "see" the image.
{% endhint %}

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FTNCX4qEMj8zFSAsOJw2Y%2Fopenai_sdk_vision_test.png?alt=media&amp;token=caa22501-66fc-4e3c-b4a0-636ebe5af4bf" alt=""><figcaption></figcaption></figure>

#### Function calling (OpenAI tools)

Pass OpenAI-style `tools` and (optionally) `tool_choice` and Unsloth forwards them to the backend. Your client is responsible for executing each tool call and returning the result on the next turn:

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name, e.g. 'Paris'"},
                },
                "required": ["city"],
            },
        },
    }
]

response = client.chat.completions.create(
    model="default",
    messages=[{"role": "user", "content": "What's the weather in Perth right now?"}],
    tools=tools,
    tool_choice="auto",
)

tool_call = response.choices[0].message.tool_calls[0]
print(tool_call.function.name, tool_call.function.arguments)
```

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2F8nzgxHsN8J23B6duQ3Zv%2Fopenai_sdk_function_calling.png?alt=media&amp;token=3551592d-31b2-4fa6-94a9-6a9f0974c21a" alt=""><figcaption></figcaption></figure>

#### Unsloth server-side tools (shorthand)

In addition to OpenAI-style client-side tools, Unsloth can execute **Python**, **bash**, and **web search** server-side and stream the results back automatically. Opt in via the `extra_body` parameter so the fields pass straight through to Unsloth:

```python
stream = client.chat.completions.create(
    model="default",
    messages=[{"role": "user", "content": "What is 123 * 456? Use Python to compute it."}],
    stream=True,
    extra_body={
        "enable_tools": True,
        "enabled_tools": ["python", "web_search"],
        "session_id": "my-session",
    },
)
for chunk in stream:
    if chunk.choices:
        delta = chunk.choices[0].delta.content
        if delta:
            print(delta, end="", flush=True)
```

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FvdZuLwIh7LT0C8y7AWaR%2FScreenshot%202026-04-22%20at%203.01.06%E2%80%AFAM.png?alt=media&amp;token=35ff3039-d941-406b-b3fc-5e1e564c7651" alt=""><figcaption></figcaption></figure>

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FnW60ezYCOJQmTjd52bnu%2FScreenshot%202026-04-22%20at%203.05.23%E2%80%AFAM.png?alt=media&amp;token=f7125db4-cb94-46f7-974d-abe58ec348a7" alt=""><figcaption></figcaption></figure>

The `session_id` is optional. Use it to persist tool state (e.g. a Python kernel) across calls.

{% hint style="info" %}
`enabled_tools` currently supports `"python"`, `"bash"`, and `"web_search"`. Tool results are streamed back as `tool_result` events so the model can see them on its next turn.
{% endhint %}

**Listing models**

```python
models = client.models.list()
for m in models.data:
    print(m.id)
```

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2F6GKdrximwyplotWu3u5s%2FScreenshot%202026-04-22%20at%203.06.57%E2%80%AFAM.png?alt=media&amp;token=48d17278-e4b0-4437-a426-5f12c0c45b1e" alt=""><figcaption></figcaption></figure>

#### 🧠 Anthropic SDK

Unsloth's `/v1/messages` endpoint is a drop-in for the Anthropic Python SDK.

**1. Install the SDK:**

```bash
pip install anthropic
```

**2. Create a client** pointed at Unsloth:

{% code overflow="wrap" %}

```python
import os
from anthropic import Anthropic

client = Anthropic(
    base_url="http://localhost:8888", # your unsloth port (no /v1 here - the SDK adds it)
    api_key="dummy", # a random none empty value
    default_headers={"Authorization": f"Bearer {os.environ['UNSLOTH_STUDIO_AUTH_TOKEN']}"} # your sk-unsloth-… key
)
```

{% endcode %}

#### Basic message

```python
message = client.messages.create(
    model="default",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Say hello in three languages."}
    ],
)
print(message.content[0].text)
```

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2Fc4yQCiRHjebKomV4H2Eh%2FScreenshot%202026-04-22%20at%202.29.04%E2%80%AFAM.png?alt=media&amp;token=4ad983da-83fd-48c0-8fa8-1fbe92fcfd40" alt=""><figcaption></figcaption></figure>

#### Streaming

The SDK exposes a context manager that yields text deltas:

```python
with client.messages.stream(
    model="default",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Explain LoRA in two sentences."}],
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
```

#### Images (vision)

Anthropic-style image content uses a `source` block with base64 data:

```python
import base64
from pathlib import Path

img_b64 = base64.standard_b64encode(Path("photo.jpg").read_bytes()).decode()

message = client.messages.create(
    model="default",
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": img_b64,
                    },
                },
                {"type": "text", "text": "What's in this image?"},
            ],
        }
    ],
)
print(message.content[0].text)
```

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FKI75sgbWxmo8BNXQEP6s%2Fanthropic_sdk_vision_test.png?alt=media&amp;token=f72c2dd6-b811-41a7-82bb-a2a6f30513ac" alt=""><figcaption></figcaption></figure>

#### Tool calling (Anthropic tools)

Pass Anthropic-style `tools` with an `input_schema` and Unsloth forwards them natively:

```python
tools = [
    {
        "name": "get_weather",
        "description": "Get the current weather for a city",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name, e.g. 'Tokyo'"},
            },
            "required": ["city"],
        },
    }
]

message = client.messages.create(
    model="default",
    max_tokens=1024,
    tools=tools,
    tool_choice={"type": "auto"},
    messages=[{"role": "user", "content": "What's the weather in Tokyo?"}],
)

for block in message.content:
    if block.type == "tool_use":
        print(block.name, block.input)
```

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FWnWPZdZOtV2o1o5FIzlD%2Fanthropic_tool_use_get_weather_tokyo.png?alt=media&amp;token=39587916-f4c0-45cf-8e59-11245b3432b8" alt=""><figcaption></figcaption></figure>

#### Unsloth server-side tools (shorthand)

The same `enable_tools` / `enabled_tools` / `session_id` shorthand works against `/v1/messages` pass it through `extra_body`:

```python
with client.messages.stream(
    model="default",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Search for Python 3.13 features and summarize."}],
    extra_body={
        "enable_tools": True,
        "enabled_tools": ["web_search", "python"],
        "session_id": "my-session",
    },
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
```

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2F2wA6aleUHPJN1gAB3ClL%2Fserver_side_tool_call_backend.png?alt=media&amp;token=7440befb-d517-473a-a431-c6b4cb413ca5" alt=""><figcaption></figcaption></figure>

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FwcIerVboFjEZPkI2vU0L%2Fserver_side_tool_call_output.png?alt=media&amp;token=33800495-70d1-4a5f-9173-cde144abecb3" alt=""><figcaption></figcaption></figure>

Unsloth emits custom `tool_result` SSE events for the model's view of each tool call's output. The Anthropic SDK passes these through its event stream unchanged.

#### JSON decoding (`response_format`)

Unsloth supports OpenAI-style structured outputs via `response_format`. Pass a JSON Schema and the model is constrained to produce JSON matching it.

````python
import json
import os
import re
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8888/v1",
    api_key=os.environ["UNSLOTH_STUDIO_AUTH_TOKEN"],
)

response = client.chat.completions.create(
    model="default",
    stream=False,
    temperature=0.0,
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": "Pick a country: Japan, Egypt, or Peru. Explain why in one sentence.",
        },
    ],
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "country_pick",
            "schema": {
                "type": "object",
                "properties": {
                    "country": {"type": "string", "enum": ["Japan", "Egypt", "Peru"]},
                    "reason":  {"type": "string"},
                },
                "required": ["country", "reason"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
)

raw = response.choices[0].message.content
# Strip the markdown fence Gemma 4 wraps around the JSON, then parse.
cleaned = re.sub(r"^```(?:json)?\s*", "", raw)
cleaned = re.sub(r"\s*```$", "", cleaned)
parsed = json.loads(cleaned)

print(json.dumps(parsed, indent=2))
print()
print("country:", parsed["country"])
print("reason :", parsed["reason"])
````

The `strict: True` flag tells Unsloth to enforce the schema during decoding rather than relying on the model to comply on its own. `additionalProperties: False` and `required` work as in standard JSON Schema.

The terminal output should look roughly like this:

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FmhPxaVA6sxkyF3nFf51f%2FScreenshot%202026-05-05%20at%201.46.44%E2%80%AFPM.png?alt=media&amp;token=50b1600d-9e5a-4d22-819a-274c6bfbf8f7" alt=""><figcaption></figcaption></figure>

### 🧪 Choosing an SDK

Both SDKs work against Unsloth. The right choice depends on the rest of your stack:

* Use the **OpenAI SDK** if your code already depends on the OpenAI Python package, you want OpenAI-style `tools` / `tool_choice`, or you plan to call the Responses API.
* Use the **Anthropic SDK** if your code already depends on the Anthropic package, you prefer Anthropic's `input_schema` tool format, or you want the Anthropic-native streaming event types.

You can use both in the same project. Unsloth serves them on the same port, so a single `sk-unsloth-…` key authenticates both.

### ❔ Troubleshooting

**`401 Unauthorized`**  The `UNSLOTH_STUDIO_AUTH_TOKEN` env var isn't set, or the key is wrong. Re-export and confirm with `echo $UNSLOTH_STUDIO_AUTH_TOKEN`.

**`404 Not Found` from the OpenAI SDK** Check that `base_url` ends in `/v1`. The OpenAI SDK appends endpoint paths to the base URL as-is.

**`404 Not Found` from the Anthropic SDK** Check that `base_url` does **not** end in `/v1`. The Anthropic SDK adds `/v1/messages` itself.

**`extra_body` fields aren't reaching Unsloth** Make sure you're on a recent `openai` / `anthropic` SDK. Older versions silently drop unknown fields. Upgrade with `pip install -U openai anthropic`.

**Streaming "hangs" then dumps everything at once** Whatever is wrapping your output is buffering. In a script, `print(..., flush=True)`; in a notebook, it's usually fine; behind a proxy, disable response buffering on the proxy.

For endpoint-level issues (wrong port, model not loading, lost connection, etc.) see the API overview page.

### Optional: set server defaults

You can configure default server behavior before connecting with the Python SDK, when using the `unsloth run` command.

```bash
# Start the server with custom defaults
unsloth run \
  --model unsloth/Qwen3-1.7B-GGUF \
  --reasoning off \
  --temp 0.6 \
  -p 8888
```

Use `--reasoning off` to turn thinking off, or `--reasoning on` to turn it on for models that support reasoning.

```bash
# Expose the API on your local network
unsloth run \
  --model unsloth/Qwen3-1.7B-GGUF \
  -H 0.0.0.0 \
  -p 8888
```

This starts the server on `0.0.0.0:8888`, allowing other devices on your local network to connect.

These settings become the server defaults when requests do not specify their own generation parameters.

Request-level values like `temperature`, `top_p`, `max_tokens`, and `stream` can still override the defaults for that request.


---

# Agent Instructions
This documentation is published with GitBook. GitBook is the documentation platform designed so that both humans and AI agents can read, navigate, and reason over technical content effectively. Learn more at gitbook.com.

## Querying This Documentation
If you need additional information that is not directly available in this page, you can query the documentation by asking a question.

Perform an HTTP GET request on the following URL with the `ask` and `goal` query parameters:

```
GET https://unsloth.ai/docs/integrations/connect-python-sdk-to-unsloth.md?ask=<question>&goal=<user_goal>
```

`ask` is the immediate question: it should be specific, self-contained, and written in natural language.
`goal` is what the user is ultimately trying to achieve, the reason they need the answer. Sharing it helps GitBook give you a better, more relevant answer. A goal is most helpful when it describes the outcome the user wants rather than restating the question. For example, with `ask=how do I create an API token`, a goal like `automate deployments from our CI pipeline` lets GitBook tailor the answer to that use case.

The response will contain a direct answer to the question and relevant excerpts and sources from the documentation.

Use this mechanism when the answer is not explicitly present in the current page, you need clarification or additional context, or you want to retrieve related documentation sections.
