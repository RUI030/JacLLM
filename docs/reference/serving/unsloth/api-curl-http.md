> For the complete documentation index, see [llms.txt](https://unsloth.ai/docs/llms.txt). Markdown versions of documentation pages are available by appending `.md` to page URLs; this page is available as [Markdown](https://unsloth.ai/docs/integrations/connect-curl-and-http-to-unsloth.md).

# Connect Curl & HTTP to Unsloth

Guide to hitting Unsloth's API with curl (or any HTTP client), complete with copy-pasteable recipes for every endpoint and feature..

Unsloth exposes three OpenAI/Anthropic-compatible wire formats at the same base URL on the port Unsloth started on. All of them take an `Authorization: Bearer sk-unsloth-…` header and return either JSON or SSE, depending on whether you set `stream`.

This page groups the recipes by endpoint (`/v1/chat/completions`, `/v1/messages`, `/v1/responses`, `/v1/models`, `/v1/embeddings`, `/v1/systemone`) and ends with a shared section on Unsloth's built-in **server-side tools**, which work across all the chat endpoints.

{% hint style="info" %}
If you're not sure what URL / key / model name to use, read the API overview first. It walks you through starting Unsloth, loading a model, and creating an `sk-unsloth-…` key.
{% endhint %}

### 🔑 Authentication

Every request needs an `Authorization` header:

```
Authorization: Bearer sk-unsloth-xxxxxxxxxxxx
```

To keep keys out of your shell history, export the key once and reference the env var:

```bash
export UNSLOTH_STUDIO_AUTH_TOKEN=sk-unsloth-xxxxxxxxxxxx
```

The snippets below inline the key as `sk-unsloth-xxxxxxxxxxxx` for clarity. In practice, substitute `$UNSLOTH_STUDIO_AUTH_TOKEN`.

### 📋 List loaded models

```bash
curl http://localhost:8888/v1/models \
  -H "Authorization: Bearer sk-unsloth-xxxxxxxxxxxx"
```

Response:

```json
{
  "object": "list",
  "data": [
    {"id": "unsloth/gemma-3-27b-it-GGUF", "object": "model", "owned_by": "local"}
  ]
}
```

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FgVC1VPkCkUQBVg0HScEc%2FScreenshot%202026-04-22%20at%203.06.57%E2%80%AFAM.png?alt=media&amp;token=6f77cc78-bd0e-4141-b555-b232df1036dc" alt=""><figcaption></figcaption></figure>

Use the `id` field whenever a request needs a `"model"` value (or when a client like opencode asks for a **Model ID**).

### 💬 Chat Completions (`/v1/chat/completions`)

The OpenAI Chat Completions dialect. The broadest compatibility surface. Works with the OpenAI SDK, opencode, Cursor, Continue, Cline, Open WebUI, SillyTavern, and most OpenAI-compatible tools.

#### Basic request

```bash
curl http://localhost:8888/v1/chat/completions \
  -H "Authorization: Bearer sk-unsloth-xxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "default",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2Fvy9TyeJZljKrMJAath0L%2FScreenshot%202026-04-22%20at%203.40.35%E2%80%AFAM.png?alt=media&amp;token=98f8d622-83c0-4f55-aa37-d3571f0a38cd" alt=""><figcaption></figcaption></figure>

#### Streaming

Add `"stream": true` and the response switches to Server-Sent Events (`text/event-stream`). Tell `curl` to flush as bytes arrive with `--no-buffer` (`-N`):

```bash
curl -N http://localhost:8888/v1/chat/completions \
  -H "Authorization: Bearer sk-unsloth-xxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-local",
    "messages": [{"role": "user", "content": "Write a haiku about locally-run LLMs."}],
    "stream": true
  }'
```

Each line of the response looks like `data: {"choices":[{"delta":{"content":"..."}}]}`, ending with `data: [DONE]`.

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FsazSu4RpyiEa6HeamYbj%2FScreenshot%202026-04-22%20at%203.42.05%E2%80%AFAM.png?alt=media&amp;token=f62cf129-74cd-4e8e-986a-1755eeb0e048" alt=""><figcaption></figcaption></figure>

#### Images (vision)

Attach an image as an `image_url` content part in the user message. The URL can be HTTPS or a base64 `data:` URI:

```bash
# Embed a local file as base64 (trimmed for brevity)
IMG=$(base64 -w 0 test.jpg)

cat > /tmp/request.json <<EOF
{
  "model":"default",
  "messages":[{"role":"user","content":[
    {"type":"text","text":"Describe the image."},
    {"type":"image_url","image_url":{"url":"data:image/jpeg;base64,$IMG"}}
  ]}],
  "max_tokens":200,
  "stream":false
}
EOF

curl http://localhost:8888/v1/chat/completions \
  -H "Authorization: Bearer sk-unsloth-xxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d @/tmp/request.json
```

{% hint style="info" %}
The loaded model must be multimodal. If you load a text-only model the request succeeds structurally but the model won't process the image.
{% endhint %}

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2F9yO7ersnyaIj3X8UkD5q%2FScreenshot%202026-04-22%20at%203.59.30%E2%80%AFAM.png?alt=media&amp;token=9e0af9e5-d565-4acd-8b4a-020c02d74cd8" alt=""><figcaption></figcaption></figure>

#### Function calling (OpenAI tools)

Pass OpenAI-style `tools` and (optionally) `tool_choice`. Your client runs each tool call and returns the result on the next turn.

```bash
curl http://localhost:8888/v1/chat/completions \
  -H "Authorization: Bearer sk-unsloth-xxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model":"default",
    "messages":[{"role":"user","content":"What is the weather in Paris?"}],
    "tools":[{
      "type":"function",
      "function":{
        "name":"get_weather",
        "description":"Get current weather for a city.",
        "parameters":{
          "type":"object",
          "properties":{"city":{"type":"string"}},
          "required":["city"]
        }
      }
    }],
    "tool_choice":"required"
  }' | jq '.choices[0].message, .usage'
```

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2F39CDJk0Z1WhG5JyaJIfV%2Ftests_codex_pr_2.png?alt=media&amp;token=c3f01286-7dc9-47dd-b7f9-9ee8c2d3cb2f" alt=""><figcaption></figcaption></figure>

### 📨 Anthropic Messages (`/v1/messages`)

Unsloth's Anthropic-compatible dialect used by Claude Code, the Anthropic SDK, OpenClaw, and any client that speaks the Messages API.

#### Basic request

```bash
curl http://localhost:8888/v1/messages \
  -H "Authorization: Bearer sk-unsloth-xxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "default",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

{% hint style="warning" %}
`max_tokens` is required on `/v1/messages` (it's optional on `/v1/chat/completions`).
{% endhint %}

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FOz7xeC4dRnDjO5GDAsmC%2FScreenshot%202026-04-22%20at%204.01.52%E2%80%AFAM.png?alt=media&amp;token=b7025ce1-e3a8-46ad-91fa-e87b96a22d6b" alt=""><figcaption></figcaption></figure>

#### Streaming

```bash
curl -N http://localhost:8888/v1/messages \
  -H "Authorization: Bearer sk-unsloth-xxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-local",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "Explain LoRA in two sentences."}],
    "stream": true
  }'
```

Events follow Anthropic's SSE shape: `message_start`, `content_block_start`, `content_block_delta`, `content_block_stop`, `message_delta`, `message_stop`, plus Unsloth's custom `tool_result` event for server-side tool output.

#### Images (vision)

Anthropic-style image content uses a `source` block with base64 data:

```bash
IMG=$(base64 -w 0 test.jpg)

cat > /tmp/request.json <<EOF
{
  "messages":[{"role":"user","content":[
    {"type":"text","text":"Describe the image."},
    {"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":"$IMG"}}
  ]}],
  "max_tokens":200,
  "stream":true
}
EOF

curl -s http://localhost/v1/messages \
  -H "Authorization: Bearer sk-unsloth-xxxxxxxx" \
  -H "Content-Type: application/json" \
  -d @/tmp/request.json
```

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FMkzYMtkw9dt0V7cbqduU%2FScreenshot%202026-04-22%20at%204.03.28%E2%80%AFAM.png?alt=media&amp;token=de854c5a-b399-4736-83bb-23ffe26981e2" alt=""><figcaption></figcaption></figure>

#### Tool calling (Anthropic tools)

```bash
curl http://localhost:8888/v1/messages \
  -H "Authorization: Bearer sk-unsloth-xxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-local",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "Whats the weather in Tokyo?"}],
    "tools": [
      {
        "name": "get_weather",
        "description": "Get the current weather for a city",
        "input_schema": {
          "type": "object",
          "properties": {
            "city": {"type": "string"}
          },
          "required": ["city"]
        }
      }
    ],
    "tool_choice": {"type": "auto"}
  }'
```

`tool_choice` values map as follows to the OpenAI dialect: Anthropic `auto` → OpenAI `auto`, Anthropic `any` → OpenAI `required`, Anthropic `{type: "tool", name: "x"}` → OpenAI `{type: "function", function: {name: "x"}}`, Anthropic `none` → OpenAI `none`.

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2Fqb37JN1ffgBFBKyd1uWD%2FScreenshot%202026-04-22%20at%204.07.43%E2%80%AFAM.png?alt=media&amp;token=1fb7ec5d-8326-4e9f-b752-2d5d7e830a39" alt=""><figcaption></figcaption></figure>

### 🧬 Responses (`/v1/responses`)

Unsloth also speaks the newer **OpenAI Responses API**, the protocol Codex and other recent OpenAI clients have moved to.

```bash
curl http://localhost:8888/v1/responses \
  -H "Authorization: Bearer sk-unsloth-xxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-local",
    "input": "Write a one-sentence greeting."
  }'
```

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FhmyMSCTgdD1NYiLUdYNZ%2Fopenai_responses.png?alt=media&amp;token=dd56bd52-71db-46f3-8f6c-1499df8e443c" alt=""><figcaption></figcaption></figure>

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FZ3MEH4vV2RjxhLe0DsWJ%2Fresponses_function_calling.png?alt=media&amp;token=a8637d5a-51d2-47f5-9658-add9cdb757e3" alt=""><figcaption></figcaption></figure>

For streaming, add `"stream": true` and use `curl -N`. Responses streams use named events such as `response.output_text.delta`, rather than Chat Completions chunks.

Send the full conversation history in `input` on each request. Unsloth does not support `previous_response_id` or `conversation` for server-managed history.

#### Embeddings (`/v1/embeddings`)

Generate embedding vectors from text using a loaded embedding GGUF or Unsloth’s configured embedding model.

With `"model": "default"`, Unsloth uses the resident embedding GGUF when available, otherwise its configured embedding model.

```bash
curl http://localhost:8888/v1/embeddings \
  -H "Authorization: Bearer sk-unsloth-xxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "default",
    "input": [
      "Unsloth runs local models.",
      "Generate a vector for each text."
    ],
    "encoding_format": "float"
  }'
```

The response contains a `data` array with an `embedding` vector and `index` for each input. Use text input for portability; support for token-array input depends on the embedding backend.

#### Decision API (`/v1/systemone`)

Enable the **Decision API** in **Settings → API** and select a decision model first. The endpoint returns `404` when the Decision API is disabled.

Requests contain `state` and named `questions`. Supported question types are:

* `noul`: a yes/no decision.
* `choice`: a decision between named options supplied in `criteria`.
* `score`: a score based on ordered criteria levels supplied in `criteria`.

Use `"model": "default"` to select the configured decision model.

```bash
curl http://localhost:8888/v1/systemone \
  -H "Authorization: Bearer sk-unsloth-xxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "default",
    "state": "The customer says their order arrived damaged and requests a refund.",
    "questions": {
      "refund_requested": {
        "type": "noul",
        "instructions": "Does the customer request a refund?"
      }
    }
  }'
```

To discover decision models:

```bash
curl "http://localhost:8888/v1/models?output_modalities=decisions" \
  -H "Authorization: Bearer sk-unsloth-xxxxxxxxxxxx"
```

Replace `8888` with your Unsloth port and the example API key with your own.

### 🧰 Unsloth server-side tools (shorthand)

In addition to client-side function calling, Unsloth can execute **Python**, **bash**, and **web search** server-side and stream the results back as custom `tool_result` events. This is the feature that makes Unsloth feel like a "real" agent out of the box, no round-tripping tool calls through your client.

Opt in by passing these extra fields to **either** `/v1/chat/completions` or `/v1/messages`:

| Field             | Type            | Notes                                                                    |
| ----------------- | --------------- | ------------------------------------------------------------------------ |
| `enable_thinking` | `boolean`       | `false` to disable thinking. `true` by default                           |
| `enable_tools`    | `boolean`       | `true` to enable server-side tool execution.                             |
| `enabled_tools`   | `array<string>` | Which tools the model can call. Supports `python`, `bash`, `web_search`. |
| `session_id`      | `string`        | Optional. Persists tool state (e.g. Python kernel) across calls.         |

#### Thinking mode

Thinking mode is enabled by default.&#x20;

```bash
curl http://localhost:8888/v1/chat/completions \
  -H "Authorization: Bearer sk-unsloth-xxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "default",
    "messages": [{"role": "user", "content": "summarize quantum tunneling in one sentence"}],
    "stream": false
  }'
```

The model will think before providing an answer.

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2F4XHr9KJhzpFEibCGEuHF%2FScreenshot%202026-04-22%20at%2012.22.46%E2%80%AFPM.png?alt=media&amp;token=15fa68ae-0ca5-464f-af16-25cfabc84c33" alt=""><figcaption></figcaption></figure>

To disable thinking pass `enable_thinking: false` in your request. The model will provide an answer without thinking first.

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FKQR2nh8sb5G1zUc7YSs9%2FScreenshot%202026-04-22%20at%2012.25.47%E2%80%AFPM.png?alt=media&amp;token=4646a17e-2217-4f00-9e39-5362f989126f" alt=""><figcaption></figcaption></figure>

#### Python execution

```bash
curl http://localhost:8888/v1/chat/completions \
  -H "Authorization: Bearer sk-unsloth-xxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-local",
    "messages": [{"role": "user", "content": "What is 123 * 456? Use code to compute it."}],
    "stream": false,
    "enable_tools": true,
    "enabled_tools": ["python"],
    "session_id": "my-session"
  }'
```

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FVGbYtwBfSoqgZov5ivMA%2FScreenshot%202026-04-22%20at%204.16.13%E2%80%AFAM.png?alt=media&amp;token=28b83469-24fb-412d-9489-a0c6b92dd8b5" alt=""><figcaption></figcaption></figure>

#### Web search + Python (streaming)

```bash
curl http://localhost:8888/v1/chat/completions \
  -H "Authorization: Bearer sk-unsloth-xxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-local",
    "messages": [{"role": "user", "content": "Search for Python 3.13 features"}],
    "stream": true,
    "enable_tools": true,
    "enabled_tools": ["web_search", "python"],
    "session_id": "my-session"
  }'
```

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FzSFyzwXtJ0Hgvqq7gZcV%2FScreenshot%202026-04-22%20at%204.25.13%E2%80%AFAM.png?alt=media&amp;token=a8fc5908-cb11-4ec9-85c6-77a6b5c2e205" alt=""><figcaption></figcaption></figure>

#### On `/v1/messages`

The same shorthand works against the Anthropic Messages endpoint:

```bash
curl http://localhost:8888/v1/messages \
  -H "Authorization: Bearer sk-unsloth-xxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-local",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "Search for Python 3.13 features"}],
    "stream": true,
    "enable_tools": true,
    "enabled_tools": ["web_search", "python"],
    "session_id": "my-session"
  }'
```

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FPpJxE60f2J59T5o85tQ1%2FScreenshot%202026-04-22%20at%204.28.43%E2%80%AFAM.png?alt=media&amp;token=870d74cb-dd8e-42c1-adeb-287807b22e16" alt=""><figcaption></figcaption></figure>

Unsloth streams its own `tool_result` SSE events in addition to the standard Anthropic / OpenAI event types, The model sees each tool's output on its next turn.

### ❔ Troubleshooting

**`401 Unauthorized`** **-** The `Authorization` header is missing or the key is wrong. Double-check: `Authorization: Bearer sk-unsloth-…`.

**`curl` hangs on streaming requests -** Add `-N` (same as `--no-buffer`). Without it, `curl` buffers the SSE stream and you see nothing until the end.

**Base64 encoding differs between OSes** **-** Linux's `base64` defaults to wrapping lines, macOS / BSD does not. Use `base64 -w 0` on Linux, `base64` on macOS, or pipe the output through `tr -d '\n'`.

**JSON escaping in shells** **-** Heredocs (`-d @file.json`) are cleaner than inline strings once the body gets complex. Example: `curl ... -d @body.json`.

**`max_tokens` errors on `/v1/messages`** **-** The Anthropic dialect requires it. Add `"max_tokens": 1024` (or whatever limit you want).

For endpoint-level issues (model not loading, connection dropped, wrong port) see the API overview page.

### Optional: tune server defaults

You can customize default behavior when starting the server with `unsloth run`.

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

#### Override settings per request

You can also override generation settings directly in each API request.

```bash
curl http://localhost:8888/v1/chat/completions \
  -H "Authorization: Bearer $UNSLOTH_STUDIO_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "default",
    "messages": [
      {
        "role": "user",
        "content": "Write a short poem about local AI."
      }
    ],
    "temperature": 0.8,
    "top_p": 0.9,
    "max_tokens": 512
  }'
```

Request-level values like `temperature`, `top_p`, `max_tokens`, and `stream` override the server defaults for that request.


---

# Agent Instructions
This documentation is published with GitBook. GitBook is the documentation platform designed so that both humans and AI agents can read, navigate, and reason over technical content effectively. Learn more at gitbook.com.

## Querying This Documentation
If you need additional information that is not directly available in this page, you can query the documentation by asking a question.

Perform an HTTP GET request on the following URL with the `ask` and `goal` query parameters:

```
GET https://unsloth.ai/docs/integrations/connect-curl-and-http-to-unsloth.md?ask=<question>&goal=<user_goal>
```

`ask` is the immediate question: it should be specific, self-contained, and written in natural language.
`goal` is what the user is ultimately trying to achieve, the reason they need the answer. Sharing it helps GitBook give you a better, more relevant answer. A goal is most helpful when it describes the outcome the user wants rather than restating the question. For example, with `ask=how do I create an API token`, a goal like `automate deployments from our CI pipeline` lets GitBook tailor the answer to that use case.

The response will contain a direct answer to the question and relevant excerpts and sources from the documentation.

Use this mechanism when the answer is not explicitly present in the current page, you need clarification or additional context, or you want to retrieve related documentation sections.
