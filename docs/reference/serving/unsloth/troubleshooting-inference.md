> For the complete documentation index, see [llms.txt](https://unsloth.ai/docs/llms.txt). Markdown versions of documentation pages are available by appending `.md` to page URLs; this page is available as [Markdown](https://unsloth.ai/docs/basics/inference-and-deployment/troubleshooting-inference.md).

# Troubleshooting Inference

If you're experiencing issues when running or saving your model.

### Running in Unsloth works well, but after exporting & running on other platforms, the results are poor

You might sometimes encounter an issue where your model runs and produces good results on Unsloth, but when you use it on another platform like Ollama or vLLM, the results are poor or you might get gibberish, endless/infinite generations *or* repeated output&#x73;**.**

* The most common cause of this error is using an <mark style="background-color:blue;">**incorrect chat template**</mark>**.** It’s essential to use the SAME chat template that was used when training the model in Unsloth and later when you run it in another framework, such as llama.cpp or Ollama. When inferencing from a saved model, it's crucial to apply the correct template.
* You must use the correct `eos token`. If not, you might get gibberish on longer generations.
* It might also be because your inference engine adds an unnecessary "start of sequence" token (or the lack of thereof on the contrary) so ensure you check both hypotheses!
* <mark style="background-color:green;">**Use our conversational notebooks to force the chat template - this will fix most issues.**</mark>
  * Qwen-3 14B Conversational notebook [**Open in Colab**](https://colab.research.google.com/github/unslothai/notebooks/blob/main/nb/Qwen3_\(14B\)-Reasoning-Conversational.ipynb)
  * Gemma-3 4B Conversational notebook [**Open in Colab**](https://colab.research.google.com/github/unslothai/notebooks/blob/main/nb/Gemma3_\(4B\).ipynb)
  * Llama-3.2 3B Conversational notebook [**Open in Colab**](https://colab.research.google.com/github/unslothai/notebooks/blob/main/nb/Llama3.2_\(1B_and_3B\)-Conversational.ipynb)
  * Phi-4 14B Conversational notebook [**Open in Colab**](https://colab.research.google.com/github/unslothai/notebooks/blob/main/nb/Phi_4-Conversational.ipynb)
  * Mistral v0.3 7B Conversational notebook [**Open in Colab**](https://colab.research.google.com/github/unslothai/notebooks/blob/main/nb/Mistral_v0.3_\(7B\)-Conversational.ipynb)
  * **More notebooks in our** [**notebooks repo**](https://github.com/unslothai/notebooks)**.**

### Saving to `safetensors`, not `bin` format in Colab

We save to `.bin` in Colab so it's like 4x faster, but set `safe_serialization = None` to force saving to `.safetensors`. So `model.save_pretrained(..., safe_serialization = None)` or `model.push_to_hub(..., safe_serialization = None)`

### If saving to GGUF or vLLM 16bit crashes

You can try reducing the maximum GPU usage during saving by changing `maximum_memory_usage`.

The default is `model.save_pretrained(..., maximum_memory_usage = 0.75)`. Reduce it to say 0.5 to use 50% of GPU peak memory or lower. This can reduce OOM crashes during saving.


---

# Agent Instructions
This documentation is published with GitBook. GitBook is the documentation platform designed so that both humans and AI agents can read, navigate, and reason over technical content effectively. Learn more at gitbook.com.

## Querying This Documentation
If you need additional information that is not directly available in this page, you can query the documentation by asking a question.

Perform an HTTP GET request on the following URL with the `ask` and `goal` query parameters:

```
GET https://unsloth.ai/docs/basics/inference-and-deployment/troubleshooting-inference.md?ask=<question>&goal=<user_goal>
```

`ask` is the immediate question: it should be specific, self-contained, and written in natural language.
`goal` is what the user is ultimately trying to achieve, the reason they need the answer. Sharing it helps GitBook give you a better, more relevant answer. A goal is most helpful when it describes the outcome the user wants rather than restating the question. For example, with `ask=how do I create an API token`, a goal like `automate deployments from our CI pipeline` lets GitBook tailor the answer to that use case.

The response will contain a direct answer to the question and relevant excerpts and sources from the documentation.

Use this mechanism when the answer is not explicitly present in the current page, you need clarification or additional context, or you want to retrieve related documentation sections.
