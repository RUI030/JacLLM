> For the complete documentation index, see [llms.txt](https://unsloth.ai/docs/llms.txt). Markdown versions of documentation pages are available by appending `.md` to page URLs; this page is available as [Markdown](https://unsloth.ai/docs/integrations/connections/vllm.md).

# Connect vLLM to Unsloth for Local Chat Inference

Learn how to connect **vLLM to** [**Unsloth**](https://github.com/unslothai/unsloth) using vLLM’s **OpenAI-compatible API** so you can serve models and chat with them locally inside a open-source UI chat interface. This guide walks through installing vLLM, launching a local vLLM server, configuring the API base URL, loading available model IDs, and selecting your hosted vLLM model.

By the end, your vLLM-served models will appear alongside local models, giving you a fast and flexible way to run external LLM inference from a UI chat interface.

### Setup

{% stepper %}
{% step %}

#### Install vLLM

Install vLLM first so you can run the `vllm serve` command. Follow the official [vLLM install guide](https://docs.vllm.ai/en/stable/getting_started/installation/) for your platform and hardware.

After installing, check that vLLM works in your terminal: `vllm --help`
{% endstep %}

{% step %}

#### Choose a model

vLLM serves models from Hugging Face.

For example, start a vLLM server with an Unsloth model:

```bash
vllm serve unsloth/gemma-4-26B-A4B-it 
\ --dtype auto
```

This exposes an API endpoint at:

`http://localhost:8000/v1`

To require an API key, add:

```bash
--api-key token-abc123
```

{% endstep %}

{% step %}

#### Connect vLLM to Unsloth

Open **Settings → Connections**, then click **Add Connection**.

Select **vLLM**, then enter your server details.

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FN80ObNBvpN7hDypheYkt%2Fimage.png?alt=media&amp;token=481f4c1f-afb6-438d-ae35-85566f15e414" alt=""><figcaption></figcaption></figure>

Enter your vLLM server details:

* **API key:** leave empty unless you started vLLM with --api-key
* **Base URL:** for example, <http://localhost:8000/v1>
* **Reasoning model:** enable this if the served model supports thinking
* **Model IDs:** click **Load Models**, or enter custom IDs manually

After you click **Add Connection**, the models you enabled will appear under **Connection** in the model dropdown.
{% endstep %}

{% step %}

#### Ready to Chat

After saving the connection, your vLLM model will appear under **Connected** in the model dropdown. Select it to start chatting through your vLLM server.

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FpoXSmL3PcpprEy8CIT7S%2Fexport-1779046578662.gif?alt=media&amp;token=acf1de86-6fa4-466f-97f7-2d91662a124e" alt=""><figcaption></figcaption></figure>

{% hint style="info" %}
If your vLLM server is slow to respond (especially during model loading), you can adjust the timeout:

```bash
AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST=30
```

{% endhint %}
{% endstep %}
{% endstepper %}

### Common vLLM arguments

The example above uses the core serving settings. You can add more vllm serve arguments depending on your model and hardware.

Common options include:

```bash
vllm serve unsloth/gemma-4-26B-A4B-it \
  --dtype auto \
  --host 0.0.0.0 \
  --port 8000 \
  --api-key token-abc123 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.9
```

For the full list of vLLM server arguments, see the official vLLM [OpenAI-compatible server](https://docs.vllm.ai/en/stable/serving/openai_compatible_server/) docs.


---

# Agent Instructions
This documentation is published with GitBook. GitBook is the documentation platform designed so that both humans and AI agents can read, navigate, and reason over technical content effectively. Learn more at gitbook.com.

## Querying This Documentation
If you need additional information that is not directly available in this page, you can query the documentation by asking a question.

Perform an HTTP GET request on the following URL with the `ask` and `goal` query parameters:

```
GET https://unsloth.ai/docs/integrations/connections/vllm.md?ask=<question>&goal=<user_goal>
```

`ask` is the immediate question: it should be specific, self-contained, and written in natural language.
`goal` is what the user is ultimately trying to achieve, the reason they need the answer. Sharing it helps GitBook give you a better, more relevant answer. A goal is most helpful when it describes the outcome the user wants rather than restating the question. For example, with `ask=how do I create an API token`, a goal like `automate deployments from our CI pipeline` lets GitBook tailor the answer to that use case.

The response will contain a direct answer to the question and relevant excerpts and sources from the documentation.

Use this mechanism when the answer is not explicitly present in the current page, you need clarification or additional context, or you want to retrieve related documentation sections.
