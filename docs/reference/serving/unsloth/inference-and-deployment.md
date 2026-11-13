> For the complete documentation index, see [llms.txt](https://unsloth.ai/docs/llms.txt). Markdown versions of documentation pages are available by appending `.md` to page URLs; this page is available as [Markdown](https://unsloth.ai/docs/basics/inference-and-deployment.md).

# Inference & Deployment

Learn how to save your finetuned model so you can run it in your favorite inference engine.

You can also run your fine-tuned models by using [Unsloth's 2x faster inference](/docs/basics/inference-and-deployment/unsloth-inference.md).

<table data-card-size="large" data-view="cards"><thead><tr><th></th><th data-hidden data-card-target data-type="content-ref"></th><th data-hidden data-type="content-ref"></th></tr></thead><tbody><tr><td><a href="/docs/new/studio.md#run-models-locally">Unsloth Studio Chat</a></td><td><a href="/docs/new/studio/chat.md">Chat with models</a></td><td></td></tr><tr><td><a href="/docs/basics/inference-and-deployment/saving-to-gguf.md">llama.cpp - Saving to GGUF</a></td><td><a href="/docs/basics/inference-and-deployment/saving-to-gguf.md">GGUF &amp; llama.cpp</a></td><td><a href="/docs/basics/inference-and-deployment/saving-to-gguf.md">GGUF &amp; llama.cpp</a></td></tr><tr><td><a href="/docs/basics/api.md">Unsloth API endpoint</a></td><td><a href="/docs/basics/api.md">Unsloth API</a></td><td></td></tr><tr><td><a href="/docs/basics/inference-and-deployment/vllm-guide.md">vLLM</a></td><td><a href="/docs/basics/inference-and-deployment/vllm-guide.md">vLLM</a></td><td><a href="/docs/basics/inference-and-deployment/vllm-guide.md">vLLM</a></td></tr><tr><td><a href="/docs/basics/inference-and-deployment/saving-to-ollama.md">Ollama</a></td><td><a href="/docs/basics/inference-and-deployment/saving-to-ollama.md">Ollama</a></td><td><a href="/docs/basics/inference-and-deployment/saving-to-ollama.md">Ollama</a></td></tr><tr><td><a href="/docs/integrations/connections.md">Connecting to a Provider</a></td><td><a href="/docs/integrations/connections.md">Connect a Provider</a></td><td></td></tr><tr><td><a href="/docs/basics/inference-and-deployment/sglang-guide.md">SGLang</a></td><td><a href="/docs/basics/inference-and-deployment/sglang-guide.md">SGLang</a></td><td><a href="/docs/basics/inference-and-deployment/vllm-guide/vllm-engine-arguments.md">vLLM Engine Arguments</a></td></tr><tr><td><a href="/docs/basics/inference-and-deployment/troubleshooting-inference.md">Troubleshooting</a></td><td><a href="/docs/basics/inference-and-deployment/troubleshooting-inference.md">Troubleshooting Inference</a></td><td><a href="/docs/basics/inference-and-deployment/troubleshooting-inference.md">Troubleshooting Inference</a></td></tr><tr><td><a href="/docs/basics/inference-and-deployment/llama-server-and-openai-endpoint.md">llama-server &#x26; OpenAI endpoint</a></td><td><a href="/docs/basics/inference-and-deployment/llama-server-and-openai-endpoint.md">llama-server</a></td><td></td></tr><tr><td><a href="/docs/basics/nvfp4.md">NVFP4</a></td><td></td><td></td></tr></tbody></table>


---

# Agent Instructions
This documentation is published with GitBook. GitBook is the documentation platform designed so that both humans and AI agents can read, navigate, and reason over technical content effectively. Learn more at gitbook.com.

## Querying This Documentation
If you need additional information that is not directly available in this page, you can query the documentation by asking a question.

Perform an HTTP GET request on the following URL with the `ask` and `goal` query parameters:

```
GET https://unsloth.ai/docs/basics/inference-and-deployment.md?ask=<question>&goal=<user_goal>
```

`ask` is the immediate question: it should be specific, self-contained, and written in natural language.
`goal` is what the user is ultimately trying to achieve, the reason they need the answer. Sharing it helps GitBook give you a better, more relevant answer. A goal is most helpful when it describes the outcome the user wants rather than restating the question. For example, with `ask=how do I create an API token`, a goal like `automate deployments from our CI pipeline` lets GitBook tailor the answer to that use case.

The response will contain a direct answer to the question and relevant excerpts and sources from the documentation.

Use this mechanism when the answer is not explicitly present in the current page, you need clarification or additional context, or you want to retrieve related documentation sections.
