> For the complete documentation index, see [llms.txt](https://unsloth.ai/docs/llms.txt). Markdown versions of documentation pages are available by appending `.md` to page URLs; this page is available as [Markdown](https://unsloth.ai/docs/basics/chat-templates.md).

# Chat Templates

Learn the fundamentals and customization options of chat templates, including Conversational, ChatML, ShareGPT, Alpaca formats, and more!

In our GitHub, we have a list of every chat template Unsloth uses including for Llama, Mistral, Phi-4 etc. So if you need any pointers on the formatting or use case, you can view them here: [github.com/unslothai/unsloth/blob/main/unsloth/chat\_templates.py](https://github.com/unslothai/unsloth/blob/main/unsloth/chat_templates.py)

#### List of Colab chat template notebooks:

* [Conversational](https://colab.research.google.com/github/unslothai/notebooks/blob/main/nb/Llama3.2_\(1B_and_3B\)-Conversational.ipynb)
* [ChatML](https://colab.research.google.com/github/unslothai/notebooks/blob/main/nb/Llama3_\(8B\)-Ollama.ipynb)
* [Ollama](https://colab.research.google.com/drive/1WZDi7APtQ9VsvOrQSSC5DDtxq159j8iZ?usp=sharing)
* [Text Classification](https://github.com/timothelaborie/text_classification_scripts/blob/main/unsloth_classification.ipynb) by Timotheeee
* [Multiple Datasets](https://colab.research.google.com/drive/1njCCbE1YVal9xC83hjdo2hiGItpY_D6t?usp=sharing) by Flail

### Adding new tokens

Unsloth has a function called `add_new_tokens` which allows you to add new tokens to your finetune. For example if you want to add `<CHARACTER_1>`, `<THINKING>` and `<SCRATCH_PAD>` we can do the following:

```python
model, tokenizer = FastLanguageModel.from_pretrained(...)
from unsloth import add_new_tokens
add_new_tokens(model, tokenizer, new_tokens = ["<CHARACTER_1>", "<THINKING>", "<SCRATCH_PAD>"])
model = FastLanguageModel.get_peft_model(...)
```

{% hint style="warning" %}
Note - you MUST always call `add_new_tokens` before `FastLanguageModel.get_peft_model`!
{% endhint %}

## Multi turn conversations

An issue if you didn't notice is the Alpaca dataset is single turn, whilst remember using ChatGPT was interactive and you can talk to it in multiple turns. For example, the left is what we want, but the right which is the Alpaca dataset only provides singular conversations. We want the finetuned language model to somehow learn how to do multi turn conversations just like ChatGPT.

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2Fgit-blob-2a65cd74ddd03a6bcbbc9827d9d034e4879a8e6a%2Fdiff.png?alt=media" alt=""><figcaption></figcaption></figure>

So we introduced the `conversation_extension` parameter, which essentially selects some random rows in your single turn dataset, and merges them into 1 conversation! For example, if you set it to 3, we randomly select 3 rows and merge them into 1! Setting them too long can make training slower, but could make your chatbot and final finetune much better!

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2Fgit-blob-2b1b3494b260f1102942d86143a885225c6a06f2%2Fcombine.png?alt=media" alt=""><figcaption></figcaption></figure>

Then set `output_column_name` to the prediction / output column. For the Alpaca dataset, it would be the output column.

We then use the `standardize_sharegpt` function to just make the dataset in a correct format for finetuning! Always call this!

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2Fgit-blob-7bf83bf802191bda9e417bbe45afa181e7f24f38%2Fimage.png?alt=media" alt=""><figcaption></figcaption></figure>

## Customizable Chat Templates

We can now specify the chat template for finetuning itself. The very famous Alpaca format is below:

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2Fgit-blob-59737e6dcb09fed15487d5a57c69f07cb40bb8e7%2Fimage.png?alt=media" alt=""><figcaption></figcaption></figure>

But remember we said this was a bad idea because ChatGPT style finetunes require only 1 prompt? Since we successfully merged all dataset columns into 1 using Unsloth, we essentially can create the below style chat template with 1 input column (instruction) and 1 output:

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2Fgit-blob-d54582ae98c396d51bfb85628b46c54f2517d030%2Fimage.png?alt=media" alt=""><figcaption></figcaption></figure>

We just require you must put a `{INPUT}` field for the instruction and an `{OUTPUT}` field for the model's output field. We in fact allow an optional `{SYSTEM}` field as well which is useful to customize a system prompt just like in ChatGPT. For example, below are some cool examples which you can customize the chat template to be:

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2Fgit-blob-cc455dc380d3d44ef136e485754964159dc773d8%2Fimage.png?alt=media" alt=""><figcaption></figcaption></figure>

For the ChatML format used in OpenAI models:

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2Fgit-blob-15bfca9cfadf10d54b4d3f66e3050044317d62c5%2Fimage.png?alt=media" alt=""><figcaption></figcaption></figure>

Or you can use the Llama-3 template itself (which only functions by using the instruct version of Llama-3): We in fact allow an optional `{SYSTEM}` field as well which is useful to customize a system prompt just like in ChatGPT.

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2Fgit-blob-80a2ed4de2ca323ac192c513cac65e9e8bf475db%2Fimage.png?alt=media" alt=""><figcaption></figcaption></figure>

Or in the Titanic prediction task where you had to predict if a passenger died or survived in this Colab notebook which includes CSV and Excel uploading: <https://colab.research.google.com/drive/1VYkncZMfGFkeCEgN2IzbZIKEDkyQuJAS?usp=sharing>

<figure><img src="https://3215535692-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FxhOjnexMCB3dmuQFQ2Zq%2Fuploads%2Fgit-blob-20911ab305c1a10e85859c703157b80175141eb1%2Fimage.png?alt=media" alt=""><figcaption></figcaption></figure>

## Applying Chat Templates with Unsloth

For datasets that usually follow the common chatml format, the process of preparing the dataset for training or finetuning, consists of four simple steps:

* Check the chat templates that Unsloth currently supports:\\

  ```
  from unsloth.chat_templates import CHAT_TEMPLATES
  print(list(CHAT_TEMPLATES.keys()))
  ```

  \
  This will print out the list of templates currently supported by Unsloth. Here is an example output:\\

  ```
  ['unsloth', 'zephyr', 'chatml', 'mistral', 'llama', 'vicuna', 'vicuna_old', 'vicuna old', 'alpaca', 'gemma', 'gemma_chatml', 'gemma2', 'gemma2_chatml', 'llama-3', 'llama3', 'phi-3', 'phi-35', 'phi-3.5', 'llama-3.1', 'llama-31', 'llama-3.2', 'llama-3.3', 'llama-32', 'llama-33', 'qwen-2.5', 'qwen-25', 'qwen25', 'qwen2.5', 'phi-4', 'gemma-3', 'gemma3']
  ```

  \\
* Use `get_chat_template` to apply the right chat template to your tokenizer:\\

  ```
  from unsloth.chat_templates import get_chat_template

  tokenizer = get_chat_template(
      tokenizer,
      chat_template = "gemma-3", # change this to the right chat_template name
  )
  ```

  \\
* Define your formatting function. Here's an example:\\

  ```
  def formatting_prompts_func(examples):
     convos = examples["conversations"]
     texts = [tokenizer.apply_chat_template(convo, tokenize = False, add_generation_prompt = False) for convo in convos]
     return { "text" : texts, }
  ```

  \
  \
  This function loops through your dataset applying the chat template you defined to each sample.\\
* Finally, let's load the dataset and apply the required modifications to our dataset: \\

  ```
  # Import and load dataset
  from datasets import load_dataset
  dataset = load_dataset("repo_name/dataset_name", split = "train")

  # Apply the formatting function to your dataset using the map method
  dataset = dataset.map(formatting_prompts_func, batched = True,)
  ```

  \
  If your dataset uses the ShareGPT format with "from"/"value" keys instead of the ChatML "role"/"content" format, you can use the `standardize_sharegpt` function to convert it first. The revised code will now look as follows:\
  \\

  ```
  # Import dataset
  from datasets import load_dataset
  dataset = load_dataset("mlabonne/FineTome-100k", split = "train")

  # Convert your dataset to the "role"/"content" format if necessary
  from unsloth.chat_templates import standardize_sharegpt
  dataset = standardize_sharegpt(dataset)

  # Apply the formatting function to your dataset using the map method
  dataset = dataset.map(formatting_prompts_func, batched = True,)
  ```

## More Information

Assuming your dataset is a list of list of dictionaries like the below:

```python
[
    [{'from': 'human', 'value': 'Hi there!'},
     {'from': 'gpt', 'value': 'Hi how can I help?'},
     {'from': 'human', 'value': 'What is 2+2?'}],
    [{'from': 'human', 'value': 'What's your name?'},
     {'from': 'gpt', 'value': 'I'm Daniel!'},
     {'from': 'human', 'value': 'Ok! Nice!'},
     {'from': 'gpt', 'value': 'What can I do for you?'},
     {'from': 'human', 'value': 'Oh nothing :)'},],
]
```

You can use our `get_chat_template` to format it. Select `chat_template` to be any of `zephyr, chatml, mistral, llama, alpaca, vicuna, vicuna_old, unsloth`, and use `mapping` to map the dictionary values `from`, `value` etc. `map_eos_token` allows you to map `<|im_end|>` to EOS without any training.

```python
from unsloth.chat_templates import get_chat_template

tokenizer = get_chat_template(
    tokenizer,
    chat_template = "chatml", # Supports zephyr, chatml, mistral, llama, alpaca, vicuna, vicuna_old, unsloth
    mapping = {"role" : "from", "content" : "value", "user" : "human", "assistant" : "gpt"}, # ShareGPT style
    map_eos_token = True, # Maps <|im_end|> to </s> instead
)

def formatting_prompts_func(examples):
    convos = examples["conversations"]
    texts = [tokenizer.apply_chat_template(convo, tokenize = False, add_generation_prompt = False) for convo in convos]
    return { "text" : texts, }
pass

from datasets import load_dataset
dataset = load_dataset("philschmid/guanaco-sharegpt-style", split = "train")
dataset = dataset.map(formatting_prompts_func, batched = True,)
```

You can also make your own custom chat templates! For example our internal chat template we use is below. You must pass in a `tuple` of `(custom_template, eos_token)` where the `eos_token` must be used inside the template.

```python
unsloth_template = \
    "{{ bos_token }}"\
    "{{ 'You are a helpful assistant to the user\n' }}"\
    "</div>"\
    "<div data-gb-custom-block data-tag="for">"\
        "<div data-gb-custom-block data-tag="if" data-0='role' data-1='role' data-2='] == ' data-3='user'>"\
            "{{ '>>> User: ' + message['content'] + '\n' }}"\
        "<div data-gb-custom-block data-tag="elif" data-0='role' data-1='role' data-2='] == ' data-3='assistant'></div>"\
            "{{ '>>> Assistant: ' + message['content'] + eos_token + '\n' }}"\
        "</div>"\
    "</div>"\
    "<div data-gb-custom-block data-tag="if">"\
        "{{ '>>> Assistant: ' }}"\
    "</div>"
unsloth_eos_token = "eos_token"

tokenizer = get_chat_template(
    tokenizer,
    chat_template = (unsloth_template, unsloth_eos_token,), # You must provide a template and EOS token
    mapping = {"role" : "from", "content" : "value", "user" : "human", "assistant" : "gpt"}, # ShareGPT style
    map_eos_token = True, # Maps <|im_end|> to </s> instead
)
```


---

# Agent Instructions
This documentation is published with GitBook. GitBook is the documentation platform designed so that both humans and AI agents can read, navigate, and reason over technical content effectively. Learn more at gitbook.com.

## Querying This Documentation
If you need additional information that is not directly available in this page, you can query the documentation by asking a question.

Perform an HTTP GET request on the following URL with the `ask` and `goal` query parameters:

```
GET https://unsloth.ai/docs/basics/chat-templates.md?ask=<question>&goal=<user_goal>
```

`ask` is the immediate question: it should be specific, self-contained, and written in natural language.
`goal` is what the user is ultimately trying to achieve, the reason they need the answer. Sharing it helps GitBook give you a better, more relevant answer. A goal is most helpful when it describes the outcome the user wants rather than restating the question. For example, with `ask=how do I create an API token`, a goal like `automate deployments from our CI pipeline` lets GitBook tailor the answer to that use case.

The response will contain a direct answer to the question and relevant excerpts and sources from the documentation.

Use this mechanism when the answer is not explicitly present in the current page, you need clarification or additional context, or you want to retrieve related documentation sections.
