> For the complete documentation index, see [llms.txt](https://unsloth.ai/docs/llms.txt). Markdown versions of documentation pages are available by appending `.md` to page URLs; this page is available as [Markdown](https://unsloth.ai/docs/new/studio/export.md).

# Export models with Unsloth Studio

Learn how to export your safetensor or LoRA model files to GGUF or other formats.

Use [Unsloth Studio](/docs/new/studio.md) to export, save, or convert models to GGUF, Safetensors, or LoRA for deployment, sharing, or local inference in Unsloth, llama.cpp, Ollama, vLLM, and more. Export a trained checkpoint or convert any existing model.

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FrrFY8YczW3dDpfYi1k9f%2FScreenshot%202026-03-15%20at%209.28.19%E2%80%AFPM.png?alt=media&amp;token=d2729e16-799f-48f0-8b07-0248b93fa599" alt="" width="563"><figcaption></figcaption></figure></div>

{% stepper %}
{% step %}

### Select Training Run

Start by selecting the training run you want to export from. Each run represents a complete training session and may contain multiple checkpoints.

After choosing a run, select the checkpoint to export. A checkpoint is a saved version of the model created during training.

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FzB12XFNP3UjoAT1l9vz3%2Fimage.png?alt=media&amp;token=021b8864-b2c5-4a92-927e-e23350610036" alt="" width="563"><figcaption></figcaption></figure></div>
{% endstep %}

{% step %}

### Select Checkpoint

Later checkpoints typically represent the final trained model, but you can export any checkpoint depending on your needs.

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2F8VfRPUcY3w6zYfNmAIDn%2Fimage.png?alt=media&amp;token=42565a7d-e62f-4cf0-bd33-90422f1b2194" alt="" width="560"><figcaption></figcaption></figure></div>
{% endstep %}

{% step %}

### Export Methods

Depending on your workflow, you can export a merged model, LoRA adapter weights, or a GGUF model for local inference.

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2Fh4sPts9rJhHiGqf0UxIs%2Fimage.png?alt=media&amp;token=4f1d6a76-bd40-4471-ab8d-0b2fe33d0410" alt=""><figcaption></figcaption></figure></div>

Each export method produces a different version of the model depending on how you plan to run or share it. The table below explains what each option exports.

| Export Type      | Description                                                                                       |
| ---------------- | ------------------------------------------------------------------------------------------------- |
| Merged Model     | **16-bit model** with the LoRA adapter merged into the base weights.                              |
| LoRA Only        | Exports **only the adapter weights**. Requires the original base model.                           |
| GGUF / llama.cpp | Converts the model to **GGUF format** for Unsloth / llama.cpp **/** Ollama / LM Studio inference. |
| {% endstep %}    |                                                                                                   |

{% step %}

### Export / Save Locally

When exporting a model, you can choose where the resulting files should be saved. Models can be downloaded directly to your machine or pushed to the Hugging Face Hub for hosting and sharing.

Save the exported model files directly to your machine. This option is useful for running the model locally, distributing files manually, or integrating with local inference tools.

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FfsBaE8V2o69jSyCVGIz4%2Fimage.png?alt=media&amp;token=4ef3fa06-d25b-424a-91e3-42debd3b6908" alt="" width="325"><figcaption></figcaption></figure></div>
{% endstep %}

{% step %}

### Push to Hub

Upload the exported model to the Hugging Face Hub. This allows you to host, share, and deploy the model from a central repository.

You will need a Hugging Face write token to publish the model.

<div data-with-frame="true"><figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2FrvVnuVUYQWv2nkrgFxpK%2Fimage.png?alt=media&amp;token=5e0b91fe-5225-4bff-9fa9-ec1fb3867b1a" alt="" width="325"><figcaption></figcaption></figure></div>

{% hint style="success" %}
If you are already authenticated with the Hugging Face CLI, the write token can be left empty.
{% endhint %}
{% endstep %}
{% endstepper %}


---

# Agent Instructions
This documentation is published with GitBook. GitBook is the documentation platform designed so that both humans and AI agents can read, navigate, and reason over technical content effectively. Learn more at gitbook.com.

## Querying This Documentation
If you need additional information that is not directly available in this page, you can query the documentation by asking a question.

Perform an HTTP GET request on the following URL with the `ask` and `goal` query parameters:

```
GET https://unsloth.ai/docs/new/studio/export.md?ask=<question>&goal=<user_goal>
```

`ask` is the immediate question: it should be specific, self-contained, and written in natural language.
`goal` is what the user is ultimately trying to achieve, the reason they need the answer. Sharing it helps GitBook give you a better, more relevant answer. A goal is most helpful when it describes the outcome the user wants rather than restating the question. For example, with `ask=how do I create an API token`, a goal like `automate deployments from our CI pipeline` lets GitBook tailor the answer to that use case.

The response will contain a direct answer to the question and relevant excerpts and sources from the documentation.

Use this mechanism when the answer is not explicitly present in the current page, you need clarification or additional context, or you want to retrieve related documentation sections.
